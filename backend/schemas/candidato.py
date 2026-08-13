from typing import Optional

from pydantic import BaseModel


class HabilidadResponse(BaseModel):
    nombre: str
    categoria: str
    anios_experiencia: Optional[float] = None
    evidencia_texto: Optional[str] = None

    model_config = {"from_attributes": True}


class ExperienciaResponse(BaseModel):
    cargo: str
    empresa: Optional[str] = None
    periodo: Optional[str] = None
    descripcion: Optional[str] = None
    tecnologias: list[str] = []


class CandidatoResponse(BaseModel):
    id: str
    nombre: str
    rol_principal: Optional[str] = None
    anios_experiencia: Optional[int] = None
    ubicacion: Optional[str] = None
    idiomas: Optional[str] = None
    resumen: Optional[str] = None

    hoja_de_vida_id: str
    nombre_archivo: Optional[str] = None
    ruta_hoja_vida: Optional[str] = None
    url_hoja_vida: Optional[str] = None

    habilidades: list[HabilidadResponse] = []
    experiencia: list[ExperienciaResponse] = []

    model_config = {"from_attributes": True}
