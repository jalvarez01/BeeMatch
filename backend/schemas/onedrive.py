from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ConexionOneDriveRequest(BaseModel):
    """
    Datos de conexión (HU-05).

    `client_secret` es opcional: si se omite, se reutiliza el ya almacenado.
    Esto permite corregir la ruta sin volver a escribir la credencial.
    """

    tenant_id: str = Field(min_length=1, max_length=100)
    client_id: str = Field(min_length=1, max_length=100)
    client_secret: Optional[str] = Field(default=None, max_length=400)
    drive_id: str = Field(min_length=1, max_length=200)
    carpeta_cv: str = Field(default="/HojasDeVida", max_length=400)


class ConexionOneDriveResponse(BaseModel):
    """
    Configuración actual. El secreto siempre viaja enmascarado (RNF10): la API
    nunca devuelve la credencial en claro.
    """

    configurado: bool = False
    tenant_id: Optional[str] = None
    client_id: Optional[str] = None
    client_secret_enmascarado: Optional[str] = None
    secreto_legible: bool = True
    drive_id: Optional[str] = None
    carpeta_cv: Optional[str] = None
    ultima_validacion: Optional[datetime] = None
    documentos_detectados: Optional[int] = None


class PruebaConexionResponse(BaseModel):
    """Resultado de "Probar conexión"."""

    exito: bool
    documentos_detectados: int = 0
    mensaje: str
    detalle: Optional[str] = None


class GuardarConexionResponse(BaseModel):
    guardado: bool
    prueba: PruebaConexionResponse
    configuracion: Optional[ConexionOneDriveResponse] = None
