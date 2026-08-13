from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models._base import nuevo_id, utcnow

ESTADO_BORRADOR = "BORRADOR"
ESTADO_EN_ANALISIS = "EN_ANALISIS"
ESTADO_PROCESADA = "PROCESADA"
ESTADO_ERROR = "ERROR"


class SolicitudModel(Base):
    """Necesidad de staffing registrada por el reclutador. Agregado central."""

    __tablename__ = "solicitudes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=nuevo_id)
    descripcion_libre: Mapped[str] = mapped_column(Text, default="")
    rol_buscado: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    experiencia_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    estado: Mapped[str] = mapped_column(String(20), default=ESTADO_BORRADOR, index=True)

    cliente_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("clientes.id"), nullable=True)
    proyecto_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("proyectos.id"), nullable=True)
    usuario_id: Mapped[str] = mapped_column(String(36), ForeignKey("usuarios.id"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class CriterioModel(Base):
    """Requisito estructurado asociado a una solicitud."""

    __tablename__ = "criterios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=nuevo_id)
    solicitud_id: Mapped[str] = mapped_column(String(36), ForeignKey("solicitudes.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(20))  # TECNOLOGIA, FRAMEWORK, DOMINIO, CERTIFICACION, IDIOMA
    valor: Mapped[str] = mapped_column(String(120))
    obligatorio: Mapped[bool] = mapped_column(Boolean, default=False)
    peso: Mapped[float] = mapped_column(Float, default=1.0)
