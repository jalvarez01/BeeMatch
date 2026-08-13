from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field

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


class UsuarioUpdate(BaseModel):
    rol: Optional[Rol] = None
    activo: Optional[bool] = None


class CambiarPasswordRequest(BaseModel):
    password_actual: str
    password_nueva: str = Field(min_length=8, max_length=128)