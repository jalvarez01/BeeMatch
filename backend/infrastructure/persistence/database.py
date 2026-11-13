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

    if USA_PGVECTOR:
        # PostgreSQL: el esquema lo gobiernan las migraciones (backend/migrations).
        from backend.migraciones import actualizar_esquema

        actualizar_esquema()
    else:
        # SQLite (desarrollo y pruebas): tablas desde los modelos y ALTER de las columnas nuevas.
        Base.metadata.create_all(bind=engine)
        _agregar_columnas_faltantes()
    _rellenar_nombres_normalizados()


# Índices de la recuperación híbrida (C20 y C21). `create_all` no los crea:
# dependen de operadores propios de PostgreSQL y pgvector.
#
# - HNSW con distancia coseno: es el operador `<=>` que usa el recuperador.
#   Parámetros por defecto de pgvector (m=16, ef_construction=64): para unos
#   miles de fragmentos no hace falta afinarlos.
# - GIN sobre to_tsvector('spanish', texto): la expresión debe ser idéntica a
#   la de la consulta léxica, o el planificador no usa el índice.
INDICES_DE_BUSQUEDA = {
    "ix_fragmentos_cv_embedding_hnsw": (
        "CREATE INDEX IF NOT EXISTS ix_fragmentos_cv_embedding_hnsw "
        "ON fragmentos_cv USING hnsw (embedding vector_cosine_ops)"
    ),
    "ix_fragmentos_cv_texto_fts": (
        "CREATE INDEX IF NOT EXISTS ix_fragmentos_cv_texto_fts "
        "ON fragmentos_cv USING gin (to_tsvector('spanish', texto))"
    ),
}


def crear_indices_de_busqueda():
    """Crea los índices vectorial y léxico si faltan. Es idempotente."""
    from sqlalchemy import text

    with engine.begin() as conn:
        for sentencia in INDICES_DE_BUSQUEDA.values():
            conn.execute(text(sentencia))


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
