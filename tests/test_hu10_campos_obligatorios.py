"""
HU-10, aviso de información indispensable. Criterios de aceptación:

    1. Si el rol o la descripción del perfil están vacíos no se ejecuta la
       búsqueda y se indica el campo faltante.
    2. El campo años de experiencia solo acepta valores numéricos positivos.
    3. Los campos con error se resaltan visualmente.
    4. Al corregir la información faltante la búsqueda se ejecuta normalmente.

El criterio 3 es de interfaz y se verifica a mano en NuevaBusqueda. Aquí se
prueba lo que garantiza el servidor aunque alguien llame a la API sin pasar por
el formulario. El worker no se ejecuta: `despachar` se sustituye por un doble.
"""

import pytest
from pydantic import ValidationError

from backend.domain.services.solicitud_service import (
    CAMPO_DESCRIPCION,
    CAMPO_ROL,
    campos_faltantes,
    mensaje_campos_faltantes,
)
from backend.infrastructure.persistence.models.busqueda import BusquedaModel
from backend.schemas.solicitud import EXPERIENCIA_MAX_ANIOS, SolicitudCreate, SolicitudUpdate

DESCRIPCION = "Desarrollador Backend Java con Spring Boot y experiencia en banca."
ROL = "Desarrollador Backend"


@pytest.fixture
def cabeceras(crear_usuario, entrar):
    crear_usuario("ana@bee.com.co")
    return entrar("ana@bee.com.co")


@pytest.fixture
def sin_worker(monkeypatch):
    """La búsqueda se encola pero no corre: no hay servicio de IA en las pruebas."""
    import backend.api.busquedas as router

    monkeypatch.setattr(router, "despachar", lambda *args, **kwargs: None)


def _crear_solicitud(cliente, cabeceras, **datos) -> str:
    respuesta = cliente.post("/solicitudes/", json=datos, headers=cabeceras)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["id"]


# --- Criterio 1 --------------------------------------------------------------


@pytest.mark.parametrize(
    ("descripcion", "rol", "esperados"),
    [
        pytest.param("", ROL, [CAMPO_DESCRIPCION], id="sin_descripcion"),
        pytest.param(DESCRIPCION, "", [CAMPO_ROL], id="sin_rol"),
        pytest.param(DESCRIPCION, None, [CAMPO_ROL], id="rol_sin_valor"),
        pytest.param("   ", "   ", [CAMPO_DESCRIPCION, CAMPO_ROL], id="solo_espacios"),
        pytest.param(DESCRIPCION, ROL, [], id="completa"),
    ],
)
def test_hu10_criterio1_identifica_los_campos_faltantes(descripcion, rol, esperados):
    assert campos_faltantes(descripcion, rol) == esperados


def test_hu10_criterio1_el_mensaje_nombra_cada_campo_faltante():
    mensaje = mensaje_campos_faltantes([CAMPO_DESCRIPCION, CAMPO_ROL])

    assert CAMPO_DESCRIPCION in mensaje
    assert CAMPO_ROL in mensaje


def test_hu10_criterio1_sin_rol_no_se_ejecuta_la_busqueda(cliente, cabeceras, sin_worker, db):
    solicitud_id = _crear_solicitud(cliente, cabeceras, descripcion_libre=DESCRIPCION)

    respuesta = cliente.post(f"/busquedas/solicitud/{solicitud_id}", headers=cabeceras)

    assert respuesta.status_code == 422
    assert CAMPO_ROL in respuesta.json()["detail"]
    assert db.query(BusquedaModel).count() == 0


def test_hu10_criterio1_sin_descripcion_no_se_ejecuta_la_busqueda(cliente, cabeceras, sin_worker, db):
    solicitud_id = _crear_solicitud(cliente, cabeceras, rol_buscado=ROL)

    respuesta = cliente.post(f"/busquedas/solicitud/{solicitud_id}", headers=cabeceras)

    assert respuesta.status_code == 422
    assert CAMPO_DESCRIPCION in respuesta.json()["detail"]
    assert db.query(BusquedaModel).count() == 0


# --- Criterio 2 --------------------------------------------------------------


@pytest.mark.parametrize("esquema", [SolicitudCreate, SolicitudUpdate])
@pytest.mark.parametrize("anios", [1, 5, EXPERIENCIA_MAX_ANIOS])
def test_hu10_criterio2_acepta_anios_enteros_positivos(esquema, anios):
    assert esquema(experiencia_min=anios).experiencia_min == anios


@pytest.mark.parametrize("esquema", [SolicitudCreate, SolicitudUpdate])
@pytest.mark.parametrize(
    "anios",
    [
        pytest.param(0, id="cero"),
        pytest.param(-3, id="negativo"),
        pytest.param(2.5, id="decimal"),
        pytest.param("cinco", id="texto"),
        pytest.param(EXPERIENCIA_MAX_ANIOS + 1, id="sobre_el_maximo"),
    ],
)
def test_hu10_criterio2_rechaza_lo_que_no_es_un_entero_positivo(esquema, anios):
    with pytest.raises(ValidationError):
        esquema(experiencia_min=anios)


@pytest.mark.parametrize("esquema", [SolicitudCreate, SolicitudUpdate])
def test_hu10_criterio2_la_experiencia_sigue_siendo_opcional(esquema):
    assert esquema().experiencia_min is None


def test_hu10_criterio2_la_api_rechaza_una_experiencia_negativa_al_editar(cliente, cabeceras):
    solicitud_id = _crear_solicitud(cliente, cabeceras, descripcion_libre=DESCRIPCION, rol_buscado=ROL)

    respuesta = cliente.put(
        f"/solicitudes/{solicitud_id}", json={"experiencia_min": -2}, headers=cabeceras
    )

    assert respuesta.status_code == 422


# --- Criterio 4 --------------------------------------------------------------


def test_hu10_criterio4_al_completar_el_rol_la_busqueda_se_ejecuta(cliente, cabeceras, sin_worker, db):
    solicitud_id = _crear_solicitud(cliente, cabeceras, descripcion_libre=DESCRIPCION)
    assert cliente.post(f"/busquedas/solicitud/{solicitud_id}", headers=cabeceras).status_code == 422

    corregida = cliente.put(
        f"/solicitudes/{solicitud_id}",
        json={"descripcion_libre": DESCRIPCION, "rol_buscado": ROL, "experiencia_min": 5},
        headers=cabeceras,
    )
    assert corregida.status_code == 200

    respuesta = cliente.post(f"/busquedas/solicitud/{solicitud_id}", headers=cabeceras)

    assert respuesta.status_code == 202
    assert db.query(BusquedaModel).count() == 1
