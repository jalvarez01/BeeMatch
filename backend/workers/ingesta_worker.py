"""Worker de ingesta (componente C16): extrae e indexa una hoja de vida."""

from backend.domain.services.indexacion_service import IndexacionService
from backend.infrastructure.persistence.database import SessionLocal


def indexar_hoja_de_vida(hoja_id: str) -> bool:
    db = SessionLocal()
    try:
        return IndexacionService(db).indexar_hoja(hoja_id)
    finally:
        db.close()


def indexar_lote(hoja_ids: list[str]) -> dict:
    indexadas, fallidas = 0, 0
    for hoja_id in hoja_ids:
        if indexar_hoja_de_vida(hoja_id):
            indexadas += 1
        else:
            fallidas += 1
    return {"indexadas": indexadas, "fallidas": fallidas}
