from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.domain.services.bitacora_service import ACCION_SINCRONIZACION, BitacoraService
from backend.infrastructure.persistence.database import get_db
from backend.infrastructure.persistence.models.hoja_vida import (
    ESTADO_INDEXADA,
    ESTADO_NO_PROCESABLE,
    ESTADO_PENDIENTE,
)
from backend.infrastructure.persistence.repositories.hoja_vida_repo import HojaDeVidaRepository
from backend.schemas.hoja_vida import EstadoIndiceResponse, SincronizacionResponse
from backend.security import ROL_ADMINISTRADOR, exigir_rol, get_current_user
from backend.workers.scheduler import sincronizar_y_encolar

router = APIRouter()


@router.get("/estado", response_model=EstadoIndiceResponse)
def estado_indice(db: Session = Depends(get_db), _=Depends(get_current_user)):
    """HU-17: cuántas hojas de vida hay indexadas y cuántas no se pudieron procesar."""
    repo = HojaDeVidaRepository(db)
    indexadas = repo.contar_por_estado(ESTADO_INDEXADA)
    pendientes = repo.contar_por_estado(ESTADO_PENDIENTE)
    no_procesables = repo.contar_por_estado(ESTADO_NO_PROCESABLE)
    return EstadoIndiceResponse(
        total=indexadas + pendientes + no_procesables,
        indexadas=indexadas,
        pendientes=pendientes,
        no_procesables=no_procesables,
    )


@router.post("/sincronizar", response_model=SincronizacionResponse)
def sincronizar(
    db: Session = Depends(get_db),
    current_user=Depends(exigir_rol(ROL_ADMINISTRADOR)),
):
    """HU-05, HU-16: sincronización bajo demanda con OneDrive."""
    resultado = sincronizar_y_encolar()
    BitacoraService(db).registrar(ACCION_SINCRONIZACION, usuario_id=current_user.id)
    return SincronizacionResponse(
        documentos_detectados=resultado["documentos_detectados"],
        documentos_encolados=resultado["documentos_encolados"],
        mensaje="Sincronización iniciada. La indexación continúa en segundo plano.",
    )
