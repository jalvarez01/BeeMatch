"""
Construcción del cliente del origen configurado.

Único punto del sistema que sabe qué implementación corresponde a cada `tipo`.
La sincronización y la indexación piden el cliente aquí y trabajan contra
RepositorioDocumentos, sin conocer el proveedor.
"""

from backend.infrastructure.repositorio.base import (
    TIPO_GDRIVE,
    TIPO_ONEDRIVE,
    RepositorioDocumentos,
    RepositorioError,
)

# Campos de credenciales que son secretos: se enmascaran en la API y se
# reutilizan si el administrador guarda sin volver a escribirlos (HU-05).
CAMPOS_SECRETOS = {
    TIPO_ONEDRIVE: ("client_secret",),
    TIPO_GDRIVE: ("credenciales_json",),
}


class TipoRepositorioInvalidoError(RepositorioError):
    """El `tipo` guardado no corresponde a ningún origen soportado."""


def crear_cliente(tipo: str, carpeta: str, credenciales: dict) -> RepositorioDocumentos:
    """
    Cliente del origen indicado.

    `credenciales` es el JSON ya descifrado de la configuración; su forma
    depende del proveedor y solo la interpreta la implementación destino.
    """
    if tipo == TIPO_ONEDRIVE:
        from backend.infrastructure.onedrive.graph_client import GraphClient

        return GraphClient.desde_credenciales(credenciales, carpeta)

    if tipo == TIPO_GDRIVE:
        from backend.infrastructure.gdrive.drive_client import GoogleDriveClient

        return GoogleDriveClient.desde_credenciales(credenciales, carpeta)

    raise TipoRepositorioInvalidoError(
        f"Tipo de repositorio no soportado: '{tipo}'. Los válidos son "
        f"{TIPO_ONEDRIVE} y {TIPO_GDRIVE}."
    )


def campos_secretos(tipo: str) -> tuple[str, ...]:
    return CAMPOS_SECRETOS.get(tipo, ())
