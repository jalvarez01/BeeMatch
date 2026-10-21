"""Worker de búsqueda (componente C17): ejecuta el motor de matching."""

import logging

from backend.domain.services.busqueda_service import BusquedaService
from backend.infrastructure.repositorio.base import RepositorioError
from backend.domain.services.repositorio_config_service import RepositorioNoConfiguradoError
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

        try:
            _sincronizar_repositorio()
        except (RepositorioError, RepositorioNoConfiguradoError) as exc:
            logger.exception("No fue posible acceder al repositorio antes de la búsqueda")
            BusquedaService(db).marcar_error_repositorio(busqueda_id, str(exc))
            return

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
    Sincroniza el repositorio antes de ejecutar el análisis.

    Los errores del repositorio se propagan a ejecutar_busqueda()
    para registrar el fallo y actualizar el estado de la búsqueda.
    """
    sincronizar_y_encolar()