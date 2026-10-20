"""Worker de búsqueda (componente C17): ejecuta el motor de matching."""

import logging

from backend.domain.services.busqueda_service import BusquedaService
from backend.infrastructure.repositorio.base import RepositorioError
from backend.domain.services.repositorio_config_service import RepositorioNoConfiguradoError
from backend.infrastructure.persistence.database import SessionLocal
from backend.workers.scheduler import sincronizar_y_encolar

logger = logging.getLogger(__name__)


def ejecutar_busqueda(busqueda_id: str) -> None:
    db = SessionLocal()
    try:
        try:
            _sincronizar_repositorio()
        except (RepositorioError, RepositorioNoConfiguradoError) as exc:
            logger.exception(
                "No fue posible acceder al repositorio antes de la búsqueda"
            )
            BusquedaService(db).marcar_error_repositorio(
                busqueda_id,
                str(exc),
            )
            return

        BusquedaService(db).ejecutar(busqueda_id)
    finally:
        db.close()


def _sincronizar_repositorio() -> None:
    """
    Sincroniza el repositorio antes de ejecutar el análisis.

    Los errores del repositorio se propagan a ejecutar_busqueda()
    para registrar el fallo y actualizar el estado de la búsqueda.
    """
    sincronizar_y_encolar()