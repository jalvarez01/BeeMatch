from pydantic import BaseModel, Field


class ClienteResponse(BaseModel):
    """HU-12: cliente registrado, para el selector del formulario y el filtro del historial."""

    id: str
    nombre: str

    model_config = {"from_attributes": True}


class ClienteCreate(BaseModel):
    """La superadministradora registra a un cliente."""

    nombre: str = Field(min_length=2, max_length=160)


class ClienteUpdate(BaseModel):
    nombre: str = Field(min_length=2, max_length=160)
