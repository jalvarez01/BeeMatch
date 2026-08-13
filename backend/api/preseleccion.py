from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.domain.services.bitacora_service import ACCION_EXPORTACION, BitacoraService
from backend.domain.services.export_service import ExportService
from backend.infrastructure.persistence.database import get_db
from backend.schemas.busqueda import ExportarPreseleccionRequest
from backend.security import get_current_user

router = APIRouter()


@router.post("/{busqueda_id}/exportar")
def exportar(
    busqueda_id: str,
    datos: ExportarPreseleccionRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """HU-25: exportar la preselección para enviarla al cliente."""
    try:
        archivo = ExportService(db).exportar(busqueda_id, datos.formato)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc))

    BitacoraService(db).registrar(
        ACCION_EXPORTACION,
        usuario_id=current_user.id,
        entidad="busqueda",
        entidad_id=busqueda_id,
        detalle=datos.formato,
    )
    return FileResponse(archivo, filename=archivo.name)
