from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ParametroResponse(BaseModel):
    clave: str
    valor: str
    descripcion: Optional[str] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ParametroUpdate(BaseModel):
    valor: str


class BitacoraResponse(BaseModel):
    id: str
    usuario_id: Optional[str] = None
    accion: str
    entidad: Optional[str] = None
    entidad_id: Optional[str] = None
    detalle: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
