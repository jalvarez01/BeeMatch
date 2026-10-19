"""HU-17, criterio 4: al finalizar se indica cuántos documentos se analizaron y cuántos no."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.hojas_vida import resumen_de_analisis, router
from backend.infrastructure.persistence import models  # noqa: F401
from backend.infrastructure.persistence.database import Base, get_db
from backend.infrastructure.persistence.models.hoja_vida import (
    ESTADO_INDEXADA,
    ESTADO_NO_PROCESABLE,
    ESTADO_PENDIENTE,
    HojaDeVidaModel,
)
from backend.security import get_current_user


@pytest.fixture()
def cliente():
    motor = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=motor)
    Sesion = sessionmaker(bind=motor)

    app = FastAPI()
    app.include_router(router, prefix="/hojas-vida")

    def _db():
        sesion = Sesion()
        try:
            yield sesion
        finally:
            sesion.close()

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: object()

    def cargar(*hojas: tuple[str, str, str | None]):
        with Sesion() as sesion:
            for nombre, estado, motivo in hojas:
                sesion.add(
                    HojaDeVidaModel(
                        id_documento=nombre,
                        nombre_archivo=nombre,
                        formato="PDF",
                        estado_procesamiento=estado,
                        motivo_error=motivo,
                    )
                )
            sesion.commit()

    http = TestClient(app)
    http.cargar = cargar
    return http


def test_mientras_quedan_pendientes_sigue_en_proceso_y_sin_resumen(cliente):
    cliente.cargar(("a.pdf", ESTADO_INDEXADA, None), ("b.pdf", ESTADO_PENDIENTE, None))

    estado = cliente.get("/hojas-vida/estado").json()

    assert estado["en_proceso"] is True
    assert estado["resumen"] is None


def test_al_terminar_informa_analizados_y_no_procesados(cliente):
    cliente.cargar(
        ("a.pdf", ESTADO_INDEXADA, None),
        ("b.docx", ESTADO_INDEXADA, None),
        ("c.pdf", ESTADO_NO_PROCESABLE, "PDF protegido con contraseña."),
    )

    estado = cliente.get("/hojas-vida/estado").json()

    assert estado["en_proceso"] is False
    assert (estado["indexadas"], estado["no_procesables"]) == (2, 1)
    assert estado["resumen"] == (
        "Análisis finalizado: 2 documentos fueron analizados y 1 no pudo procesarse."
    )


def test_sin_documentos_no_hay_resumen(cliente):
    estado = cliente.get("/hojas-vida/estado").json()

    assert estado["en_proceso"] is False
    assert estado["resumen"] is None


def test_lista_de_no_procesables_trae_el_motivo(cliente):
    cliente.cargar(
        ("ok.pdf", ESTADO_INDEXADA, None),
        ("clave.pdf", ESTADO_NO_PROCESABLE, "PDF protegido con contraseña."),
        ("roto.docx", ESTADO_NO_PROCESABLE, "DOCX dañado o ilegible: File is not a zip file"),
    )

    filas = cliente.get("/hojas-vida/no-procesables").json()

    assert [f["nombre_archivo"] for f in filas] == ["clave.pdf", "roto.docx"]
    assert "contraseña" in filas[0]["motivo_error"]
    assert "dañado" in filas[1]["motivo_error"]


def test_singular_y_plural_del_resumen():
    assert resumen_de_analisis(1, 0) == (
        "Análisis finalizado: 1 documento fue analizado y 0 no pudieron procesarse."
    )
    assert resumen_de_analisis(0, 1) == (
        "Análisis finalizado: 0 documentos fueron analizados y 1 no pudo procesarse."
    )
