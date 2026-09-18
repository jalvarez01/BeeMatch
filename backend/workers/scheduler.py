"""
Planificador (componente C18): dispara la sincronización con el repositorio
configurado cada SYNC_INTERVALO_HORAS. También puede lanzarse bajo demanda
desde la interfaz.
"""

from backend.config import SYNC_INTERVALO_HORAS
from backend.infrastructure.llm.embeddings import ProveedorEmbeddingsNoDisponibleError
from backend.infrastructure.repositorio.sync_service import SincronizacionService
from backend.infrastructure.persistence.database import SessionLocal
from backend.workers.ingesta_worker import indexar_hoja_de_vida
from backend.workers.queue import encolar


def sincronizar_y_encolar() -> dict:
    """
    Detecta los documentos del origen configurado y manda a indexar los que
    cambiaron.

    Registrar e indexar son dos pasos distintos y el segundo puede no estar
    disponible todavía: sin Redis, `encolar` ejecuta el trabajo en línea, así
    que un fallo del worker llegaría hasta aquí y tumbaría una sincronización
    que en realidad sí funcionó. Cuando lo que falta es el proveedor de
    embeddings, los documentos quedan registrados en estado PENDIENTE y la
    indexación se informa como aplazada.
    """
    db = SessionLocal()
    try:
        resultado = SincronizacionService(db).sincronizar()
        hojas = resultado["hojas_a_indexar"]

        encolados = 0
        aplazados = 0
        motivo_aplazamiento = None

        for posicion, hoja_id in enumerate(hojas):
            try:
                encolar(indexar_hoja_de_vida, hoja_id)
                encolados += 1
            except ProveedorEmbeddingsNoDisponibleError as exc:
                # Le falta al sistema, no al documento: reintentar con los
                # demás daría el mismo resultado.
                aplazados = len(hojas) - posicion
                motivo_aplazamiento = str(exc)
                break

        return {
            "documentos_detectados": resultado["documentos_detectados"],
            "documentos_encolados": encolados,
            "documentos_aplazados": aplazados,
            "motivo_aplazamiento": motivo_aplazamiento,
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
