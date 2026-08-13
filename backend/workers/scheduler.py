"""
Planificador (componente C18): dispara la sincronización con OneDrive cada
SYNC_INTERVALO_HORAS. También puede lanzarse bajo demanda desde la interfaz.
"""

from backend.config import SYNC_INTERVALO_HORAS
from backend.infrastructure.onedrive.sync_service import SincronizacionService
from backend.infrastructure.persistence.database import SessionLocal
from backend.workers.ingesta_worker import indexar_hoja_de_vida
from backend.workers.queue import encolar


def sincronizar_y_encolar() -> dict:
    db = SessionLocal()
    try:
        resultado = SincronizacionService(db).sincronizar()
        for hoja_id in resultado["hojas_a_indexar"]:
            encolar(indexar_hoja_de_vida, hoja_id)
        return {
            "documentos_detectados": resultado["documentos_detectados"],
            "documentos_encolados": len(resultado["hojas_a_indexar"]),
        }
    finally:
        db.close()


def iniciar_planificador():
    """Arranca APScheduler en background. Se llama desde el startup de FastAPI."""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        return None

    planificador = BackgroundScheduler()
    planificador.add_job(sincronizar_y_encolar, "interval", hours=SYNC_INTERVALO_HORAS)
    planificador.start()
    return planificador
