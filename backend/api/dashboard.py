from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.domain.services.dashboard_service import DashboardService
from backend.infrastructure.persistence.database import get_db
from backend.schemas.dashboard import DashboardResponse
from backend.security import get_current_user

router = APIRouter()


@router.get("/", response_model=DashboardResponse)
def resumen(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return DashboardService(db).resumen()
