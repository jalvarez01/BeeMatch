"""Worker de búsqueda (componente C17): ejecuta el motor de matching."""

import logging

from backend.domain.services.busqueda_service import BusquedaService
from backend.infrastructure.persistence.database import SessionLocal
from backend.workers.scheduler import sincronizar_y_encolar

logger = logging.getLogger(__name__)


def ejecutar_busqueda(busqueda_id: str) -> None:
    db = SessionLocal()
    try:
        _sincronizar_repositorio()
        BusquedaService(db).ejecutar(busqueda_id)
    finally:
        db.close()


def _sincronizar_repositorio() -> None:
    """
    HU-16, criterios 1 y 3: antes de analizar se consulta la carpeta configurada,
    así las hojas de vida nuevas entran en la búsqueda sin intervención manual.

    Va aquí y no en el router porque sin Redis `encolar` ejecuta en línea: hacerlo
    en la petición HTTP dejaba la respuesta esperando la indexación de todo el
    repositorio, y rompía el 202 inmediato que promete HU-18. Un fallo del origen
    no cancela el análisis: se busca sobre lo que ya esté indexado y el motivo
    queda en el log.
    """
    try:
        sincronizar_y_encolar()
    except Exception:
        logger.exception("No se pudo sincronizar el repositorio antes de la búsqueda")
