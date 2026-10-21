"""
HU-26 — el mensaje que ve el usuario cuando falla el servicio de IA.

Un fallo pasajero (timeout, servicio caído) invita a reintentar. Uno que
reintentar no arregla (falta la clave, el modelo declinó) dice el motivo real,
porque el administrador necesita ese dato para corregirlo.
"""

from types import SimpleNamespace

import pytest

from backend.domain.services import busqueda_service
from backend.infrastructure.llm.llm_provider import (
    ServicioIAError,
    ServicioIANoConfiguradoError,
    ServicioIARechazoError,
)
from backend.infrastructure.persistence.models.busqueda import BUSQUEDA_ERROR
from backend.infrastructure.persistence.models.solicitud import ESTADO_ERROR


def _ejecutar_con_fallo(monkeypatch, error):
    eventos = {"bitacora": []}

    class Busquedas:
        def get_by_id(self, _):
            return SimpleNamespace(id="b1", solicitud_id="s1")

        def finalizar(self, busqueda_id, **kwargs):
            eventos.setdefault("finalizar", []).append(kwargs)

        def actualizar_progreso(self, *args):
            pass

    class Solicitudes:
        def get_by_id(self, _):
            return SimpleNamespace(
                id="s1",
                usuario_id="u1",
                descripcion_libre="d",
                rol_buscado="r",
                experiencia_min=None,
            )

        def listar_criterios(self, _):
            return []

        def cambiar_estado(self, solicitud_id, estado):
            eventos["estado"] = estado

    class Embeddings:
        def generar_uno(self, _):
            raise error

    class Bitacora:
        def __init__(self, db):
            pass

        def registrar(self, **kwargs):
            eventos["bitacora"].append(kwargs)

    monkeypatch.setattr(busqueda_service, "BitacoraService", Bitacora)
    servicio = busqueda_service.BusquedaService.__new__(busqueda_service.BusquedaService)
    servicio.db = None
    servicio.busquedas = Busquedas()
    servicio.solicitudes = Solicitudes()
    servicio.embeddings = Embeddings()

    servicio.ejecutar("b1")
    return eventos


@pytest.mark.parametrize(
    "error",
    [
        ServicioIANoConfiguradoError("Falta LLM_API_KEY: configúrala en el .env."),
        ServicioIARechazoError("El modelo declinó procesar la solicitud."),
    ],
    ids=["sin_clave", "rechazo_del_modelo"],
)
def test_hu26_si_reintentar_no_ayuda_se_dice_el_motivo_real(monkeypatch, error):
    eventos = _ejecutar_con_fallo(monkeypatch, error)

    final = eventos["finalizar"][-1]
    assert final["estado"] == BUSQUEDA_ERROR
    assert final["mensaje_error"] == str(error)
    assert eventos["estado"] == ESTADO_ERROR


def test_hu26_un_fallo_pasajero_invita_a_reintentar(monkeypatch):
    eventos = _ejecutar_con_fallo(monkeypatch, ServicioIAError("timeout"))

    final = eventos["finalizar"][-1]
    assert "Puedes reintentar" in final["mensaje_error"]
    assert "timeout" not in final["mensaje_error"]


def test_hu26_todos_los_fallos_de_ia_quedan_en_la_bitacora(monkeypatch):
    eventos = _ejecutar_con_fallo(monkeypatch, ServicioIANoConfiguradoError("sin clave"))

    assert eventos["bitacora"][0]["accion"] == "ERROR_SERVICIO"
    assert "IA_NO_DISPONIBLE" in eventos["bitacora"][0]["detalle"]
