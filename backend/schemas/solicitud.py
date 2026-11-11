from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

# HU-09: OTRO recoge el campo "Otros conocimientos" (sector, metodologías, normas…),
# que no encaja en tecnología, framework ni idioma.
TipoCriterio = Literal["TECNOLOGIA", "FRAMEWORK", "DOMINIO", "CERTIFICACION", "IDIOMA", "OTRO"]
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


class AjusteSolicitud(BaseModel):
    """
    HU-15: criterios ajustados para volver a ejecutar la búsqueda.

    A diferencia de `SolicitudUpdate`, es un reemplazo completo: lo que llega es
    lo que queda. Un campo nulo borra el valor anterior (por ejemplo, la
    experiencia mínima), que con una actualización parcial no se podría quitar.
    """

    descripcion_libre: str = Field(default="", max_length=DESCRIPCION_MAX_CARACTERES)
    rol_buscado: Optional[str] = None
    experiencia_min: Optional[int] = Field(default=None, gt=0, le=EXPERIENCIA_MAX_ANIOS)
    cliente: Optional[str] = None
    proyecto: Optional[str] = None
    criterios: list[CriterioBase] = []


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
    cliente_id: Optional[str] = None
    proyecto_id: Optional[str] = None

    # Datos enriquecidos para el historial (HU-13)
    cliente_nombre: Optional[str] = None
    proyecto_nombre: Optional[str] = None
    usuario_nombre: Optional[str] = None
    criterios: list[CriterioResponse] = []
    total_candidatos: Optional[int] = None
    mejor_afinidad: Optional[float] = None
    # HU-24: cuántos candidatos de la última búsqueda se marcaron para el cliente.
    total_preseleccionados: Optional[int] = None
    busqueda_id: Optional[str] = None
    # HU-15: cuántas veces se ejecutó el análisis de esta solicitud.
    total_ejecuciones: int = 0

    model_config = {"from_attributes": True}


class HistorialResponse(BaseModel):
    total: int
    pagina: int
    solicitudes: list[SolicitudResponse]
