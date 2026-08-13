"""Worker de búsqueda (componente C17): ejecuta el motor de matching."""

from backend.domain.services.busqueda_service import BusquedaService
from backend.infrastructure.persistence.database import SessionLocal


def ejecutar_busqueda(busqueda_id: str) -> None:
    db = SessionLocal()
    try:
        BusquedaService(db).ejecutar(busqueda_id)
    finally:
        db.close()
