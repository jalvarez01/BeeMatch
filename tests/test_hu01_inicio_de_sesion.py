"""
HU-01 — una o más pruebas por cada criterio de aceptación.

Todas pasan por la API real (`/auth/login`) con una base temporal; no hay red.
"""

from datetime import timedelta

import pytest

from backend.config import LOGIN_BLOQUEO_MINUTOS, LOGIN_MAX_INTENTOS
from backend.infrastructure.persistence.models._base import utcnow
from backend.infrastructure.persistence.models.usuario import IntentoLoginModel
from tests.conftest import CLAVE_DE_PRUEBA

MENSAJE = "Usuario o contraseña incorrectos"


def _login(cliente, correo, password):
    return cliente.post("/auth/login", json={"correo": correo, "password": password})


def test_hu01_criterio1_autentica_con_usuario_y_contrasena(cliente, crear_usuario):
    crear_usuario("ana@bee.com.co")

    respuesta = _login(cliente, "ana@bee.com.co", CLAVE_DE_PRUEBA)

    assert respuesta.status_code == 200
    assert respuesta.json()["access_token"]


def test_hu01_criterio2_devuelve_nombre_y_rol_para_la_pantalla_principal(cliente, crear_usuario):
    crear_usuario("ana@bee.com.co", rol="DIRECTOR", nombre="Ana Gómez")

    usuario = _login(cliente, "ana@bee.com.co", CLAVE_DE_PRUEBA).json()["usuario"]

    assert (usuario["nombre"], usuario["rol"]) == ("Ana Gómez", "DIRECTOR")


@pytest.mark.parametrize(
    "correo, password",
    [
        ("ana@bee.com.co", "Equivocada1"),
        ("nadie@bee.com.co", CLAVE_DE_PRUEBA),
    ],
    ids=["clave_errada", "correo_inexistente"],
)
def test_hu01_criterio3_mensaje_unico_sin_indicar_que_dato_fallo(
    cliente, crear_usuario, correo, password
):
    crear_usuario("ana@bee.com.co")

    respuesta = _login(cliente, correo, password)

    assert respuesta.status_code == 401
    assert respuesta.json()["detail"] == MENSAJE


def test_hu01_criterio3_cuenta_inactiva_recibe_el_mismo_mensaje(cliente, crear_usuario):
    crear_usuario("baja@bee.com.co", activo=False)

    respuesta = _login(cliente, "baja@bee.com.co", CLAVE_DE_PRUEBA)

    assert (respuesta.status_code, respuesta.json()["detail"]) == (401, MENSAJE)


def test_hu01_criterio4_bloquea_tras_cinco_intentos_fallidos(cliente, crear_usuario):
    crear_usuario("ana@bee.com.co")

    for _ in range(LOGIN_MAX_INTENTOS):
        assert _login(cliente, "ana@bee.com.co", "Equivocada1").status_code == 401

    # Ya bloqueada: ni la clave correcta entra.
    respuesta = _login(cliente, "ana@bee.com.co", CLAVE_DE_PRUEBA)
    assert respuesta.status_code == 429
    assert "bloqueado temporalmente" in respuesta.json()["detail"]
    assert str(LOGIN_BLOQUEO_MINUTOS) in respuesta.json()["detail"]


def test_hu01_criterio4_el_bloqueo_dura_quince_minutos(cliente, crear_usuario, db):
    crear_usuario("ana@bee.com.co")
    for _ in range(LOGIN_MAX_INTENTOS):
        _login(cliente, "ana@bee.com.co", "Equivocada1")

    fila = db.get(IntentoLoginModel, "ana@bee.com.co")
    assert timedelta(minutes=14) < fila.bloqueado_hasta.replace(tzinfo=utcnow().tzinfo) - utcnow()

    # Pasado el plazo, la cuenta vuelve a funcionar.
    fila.bloqueado_hasta = utcnow() - timedelta(seconds=1)
    db.commit()
    assert _login(cliente, "ana@bee.com.co", CLAVE_DE_PRUEBA).status_code == 200


def test_hu01_criterio4_el_bloqueo_tambien_aplica_a_correos_inexistentes(cliente):
    """Si solo se bloquearan las cuentas reales, el bloqueo delataría cuáles existen."""
    for _ in range(LOGIN_MAX_INTENTOS):
        _login(cliente, "fantasma@bee.com.co", "Equivocada1")

    assert _login(cliente, "fantasma@bee.com.co", "Equivocada1").status_code == 429


def test_hu01_criterio4_un_acceso_correcto_reinicia_la_cuenta(cliente, crear_usuario):
    crear_usuario("ana@bee.com.co")

    for _ in range(LOGIN_MAX_INTENTOS - 1):
        _login(cliente, "ana@bee.com.co", "Equivocada1")
    assert _login(cliente, "ana@bee.com.co", CLAVE_DE_PRUEBA).status_code == 200

    for _ in range(LOGIN_MAX_INTENTOS - 1):
        _login(cliente, "ana@bee.com.co", "Equivocada1")
    assert _login(cliente, "ana@bee.com.co", CLAVE_DE_PRUEBA).status_code == 200


def test_hu01_criterio4_un_bloqueo_no_afecta_a_otros_usuarios(cliente, crear_usuario):
    crear_usuario("ana@bee.com.co")
    crear_usuario("luis@bee.com.co")
    for _ in range(LOGIN_MAX_INTENTOS):
        _login(cliente, "ana@bee.com.co", "Equivocada1")

    assert _login(cliente, "luis@bee.com.co", CLAVE_DE_PRUEBA).status_code == 200


def test_hu01_criterio5_sin_sesion_la_api_rechaza_las_rutas_internas(cliente):
    """El redirect al login lo hace el frontend a partir de este 401."""
    assert cliente.get("/auth/yo").status_code == 401
    assert cliente.get("/candidatos").status_code == 401
