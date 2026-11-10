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
    _rellenar_nombres_normalizados()


# Columnas añadidas después de crear las tablas. `create_all` no altera tablas
# existentes, y una base ya poblada (HU-03: `usuarios.pendiente`) las perdería.
_COLUMNAS_NUEVAS = {
    "usuarios": {"pendiente": "BOOLEAN NOT NULL DEFAULT FALSE"},
    "bitacora": {"rol": "VARCHAR(20)"},
    # HU-12: nombre comparable de clientes y proyectos.
    "clientes": {"nombre_normalizado": "VARCHAR(160)"},
    "proyectos": {"nombre_normalizado": "VARCHAR(160)"},
    # HU-15: criterios, cliente y proyecto de cada ejecución.
    "busquedas": {"parametros_json": "TEXT"},
}


def _agregar_columnas_faltantes():
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    with engine.begin() as conn:
        for tabla, columnas in _COLUMNAS_NUEVAS.items():
            existentes = {c["name"] for c in inspector.get_columns(tabla)}
            for nombre, definicion in columnas.items():
                if nombre not in existentes:
                    conn.execute(text(f"ALTER TABLE {tabla} ADD COLUMN {nombre} {definicion}"))


def _rellenar_nombres_normalizados():
    """
    HU-12: los clientes y proyectos registrados antes de la columna quedan sin
    nombre comparable; se les calcula para que también cuenten al evitar duplicados.
    """
    from backend.infrastructure.persistence.models.cliente import ClienteModel, ProyectoModel
    from backend.infrastructure.persistence.normalizacion import normalizar_nombre

    with SessionLocal() as db:
        for modelo in (ClienteModel, ProyectoModel):
            for registro in db.query(modelo).filter(modelo.nombre_normalizado.is_(None)).all():
                registro.nombre_normalizado = normalizar_nombre(registro.nombre)
        db.commit()


def get_db():
    """Generador de sesión para inyección de dependencias en FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
