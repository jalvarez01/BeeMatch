from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models._base import nuevo_id, utcnow


class ConfiguracionRepositorioModel(Base):
    """
    Conexión al repositorio de hojas de vida (HU-05).

    Reemplaza a la antigua `configuracion_onedrive`: el origen dejó de ser
    forzosamente OneDrive, así que los datos propios de cada proveedor viven en
    un JSON cifrado (RNF10) en lugar de columnas sueltas. Lo común —el tipo, la
    carpeta, el cursor y el resultado de la última validación— sí son columnas.

    Solo existe un registro activo a la vez. Las credenciales nunca se
    devuelven en claro por la API: la interfaz recibe una versión enmascarada.

    La ruta configurada aquí es el origen que usan la sincronización y, por
    consiguiente, todas las búsquedas de los usuarios.
    """

    __tablename__ = "configuracion_repositorio"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=nuevo_id)

    # ONEDRIVE | GDRIVE (ver backend.infrastructure.repositorio.base).
    tipo: Mapped[str] = mapped_column(String(20), default="ONEDRIVE")

    # Carpeta de hojas de vida: ruta en OneDrive, folder id en Google Drive.
    carpeta: Mapped[str] = mapped_column(String(400), default="")

    # JSON cifrado con los datos propios del proveedor. OneDrive guarda aquí
    # tenant_id, client_id, client_secret y drive_id; Google Drive, el JSON de
    # la cuenta de servicio.
    credenciales_cifradas: Mapped[str] = mapped_column(Text)

    activa: Mapped[bool] = mapped_column(Boolean, default=True)

    # Resultado de la última validación exitosa ("Probar conexión").
    ultima_validacion: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    documentos_detectados: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Cursor opaco para sincronizar solo lo que cambió (RD5): delta link en
    # Microsoft Graph. Google Drive no ofrece delta por carpeta y lo deja nulo.
    cursor_sincronizacion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

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
