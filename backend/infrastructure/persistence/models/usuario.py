from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models._base import nuevo_id, utcnow


class UsuarioModel(Base):
    """
    Usuario del área de Talento Humano.

    `password_hash` guarda el resultado de PBKDF2-SHA256 con salt: nunca la
    contraseña en claro. Es opcional porque los usuarios federados con
    Microsoft Entra ID no tienen contraseña local (RNF07).
    """

    __tablename__ = "usuarios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=nuevo_id)
    nombre: Mapped[str] = mapped_column(String(160))
    correo: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    id_entra: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    rol: Mapped[str] = mapped_column(String(20), default="COORDINADOR")
    activo: Mapped[bool] = mapped_column(Boolean, default=True)

    # Obliga a cambiar la contraseña sembrada en el primer ingreso.
    debe_cambiar_password: Mapped[bool] = mapped_column(Boolean, default=False)

    ultimo_acceso: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)