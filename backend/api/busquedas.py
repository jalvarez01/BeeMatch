from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.domain.services.bitacora_service import ACCION_PRESELECCION, BitacoraService
from backend.domain.services.busqueda_service import BusquedaService
from backend.domain.services.resultado_service import ResultadoService
from backend.domain.services.solicitud_service import (
    MENSAJE_DESCRIPCION_CORTA,
    SolicitudService,
    campos_faltantes_busqueda,
    descripcion_insuficiente,
    mensaje_campos_faltantes,
)
from backend.infrastructure.persistence.database import get_db
from backend.infrastructure.persistence.models.solicitud import ESTADO_EN_ANALISIS
from backend.infrastructure.persistence.repositories.solicitud_repo import SolicitudRepository
from backend.schemas.busqueda import (
    BusquedaEstadoResponse,
    BusquedaResultadoResponse,
    EjecucionResumen,
    PreseleccionToggle,
    RecomendacionResponse,
)
from backend.schemas.hoja_vida import DisponibilidadHojaVidaResponse
from backend.schemas.solicitud import AjusteSolicitud
from backend.security import get_current_user, puede_ver_solicitud
from backend.workers.busqueda_worker import ejecutar_busqueda
from backend.workers.queue import despachar

router = APIRouter()


def _exigir_acceso_a_busqueda(db: Session, busqueda_id: str, usuario) -> None:
    """
    HU-04: los resultados de una búsqueda son de quien la pidió. El Coordinador
    solo abre los suyos; Director, Administrador y la superusuaria, los del área.
    Si la búsqueda no existe se deja pasar: cada endpoint responde su propio 404.
    """
    busqueda = BusquedaService(db).busquedas.get_by_id(busqueda_id)
    if not busqueda:
        return
    solicitud = SolicitudRepository(db).get_by_id(busqueda.solicitud_id)
    if solicitud and not puede_ver_solicitud(usuario, solicitud):
        raise HTTPException(
            status_code=403, detail="No tienes permiso para acceder a esta búsqueda."
        )


def _exigir_acceso_a_recomendacion(db: Session, recomendacion_id: str, usuario) -> None:
    recomendacion = BusquedaService(db).busquedas.get_recomendacion(recomendacion_id)
    if recomendacion:
        _exigir_acceso_a_busqueda(db, recomendacion.busqueda_id, usuario)


def _obtener_solicitud_accesible(db: Session, solicitud_id: str, usuario):
    solicitud = SolicitudRepository(db).get_by_id(solicitud_id)
    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    if not puede_ver_solicitud(usuario, solicitud):
        raise HTTPException(
            status_code=403, detail="No tienes permiso para acceder a esta solicitud."
        )
    return solicitud


def _exigir_solicitud_completa(descripcion, rol, cliente) -> None:
    """HU-10 y HU-12: sin rol, descripción o cliente la búsqueda no se ejecuta."""
    faltantes = campos_faltantes_busqueda(descripcion, rol, cliente)
    if faltantes:
        raise HTTPException(status_code=422, detail=mensaje_campos_faltantes(faltantes))
    if descripcion_insuficiente(descripcion):
        raise HTTPException(status_code=422, detail=MENSAJE_DESCRIPCION_CORTA)


def _lanzar_busqueda(db: Session, tareas: BackgroundTasks, solicitud_id: str, usuario) -> str:
    """Crea la ejecución con la copia de los criterios actuales y la despacha al worker."""
    servicio = BusquedaService(db)
    # La bitácora de HU-06 la registra `encolar`, que es donde se crea la búsqueda.
    busqueda_id = servicio.encolar(solicitud_id, usuario_id=usuario.id)
    SolicitudRepository(db).cambiar_estado(solicitud_id, ESTADO_EN_ANALISIS)
    # La sincronización con el repositorio (HU-16) la hace el worker, no esta
    # petición: ver backend/workers/busqueda_worker.py.
    despachar(tareas, ejecutar_busqueda, busqueda_id)
    return busqueda_id


@router.post("/solicitud/{solicitud_id}", response_model=BusquedaEstadoResponse, status_code=202)
def ejecutar(
    solicitud_id: str,
    tareas: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    HU-18. Responde 202 de inmediato: el análisis corre en un worker y el
    frontend consulta el progreso (RNF04, HU-22).
    """
    solicitud = _obtener_solicitud_accesible(db, solicitud_id, current_user)
    cliente = SolicitudService(db).clientes.get_by_id(solicitud.cliente_id) if solicitud.cliente_id else None
    _exigir_solicitud_completa(
        solicitud.descripcion_libre, solicitud.rol_buscado, cliente.nombre if cliente else None
    )

    servicio = BusquedaService(db)

    # HU-22: si la solicitud ya se está analizando no se lanza otra búsqueda
    # encima (doble clic, dos pestañas): se devuelve la que está en curso.
    en_curso = servicio.en_curso(solicitud_id)
    if en_curso:
        return BusquedaEstadoResponse.model_validate(en_curso)

    busqueda_id = _lanzar_busqueda(db, tareas, solicitud_id, current_user)
    return BusquedaEstadoResponse.model_validate(servicio.busquedas.get_by_id(busqueda_id))


@router.post(
    "/solicitud/{solicitud_id}/reejecutar", response_model=BusquedaEstadoResponse, status_code=202
)
def reejecutar(
    solicitud_id: str,
    datos: AjusteSolicitud,
    tareas: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    HU-15: ajusta los criterios de la solicitud y vuelve a ejecutar el análisis.

    Es una sola operación: si los criterios no son válidos (por ejemplo, falta el
    cliente) o ya hay un análisis en curso, no se cambia nada. La ejecución nueva
    se suma a las anteriores, que conservan sus criterios y resultados.
    """
    _obtener_solicitud_accesible(db, solicitud_id, current_user)
    _exigir_solicitud_completa(datos.descripcion_libre, datos.rol_buscado, datos.cliente)

    servicio = BusquedaService(db)
    if servicio.en_curso(solicitud_id):
        # HU-22: un segundo envío (doble clic, otra pestaña) no pisa el análisis en marcha.
        raise HTTPException(
            status_code=409,
            detail="Esta solicitud ya se está analizando. Espera a que termine para ajustar los criterios.",
        )

    SolicitudService(db).reemplazar(solicitud_id, datos)
    busqueda_id = _lanzar_busqueda(db, tareas, solicitud_id, current_user)
    return BusquedaEstadoResponse.model_validate(servicio.busquedas.get_by_id(busqueda_id))


@router.get("/solicitud/{solicitud_id}/ejecuciones", response_model=list[EjecucionResumen])
def ejecuciones(
    solicitud_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)
):
    """HU-15: historial de ejecuciones de la solicitud, de la más reciente a la más antigua."""
    _obtener_solicitud_accesible(db, solicitud_id, current_user)
    return ResultadoService(db).ejecuciones(solicitud_id)


@router.get("/{busqueda_id}/estado", response_model=BusquedaEstadoResponse)
def estado(busqueda_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """HU-22: indicador de progreso durante el análisis."""
    _exigir_acceso_a_busqueda(db, busqueda_id, current_user)
    busqueda = BusquedaService(db).busquedas.get_by_id(busqueda_id)
    if not busqueda:
        raise HTTPException(status_code=404, detail="Búsqueda no encontrada")
    return BusquedaEstadoResponse.model_validate(busqueda)


@router.get("/{busqueda_id}", response_model=BusquedaResultadoResponse)
def resultados(
    busqueda_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)
):
    """HU-18, HU-20, HU-23: Top 5 con afinidad, o lista vacía si nadie superó el umbral."""
    _exigir_acceso_a_busqueda(db, busqueda_id, current_user)
    resultado = ResultadoService(db).resultados(busqueda_id)
    if not resultado:
        raise HTTPException(status_code=404, detail="Búsqueda no encontrada")
    return resultado


@router.get("/recomendacion/{recomendacion_id}", response_model=RecomendacionResponse)
def detalle(
    recomendacion_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)
):
    """HU-19, HU-21: explicación de coincidencias y ubicación de la hoja de vida."""
    _exigir_acceso_a_recomendacion(db, recomendacion_id, current_user)
    recomendacion = ResultadoService(db).detalle_recomendacion(recomendacion_id)
    if not recomendacion:
        raise HTTPException(status_code=404, detail="Recomendación no encontrada")
    return recomendacion


@router.get(
    "/recomendacion/{recomendacion_id}/hoja-de-vida",
    response_model=DisponibilidadHojaVidaResponse,
)
def hoja_de_vida(
    recomendacion_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)
):
    """HU-21: ubicación de la hoja de vida y si el archivo sigue disponible."""
    _exigir_acceso_a_recomendacion(db, recomendacion_id, current_user)
    disponibilidad = ResultadoService(db).disponibilidad_hoja_vida(recomendacion_id)
    if not disponibilidad:
        raise HTTPException(status_code=404, detail="Hoja de vida no encontrada")
    return disponibilidad


@router.patch("/recomendacion/{recomendacion_id}/preseleccion", response_model=RecomendacionResponse)
def preseleccionar(
    recomendacion_id: str,
    datos: PreseleccionToggle,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """HU-24."""
    _exigir_acceso_a_recomendacion(db, recomendacion_id, current_user)
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
