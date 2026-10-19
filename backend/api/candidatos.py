from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.domain.services.candidato_service import CandidatoService
from backend.infrastructure.persistence.database import get_db
from backend.schemas.candidato import CandidatoResponse, RolDisponibleResponse
from backend.security import get_current_user

router = APIRouter()


@router.get("/", response_model=list[CandidatoResponse])
def listar(
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    return CandidatoService(db).listar(pagina, por_pagina)


@router.get("/roles", response_model=list[RolDisponibleResponse])
def roles(db: Session = Depends(get_db), _=Depends(get_current_user)):
    """
    Roles disponibles para filtrar una búsqueda (HU-09).

    Se derivan de lo que la IA extrajo de las hojas de vida, así que reflejan
    lo que hay en el repositorio en cada momento.
    """
    return CandidatoService(db).roles_disponibles()


@router.get("/{candidato_id}", response_model=CandidatoResponse)
def obtener(candidato_id: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    candidato = CandidatoService(db).obtener(candidato_id)
    if not candidato:
        raise HTTPException(status_code=404, detail="Candidato no encontrado")
    return candidato
