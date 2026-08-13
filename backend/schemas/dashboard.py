from typing import Optional

from pydantic import BaseModel


class SolicitudRecienteResponse(BaseModel):
    id: str
    perfil: str
    cliente: Optional[str] = None
    estado: str
    hace: str


class DashboardResponse(BaseModel):
    """Métricas de la pantalla de inicio."""

    solicitudes_activas: int
    perfiles_recomendados: int
    hojas_vida_analizadas: int
    afinidad_promedio: float

    candidatos_alta_afinidad: int
    perfiles_nuevos: int
    solicitudes_sin_coincidencias: int

    recientes: list[SolicitudRecienteResponse] = []
