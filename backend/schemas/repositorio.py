from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from backend.schemas.onedrive import PruebaConexionResponse  # noqa: F401  (reexport)

TipoRepositorio = Literal["ONEDRIVE", "GDRIVE"]


class ConexionRepositorioRequest(BaseModel):
    """
    Datos de conexión al origen de hojas de vida (HU-05), sea cual sea el
    proveedor.

    `credenciales` es un diccionario cuya forma depende de `tipo`:

    - ONEDRIVE: tenant_id, client_id, client_secret, drive_id
    - GDRIVE:   credenciales_json (el archivo de la cuenta de servicio)

    Los campos secretos pueden omitirse o enviarse vacíos: se reutiliza el
    valor almacenado del mismo proveedor. Así se corrige la carpeta sin volver
    a escribir la credencial.
    """

    tipo: TipoRepositorio
    carpeta: str = Field(default="", max_length=400)
    credenciales: dict[str, str] = Field(default_factory=dict)


class ConexionRepositorioResponse(BaseModel):
    """
    Configuración actual. Los secretos siempre viajan enmascarados (RNF10): la
    API nunca devuelve la credencial en claro.
    """

    configurado: bool = False
    tipo: Optional[TipoRepositorio] = None
    carpeta: Optional[str] = None
    credenciales: dict[str, str] = Field(default_factory=dict)
    secreto_legible: bool = True
    ultima_validacion: Optional[datetime] = None
    documentos_detectados: Optional[int] = None


class GuardarRepositorioResponse(BaseModel):
    guardado: bool
    prueba: PruebaConexionResponse
    configuracion: Optional[ConexionRepositorioResponse] = None
