"""HU-17: ningún documento se queda sin analizar por una cola caída o una corrida interrumpida."""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.domain.services.indexacion_service import IndexacionService
from backend.infrastructure.persistence import models  # noqa: F401
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models.hoja_vida import (
    ESTADO_INDEXADA,
    ESTADO_PENDIENTE,
    HojaDeVidaModel,
)
from backend.infrastructure.persistence.repositories.candidato_repo import CandidatoRepository
from backend.infrastructure.persistence.repositories.hoja_vida_repo import HojaDeVidaRepository
from backend.infrastructure.repositorio.base import DocumentoRepositorio
from backend.infrastructure.repositorio.sync_service import SincronizacionService
from backend.workers import queue as cola_modulo


@pytest.fixture()
def db():
    motor = create_engine("sqlite://")
    Base.metadata.create_all(bind=motor)
    sesion = sessionmaker(bind=motor)()
    yield sesion
    sesion.close()


# --- Cola: sin Redis se ejecuta en línea ---------------------------------------


def test_sin_redis_la_tarea_se_ejecuta_en_linea(monkeypatch):
    monkeypatch.setattr(cola_modulo, "_cola", None)
    monkeypatch.setattr(cola_modulo, "REDIS_URL", "redis://127.0.0.1:1/0")  # nadie escucha aquí
    ejecutadas = []

    resultado = cola_modulo.encolar(ejecutadas.append, "hoja-1")

    assert ejecutadas == ["hoja-1"]
    assert resultado is None  # None = se ejecutó directo, no se encoló


# --- Sincronización: los PENDIENTES se reintentan --------------------------------


class ClienteFalso:
    def __init__(self, documentos):
        self.documentos = documentos

    def listar_documentos(self, cursor=None):
        return self.documentos, None


class ConfigRepoFalso:
    def get_activa(self):
        return None

    def actualizar_cursor(self, cursor):
        pass


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
        fecha_modificacion=datetime(2026, 9, 1),  # naive: así la devuelve SQLite
        tamanio=10,
    )


def _sincronizador(db, documentos) -> SincronizacionService:
    servicio = SincronizacionService.__new__(SincronizacionService)
    servicio.db = db
    servicio.repo = HojaDeVidaRepository(db)
    servicio.config_repo = ConfigRepoFalso()
    servicio.config_service = ConfigServiceFalso(ClienteFalso(documentos))
    return servicio


def test_documento_pendiente_sin_cambios_se_vuelve_a_encolar(db):
    documentos = [_documento("a.pdf"), _documento("b.pdf")]
    servicio = _sincronizador(db, documentos)

    primera = servicio.sincronizar()
    assert len(primera["hojas_a_indexar"]) == 2

    # La cola falló: "a.pdf" nunca se indexó. "b.pdf" sí.
    hojas = HojaDeVidaRepository(db)
    hojas.marcar_indexada(hojas.get_by_id_documento("b.pdf").id)

    segunda = servicio.sincronizar()  # mismos archivos, sin cambios

    ids_reintentados = segunda["hojas_a_indexar"]
    assert ids_reintentados == [hojas.get_by_id_documento("a.pdf").id]


def test_documento_ya_indexado_y_sin_cambios_no_se_encola(db):
    servicio = _sincronizador(db, [_documento("a.pdf")])
    servicio.sincronizar()
    hojas = HojaDeVidaRepository(db)
    hojas.marcar_indexada(hojas.get_by_id_documento("a.pdf").id)

    assert servicio.sincronizar()["hojas_a_indexar"] == []


# --- Indexación: un trabajo repetido no rehace lo que ya está hecho --------------


class RepositorioQueNoDebeUsarse:
    def descargar(self, id_documento):
        raise AssertionError("No debía descargar una hoja ya indexada")


def test_indexar_una_hoja_ya_indexada_no_repite_el_trabajo(db):
    hoja = HojaDeVidaModel(
        id_documento="x", nombre_archivo="x.pdf", formato="PDF", estado_procesamiento=ESTADO_INDEXADA
    )
    db.add(hoja)
    db.commit()
    servicio = IndexacionService.__new__(IndexacionService)
    servicio.db = db
    servicio.hojas = HojaDeVidaRepository(db)
    servicio.candidatos = CandidatoRepository(db)
    servicio.repositorio = RepositorioQueNoDebeUsarse()

    assert servicio.indexar_hoja(hoja.id) is True
