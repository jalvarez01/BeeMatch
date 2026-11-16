from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.infrastructure.persistence.database import get_db
from backend.infrastructure.persistence.repositories.cliente_repo import (
    LIMITE_SUGERENCIAS,
    ClienteDuplicadoError,
    ClienteEnUsoError,
    ClienteRepository,
)
from backend.schemas.cliente import ClienteCreate, ClienteResponse, ClienteUpdate
from backend.security import ROL_SUPERADMINISTRADOR, exigir_rol, get_current_user

router = APIRouter()


@router.get("/", response_model=list[ClienteResponse])
def listar_clientes(
    q: Optional[str] = Query(default=None, max_length=160),
    limite: int = Query(default=LIMITE_SUGERENCIAS, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """
    HU-12: clientes registrados. Cualquier persona con sesión los consulta: alimentan
    el selector del formulario de solicitud y el filtro del historial. Con `q`, solo
    los que empiezan por lo escrito.
    """
    return ClienteRepository(db).sugerir(q or "", limite)


@router.post("/", response_model=ClienteResponse, status_code=201)
def registrar_cliente(
    datos: ClienteCreate,
    db: Session = Depends(get_db),
    _=Depends(exigir_rol(ROL_SUPERADMINISTRADOR)),
):
    """Solo la superadministradora registra clientes; los demás roles eligen entre ellos."""
    try:
        return ClienteRepository(db).registrar(datos.nombre)
    except ClienteDuplicadoError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None


@router.patch("/{cliente_id}", response_model=ClienteResponse)
def renombrar_cliente(
    cliente_id: str,
    datos: ClienteUpdate,
    db: Session = Depends(get_db),
    _=Depends(exigir_rol(ROL_SUPERADMINISTRADOR)),
):
    repo = ClienteRepository(db)
    cliente = repo.get_by_id(cliente_id)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")
    try:
        return repo.renombrar(cliente, datos.nombre)
    except ClienteDuplicadoError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None


@router.delete("/{cliente_id}", status_code=204)
def borrar_cliente(
    cliente_id: str,
    db: Session = Depends(get_db),
    _=Depends(exigir_rol(ROL_SUPERADMINISTRADOR)),
):
    repo = ClienteRepository(db)
    cliente = repo.get_by_id(cliente_id)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")
    try:
        repo.eliminar(cliente)
    except ClienteEnUsoError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
