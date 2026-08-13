from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.domain.services.bitacora_service import (
    ACCION_BUSQUEDA_EJECUTADA,
    ACCION_PRESELECCION,
    BitacoraService,
)
from backend.domain.services.busqueda_service import BusquedaService
from backend.domain.services.resultado_service import ResultadoService
from backend.infrastructure.persistence.database import get_db
from backend.infrastructure.persistence.models.solicitud import ESTADO_EN_ANALISIS
from backend.infrastructure.persistence.repositories.solicitud_repo import SolicitudRepository
from backend.schemas.busqueda import (
    BusquedaEstadoResponse,
    BusquedaResultadoResponse,
    PreseleccionToggle,
    RecomendacionResponse,
)
from backend.security import get_current_user
from backend.workers.busqueda_worker import ejecutar_busqueda
from backend.workers.queue import encolar

router = APIRouter()


@router.post("/solicitud/{solicitud_id}", response_model=BusquedaEstadoResponse, status_code=202)
def ejecutar(
    solicitud_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    HU-18. Responde 202 de inmediato: el análisis corre en un worker y el
    frontend consulta el progreso (RNF04, HU-22).
    """
    solicitudes = SolicitudRepository(db)
    if not solicitudes.get_by_id(solicitud_id):
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    busqueda_id = BusquedaService(db).encolar(solicitud_id)
    solicitudes.cambiar_estado(solicitud_id, ESTADO_EN_ANALISIS)
    encolar(ejecutar_busqueda, busqueda_id)

    BitacoraService(db).registrar(
        ACCION_BUSQUEDA_EJECUTADA,
        usuario_id=current_user.id,
        entidad="busqueda",
        entidad_id=busqueda_id,
    )

    busqueda = BusquedaService(db).busquedas.get_by_id(busqueda_id)
    return BusquedaEstadoResponse.model_validate(busqueda)


@router.get("/{busqueda_id}/estado", response_model=BusquedaEstadoResponse)
def estado(busqueda_id: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    """HU-22: indicador de progreso durante el análisis."""
    busqueda = BusquedaService(db).busquedas.get_by_id(busqueda_id)
    if not busqueda:
        raise HTTPException(status_code=404, detail="Búsqueda no encontrada")
    return BusquedaEstadoResponse.model_validate(busqueda)


@router.get("/{busqueda_id}", response_model=BusquedaResultadoResponse)
def resultados(busqueda_id: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    """HU-18, HU-20, HU-23: Top 5 con afinidad, o lista vacía si nadie superó el umbral."""
    resultado = ResultadoService(db).resultados(busqueda_id)
    if not resultado:
        raise HTTPException(status_code=404, detail="Búsqueda no encontrada")
    return resultado


@router.get("/recomendacion/{recomendacion_id}", response_model=RecomendacionResponse)
def detalle(recomendacion_id: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    """HU-19, HU-21: explicación de coincidencias y ubicación de la hoja de vida."""
    recomendacion = ResultadoService(db).detalle_recomendacion(recomendacion_id)
    if not recomendacion:
        raise HTTPException(status_code=404, detail="Recomendación no encontrada")
    return recomendacion


@router.patch("/recomendacion/{recomendacion_id}/preseleccion", response_model=RecomendacionResponse)
def preseleccionar(
    recomendacion_id: str,
    datos: PreseleccionToggle,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """HU-24."""
    recomendacion = ResultadoService(db).marcar_preseleccion(recomendacion_id, datos.preseleccionado)
    if not recomendacion:
        raise HTTPException(status_code=404, detail="Recomendación no encontrada")

    BitacoraService(db).registrar(
        ACCION_PRESELECCION,
        usuario_id=current_user.id,
        entidad="recomendacion",
        entidad_id=recomendacion_id,
        detalle=str(datos.preseleccionado),
    )
    return recomendacion
