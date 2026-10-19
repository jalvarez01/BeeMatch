"""
HU-21: consulta de la ubicación de la hoja de vida.

Criterios de aceptación:

    1. El detalle del candidato muestra la ruta del archivo y el nombre del
       documento.
    2. Al seleccionar el enlace, la hoja de vida se abre en una nueva pestaña.
    3. Si el documento fue movido o eliminado, se indica que el archivo no está
       disponible.

El criterio 2 (target="_blank") es de interfaz y se verifica a mano en
Candidato. Aquí se prueba lo que decide si el enlace se ofrece o no: la
consulta al origen y la respuesta del API. Nada sale a la red: Google Drive se
sustituye por un doble de httpx.get.
"""

from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.domain.services import hoja_vida_service
from backend.domain.services.hoja_vida_service import (
    ENLACE_INVALIDO,
    MENSAJE_ENLACE_INVALIDO,
    MENSAJE_NO_DISPONIBLE,
    MENSAJE_NO_VERIFICABLE,
    HojaDeVidaService,
)
from backend.infrastructure.gdrive import drive_client
from backend.infrastructure.gdrive.drive_client import GoogleDriveClient
from backend.infrastructure.persistence import models  # noqa: F401
from backend.infrastructure.persistence.database import Base, get_db
from backend.infrastructure.persistence.models.busqueda import RecomendacionModel
from backend.infrastructure.persistence.models.hoja_vida import CandidatoModel, HojaDeVidaModel
from backend.infrastructure.repositorio.base import (
    DOC_DISPONIBLE,
    DOC_ELIMINADO,
    DOC_MOVIDO,
    DOC_NO_VERIFICABLE,
    CredencialesInvalidasError,
    EstadoDocumento,
    RepositorioDocumentos,
    RepositorioError,
)
from backend.main import app
from backend.security import get_current_user

CARPETA = "carpeta-cvs"
URL = "https://drive.google.com/file/d/abc123/view"


# --- Doble de Google Drive ---------------------------------------------------


class RespuestaFalsa:
    def __init__(self, status_code=200, cuerpo=None):
        self.status_code = status_code
        self._cuerpo = cuerpo or {}

    def json(self):
        return self._cuerpo


def cliente_drive(monkeypatch, documento, carpeta=None):
    """
    Cliente de Drive cuyas respuestas son las indicadas.

    `documento` responde a la consulta del archivo y `carpeta` a la del nombre
    de la carpeta configurada. Cualquiera puede ser una excepción de httpx.
    """
    carpeta = carpeta if carpeta is not None else RespuestaFalsa(200, {"name": "Hojas de vida"})

    def get(url, params=None, headers=None, timeout=None, **kwargs):
        respuesta = carpeta if url.endswith(f"/files/{CARPETA}") else documento
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta

    monkeypatch.setattr(drive_client.httpx, "get", get)
    cliente = GoogleDriveClient("{}", CARPETA)
    monkeypatch.setattr(cliente, "_headers", lambda: {})
    return cliente


# --- Consulta a Google Drive -------------------------------------------------


def test_un_archivo_en_la_carpeta_esta_disponible_y_trae_el_nombre_de_la_carpeta(monkeypatch):
    cliente = cliente_drive(
        monkeypatch, RespuestaFalsa(200, {"id": "abc", "trashed": False, "parents": [CARPETA]})
    )

    estado = cliente.consultar_documento("abc")

    assert estado.estado == DOC_DISPONIBLE
    assert estado.ruta_legible == "Hojas de vida"


def test_un_archivo_que_ya_no_existe_esta_eliminado(monkeypatch):
    cliente = cliente_drive(monkeypatch, RespuestaFalsa(404))

    assert cliente.consultar_documento("abc").estado == DOC_ELIMINADO


def test_un_archivo_en_la_papelera_esta_eliminado(monkeypatch):
    cliente = cliente_drive(
        monkeypatch, RespuestaFalsa(200, {"id": "abc", "trashed": True, "parents": [CARPETA]})
    )

    assert cliente.consultar_documento("abc").estado == DOC_ELIMINADO


def test_un_archivo_que_salio_de_la_carpeta_pero_sigue_accesible_esta_movido(monkeypatch):
    cliente = cliente_drive(
        monkeypatch, RespuestaFalsa(200, {"id": "abc", "trashed": False, "parents": ["otra"]})
    )

    assert cliente.consultar_documento("abc").estado == DOC_MOVIDO


def test_sin_el_campo_parents_no_se_inventa_un_movimiento(monkeypatch):
    cliente = cliente_drive(monkeypatch, RespuestaFalsa(200, {"id": "abc", "trashed": False}))

    assert cliente.consultar_documento("abc").estado == DOC_DISPONIBLE


def test_si_no_se_puede_leer_la_carpeta_el_archivo_sigue_disponible(monkeypatch):
    cliente = cliente_drive(
        monkeypatch,
        RespuestaFalsa(200, {"id": "abc", "trashed": False, "parents": [CARPETA]}),
        carpeta=RespuestaFalsa(500),
    )

    estado = cliente.consultar_documento("abc")

    assert estado.estado == DOC_DISPONIBLE
    assert estado.ruta_legible is None


@pytest.mark.parametrize("respuesta", [RespuestaFalsa(500), RespuestaFalsa(403)])
def test_un_error_de_google_no_se_toma_por_archivo_eliminado(monkeypatch, respuesta):
    cliente = cliente_drive(monkeypatch, respuesta)

    with pytest.raises(RepositorioError):
        cliente.consultar_documento("abc")


def test_una_credencial_rechazada_no_se_toma_por_archivo_eliminado(monkeypatch):
    cliente = cliente_drive(monkeypatch, RespuestaFalsa(401))

    with pytest.raises(CredencialesInvalidasError):
        cliente.consultar_documento("abc")


def test_una_caida_de_red_no_se_toma_por_archivo_eliminado(monkeypatch):
    cliente = cliente_drive(monkeypatch, httpx.ConnectError("sin red"))

    with pytest.raises(RepositorioError):
        cliente.consultar_documento("abc")


def test_un_origen_que_no_sabe_consultar_responde_no_verificable():
    class OrigenSinConsulta(RepositorioDocumentos):
        def probar_conexion(self):
            raise NotImplementedError

        def listar_documentos(self, cursor=None):
            return [], None

        def descargar(self, id_documento):
            return b""

    assert OrigenSinConsulta().consultar_documento("x").estado == DOC_NO_VERIFICABLE


# --- Servicio ---------------------------------------------------------------


class ClienteFalso:
    """Origen que responde lo indicado, o lanza lo indicado."""

    def __init__(self, respuesta):
        self.respuesta = respuesta
        self.consultas = []

    def consultar_documento(self, id_documento):
        self.consultas.append(id_documento)
        if isinstance(self.respuesta, Exception):
            raise self.respuesta
        return self.respuesta


def hoja(url=URL, ruta=CARPETA):
    return SimpleNamespace(
        id="hoja-1",
        id_documento="abc",
        nombre_archivo="Ana.pdf",
        ruta=ruta,
        url_web=url,
    )


def servicio_con(monkeypatch, respuesta):
    cliente = ClienteFalso(respuesta)
    servicio = HojaDeVidaService(db=None)
    monkeypatch.setattr(servicio.config, "cliente_activo", lambda: cliente)
    return servicio, cliente


def test_disponible_muestra_nombre_ruta_legible_y_enlace(monkeypatch):
    servicio, _ = servicio_con(
        monkeypatch, EstadoDocumento(estado=DOC_DISPONIBLE, ruta_legible="Hojas de vida")
    )

    resultado = servicio.disponibilidad(hoja())

    assert resultado.estado == DOC_DISPONIBLE
    assert resultado.disponible is True
    assert resultado.mensaje is None
    assert resultado.nombre_archivo == "Ana.pdf"
    assert resultado.ruta == "Hojas de vida/Ana.pdf"
    assert resultado.url == URL


def test_la_ruta_nunca_muestra_el_id_de_la_carpeta_de_drive(monkeypatch):
    """En Drive `ruta` guarda el ID de la carpeta; no le dice nada a nadie."""
    servicio, _ = servicio_con(monkeypatch, EstadoDocumento(estado=DOC_DISPONIBLE))

    resultado = servicio.disponibilidad(hoja(ruta="1AbCdEfGhIjKlMnOp"))

    assert resultado.ruta == "Ana.pdf"
    assert "1AbCdEfGhIjKlMnOp" not in resultado.ruta


@pytest.mark.parametrize("estado", [DOC_MOVIDO, DOC_ELIMINADO])
def test_movido_o_eliminado_dice_que_no_esta_disponible_y_no_ofrece_enlace(monkeypatch, estado):
    servicio, _ = servicio_con(monkeypatch, EstadoDocumento(estado=estado))

    resultado = servicio.disponibilidad(hoja())

    assert resultado.estado == estado
    assert resultado.disponible is False
    assert resultado.mensaje == MENSAJE_NO_DISPONIBLE
    assert resultado.url is None
    assert resultado.nombre_archivo == "Ana.pdf"


@pytest.mark.parametrize("url", [None, "", "javascript:alert(1)", "ftp://servidor/cv.pdf", "no es un enlace"])
def test_un_enlace_invalido_no_se_ofrece_ni_se_consulta_al_origen(monkeypatch, url):
    servicio, cliente = servicio_con(monkeypatch, EstadoDocumento(estado=DOC_DISPONIBLE))

    resultado = servicio.disponibilidad(hoja(url=url))

    assert resultado.estado == ENLACE_INVALIDO
    assert resultado.disponible is False
    assert resultado.mensaje == MENSAJE_ENLACE_INVALIDO
    assert resultado.url is None
    assert cliente.consultas == []


def test_si_el_origen_falla_no_se_dice_que_el_archivo_desaparecio(monkeypatch):
    servicio, _ = servicio_con(monkeypatch, RepositorioError("Google no responde"))

    resultado = servicio.disponibilidad(hoja())

    assert resultado.estado == DOC_NO_VERIFICABLE
    assert resultado.disponible is True
    assert resultado.mensaje == MENSAJE_NO_VERIFICABLE
    assert resultado.url == URL


def test_sin_repositorio_configurado_tampoco_se_bloquea_el_enlace(monkeypatch):
    servicio = HojaDeVidaService(db=None)

    def sin_configuracion():
        raise hoja_vida_service.RepositorioNoConfiguradoError("sin configurar")

    monkeypatch.setattr(servicio.config, "cliente_activo", sin_configuracion)

    resultado = servicio.disponibilidad(hoja())

    assert resultado.estado == DOC_NO_VERIFICABLE
    assert resultado.disponible is True


# --- API --------------------------------------------------------------------


@pytest.fixture()
def api(monkeypatch):
    motor = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=motor)
    Sesion = sessionmaker(bind=motor)
    db = Sesion()

    def get_db_de_prueba():
        yield db

    app.dependency_overrides[get_db] = get_db_de_prueba
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="usuario-1")
    yield TestClient(app), db
    app.dependency_overrides.clear()
    db.close()


def recomendacion(db, url=URL) -> str:
    hoja_db = HojaDeVidaModel(
        id_documento="abc",
        nombre_archivo="Ana.pdf",
        ruta=CARPETA,
        url_web=url,
        formato="PDF",
    )
    db.add(hoja_db)
    db.commit()
    candidato = CandidatoModel(hoja_de_vida_id=hoja_db.id, nombre="Ana")
    db.add(candidato)
    db.commit()
    rec = RecomendacionModel(busqueda_id="busqueda-1", candidato_id=candidato.id)
    db.add(rec)
    db.commit()
    return rec.id


def origen(monkeypatch, respuesta):
    cliente = ClienteFalso(respuesta)
    monkeypatch.setattr(
        hoja_vida_service.RepositorioConfigService, "cliente_activo", lambda self: cliente
    )


def test_el_api_responde_nombre_ruta_y_enlace_del_documento(api, monkeypatch):
    cliente, db = api
    rec_id = recomendacion(db)
    origen(monkeypatch, EstadoDocumento(estado=DOC_DISPONIBLE, ruta_legible="Hojas de vida"))

    respuesta = cliente.get(f"/busquedas/recomendacion/{rec_id}/hoja-de-vida")

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "estado": "DISPONIBLE",
        "disponible": True,
        "mensaje": None,
        "nombre_archivo": "Ana.pdf",
        "ruta": "Hojas de vida/Ana.pdf",
        "url": URL,
    }


def test_el_api_avisa_cuando_el_archivo_ya_no_esta(api, monkeypatch):
    cliente, db = api
    rec_id = recomendacion(db)
    origen(monkeypatch, EstadoDocumento(estado=DOC_ELIMINADO))

    cuerpo = cliente.get(f"/busquedas/recomendacion/{rec_id}/hoja-de-vida").json()

    assert cuerpo["disponible"] is False
    assert cuerpo["mensaje"] == MENSAJE_NO_DISPONIBLE
    assert cuerpo["url"] is None


def test_el_api_responde_404_si_la_recomendacion_no_existe(api):
    cliente, _ = api

    assert cliente.get("/busquedas/recomendacion/no-existe/hoja-de-vida").status_code == 404


def test_el_detalle_de_la_recomendacion_trae_el_nombre_del_documento(api):
    cliente, db = api
    rec_id = recomendacion(db)

    cuerpo = cliente.get(f"/busquedas/recomendacion/{rec_id}").json()

    assert cuerpo["nombre_archivo"] == "Ana.pdf"
    assert cuerpo["url_hoja_vida"] == URL
