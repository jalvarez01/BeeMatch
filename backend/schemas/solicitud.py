from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

TipoCriterio = Literal["TECNOLOGIA", "FRAMEWORK", "DOMINIO", "CERTIFICACION", "IDIOMA"]
DESCRIPCION_MIN_CARACTERES = 15
DESCRIPCION_MAX_CARACTERES = 1000
EXPERIENCIA_MAX_ANIOS = 50

class CriterioBase(BaseModel):
    tipo: TipoCriterio
    valor: str
    obligatorio: bool = False
    peso: float = 1.0


class CriterioResponse(CriterioBase):
    id: str

    model_config = {"from_attributes": True}


class SolicitudCreate(BaseModel):
    """HU-08 (lenguaje natural) + HU-09 (criterios estructurados) + HU-12 (cliente)."""

    descripcion_libre: str = Field(default="", max_length=DESCRIPCION_MAX_CARACTERES)
    rol_buscado: Optional[str] = None
    # HU-10: los años de experiencia solo admiten enteros positivos.
    experiencia_min: Optional[int] = Field(default=None, gt=0, le=EXPERIENCIA_MAX_ANIOS)
    cliente: Optional[str] = None
    proyecto: Optional[str] = None
    criterios: list[CriterioBase] = []
    guardar_como_borrador: bool = False


class SolicitudUpdate(BaseModel):
    descripcion_libre: Optional[str] = Field(default=None, max_length=DESCRIPCION_MAX_CARACTERES)
    rol_buscado: Optional[str] = None
    experiencia_min: Optional[int] = Field(default=None, gt=0, le=EXPERIENCIA_MAX_ANIOS)
    cliente: Optional[str] = None
    proyecto: Optional[str] = None
    criterios: Optional[list[CriterioBase]] = None


class SolicitudResponse(BaseModel):
    id: str
    descripcion_libre: str
    rol_buscado: Optional[str] = None
    experiencia_min: Optional[int] = None
    estado: str
    created_at: Optional[datetime] = None

    # Datos enriquecidos para el historial (HU-13)
    cliente_nombre: Optional[str] = None
    proyecto_nombre: Optional[str] = None
    usuario_nombre: Optional[str] = None
    criterios: list[CriterioResponse] = []
    total_candidatos: Optional[int] = None
    mejor_afinidad: Optional[float] = None
    busqueda_id: Optional[str] = None

    model_config = {"from_attributes": True}


class HistorialResponse(BaseModel):
    total: int
    pagina: int
    solicitudes: list[SolicitudResponse]
