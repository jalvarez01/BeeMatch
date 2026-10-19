"""Worker de búsqueda (componente C17): ejecuta el motor de matching."""

import logging

from backend.domain.services.busqueda_service import BusquedaService
from backend.infrastructure.persistence.database import SessionLocal
from backend.infrastructure.persistence.models.busqueda import BUSQUEDA_EJECUTANDO
from backend.infrastructure.persistence.repositories.busqueda_repo import BusquedaRepository
from backend.workers.scheduler import sincronizar_y_encolar

logger = logging.getLogger(__name__)


def ejecutar_busqueda(busqueda_id: str) -> None:
    db = SessionLocal()
    try:
        if not _marcar_sincronizacion(db, busqueda_id):
            return
        _sincronizar_repositorio()
        BusquedaService(db).ejecutar(busqueda_id)
    finally:
        db.close()


def _marcar_sincronizacion(db, busqueda_id: str) -> bool:
    """
    HU-22: la sincronización previa también se ve en el indicador de progreso.

    Sin esto la búsqueda se queda en "pendiente" mientras se consulta el
    repositorio, que en la primera corrida puede tardar bastante más que el análisis.
    Devuelve False si la búsqueda ya no existe.
    """
    busqueda = BusquedaRepository(db).finalizar(
        busqueda_id,
        estado=BUSQUEDA_EJECUTANDO,
        etapa="Sincronizando el repositorio",
        progreso=5,
    )
    return busqueda is not None


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
