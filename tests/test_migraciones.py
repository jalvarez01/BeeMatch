"""
Migraciones de Alembic sobre PostgreSQL.

Lo importante: que las migraciones y los modelos digan lo mismo. Si alguien
cambia un modelo sin escribir su migración, `test_las_migraciones_coinciden_con_los_modelos`
falla y dice qué falta. Para generarla:

    DATABASE_URL=postgresql+psycopg://... python -m backend.migraciones crear "texto"

Solo corre con PRUEBAS_DATABASE_URL (PostgreSQL).
"""

import pytest
from alembic import command
from sqlalchemy import inspect, text

from backend.config import USA_PGVECTOR
from backend.infrastructure.persistence.database import INDICES_DE_BUSQUEDA, Base, engine
from backend.migraciones import (
    _configuracion,
    actualizar_esquema,
    cambios_sin_migrar,
    ultima_version,
    version_actual,
)

pytestmark = pytest.mark.skipif(not USA_PGVECTOR, reason="Requiere PostgreSQL con pgvector")


def _vaciar_todo():
    with engine.begin() as conexion:
        conexion.execute(text("DROP SCHEMA public CASCADE"))
        conexion.execute(text("CREATE SCHEMA public"))
        conexion.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))


@pytest.fixture
def base_vacia():
    _vaciar_todo()
    yield
    _vaciar_todo()


def _indices() -> set[str]:
    with engine.connect() as conexion:
        return {
            f[0]
            for f in conexion.execute(
                text("SELECT indexname FROM pg_indexes WHERE tablename = 'fragmentos_cv'")
            )
        }


def test_una_base_vacia_queda_en_la_ultima_version_con_todas_las_tablas(base_vacia):
    actualizar_esquema()

    with engine.connect() as conexion:
        assert version_actual(conexion) == ultima_version()
        tablas = set(inspect(conexion).get_table_names())
    assert set(Base.metadata.tables) <= tablas
    assert set(INDICES_DE_BUSQUEDA) <= _indices()


def test_las_migraciones_coinciden_con_los_modelos(base_vacia):
    actualizar_esquema()
    with engine.connect() as conexion:
        diferencias = cambios_sin_migrar(conexion)
    assert diferencias == [], (
        "Los modelos cambiaron y falta la migración. Genérala con: "
        f'python -m backend.migraciones crear "descripcion". Diferencias: {diferencias}'
    )


def test_actualizar_dos_veces_no_cambia_nada(base_vacia):
    actualizar_esquema()
    actualizar_esquema()
    with engine.connect() as conexion:
        assert version_actual(conexion) == ultima_version()


def test_una_base_creada_antes_de_alembic_se_marca_sin_perder_datos(base_vacia):
    # Lo que producía la versión anterior: create_all, sin tabla alembic_version.
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conexion:
        conexion.execute(
            text("INSERT INTO habilidades (id, nombre, categoria) VALUES ('h1', 'Java', 'TECNOLOGIA')")
        )

    actualizar_esquema()

    with engine.connect() as conexion:
        assert version_actual(conexion) == ultima_version()
        assert conexion.execute(text("SELECT nombre FROM habilidades WHERE id = 'h1'")).scalar() == "Java"
    assert set(INDICES_DE_BUSQUEDA) <= _indices()


def test_una_base_antigua_sin_las_columnas_nuevas_las_recupera(base_vacia):
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conexion:
        conexion.execute(text("ALTER TABLE busquedas DROP COLUMN parametros_json"))
        conexion.execute(text("ALTER TABLE usuarios DROP COLUMN pendiente"))

    actualizar_esquema()

    with engine.connect() as conexion:
        columnas = {c["name"] for c in inspect(conexion).get_columns("busquedas")}
        assert "parametros_json" in columnas
        assert "pendiente" in {c["name"] for c in inspect(conexion).get_columns("usuarios")}
        assert cambios_sin_migrar(conexion) == []


def test_se_puede_volver_a_la_version_inicial_y_subir_otra_vez(base_vacia):
    actualizar_esquema()
    with engine.connect() as conexion:
        command.downgrade(_configuracion(conexion), "0001")
        conexion.commit()
    assert not (set(INDICES_DE_BUSQUEDA) & _indices())

    actualizar_esquema()
    assert set(INDICES_DE_BUSQUEDA) <= _indices()


def test_el_comando_estado_funciona_sin_importar_los_modelos_antes(base_vacia):
    """`python -m backend.migraciones estado` arranca en frío: no debe ver un metadata vacío."""
    import os
    import subprocess
    import sys

    actualizar_esquema()
    resultado = subprocess.run(
        [sys.executable, "-m", "backend.migraciones", "estado"],
        capture_output=True,
        text=True,
        env={**os.environ, "DATABASE_URL": str(engine.url.render_as_string(hide_password=False))},
    )
    assert resultado.returncode == 0, resultado.stderr
    assert "Cambios sin migrar: ninguno" in resultado.stdout
