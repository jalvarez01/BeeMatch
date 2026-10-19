"""
Ubicación y disponibilidad de la hoja de vida en el repositorio (HU-21).

RNF14: BeeMatch no copia el archivo, solo su referencia. Este servicio responde
dos preguntas del coordinador antes de abrir el documento: dónde está y si
todavía está ahí.
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from backend.domain.services.repositorio_config_service import (
    RepositorioConfigService,
    RepositorioNoConfiguradoError,
)
from backend.infrastructure.repositorio.base import (
    DOC_DISPONIBLE,
    DOC_ELIMINADO,
    DOC_MOVIDO,
    DOC_NO_VERIFICABLE,
    RepositorioError,
)
from backend.schemas.hoja_vida import DisponibilidadHojaVidaResponse

logger = logging.getLogger(__name__)

# Estado que solo existe en la API: el documento no tiene un enlace usable.
ENLACE_INVALIDO = "ENLACE_INVALIDO"

MENSAJE_NO_DISPONIBLE = (
    "El archivo no está disponible: pudo haber sido movido o eliminado del repositorio."
)
MENSAJE_ENLACE_INVALIDO = "La hoja de vida no tiene un enlace válido al repositorio."
MENSAJE_NO_VERIFICABLE = (
    "No se pudo comprobar si el archivo sigue disponible. Puedes intentar abrirlo igualmente."
)


def ruta_hoja_vida(hoja) -> str:
    """Ruta completa guardada del documento: carpeta y nombre."""
    return f"{hoja.ruta}/{hoja.nombre_archivo}".replace("//", "/")


def _enlace_valido(url: Optional[str]) -> bool:
    return bool(url) and url.lower().startswith(("http://", "https://"))


def _ruta_para_persona(hoja, ruta_legible: Optional[str]) -> str:
    """
    Ubicación legible del documento.

    Google Drive guarda en `ruta` el ID de la carpeta, que no le dice nada a
    nadie: se usa el nombre de la carpeta que resolvió el proveedor. Si no se
    pudo resolver, solo se muestra la ruta guardada cuando parece una ruta de
    verdad (tiene "/"); si no, únicamente el nombre del archivo.
    """
    if ruta_legible:
        return f"{ruta_legible}/{hoja.nombre_archivo}"
    guardada = (hoja.ruta or "").strip()
    if "/" in guardada:
        return ruta_hoja_vida(hoja)
    return hoja.nombre_archivo


class HojaDeVidaService:
    def __init__(self, db: Session):
        self.db = db
        self.config = RepositorioConfigService(db)

    def disponibilidad(self, hoja) -> DisponibilidadHojaVidaResponse:
        """
        Consulta al origen si el documento sigue disponible.

        Un fallo al consultar no se presenta como "archivo eliminado": se
        devuelve NO_VERIFICABLE y el enlace queda disponible, porque bloquear
        el acceso por un problema de red sería peor que dejar intentar.
        """
        if not _enlace_valido(hoja.url_web):
            return self._respuesta(
                hoja, ENLACE_INVALIDO, disponible=False, mensaje=MENSAJE_ENLACE_INVALIDO
            )

        try:
            cliente = self.config.cliente_activo()
            consulta = cliente.consultar_documento(hoja.id_documento)
        except (RepositorioNoConfiguradoError, RepositorioError) as exc:
            logger.warning("No se pudo verificar %s: %s", hoja.nombre_archivo, exc)
            return self._respuesta(
                hoja, DOC_NO_VERIFICABLE, disponible=True, mensaje=MENSAJE_NO_VERIFICABLE
            )

        if consulta.estado in (DOC_MOVIDO, DOC_ELIMINADO):
            return self._respuesta(
                hoja,
                consulta.estado,
                disponible=False,
                mensaje=MENSAJE_NO_DISPONIBLE,
                ruta_legible=consulta.ruta_legible,
            )
        if consulta.estado == DOC_DISPONIBLE:
            return self._respuesta(
                hoja, DOC_DISPONIBLE, disponible=True, ruta_legible=consulta.ruta_legible
            )
        return self._respuesta(
            hoja, DOC_NO_VERIFICABLE, disponible=True, mensaje=MENSAJE_NO_VERIFICABLE
        )

    @staticmethod
    def _respuesta(
        hoja,
        estado: str,
        disponible: bool,
        mensaje: Optional[str] = None,
        ruta_legible: Optional[str] = None,
    ) -> DisponibilidadHojaVidaResponse:
        return DisponibilidadHojaVidaResponse(
            estado=estado,
            disponible=disponible,
            mensaje=mensaje,
            nombre_archivo=hoja.nombre_archivo,
            ruta=_ruta_para_persona(hoja, ruta_legible),
            # Si el archivo no está disponible no se ofrece el enlace: llevaría a un error.
            url=hoja.url_web if disponible else None,
        )
