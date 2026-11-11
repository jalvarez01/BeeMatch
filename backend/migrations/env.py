"""
Entorno de Alembic. La URL sale de backend.config (DATABASE_URL), así que las
migraciones corren contra la misma base que la aplicación.

Solo se usa con PostgreSQL: SQLite (desarrollo) sigue creándose con create_all
y `_COLUMNAS_NUEVAS`.
"""

from alembic import context
from sqlalchemy import pool

from backend.infrastructure.persistence import models  # noqa: F401  (registra las tablas)
from backend.infrastructure.persistence.database import Base, engine
from backend.migraciones import incluir_objeto

target_metadata = Base.metadata


def run_migrations_online() -> None:
    conexion = context.config.attributes.get("connection")
    if conexion is None:
        with engine.connect() as conexion:
            _ejecutar(conexion)
    else:
        _ejecutar(conexion)


def _ejecutar(conexion) -> None:
    context.configure(
        connection=conexion,
        target_metadata=target_metadata,
        compare_type=True,
        include_object=incluir_objeto,
        poolclass=pool.NullPool,
    )
    with context.begin_transaction():
        context.run_migrations()


run_migrations_online()
