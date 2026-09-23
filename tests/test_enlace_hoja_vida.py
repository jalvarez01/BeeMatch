"""
El botón "Ver CV" tiene que abrir el documento en el repositorio.

RNF14: BeeMatch no copia el archivo, solo guarda su referencia. El enlace del
origen es entonces la única forma que tiene el reclutador de leer la hoja de
vida completa, así que la respuesta del API lo tiene que traer tanto en el
detalle del candidato como en el listado.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.domain.services.candidato_service import CandidatoService
from backend.infrastructure.persistence import models  # noqa: F401
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models.hoja_vida import HojaDeVidaModel
from backend.infrastructure.persistence.repositories.candidato_repo import CandidatoRepository

URL = "https://drive.google.com/file/d/1SpJ9uZ3tzt/view?usp=drivesdk"


@pytest.fixture()
def db():
    motor = create_engine("sqlite://")
    Base.metadata.create_all(bind=motor)
    sesion = sessionmaker(bind=motor)()
    yield sesion
    sesion.close()


def _candidato(db, nombre: str, url: str | None = URL) -> str:
    hoja = HojaDeVidaModel(
        id_documento="doc-" + nombre,
        nombre_archivo=f"{nombre}.pdf",
        ruta="carpeta",
        url_web=url,
        formato="PDF",
    )
    db.add(hoja)
    db.commit()
    return CandidatoRepository(db).crear_o_reemplazar(hoja.id, {"nombre": nombre}).id


def test_el_listado_trae_el_enlace_al_documento(db):
    _candidato(db, "Ana")

    (candidato,) = CandidatoService(db).listar()

    assert candidato.url_hoja_vida == URL
    assert candidato.nombre_archivo == "Ana.pdf"
    assert candidato.ruta_hoja_vida == "carpeta/Ana.pdf"


def test_el_detalle_y_el_listado_dicen_lo_mismo(db):
    candidato_id = _candidato(db, "Ana")

    (del_listado,) = CandidatoService(db).listar()
    del_detalle = CandidatoService(db).obtener(candidato_id)

    assert del_listado.url_hoja_vida == del_detalle.url_hoja_vida
    assert del_listado.ruta_hoja_vida == del_detalle.ruta_hoja_vida


def test_un_documento_sin_enlace_no_inventa_uno(db):
    """El origen puede no exponer enlace; la interfaz muestra el botón apagado."""
    _candidato(db, "Ana", url=None)

    (candidato,) = CandidatoService(db).listar()

    assert candidato.url_hoja_vida is None
    assert candidato.nombre_archivo == "Ana.pdf"


def test_el_listado_no_consulta_una_hoja_por_candidato(db):
    """
    Con una consulta por candidato, una página de 20 haría 21 viajes a la base.
    Se piden todas juntas.
    """
    for nombre in ("Ana", "Beto", "Carla"):
        _candidato(db, nombre)

    servicio = CandidatoService(db)
    consultas = []
    original = servicio.hojas.listar_por_ids
    servicio.hojas.listar_por_ids = lambda ids: consultas.append(ids) or original(ids)

    candidatos = servicio.listar()

    assert len(candidatos) == 3
    assert len(consultas) == 1 and len(consultas[0]) == 3
