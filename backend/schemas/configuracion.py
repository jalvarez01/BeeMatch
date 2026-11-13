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


class RecomendacionParametros(BaseModel):
    """HU-07: valores vigentes y los límites que acepta el servidor."""

    num_candidatos: int
    umbral_afinidad: int
    num_candidatos_por_defecto: int
    umbral_afinidad_por_defecto: int
    minimo_candidatos: int
    maximo_candidatos: int
    minimo_umbral: int
    maximo_umbral: int


class RecomendacionParametrosUpdate(BaseModel):
    num_candidatos: int
    umbral_afinidad: int


class BitacoraResponse(BaseModel):
    """HU-06: un evento con fecha y hora, quién lo hizo, con qué rol y qué hizo."""

    id: str
    created_at: Optional[datetime] = None
    usuario_id: Optional[str] = None
    usuario_nombre: Optional[str] = None
    usuario_correo: Optional[str] = None
    rol: Optional[str] = None
    accion: str
    entidad: Optional[str] = None
    entidad_id: Optional[str] = None
    detalle: Optional[str] = None


class BitacoraPagina(BaseModel):
    total: int
    limite: int
    desplazamiento: int
    items: list[BitacoraResponse]
