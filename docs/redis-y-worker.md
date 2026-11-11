# Redis, cola de trabajos, worker y caché

Redis cumple dos funciones en BeeMatch, con prefijos distintos y sin depender una de otra:

| Función | Componente | Claves |
|---|---|---|
| Cola de trabajos (RQ): búsquedas e indexación de hojas de vida | C15, C16, C17 | las de RQ (`rq:*`) |
| Caché de embeddings de consultas repetidas | C22 | `beematch:emb:<modelo>:<dimensiones>:<sha256>` |

El progreso de las búsquedas **no** vive en Redis: está en `busquedas.progreso` (PostgreSQL), así sobrevive aunque Redis se reinicie. La sesión es un JWT sin estado, por lo que tampoco hay sesiones en Redis. El diseño original del Sprint 0 preveía ambas cosas en Redis; se descartó porque con menos de 10 usuarios concurrentes no aportan nada y añaden un punto de fallo.

## Procesos

| Proceso | Comando | Qué hace |
|---|---|---|
| API | `uvicorn backend.main:app` | Atiende HTTP y encola |
| Worker | `python -m backend.workers.run_worker [--planificador]` | Toma trabajos de la cola |
| Planificador | dentro del worker con `--planificador` | Sincroniza el repositorio cada `SYNC_INTERVALO_HORAS` (6 h) |

El worker usa `SimpleWorker` (sin `fork`), igual en macOS, Linux y Windows. El `docker-compose.yml` usa el mismo comando.

**El planificador debe correr en un solo proceso.** Con una API sola (desarrollo) corre dentro de ella (`PLANIFICADOR_EN_API=true`, valor por defecto). En el despliegue la API lleva `PLANIFICADOR_EN_API=false` y el planificador va en **un** worker; si no, cada instancia de la API sincronizaría el repositorio por su cuenta. Escalar workers está bien, pero solo uno lleva `--planificador`.

## Qué pasa cuando algo falta

| Situación | Comportamiento | Probado |
|---|---|---|
| Redis y worker activos | El trabajo va a la cola y lo ejecuta el worker | Sí, en vivo con Docker |
| Redis activo, sin worker | La API lo ejecuta en segundo plano | Sí, en vivo |
| Sin Redis desde el arranque | La API lo ejecuta en segundo plano | Sí |
| Redis se cae con la API ya en marcha | La API lo ejecuta en segundo plano, sin error 500 | Sí, en vivo y con pruebas |
| Redis vuelve | La API lo detecta y retoma la cola | Sí, en vivo |
| La API se reinicia con un trabajo encolado | El trabajo sigue en Redis y lo ejecuta el worker | Sí, `test_redis_real.py` |

Al arrancar, la API deja en el log cuál de los modos usa.

Corrección que salió de esta prueba: antes, si Redis caía con la API ya conectada, `POST /busquedas/solicitud/{id}` devolvía 500, porque la cola quedaba guardada, `hay_workers` asumía que sí había worker y el `enqueue` fallaba. Ahora se detecta el error de conexión, se olvida la conexión y el trabajo corre en la API.

## Caché de embeddings (C22)

`ProveedorEmbeddings.generar_uno` es el embedding de la consulta de una búsqueda. Re-ejecutar o ajustar una solicitud (HU-15) repite el mismo texto, y cada embedding es una llamada de pago a OpenAI.

- La clave incluye modelo, dimensiones y el hash del texto sin espacios en los bordes: cambiar de modelo nunca reutiliza vectores viejos.
- Vence a las `EMBEDDING_CACHE_TTL_HORAS` (168 h = 7 días).
- Es un acelerador, no un requisito: sin Redis, o si falla a mitad, se pide al proveedor y todo sigue igual. Tras un fallo de conexión no se reintenta durante 30 s para que cada búsqueda no pague el timeout.
- Los embeddings de los fragmentos de las hojas de vida (indexación) **no** se cachean: se guardan en PostgreSQL.

## Pruebas

Las pruebas con dobles corren siempre. Las de Redis real se omiten si no hay uno:

```bash
docker run -d --name bm-redis -p 56379:6379 redis:7-alpine
PRUEBAS_REDIS_URL=redis://localhost:56379/0 python -m pytest tests/test_redis_real.py tests/test_cola_redis.py tests/test_cache_embeddings.py tests/test_planificador_y_worker.py
```

`tests/test_redis_real.py` usa un `SimpleWorker` de RQ de verdad: encola, comprueba que nadie lo ejecuta hasta que el worker arranca, y que el trabajo sobrevive a "reiniciar la API". El workflow `ci-redis.yml` corre la suite con un Redis como servicio.

## Valkey en lugar de Redis

El costeo del Sprint 2 considera Valkey administrado. RQ y el cliente `redis` usan comandos básicos (listas, hashes, pub/sub, `SETEX`), que Valkey implementa, pero **no se probó contra Valkey**. En AWS se usará Redis en contenedor (ver `docs/despliegue-aws.md`), así que la duda queda fuera del despliegue inicial.
