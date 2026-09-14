"""
Migración: configuracion_onedrive -> configuracion_repositorio.

El proyecto no usa Alembic, así que la migración es este script, pensado para
correrse una sola vez por entorno y ser idempotente: si ya migró, no hace nada.

Qué hace:

1. Crea las tablas nuevas que falten (incluida `configuracion_repositorio`).
2. Copia la configuración de OneDrive a la tabla nueva, moviendo tenant_id,
   client_id, client_secret y drive_id al JSON de credenciales cifrado. El
   secreto se descifra y se vuelve a cifrar dentro del JSON: no se pierde ni
   queda en claro en ningún momento.
3. Renombra `hojas_de_vida.id_onedrive` a `id_documento`, que es el nombre
   neutro que ahora usa el código.

La tabla antigua se conserva por defecto como respaldo. Para eliminarla una vez
verificada la migración:

    python -m scripts.migrar_configuracion_repositorio --eliminar-antigua

Uso normal:

    python -m scripts.migrar_configuracion_repositorio
"""

import json
import sys
import uuid
from datetime import datetime, timezone

from sqlalchemy import inspect, text

from backend.infrastructure.crypto import CifradoError, cifrar, descifrar
from backend.infrastructure.persistence import models  # noqa: F401  (registra las tablas)
from backend.infrastructure.persistence.database import Base, engine

TABLA_ANTIGUA = "configuracion_onedrive"
TABLA_NUEVA = "configuracion_repositorio"


def _tablas() -> list[str]:
    return inspect(engine).get_table_names()


def _columnas(tabla: str) -> list[str]:
    return [c["name"] for c in inspect(engine).get_columns(tabla)]


def crear_tablas() -> None:
    Base.metadata.create_all(bind=engine)
    print(f"[1/3] Tablas creadas o ya existentes (incluye {TABLA_NUEVA}).")


def migrar_configuracion() -> None:
    """Copia la configuración de OneDrive al formato nuevo."""
    if TABLA_ANTIGUA not in _tablas():
        print(f"[2/3] No existe {TABLA_ANTIGUA}: nada que migrar.")
        return

    with engine.begin() as conexion:
        ya_migradas = conexion.execute(text(f"SELECT COUNT(*) FROM {TABLA_NUEVA}")).scalar()
        if ya_migradas:
            print(f"[2/3] {TABLA_NUEVA} ya tiene {ya_migradas} registro(s): no se toca.")
            return

        filas = conexion.execute(
            text(
                f"""
                SELECT id, tenant_id, client_id, client_secret_cifrado, drive_id,
                       carpeta_cv, activa, ultima_validacion, documentos_detectados,
                       delta_link, actualizado_por, created_at, updated_at
                FROM {TABLA_ANTIGUA}
                """
            )
        ).mappings().all()

        if not filas:
            print(f"[2/3] {TABLA_ANTIGUA} está vacía: nada que migrar.")
            return

        migradas = 0
        for fila in filas:
            try:
                secreto = descifrar(fila["client_secret_cifrado"])
            except CifradoError:
                # El secreto no se puede recuperar (cambió ENCRYPTION_KEY). Se
                # migra el resto: el administrador solo tendrá que volver a
                # escribir la credencial, no la configuración completa.
                secreto = ""
                print(
                    f"    aviso: el Client Secret de la configuración {fila['id']} no se pudo "
                    "descifrar. Deberá registrarse de nuevo en Configuración."
                )

            credenciales = {
                "tenant_id": fila["tenant_id"] or "",
                "client_id": fila["client_id"] or "",
                "client_secret": secreto,
                "drive_id": fila["drive_id"] or "",
            }

            conexion.execute(
                text(
                    f"""
                    INSERT INTO {TABLA_NUEVA} (
                        id, tipo, carpeta, credenciales_cifradas, activa,
                        ultima_validacion, documentos_detectados, cursor_sincronizacion,
                        actualizado_por, created_at, updated_at
                    ) VALUES (
                        :id, 'ONEDRIVE', :carpeta, :credenciales, :activa,
                        :ultima_validacion, :documentos_detectados, :cursor,
                        :actualizado_por, :created_at, :updated_at
                    )
                    """
                ),
                {
                    "id": fila["id"] or str(uuid.uuid4()),
                    "carpeta": fila["carpeta_cv"] or "",
                    "credenciales": cifrar(json.dumps(credenciales)),
                    "activa": fila["activa"],
                    "ultima_validacion": fila["ultima_validacion"],
                    "documentos_detectados": fila["documentos_detectados"],
                    # El delta link sigue siendo válido: mismo drive, misma carpeta.
                    "cursor": fila["delta_link"],
                    "actualizado_por": fila["actualizado_por"],
                    "created_at": fila["created_at"] or datetime.now(timezone.utc),
                    "updated_at": fila["updated_at"] or datetime.now(timezone.utc),
                },
            )
            migradas += 1

    print(f"[2/3] Migradas {migradas} configuración(es) de OneDrive a {TABLA_NUEVA}.")


def renombrar_id_documento() -> None:
    """`hojas_de_vida.id_onedrive` pasa a llamarse `id_documento`."""
    if "hojas_de_vida" not in _tablas():
        print("[3/3] No existe hojas_de_vida: nada que renombrar.")
        return

    columnas = _columnas("hojas_de_vida")
    if "id_documento" in columnas:
        print("[3/3] hojas_de_vida.id_documento ya existe.")
        return
    if "id_onedrive" not in columnas:
        print("[3/3] hojas_de_vida no tiene id_onedrive: nada que renombrar.")
        return

    with engine.begin() as conexion:
        conexion.execute(
            text("ALTER TABLE hojas_de_vida RENAME COLUMN id_onedrive TO id_documento")
        )
    print("[3/3] hojas_de_vida.id_onedrive renombrada a id_documento.")


def eliminar_tabla_antigua() -> None:
    if TABLA_ANTIGUA not in _tablas():
        print(f"{TABLA_ANTIGUA} no existe.")
        return
    with engine.begin() as conexion:
        conexion.execute(text(f"DROP TABLE {TABLA_ANTIGUA}"))
    print(f"{TABLA_ANTIGUA} eliminada.")


def main() -> int:
    crear_tablas()
    migrar_configuracion()
    renombrar_id_documento()

    if "--eliminar-antigua" in sys.argv:
        eliminar_tabla_antigua()
    elif TABLA_ANTIGUA in _tablas():
        print(
            f"\nLa tabla {TABLA_ANTIGUA} se conservó como respaldo. Verifica que la "
            "conexión funcione desde Configuración y luego elimínala con "
            "--eliminar-antigua."
        )

    print("\nMigración completada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
