"""
HU-22: indicador de progreso durante el análisis.

Criterios de aceptación:

    1. Durante el análisis se muestra un indicador de progreso con un mensaje
       de estado.
    2. El botón de búsqueda permanece deshabilitado mientras el análisis está
       en curso.
    3. Al finalizar el análisis, el indicador desaparece automáticamente.

La barra, el botón y la desaparición del indicador son de interfaz y se
verifican a mano (ver la guía de la HU). Aquí se prueba lo que los hace
posibles: que el API responda de inmediato y publique el estado y la etapa,
que una solicitud no se analice dos veces a la vez y que la sincronización
previa del repositorio también quede reflejada en el progreso.
"""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api import busquedas as api_busquedas
from backend.domain.services.busqueda_service import BusquedaService
from backend.infrastructure.persistence import models  # noqa: F401
from backend.infrastructure.persistence.database import Base, get_db
from backend.infrastructure.persistence.models._base import utcnow
from backend.infrastructure.persistence.models.busqueda import (
    BUSQUEDA_COMPLETADA,
    BUSQUEDA_EJECUTANDO,
    BUSQUEDA_EN_COLA,
    BUSQUEDA_ERROR,
    BusquedaModel,
)
from backend.infrastructure.persistence.models.solicitud import SolicitudModel
from backend.infrastructure.persistence.models.usuario import UsuarioModel
from backend.infrastructure.persistence.repositories.busqueda_repo import BusquedaRepository
from backend.main import app
from backend.security import get_current_user
from backend.workers import busqueda_worker, queue

DESCRIPCION = "Desarrollador backend con experiencia en Java, Spring Boot y servicios bancarios."


# --- Andamiaje ----------------------------------------------------------------


@pytest.fixture()
def api(monkeypatch):
    motor = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=motor)
    db = sessionmaker(bind=motor)()

    usuario = UsuarioModel(
        nombre="Reclutador", correo="reclutador@bee.com.co", password_hash="x", rol="ANALISTA"
    )
    db.add(usuario)
    db.commit()

    def get_db_de_prueba():
        yield db

    app.dependency_overrides[get_db] = get_db_de_prueba
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=usuario.id)

    despachos = []
    monkeypatch.setattr(
        api_busquedas, "despachar", lambda tareas, funcion, *args: despachos.append(args)
    )

    yield SimpleNamespace(cliente=TestClient(app), db=db, usuario=usuario, despachos=despachos)
    app.dependency_overrides.clear()
    db.close()


def solicitud(api) -> str:
    registro = SolicitudModel(descripcion_libre=DESCRIPCION, usuario_id=api.usuario.id)
    api.db.add(registro)
    api.db.commit()
    return registro.id


def busqueda(api, solicitud_id: str, estado: str, minutos_atras: int = 0, **campos) -> str:
    registro = BusquedaModel(solicitud_id=solicitud_id, estado=estado, **campos)
    api.db.add(registro)
    api.db.commit()
    if minutos_atras:
        registro.created_at = utcnow() - timedelta(minutes=minutos_atras)
        api.db.commit()
    return registro.id


def busquedas_de(api, solicitud_id: str) -> int:
    return api.db.query(BusquedaModel).filter(BusquedaModel.solicitud_id == solicitud_id).count()


# --- Criterios 1 y 3: el API publica el estado y la etapa ----------------------


@pytest.mark.parametrize(
    "estado, etapa, progreso, mensaje_error",
    [
        (BUSQUEDA_EN_COLA, None, 0, None),
        (BUSQUEDA_EJECUTANDO, "Buscando en las hojas de vida", 35, None),
        (BUSQUEDA_COMPLETADA, "Listo", 100, None),
        (BUSQUEDA_ERROR, "Analizando los perfiles finalistas", 80, "El servicio de IA no respondió."),
    ],
)
def test_el_estado_publica_etapa_progreso_y_error(api, estado, etapa, progreso, mensaje_error):
    busqueda_id = busqueda(
        api,
        solicitud(api),
        estado,
        etapa=etapa,
        progreso=progreso,
        mensaje_error=mensaje_error,
    )

    respuesta = api.cliente.get(f"/busquedas/{busqueda_id}/estado")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == estado
    assert cuerpo["etapa"] == etapa
    assert cuerpo["progreso"] == progreso
    assert cuerpo["mensaje_error"] == mensaje_error


def test_el_estado_de_una_busqueda_inexistente_es_404(api):
    assert api.cliente.get("/busquedas/no-existe/estado").status_code == 404


# --- Criterio 1: la respuesta es inmediata ------------------------------------


def test_iniciar_responde_202_en_cola_y_despacha_el_trabajo_una_vez(api):
    solicitud_id = solicitud(api)

    respuesta = api.cliente.post(f"/busquedas/solicitud/{solicitud_id}")

    assert respuesta.status_code == 202
    assert respuesta.json()["estado"] == BUSQUEDA_EN_COLA
    assert respuesta.json()["solicitud_id"] == solicitud_id
    assert api.despachos == [(respuesta.json()["id"],)]


# --- Criterio 2: una solicitud no se analiza dos veces a la vez ----------------


@pytest.mark.parametrize("estado", [BUSQUEDA_EN_COLA, BUSQUEDA_EJECUTANDO])
def test_si_la_solicitud_ya_se_analiza_se_devuelve_esa_busqueda(api, estado):
    solicitud_id = solicitud(api)
    en_curso = busqueda(api, solicitud_id, estado, etapa="Buscando en las hojas de vida", progreso=35)

    respuesta = api.cliente.post(f"/busquedas/solicitud/{solicitud_id}")

    assert respuesta.status_code == 202
    assert respuesta.json()["id"] == en_curso
    assert respuesta.json()["progreso"] == 35
    assert busquedas_de(api, solicitud_id) == 1
    assert api.despachos == []


def test_el_doble_clic_no_crea_dos_busquedas(api):
    solicitud_id = solicitud(api)

    primera = api.cliente.post(f"/busquedas/solicitud/{solicitud_id}").json()
    segunda = api.cliente.post(f"/busquedas/solicitud/{solicitud_id}").json()

    assert segunda["id"] == primera["id"]
    assert busquedas_de(api, solicitud_id) == 1
    assert len(api.despachos) == 1


@pytest.mark.parametrize("estado", [BUSQUEDA_COMPLETADA, BUSQUEDA_ERROR])
def test_una_busqueda_terminada_no_bloquea_una_nueva(api, estado):
    """Reintentar tras un error, o repetir un análisis ya completado, debe poder hacerse."""
    solicitud_id = solicitud(api)
    anterior = busqueda(api, solicitud_id, estado)

    respuesta = api.cliente.post(f"/busquedas/solicitud/{solicitud_id}")

    assert respuesta.json()["id"] != anterior
    assert busquedas_de(api, solicitud_id) == 2
    assert len(api.despachos) == 1


def test_una_busqueda_abandonada_no_bloquea_la_solicitud_para_siempre(api):
    """Si el worker murió a mitad de camino, la búsqueda queda EJECUTANDO. No debe ser definitivo."""
    solicitud_id = solicitud(api)
    abandonada = busqueda(api, solicitud_id, BUSQUEDA_EJECUTANDO, minutos_atras=25)

    respuesta = api.cliente.post(f"/busquedas/solicitud/{solicitud_id}")

    assert respuesta.json()["id"] != abandonada
    assert len(api.despachos) == 1


def test_el_analisis_de_otra_solicitud_no_bloquea(api):
    busqueda(api, solicitud(api), BUSQUEDA_EJECUTANDO)
    otra = solicitud(api)

    respuesta = api.cliente.post(f"/busquedas/solicitud/{otra}")

    assert respuesta.json()["solicitud_id"] == otra
    assert len(api.despachos) == 1


def test_el_servicio_distingue_la_busqueda_viva_de_la_terminada(api):
    solicitud_id = solicitud(api)
    busqueda(api, solicitud_id, BUSQUEDA_COMPLETADA)
    viva = busqueda(api, solicitud_id, BUSQUEDA_EN_COLA)

    assert BusquedaService(api.db).en_curso(solicitud_id).id == viva


# --- Criterio 1: la sincronización previa también se ve -----------------------


def test_la_sincronizacion_del_repositorio_aparece_en_el_progreso(api, monkeypatch):
    solicitud_id = solicitud(api)
    busqueda_id = busqueda(api, solicitud_id, BUSQUEDA_EN_COLA)

    visto_durante_la_sincronizacion = {}
    orden = []

    def sincronizar():
        registro = BusquedaRepository(api.db).get_by_id(busqueda_id)
        visto_durante_la_sincronizacion.update(
            estado=registro.estado, etapa=registro.etapa, progreso=registro.progreso
        )
        orden.append("sincronizar")

    monkeypatch.setattr(busqueda_worker, "SessionLocal", lambda: api.db)
    monkeypatch.setattr(busqueda_worker, "_sincronizar_repositorio", sincronizar)
    monkeypatch.setattr(
        BusquedaService, "ejecutar", lambda self, busqueda_id: orden.append("analizar")
    )

    busqueda_worker.ejecutar_busqueda(busqueda_id)

    assert visto_durante_la_sincronizacion == {
        "estado": BUSQUEDA_EJECUTANDO,
        "etapa": "Sincronizando el repositorio",
        "progreso": 5,
    }
    assert orden == ["sincronizar", "analizar"]


def test_una_busqueda_que_ya_no_existe_no_dispara_el_trabajo(api, monkeypatch):
    orden = []
    monkeypatch.setattr(busqueda_worker, "SessionLocal", lambda: api.db)
    monkeypatch.setattr(busqueda_worker, "_sincronizar_repositorio", lambda: orden.append("sync"))
    monkeypatch.setattr(BusquedaService, "ejecutar", lambda self, _id: orden.append("analizar"))

    busqueda_worker.ejecutar_busqueda("no-existe")

    assert orden == []


# --- Despacho: sin Redis no se espera el análisis dentro de la petición -------


class TareasFalsas:
    def __init__(self):
        self.agregadas = []

    def add_task(self, funcion, *args):
        self.agregadas.append((funcion, args))


def test_sin_redis_el_trabajo_pasa_a_segundo_plano_y_no_corre_en_linea(monkeypatch):
    monkeypatch.setattr(queue, "get_cola", lambda: None)
    ejecutadas = []
    tareas = TareasFalsas()

    resultado = queue.despachar(tareas, ejecutadas.append, "busqueda-1")

    assert resultado is None
    assert ejecutadas == []
    assert tareas.agregadas == [(ejecutadas.append, ("busqueda-1",))]


def test_con_redis_el_trabajo_va_a_la_cola_y_no_a_segundo_plano(monkeypatch):
    llamadas = []

    class ColaFalsa:
        def enqueue(self, funcion, *args, job_timeout):
            llamadas.append((funcion, args, job_timeout))
            return SimpleNamespace(id="trabajo-7")

    monkeypatch.setattr(queue, "get_cola", lambda: ColaFalsa())
    tareas = TareasFalsas()

    resultado = queue.despachar(tareas, print, "busqueda-1")

    assert resultado == "trabajo-7"
    assert llamadas == [(print, ("busqueda-1",), 900)]
    assert tareas.agregadas == []
