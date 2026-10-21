from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.domain.services.bitacora_service import ACCION_SOLICITUD_CREADA, BitacoraService
from backend.domain.services.solicitud_service import SolicitudService
from backend.infrastructure.persistence.database import get_db
from backend.schemas.solicitud import (
    HistorialResponse,
    SolicitudCreate,
    SolicitudResponse,
    SolicitudUpdate,
)
from backend.security import (
    ROL_ADMINISTRADOR,
    ROL_DIRECTOR,
    exigir_rol,
    get_current_user,
    puede_ver_solicitud,
)

router = APIRouter()


def _verificar_acceso_solicitud(solicitud, usuario):
    """HU-04: el Coordinador solo abre sus solicitudes; los demás roles, las del área."""
    if not puede_ver_solicitud(usuario, solicitud):
        raise HTTPException(
            status_code=403,
            detail="No tienes permiso para acceder a esta solicitud.",
        )


def _service(db: Session = Depends(get_db)) -> SolicitudService:
    return SolicitudService(db)


@router.post("/", response_model=SolicitudResponse, status_code=201)
def crear_solicitud(
    datos: SolicitudCreate,
    svc: SolicitudService = Depends(_service),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """HU-08, HU-09, HU-11, HU-12."""
    if not datos.descripcion_libre.strip() and not datos.rol_buscado:
        # HU-10: validación de campos obligatorios.
        raise HTTPException(
            status_code=422,
            detail="Describe el perfil o selecciona un rol para poder buscar.",
        )

    solicitud = svc.crear(datos, current_user.id)
    BitacoraService(db).registrar(
        ACCION_SOLICITUD_CREADA, usuario_id=current_user.id, entidad="solicitud", entidad_id=solicitud.id
    )
    return solicitud


@router.get("/", response_model=HistorialResponse)
def historial(
    estado: Optional[str] = None,
    texto: Optional[str] = None,
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=10, ge=1, le=50),
    svc: SolicitudService = Depends(_service),
    _=Depends(exigir_rol(ROL_DIRECTOR, ROL_ADMINISTRADOR)),
):
    """HU-13: historial filtrable."""
    solicitudes, total = svc.historial(estado, texto, pagina, por_pagina)
    return HistorialResponse(total=total, pagina=pagina, solicitudes=solicitudes)


@router.get("/{solicitud_id}", response_model=SolicitudResponse)
def obtener_solicitud(
    solicitud_id: str,
    svc: SolicitudService = Depends(_service),
    current_user=Depends(get_current_user),
):
    solicitud_model = svc.repo.get_by_id(solicitud_id)

    if not solicitud_model:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada.")

    _verificar_acceso_solicitud(solicitud_model, current_user)

    return svc.obtener(solicitud_id)


@router.put("/{solicitud_id}", response_model=SolicitudResponse)
def actualizar_solicitud(
    solicitud_id: str,
    datos: SolicitudUpdate,
    svc: SolicitudService = Depends(_service),
    current_user=Depends(get_current_user),
):
    solicitud_model = svc.repo.get_by_id(solicitud_id)

    if not solicitud_model:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada.")

    _verificar_acceso_solicitud(solicitud_model, current_user)

    solicitud = svc.actualizar(solicitud_id, datos)

    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada.")

    return solicitud


@router.post("/{solicitud_id}/duplicar", response_model=SolicitudResponse, status_code=201)
def duplicar_solicitud(
    solicitud_id: str,
    svc: SolicitudService = Depends(_service),
    current_user=Depends(get_current_user),
):
    solicitud_model = svc.repo.get_by_id(solicitud_id)

    if not solicitud_model:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada.")

    _verificar_acceso_solicitud(solicitud_model, current_user)

    copia = svc.duplicar(solicitud_id, current_user.id)

    if not copia:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada.")

    return copia
