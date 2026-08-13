from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.domain.services.bitacora_service import ACCION_CONFIG_CAMBIADA, BitacoraService
from backend.infrastructure.persistence.database import get_db
from backend.infrastructure.persistence.repositories.configuracion_repo import ParametroRepository
from backend.schemas.configuracion import BitacoraResponse, ParametroResponse, ParametroUpdate
from backend.security import ROL_ADMINISTRADOR, exigir_rol

router = APIRouter()


@router.get("/parametros", response_model=list[ParametroResponse])
def listar_parametros(db: Session = Depends(get_db), _=Depends(exigir_rol(ROL_ADMINISTRADOR))):
    """HU-07."""
    return ParametroRepository(db).listar()


@router.put("/parametros/{clave}", response_model=ParametroResponse)
def actualizar_parametro(
    clave: str,
    datos: ParametroUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(exigir_rol(ROL_ADMINISTRADOR)),
):
    parametro = ParametroRepository(db).establecer(clave, datos.valor, current_user.id)
    BitacoraService(db).registrar(
        ACCION_CONFIG_CAMBIADA, usuario_id=current_user.id, entidad="parametro", entidad_id=clave
    )
    return parametro


@router.get("/bitacora", response_model=list[BitacoraResponse])
def bitacora(
    limite: int = Query(default=100, ge=1, le=500),
    desplazamiento: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _=Depends(exigir_rol(ROL_ADMINISTRADOR)),
):
    """HU-06."""
    return BitacoraService(db).listar(limite, desplazamiento)
