# Base de datos: PostgreSQL con pgvector

BeeMatch usa dos motores según el entorno:

| Entorno | Motor | Cómo se elige |
|---|---|---|
| Desarrollo local | SQLite (`data/beematch.db`) | Sin `DATABASE_URL` |
| Producción, staging y pruebas de integración | PostgreSQL 16 + pgvector | `DATABASE_URL=postgresql+psycopg://...` |

El código decide en `backend/config.py` (`USA_PGVECTOR`). En SQLite el vector se guarda como JSON y la búsqueda es un cálculo en memoria; en PostgreSQL es una columna `vector(1536)` con índice.

## Esquema y migraciones (Alembic)

En **PostgreSQL** el esquema lo gobiernan las migraciones de `backend/migrations/versions/`; en **SQLite** (desarrollo y pruebas) siguen siendo `create_all` y los `ALTER TABLE` de `_COLUMNAS_NUEVAS`, como siempre. Al arrancar, `init_db()` ejecuta en PostgreSQL:

1. `CREATE EXTENSION IF NOT EXISTS vector`
2. `actualizar_esquema()`, que según el estado de la base:
   - **vacía:** aplica todas las migraciones;
   - **creada antes de Alembic** (tiene tablas, no tiene `alembic_version`): completa las columnas que le falten, la marca en la versión `0001` y aplica las posteriores, sin tocar sus datos;
   - **ya migrada:** aplica solo las que falten.

| Versión | Qué hace |
|---|---|
| `0001` | Esquema inicial: las 18 tablas (generado a partir de los modelos) |
| `0002` | Índices HNSW (coseno) y GIN (`tsvector` en español), con `IF NOT EXISTS` |

| Índice | Lo usa |
|---|---|
| `ix_fragmentos_cv_embedding_hnsw` | `embedding <=> :vec` (distancia coseno) en `RecuperadorHibrido._buscar_vectorial` |
| `ix_fragmentos_cv_texto_fts` | `to_tsvector('spanish', texto) @@ plainto_tsquery(...)` en `_buscar_lexico` |

La expresión del GIN debe ser idéntica a la de la consulta léxica; si se cambia una, hay que cambiar la otra. Parámetros de HNSW: los de pgvector (`m=16`, `ef_construction=64`), suficientes para unos miles de fragmentos.

### Cambiar un modelo (qué debe hacer quien programa)

Si cambias un modelo (una columna, una tabla, un índice) hay que escribir su migración, o PostgreSQL no se enterará:

```bash
export DATABASE_URL=postgresql+psycopg://beematch:beematch@localhost:5432/beematch
python -m backend.migraciones actualizar          # deja tu base local al día
# ...cambias el modelo...
python -m backend.migraciones crear "agrega columna x a solicitudes"   # genera backend/migrations/versions/NNNN_*.py
# revisa el archivo generado, y:
python -m backend.migraciones actualizar
python -m backend.migraciones estado               # debe decir "Cambios sin migrar: ninguno"
```

Si se olvida, la prueba `test_las_migraciones_coinciden_con_los_modelos` falla en el CI (job de PostgreSQL) y dice qué falta. En SQLite no hace falta: sigue siendo `create_all`, pero **una columna nueva en un modelo también debe agregarse a `_COLUMNAS_NUEVAS`** si ya existen bases SQLite con datos.

Para volver atrás no hay un comando propio: usa un respaldo (`scripts/aws/respaldar.sh`) antes de migrar en producción. `desplegar.sh` ya lo hace. Los `downgrade` de las migraciones existen y están probados, pero un cambio destructivo no se deshace con ellos.

## Cómo levantar PostgreSQL en local

```bash
docker compose up -d db
export DATABASE_URL=postgresql+psycopg://beematch:beematch@localhost:5432/beematch
uvicorn backend.main:app --reload
```

Si `5432` está ocupado, publica otro puerto: `docker run -d -p 55432:5432 -e POSTGRES_USER=beematch -e POSTGRES_PASSWORD=beematch -e POSTGRES_DB=beematch pgvector/pgvector:pg16`.

## Migrar los datos de SQLite a PostgreSQL

```bash
# 1. Ensayo: lee el origen y no escribe nada
python -m scripts.migrar_sqlite_a_postgres --destino "$DATABASE_URL" --simular

# 2. Migración real
python -m scripts.migrar_sqlite_a_postgres --destino "$DATABASE_URL"
```

- **No llama a OpenAI.** Los embeddings que ya están en SQLite se convierten a `vector`; no se vuelve a pagar la indexación.
- **El origen no se modifica** (se abre en solo lectura).
- **Si el destino ya tiene datos**, el script se detiene. `--vaciar` los reemplaza.
- **Es una sola transacción**: si algo falla, el destino queda como estaba.
- **Referencias rotas.** SQLite no valida llaves foráneas y PostgreSQL sí. Si el origen tiene filas que apuntan a algo que ya no existe (por ejemplo, coincidencias que citan un fragmento borrado al reindexar), la referencia se deja en `NULL` si la columna lo permite, o la fila se descarta si no. El script lo informa.
- Al final compara el número de filas por tabla y falla si no coinciden.
- **Credenciales del repositorio.** El secreto de OneDrive o Drive se guarda cifrado con `ENCRYPTION_KEY` (o con una clave derivada de `JWT_SECRET` si esa no existe). Si el servidor de destino usa otra clave, esa credencial no se podrá descifrar y hay que volver a registrarla desde Configuración. El script lo avisa.

Resultado con la base de desarrollo del equipo (31 hojas de vida, 140 fragmentos): 1.179 filas copiadas, 14 referencias de `coincidencias.fragmento_id` puestas en `NULL`, verificación correcta.

### Alternativa: empezar de cero

Si el contenido de SQLite es solo de prueba, se puede arrancar PostgreSQL vacío y volver a sincronizar los documentos desde el repositorio (OneDrive o Drive). Eso sí vuelve a llamar al proveedor de embeddings.

## Pruebas

Toda la suite corre sobre SQLite por defecto. Con `PRUEBAS_DATABASE_URL` corre sobre PostgreSQL:

```bash
docker run -d --name bm-pg -p 55432:5432 -e POSTGRES_USER=beematch -e POSTGRES_PASSWORD=beematch \
  -e POSTGRES_DB=beematch pgvector/pgvector:pg16
PRUEBAS_DATABASE_URL=postgresql+psycopg://beematch:beematch@localhost:55432/beematch python -m pytest -q
```

Las pruebas de `tests/test_postgres_pgvector.py` y `tests/test_migracion_sqlite_a_postgres.py` solo se ejecutan en este modo (en SQLite se omiten). El workflow `ci-postgres.yml` hace lo mismo en cada PR.

Diferencias de comportamiento que SQLite ocultaba y que PostgreSQL destapó al correr la suite:

- pgvector exige la dimensión exacta (1536): los vectores falsos de 3 números de algunas pruebas fallaban.
- PostgreSQL hace cumplir las llaves foráneas: una prueba citaba un `fragmento_id` que no existía.

## Pendiente

- Confirmar que el PostgreSQL administrado del hosting permite `CREATE EXTENSION vector` (RDS lo permite). En el despliegue de AWS con Compose no aplica: la imagen `pgvector/pgvector` ya lo trae.
- La dimensión de los embeddings (1536) está fija en la migración `0001`. Cambiar de modelo de embeddings a otra dimensión exige una migración nueva y reindexar.
