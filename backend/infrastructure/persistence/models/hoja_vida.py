from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.config import EMBEDDING_DIMENSIONES, USA_PGVECTOR
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models._base import nuevo_id, utcnow

ESTADO_PENDIENTE = "PENDIENTE"
ESTADO_INDEXADA = "INDEXADA"
ESTADO_NO_PROCESABLE = "NO_PROCESABLE"

# pgvector en producción; en SQLite se guarda el vector serializado como texto.
if USA_PGVECTOR:  # pragma: no cover
    from pgvector.sqlalchemy import Vector

    TipoEmbedding = Vector(EMBEDDING_DIMENSIONES)
else:
    TipoEmbedding = Text


class HojaDeVidaModel(Base):
    """
    Documento del repositorio de OneDrive.

    RNF14: no se copia el archivo. Se guarda su referencia y el texto extraído.
    """

    __tablename__ = "hojas_de_vida"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=nuevo_id)
    id_onedrive: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    nombre_archivo: Mapped[str] = mapped_column(String(300))
    ruta: Mapped[str] = mapped_column(String(600), default="")
    url_web: Mapped[Optional[str]] = mapped_column(String(900), nullable=True)
    formato: Mapped[str] = mapped_column(String(10), default="PDF")
    hash_contenido: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    fecha_modificacion: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    estado_procesamiento: Mapped[str] = mapped_column(String(20), default=ESTADO_PENDIENTE, index=True)
    motivo_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    indexada_en: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CandidatoModel(Base):
    """Perfil estructurado extraído de una hoja de vida."""

    __tablename__ = "candidatos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=nuevo_id)
    hoja_de_vida_id: Mapped[str] = mapped_column(String(36), ForeignKey("hojas_de_vida.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(160))
    rol_principal: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    anios_experiencia: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ubicacion: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    idiomas: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    resumen: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class HabilidadModel(Base):
    """Tecnología, framework, dominio o certificación normalizada."""

    __tablename__ = "habilidades"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=nuevo_id)
    nombre: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    categoria: Mapped[str] = mapped_column(String(30), default="TECNOLOGIA")
    alias: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class CandidatoHabilidadModel(Base):
    """Relación candidato-habilidad con la evidencia que la sustenta (RNF28)."""

    __tablename__ = "candidato_habilidades"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=nuevo_id)
    candidato_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidatos.id"), index=True)
    habilidad_id: Mapped[str] = mapped_column(String(36), ForeignKey("habilidades.id"))
    anios_experiencia: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    evidencia_texto: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fragmento_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)


class FragmentoCVModel(Base):
    """
    Porción de texto del CV con su embedding. Unidad de recuperación del motor
    de matching y ancla de evidencia de toda explicación (RNF28).
    """

    __tablename__ = "fragmentos_cv"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=nuevo_id)
    hoja_de_vida_id: Mapped[str] = mapped_column(String(36), ForeignKey("hojas_de_vida.id"), index=True)
    orden: Mapped[int] = mapped_column(Integer, default=0)
    pagina: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    texto: Mapped[str] = mapped_column(Text)
    embedding = mapped_column(TipoEmbedding, nullable=True)
