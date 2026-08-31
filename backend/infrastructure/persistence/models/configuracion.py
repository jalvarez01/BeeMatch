from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models._base import nuevo_id, utcnow


class ConfiguracionOneDriveModel(Base):
    """
    Conexión al repositorio corporativo de hojas de vida (HU-05).

    Solo existe un registro activo a la vez. El client secret se guarda cifrado
    (RNF10) y nunca se devuelve en claro por la API: la interfaz solo recibe una
    versión enmascarada.

    La ruta configurada aquí es el origen que usan la sincronización y, por
    consiguiente, todas las búsquedas de los usuarios.
    """

    __tablename__ = "configuracion_onedrive"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=nuevo_id)

    tenant_id: Mapped[str] = mapped_column(String(100))
    client_id: Mapped[str] = mapped_column(String(100))
    client_secret_cifrado: Mapped[str] = mapped_column(Text)
    drive_id: Mapped[str] = mapped_column(String(200))
    carpeta_cv: Mapped[str] = mapped_column(String(400), default="/HojasDeVida")

    activa: Mapped[bool] = mapped_column(Boolean, default=True)

    # Resultado de la última validación exitosa ("Probar conexión").
    ultima_validacion: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    documentos_detectados: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Token delta de Microsoft Graph: permite sincronizar solo lo que cambió (RD5).
    delta_link: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    actualizado_por: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


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
