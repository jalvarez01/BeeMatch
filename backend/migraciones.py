"""
Migraciones del esquema con Alembic (solo PostgreSQL).

    python -m backend.migraciones actualizar     # lleva la base a la última versión
    python -m backend.migraciones crear "texto"  # genera una migración comparando con los modelos
    python -m backend.migraciones estado         # versión actual y si hay cambios sin migrar

La API llama a `actualizar_esquema()` al arrancar. Una base creada antes de que
existiera Alembic (con `create_all`) se detecta y se marca en la versión inicial
en vez de intentar crear de nuevo sus tablas.
"""

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from backend.infrastructure.persistence import models  # noqa: F401  (registra las tablas en el metadata)
from backend.infrastructure.persistence.database import INDICES_DE_BUSQUEDA, Base, engine

DIRECTORIO = Path(__file__).parent / "migrations"
VERSION_INICIAL = "0001"


def _configuracion(conexion=None) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(DIRECTORIO))
    if conexion is not None:
        cfg.attributes["connection"] = conexion
    return cfg


def incluir_objeto(objeto, nombre, tipo, reflejado, comparado) -> bool:
    """
    Filtro de la comparación modelos/base. Los índices HNSW y GIN se crean con SQL
    propio (migración 0002) y no están en los modelos: no deben contarse como sobrantes.
    """
    return not (tipo == "index" and nombre in INDICES_DE_BUSQUEDA)


def version_actual(conexion) -> str | None:
    return MigrationContext.configure(conexion).get_current_revision()


def ultima_version() -> str:
    return ScriptDirectory.from_config(_configuracion()).get_current_head()


def actualizar_esquema() -> None:
    """
    Deja la base en la última versión.

    - Base vacía: aplica todas las migraciones.
    - Base creada con `create_all` (tiene tablas pero no `alembic_version`): se
      completan sus columnas faltantes con el mecanismo anterior, se marca como
      versión inicial y se aplican las migraciones posteriores.
    - Base ya migrada: aplica solo las que falten.
    """
    with engine.begin() as conexion:
        cfg = _configuracion(conexion)
        tablas = set(inspect(conexion).get_table_names())
        if "alembic_version" not in tablas and "usuarios" in tablas:
            from backend.infrastructure.persistence.database import _agregar_columnas_faltantes

            _agregar_columnas_faltantes()
            command.stamp(cfg, VERSION_INICIAL)
        command.upgrade(cfg, "head")


def cambios_sin_migrar(conexion) -> list:
    """Diferencias entre los modelos y la base ya migrada. Vacía si están al día."""
    from alembic.autogenerate import compare_metadata

    contexto = MigrationContext.configure(
        conexion, opts={"compare_type": True, "include_object": incluir_objeto}
    )
    return compare_metadata(contexto, Base.metadata)


def main(argumentos: list[str]) -> int:
    if not argumentos:
        print(__doc__)
        return 1
    orden = argumentos[0]
    if orden == "actualizar":
        actualizar_esquema()
        print("Esquema al día.")
    elif orden == "crear":
        mensaje = " ".join(argumentos[1:]) or "cambio de esquema"
        with engine.connect() as conexion:
            command.revision(_configuracion(conexion), message=mensaje, autogenerate=True)
    elif orden == "estado":
        with engine.connect() as conexion:
            print("Versión actual:", version_actual(conexion))
            print("Última versión:", ultima_version())
            pendientes = cambios_sin_migrar(conexion)
            print("Cambios sin migrar:", f"{len(pendientes)} (ver `crear`)" if pendientes else "ninguno")
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
