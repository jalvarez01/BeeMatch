from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models._base import nuevo_id, utcnow

BUSQUEDA_EN_COLA = "EN_COLA"
BUSQUEDA_EJECUTANDO = "EJECUTANDO"
BUSQUEDA_COMPLETADA = "COMPLETADA"
BUSQUEDA_ERROR = "ERROR"

COINCIDENCIA_ENCONTRADO = "ENCONTRADO"
COINCIDENCIA_PARCIAL = "PARCIAL"
COINCIDENCIA_NO_EVIDENCIADO = "NO_EVIDENCIADO"


class BusquedaModel(Base):
    """Ejecución concreta del análisis para una solicitud (RD1)."""

    __tablename__ = "busquedas"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=nuevo_id)
    solicitud_id: Mapped[str] = mapped_column(String(36), ForeignKey("solicitudes.id"), index=True)
    estado: Mapped[str] = mapped_column(String(20), default=BUSQUEDA_EN_COLA)
    etapa: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    progreso: Mapped[int] = mapped_column(Integer, default=0)

    duracion_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cv_analizados: Mapped[int] = mapped_column(Integer, default=0)
    cv_no_procesables: Mapped[int] = mapped_column(Integer, default=0)
    modelo_ia: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    version_parametros: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    tokens_entrada: Mapped[int] = mapped_column(Integer, default=0)
    tokens_salida: Mapped[int] = mapped_column(Integer, default=0)
    mensaje_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RecomendacionModel(Base):
    """Resultado por candidato dentro de una búsqueda (RD2)."""

    __tablename__ = "recomendaciones"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=nuevo_id)
    busqueda_id: Mapped[str] = mapped_column(String(36), ForeignKey("busquedas.id"), index=True)
    candidato_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidatos.id"))
    puntaje_afinidad: Mapped[float] = mapped_column(Float, default=0.0)
    posicion: Mapped[int] = mapped_column(Integer, default=0)
    nivel: Mapped[str] = mapped_column(String(10), default="MEDIA")
    preseleccionado: Mapped[bool] = mapped_column(Boolean, default=False)
    resumen_ia: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class CoincidenciaModel(Base):
    """
    Desglose explicable de una recomendación, requisito por requisito.

    RD3: si el estado es ENCONTRADO o PARCIAL debe existir fragmento_id.
    RD4: NO_EVIDENCIADO significa que el documento no lo dice, nunca que la
    persona carece de la habilidad (RNF27).
    """

    __tablename__ = "coincidencias"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=nuevo_id)
    recomendacion_id: Mapped[str] = mapped_column(String(36), ForeignKey("recomendaciones.id"), index=True)
    criterio_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("criterios.id"), nullable=True)
    requisito: Mapped[str] = mapped_column(String(160))
    estado: Mapped[str] = mapped_column(String(20), default=COINCIDENCIA_NO_EVIDENCIADO)
    evidencia_texto: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fragmento_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("fragmentos_cv.id"), nullable=True)


class PreseleccionModel(Base):
    """Conjunto de candidatos marcados por el reclutador para enviar al cliente."""

    __tablename__ = "preselecciones"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=nuevo_id)
    busqueda_id: Mapped[str] = mapped_column(String(36), ForeignKey("busquedas.id"), index=True)
    usuario_id: Mapped[str] = mapped_column(String(36), ForeignKey("usuarios.id"))
    formato_exportacion: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
