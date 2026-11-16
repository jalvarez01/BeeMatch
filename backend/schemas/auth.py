import re
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from backend.config import DOMINIO_CORREO

# Los correos de Bee son nombre.apellido@beeconsultoria.com: letras y números en
# minúscula, separados por un punto.
_PARTE_LOCAL = re.compile(r"^[a-z0-9]+\.[a-z0-9]+$")


def validar_correo_corporativo(valor: str) -> str:
    """HU-03: el correo debe ser nombre.apellido@<dominio corporativo>."""
    correo = str(valor).strip().lower()
    local, _, dominio = correo.rpartition("@")
    if dominio != DOMINIO_CORREO or not _PARTE_LOCAL.match(local):
        raise ValueError(f"El correo debe tener la forma nombre.apellido@{DOMINIO_CORREO}.")
    return correo

# SUPERADMINISTRADOR no se asigna desde la API: solo la siembra lo crea.
Rol = Literal["COORDINADOR", "DIRECTOR", "ADMINISTRADOR"]


class LoginRequest(BaseModel):
    correo: EmailStr
    password: str = Field(min_length=1)


class UsuarioResponse(BaseModel):
    id: str
    nombre: str
    correo: str
    rol: str
    activo: bool
    pendiente: bool = False
    debe_cambiar_password: bool = False

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioResponse


class UsuarioCreate(BaseModel):
    """El administrador crea la cuenta con una contraseña inicial (HU-03)."""

    nombre: str = Field(min_length=2, max_length=160)
    correo: EmailStr
    password: str = Field(min_length=8, max_length=128)
    rol: Rol = "COORDINADOR"
    id_entra: Optional[str] = None

    @field_validator("correo")
    @classmethod
    def validar_correo(cls, valor: EmailStr) -> str:
        return validar_correo_corporativo(valor)


class UsuarioUpdate(BaseModel):
    """Edición, activación e inactivación de una cuenta."""

    nombre: Optional[str] = Field(default=None, min_length=2, max_length=160)
    correo: Optional[EmailStr] = None
    rol: Optional[Rol] = None
    activo: Optional[bool] = None

    @field_validator("correo")
    @classmethod
    def validar_correo(cls, valor: Optional[EmailStr]) -> Optional[str]:
        return None if valor is None else validar_correo_corporativo(valor)


class CambiarPasswordRequest(BaseModel):
    password_actual: str
    password_nueva: str = Field(min_length=8, max_length=128)
