from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class HojaDeVidaResponse(BaseModel):
    id: str
    nombre_archivo: str
    ruta: str
    url_web: Optional[str] = None
    formato: str
    estado_procesamiento: str
    motivo_error: Optional[str] = None
    indexada_en: Optional[datetime] = None

    model_config = {"from_attributes": True}


class EstadoIndiceResponse(BaseModel):
    """Estado del repositorio indexado. Alimenta la pantalla de configuración."""

    total: int
    indexadas: int
    pendientes: int
    no_procesables: int
    ultima_sincronizacion: Optional[datetime] = None


class SincronizacionResponse(BaseModel):
    documentos_detectados: int
    documentos_encolados: int
    mensaje: str
