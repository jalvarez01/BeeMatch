from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from backend.config import DATABASE_URL, USA_PGVECTOR

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def init_db():
    """Crea las tablas y habilita pgvector cuando el motor es PostgreSQL."""
    if USA_PGVECTOR:
        from sqlalchemy import text

        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()

    Base.metadata.create_all(bind=engine)
    _agregar_columnas_faltantes()


# Columnas añadidas después de crear las tablas. `create_all` no altera tablas
# existentes, y una base ya poblada (HU-03: `usuarios.pendiente`) las perdería.
_COLUMNAS_NUEVAS = {"usuarios": {"pendiente": "BOOLEAN NOT NULL DEFAULT FALSE"}}


def _agregar_columnas_faltantes():
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    with engine.begin() as conn:
        for tabla, columnas in _COLUMNAS_NUEVAS.items():
            existentes = {c["name"] for c in inspector.get_columns(tabla)}
            for nombre, definicion in columnas.items():
                if nombre not in existentes:
                    conn.execute(text(f"ALTER TABLE {tabla} ADD COLUMN {nombre} {definicion}"))


def get_db():
    """Generador de sesión para inyección de dependencias en FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
