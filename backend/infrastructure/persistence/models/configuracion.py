from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models._base import nuevo_id, utcnow


class ParametroRecomendacionModel(Base):
    """Parámetros del motor: pesos, umbrales, Top-N, modelo de IA (HU-07)."""

    __tablename__ = "parametros_recomendacion"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=nuevo_id)
    clave: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    valor: Mapped[str] = mapped_column(Text)
    descripcion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actualizado_por: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class RegistroBitacoraModel(Base):
    """Traza de auditoría de acciones relevantes (HU-06, RNF32)."""

    __tablename__ = "bitacora"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=nuevo_id)
    usuario_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    accion: Mapped[str] = mapped_column(String(60), index=True)
    entidad: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    entidad_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    detalle: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
