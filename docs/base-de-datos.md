# Base de datos: PostgreSQL con pgvector

BeeMatch usa dos motores según el entorno:

| Entorno | Motor | Cómo se elige |
|---|---|---|
| Desarrollo local | SQLite (`data/beematch.db`) | Sin `DATABASE_URL` |
| Producción, staging y pruebas de integración | PostgreSQL 16 + pgvector | `DATABASE_URL=postgresql+psycopg://...` |

El código decide en `backend/config.py` (`USA_PGVECTOR`). En SQLite el vector se guarda como JSON y la búsqueda es un cálculo en memoria; en PostgreSQL es una columna `vector(1536)` con índice.

## Qué crea la API al arrancar en PostgreSQL

`init_db()` ejecuta, en orden y de forma idempotente:

1. `CREATE EXTENSION IF NOT EXISTS vector`
2. Las tablas (`create_all`) y las columnas añadidas después (`_COLUMNAS_NUEVAS`)
3. Los índices de la recuperación híbrida:

| Índice | Definición | Lo usa |
|---|---|---|
| `ix_fragmentos_cv_embedding_hnsw` | `HNSW (embedding vector_cosine_ops)` | `embedding <=> :vec` (distancia coseno) en `RecuperadorHibrido._buscar_vectorial` |
| `ix_fragmentos_cv_texto_fts` | `GIN (to_tsvector('spanish', texto))` | `to_tsvector('spanish', texto) @@ plainto_tsquery(...)` en `_buscar_lexico` |

La expresión del índice GIN debe ser idéntica a la de la consulta; si se cambia una, hay que cambiar la otra. La prueba `test_la_busqueda_lexica_usa_el_indice_gin` lo vigila.

Los parámetros de HNSW son los de pgvector (`m=16`, `ef_construction=64`). Para el volumen previsto (cientos de hojas de vida, unos miles de fragmentos) no hace falta afinarlos.

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

- Migraciones versionadas (Alembic). Hoy los cambios de esquema que agregan columnas se aplican con `_COLUMNAS_NUEVAS`; un cambio de tipo o de índice no se aplica solo sobre una base existente.
- Confirmar que el PostgreSQL administrado del hosting permite `CREATE EXTENSION vector` (RDS lo permite).
