"""
HU-16: una hoja de vida que se retira de la carpeta deja de recomendarse.

Cuando Bee saca un CV del repositorio suele ser porque la persona pidió no ser
considerada o porque el dato caducó. La sincronización tiene que olvidarlo, con
todo lo derivado, y no solo dejar de actualizarlo.

Nada sale a la red: el origen es un doble que devuelve la lista que se le pida.
"""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.infrastructure.persistence import models  # noqa: F401
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models.hoja_vida import (
    CandidatoHabilidadModel,
    CandidatoModel,
    FragmentoCVModel,
    HojaDeVidaModel,
)
from backend.infrastructure.persistence.repositories.candidato_repo import CandidatoRepository
from backend.infrastructure.persistence.repositories.hoja_vida_repo import HojaDeVidaRepository
from backend.infrastructure.repositorio.base import DocumentoRepositorio
from backend.infrastructure.repositorio.sync_service import SincronizacionService


@pytest.fixture()
def db():
    motor = create_engine("sqlite://")
    Base.metadata.create_all(bind=motor)
    sesion = sessionmaker(bind=motor)()
    yield sesion
    sesion.close()


class ClienteFalso:
    """Origen que devuelve la lista que se le indique, y el cursor que se le indique."""

    def __init__(self, documentos, cursor_devuelto=None):
        self.documentos = documentos
        self.cursor_devuelto = cursor_devuelto

    def listar_documentos(self, cursor=None):
        return self.documentos, self.cursor_devuelto


class ConfigRepoFalso:
    def __init__(self, cursor_guardado=None):
        self.cursor_guardado = cursor_guardado

    def get_activa(self):
        if self.cursor_guardado is None:
            return None
        return type("Config", (), {"cursor_sincronizacion": self.cursor_guardado})()

    def actualizar_cursor(self, cursor):
        self.cursor_guardado = cursor


class ConfigServiceFalso:
    def __init__(self, cliente):
        self.cliente = cliente

    def cliente_activo(self):
        return self.cliente


def _documento(nombre: str) -> DocumentoRepositorio:
    return DocumentoRepositorio(
        id_documento=nombre,
        nombre_archivo=nombre,
        ruta="",
        url_web=None,
        formato="PDF",
        hash_contenido="hash-" + nombre,
        fecha_modificacion=datetime(2026, 9, 1),
        tamanio=10,
    )


def _sincronizador(db, documentos, cursor_guardado=None, cursor_devuelto=None):
    servicio = SincronizacionService.__new__(SincronizacionService)
    servicio.db = db
    servicio.repo = HojaDeVidaRepository(db)
    servicio.config_repo = ConfigRepoFalso(cursor_guardado)
    servicio.config_service = ConfigServiceFalso(ClienteFalso(documentos, cursor_devuelto))
    return servicio


def _indexar_a_mano(db, id_documento: str) -> str:
    """Deja la hoja como si ya se hubiera analizado: fragmentos, candidato y habilidad."""
    hojas = HojaDeVidaRepository(db)
    candidatos = CandidatoRepository(db)
    hoja = hojas.get_by_id_documento(id_documento)
    candidatos.reemplazar_fragmentos(hoja.id, [{"orden": 0, "texto": "Java y Spring Boot"}])
    candidato = candidatos.crear_o_reemplazar(hoja.id, {"nombre": id_documento})
    candidatos.reemplazar_habilidades(candidato.id, [{"nombre": "Java " + id_documento}])
    hojas.marcar_indexada(hoja.id)
    return hoja.id


def test_una_hoja_que_ya_no_esta_en_el_origen_se_da_de_baja(db):
    servicio = _sincronizador(db, [_documento("a.pdf"), _documento("b.pdf")])
    servicio.sincronizar()
    _indexar_a_mano(db, "a.pdf")
    _indexar_a_mano(db, "b.pdf")

    # "b.pdf" se borró de la carpeta.
    servicio.config_service.cliente.documentos = [_documento("a.pdf")]
    resultado = servicio.sincronizar()

    assert resultado["hojas_eliminadas"] == 1
    hojas = HojaDeVidaRepository(db)
    assert hojas.get_by_id_documento("b.pdf") is None
    assert hojas.get_by_id_documento("a.pdf") is not None


def test_al_darla_de_baja_no_queda_nada_derivado(db):
    """RNF16: fragmentos, candidato y habilidades se van con la hoja."""
    servicio = _sincronizador(db, [_documento("a.pdf"), _documento("b.pdf")])
    servicio.sincronizar()
    id_a = _indexar_a_mano(db, "a.pdf")
    id_b = _indexar_a_mano(db, "b.pdf")
    candidato_b = CandidatoRepository(db).get_by_hoja(id_b).id

    servicio.config_service.cliente.documentos = [_documento("a.pdf")]
    servicio.sincronizar()

    assert db.query(FragmentoCVModel).filter_by(hoja_de_vida_id=id_b).count() == 0
    assert db.query(CandidatoModel).filter_by(hoja_de_vida_id=id_b).count() == 0
    assert db.query(CandidatoHabilidadModel).filter_by(candidato_id=candidato_b).count() == 0
    # Lo del que sigue en la carpeta queda intacto.
    assert db.query(FragmentoCVModel).filter_by(hoja_de_vida_id=id_a).count() == 1
    assert db.query(CandidatoModel).filter_by(hoja_de_vida_id=id_a).count() == 1


def test_un_listado_vacio_no_borra_el_repositorio(db):
    """
    Salvaguarda: que el origen no devuelva nada se parece más a una carpeta mal
    configurada o a una falla del proveedor que a 30 borrados simultáneos.
    """
    servicio = _sincronizador(db, [_documento("a.pdf"), _documento("b.pdf")])
    servicio.sincronizar()

    servicio.config_service.cliente.documentos = []
    resultado = servicio.sincronizar()

    assert resultado["hojas_eliminadas"] == 0
    assert db.query(HojaDeVidaModel).count() == 2


def test_un_listado_incremental_no_borra_lo_que_no_vino(db):
    """
    Salvaguarda: con cursor previo (el delta link de OneDrive) el origen devuelve
    solo lo que cambió. Lo ausente no es lo borrado, es lo que sigue igual.
    """
    servicio = _sincronizador(db, [_documento("a.pdf"), _documento("b.pdf")])
    servicio.sincronizar()

    servicio.config_repo.cursor_guardado = "delta-anterior"
    servicio.config_service.cliente.documentos = [_documento("a.pdf")]
    resultado = servicio.sincronizar()

    assert resultado["hojas_eliminadas"] == 0
    assert HojaDeVidaRepository(db).get_by_id_documento("b.pdf") is not None
