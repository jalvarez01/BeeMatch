"""
HU-24: marcación de candidatos preseleccionados.

Criterio 1 — se pueden marcar uno o varios candidatos del listado.
Criterio 2 — la marcación queda guardada y asociada a la solicitud.
Criterio 3 — al consultar la solicitud después se sabe cuáles se preseleccionaron.
Criterio 4 — la marcación se puede retirar y el estado se actualiza.

Se marca por la API real (PATCH), con una directora que tiene vista de todas
las solicitudes, y se lee lo guardado con una sesión aparte.
"""

import pytest

from backend.domain.services.resultado_service import ResultadoService
from backend.domain.services.solicitud_service import SolicitudService
from backend.infrastructure.persistence.database import SessionLocal
from backend.infrastructure.persistence.repositories.busqueda_repo import BusquedaRepository
from backend.security import ROL_DIRECTOR
from tests.test_top5_candidatos import _crear_candidatos, _crear_solicitud, _servicio


@pytest.fixture
def busqueda(db):
    """Una búsqueda terminada con tres candidatos recomendados."""
    ids = _crear_candidatos(db, 3)
    solicitud_id = _crear_solicitud(db)
    servicio = _servicio(db, dict(zip(ids, [92.0, 81.0, 74.0], strict=True)), ids)
    busqueda_id = servicio.encolar(solicitud_id)
    servicio.ejecutar(busqueda_id)
    recomendaciones = [r.id for r in BusquedaRepository(db).listar_recomendaciones(busqueda_id)]
    return {"solicitud_id": solicitud_id, "busqueda_id": busqueda_id, "recomendaciones": recomendaciones}


@pytest.fixture
def cabeceras(crear_usuario, entrar):
    crear_usuario("directora@bee.com.co", rol=ROL_DIRECTOR)
    return entrar("directora@bee.com.co")


def _marcar(cliente, cabeceras, recomendacion_id: str, valor: bool):
    return cliente.patch(
        f"/busquedas/recomendacion/{recomendacion_id}/preseleccion",
        json={"preseleccionado": valor},
        headers=cabeceras,
    )


def _guardado(busqueda_id: str) -> dict[str, bool]:
    """Lee lo que quedó en la base con una sesión nueva, como otra petición."""
    sesion = SessionLocal()
    try:
        return {
            r.id: r.preseleccionado for r in BusquedaRepository(sesion).listar_recomendaciones(busqueda_id)
        }
    finally:
        sesion.close()


# --- Criterios 1 y 2: marcar varios y que quede guardado ---------------------


def test_se_pueden_marcar_varios_candidatos_y_quedan_guardados(cliente, cabeceras, busqueda):
    primero, segundo, tercero = busqueda["recomendaciones"]

    for recomendacion_id in (primero, segundo):
        respuesta = _marcar(cliente, cabeceras, recomendacion_id, True)
        assert respuesta.status_code == 200, respuesta.text
        assert respuesta.json()["preseleccionado"] is True

    assert _guardado(busqueda["busqueda_id"]) == {primero: True, segundo: True, tercero: False}


def test_marcar_una_recomendacion_que_no_existe_responde_404(cliente, cabeceras, busqueda):
    assert _marcar(cliente, cabeceras, "no-existe", True).status_code == 404


# --- Criterio 3: al volver a consultar se sabe cuáles se marcaron ------------


def test_al_consultar_la_solicitud_se_ve_cuantos_y_cuales_se_preseleccionaron(
    db, cliente, cabeceras, busqueda
):
    primero, segundo, _ = busqueda["recomendaciones"]
    _marcar(cliente, cabeceras, primero, True)
    _marcar(cliente, cabeceras, segundo, True)
    db.expire_all()

    solicitud = SolicitudService(db).obtener(busqueda["solicitud_id"])
    assert solicitud.total_preseleccionados == 2

    resultado = ResultadoService(db).resultados(busqueda["busqueda_id"])
    marcados = [r.id for r in resultado.recomendaciones if r.preseleccionado]
    assert marcados == [primero, segundo]


def test_el_historial_trae_el_total_de_preseleccionados(db, cliente, cabeceras, busqueda):
    _marcar(cliente, cabeceras, busqueda["recomendaciones"][0], True)
    db.expire_all()

    solicitudes, _ = SolicitudService(db).historial()

    assert solicitudes[0].total_preseleccionados == 1


def test_sin_marcaciones_el_total_es_cero(db, busqueda):
    assert SolicitudService(db).obtener(busqueda["solicitud_id"]).total_preseleccionados == 0


# --- Criterio 4: retirar la marcación ----------------------------------------


def test_la_marcacion_se_puede_retirar_y_se_actualiza(db, cliente, cabeceras, busqueda):
    primero, segundo, _ = busqueda["recomendaciones"]
    _marcar(cliente, cabeceras, primero, True)
    _marcar(cliente, cabeceras, segundo, True)

    respuesta = _marcar(cliente, cabeceras, primero, False)

    assert respuesta.status_code == 200
    assert respuesta.json()["preseleccionado"] is False
    assert _guardado(busqueda["busqueda_id"])[primero] is False
    db.expire_all()
    assert SolicitudService(db).obtener(busqueda["solicitud_id"]).total_preseleccionados == 1
