from pydantic import BaseModel


class ClienteResponse(BaseModel):
    """HU-12: cliente registrado, para las sugerencias y el filtro del historial."""

    id: str
    nombre: str

    model_config = {"from_attributes": True}
