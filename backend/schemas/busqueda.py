from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

EstadoCoincidencia = Literal["ENCONTRADO", "PARCIAL", "NO_EVIDENCIADO"]


class CoincidenciaResponse(BaseModel):
    """
    RNF27: NO_EVIDENCIADO significa que la hoja de vida no lo menciona, nunca
    que el candidato carezca de la habilidad.
    """

    requisito: str
    estado: EstadoCoincidencia
    evidencia_texto: Optional[str] = None
    fragmento_id: Optional[str] = None

    model_config = {"from_attributes": True}


class RecomendacionResponse(BaseModel):
    id: str
    candidato_id: str
    posicion: int
    puntaje_afinidad: float
    nivel: str
    preseleccionado: bool
    resumen_ia: Optional[str] = None

    # Datos enriquecidos del candidato
    nombre: Optional[str] = None
    rol_principal: Optional[str] = None
    anios_experiencia: Optional[int] = None
    tecnologias: list[str] = []
    ubicacion: Optional[str] = None
    ruta_hoja_vida: Optional[str] = None  # HU-21
    url_hoja_vida: Optional[str] = None

    coincidencias: list[CoincidenciaResponse] = []

    model_config = {"from_attributes": True}


class BusquedaEstadoResponse(BaseModel):
    """Respuesta del polling mientras el worker procesa (HU-22)."""

    id: str
    solicitud_id: str
    estado: str
    etapa: Optional[str] = None
    progreso: int = 0
    mensaje_error: Optional[str] = None

    model_config = {"from_attributes": True}


class BusquedaResultadoResponse(BaseModel):
    id: str
    solicitud_id: str
    estado: str
    cv_analizados: int
    cv_no_procesables: int
    duracion_ms: Optional[int] = None
    modelo_ia: Optional[str] = None
    created_at: Optional[datetime] = None
    recomendaciones: list[RecomendacionResponse] = []

    model_config = {"from_attributes": True}


class PreseleccionToggle(BaseModel):
    preseleccionado: bool


class ExportarPreseleccionRequest(BaseModel):
    formato: Literal["PDF", "XLSX"] = "PDF"
