from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

from backend.schemas.solicitud import CriterioBase

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
    nombre_archivo: Optional[str] = None  # HU-21
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


class ParametrosBusqueda(BaseModel):
    """
    HU-12 y HU-15: lo que se analizó en una ejecución. Se guarda con la búsqueda
    para que editar la solicitud no cambie lo que dicen las ejecuciones anteriores.
    """

    descripcion_libre: str = ""
    rol_buscado: Optional[str] = None
    experiencia_min: Optional[int] = None
    cliente_id: Optional[str] = None
    cliente: Optional[str] = None
    proyecto_id: Optional[str] = None
    proyecto: Optional[str] = None
    criterios: list[CriterioBase] = []


class EjecucionResumen(BaseModel):
    """HU-15: una fila del historial de ejecuciones de una solicitud."""

    id: str
    # 1 es la primera ejecución de la solicitud; el número crece con cada nueva.
    numero: int
    estado: str
    created_at: Optional[datetime] = None
    es_mas_reciente: bool = False
    total_candidatos: int = 0
    mejor_afinidad: Optional[float] = None
    mensaje_error: Optional[str] = None
    parametros: Optional[ParametrosBusqueda] = None


class BusquedaResultadoResponse(BaseModel):
    id: str
    solicitud_id: str
    estado: str
    cv_analizados: int
    cv_no_procesables: int
    duracion_ms: Optional[int] = None
    modelo_ia: Optional[str] = None
    created_at: Optional[datetime] = None
    # HU-15: criterios, cliente y proyecto de esta ejecución. Nulo en las anteriores a HU-15.
    parametros: Optional[ParametrosBusqueda] = None
    numero_ejecucion: int = 1
    total_ejecuciones: int = 1
    recomendaciones: list[RecomendacionResponse] = []

    model_config = {"from_attributes": True}


class PreseleccionToggle(BaseModel):
    preseleccionado: bool


class ExportarPreseleccionRequest(BaseModel):
    formato: Literal["PDF", "XLSX"] = "PDF"
