from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.infrastructure.persistence.database import get_db
from backend.infrastructure.persistence.repositories.cliente_repo import (
    LIMITE_SUGERENCIAS,
    ClienteRepository,
)
from backend.schemas.cliente import ClienteResponse
from backend.security import get_current_user

router = APIRouter()


@router.get("/", response_model=list[ClienteResponse])
def sugerir_clientes(
    q: Optional[str] = Query(default=None, max_length=160),
    limite: int = Query(default=LIMITE_SUGERENCIAS, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """
    HU-12: clientes ya registrados cuyo nombre empieza por lo escrito. Alimenta las
    sugerencias del formulario y, sin `q`, la lista de clientes del filtro del historial.
    """
    return ClienteRepository(db).sugerir(q or "", limite)
