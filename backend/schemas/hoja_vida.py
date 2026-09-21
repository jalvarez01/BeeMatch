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
    #: Hay documentos por analizar todavía. Mientras sea True la pantalla sigue consultando.
    en_proceso: bool = False
    #: HU-17: mensaje final cuando ya no queda nada pendiente. None mientras se analiza.
    resumen: Optional[str] = None


class SincronizacionResponse(BaseModel):
    documentos_detectados: int
    documentos_encolados: int
    #: Documentos registrados que no se pudieron mandar a indexar todavía.
    documentos_aplazados: int = 0
    mensaje: str
