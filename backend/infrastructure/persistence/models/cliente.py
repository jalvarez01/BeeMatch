from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models._base import nuevo_id, utcnow


class ClienteModel(Base):
    """Empresa cliente de Bee que solicita el recurso."""

    __tablename__ = "clientes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=nuevo_id)
    nombre: Mapped[str] = mapped_column(String(160), unique=True)
    sector: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProyectoModel(Base):
    """Iniciativa del cliente para la cual se requiere el perfil."""

    __tablename__ = "proyectos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=nuevo_id)
    nombre: Mapped[str] = mapped_column(String(160))
    cliente_id: Mapped[str] = mapped_column(String(36), ForeignKey("clientes.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
