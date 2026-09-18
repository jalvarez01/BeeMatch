"""
HU-05, segundo criterio de aceptación:

    "Las credenciales se almacenan de forma cifrada."

y su consecuencia en la superficie: la credencial tampoco puede salir en claro
por la API. Se comprueba en los dos extremos —lo que queda en la tabla y lo que
responde el endpoint— porque cifrar en base de datos no sirve de nada si el
`GET /configuracion/repositorio` devuelve el secreto descifrado.

La prueba entra por HTTP, con el rol de administrador simulado, de modo que
recorre el mismo camino que la pantalla de Configuración (RNF08, RNF10).
"""

import json

import pytest
from fastapi.testclient import TestClient

from backend.infrastructure.persistence.database import get_db
from backend.infrastructure.persistence.models.configuracion import (
    ConfiguracionRepositorioModel,
)
from backend.infrastructure.repositorio.base import TIPO_GDRIVE, ResultadoPrueba
from backend.main import app
from backend.security import get_current_user
from tests.conftest import SECRETO_DE_PRUEBA

# Fragmentos que jamás deben aparecer en una respuesta de la API.
TROZOS_DEL_SECRETO = ("BEGIN PRIVATE KEY", "AQUI-VA-LA-LLAVE", "private_key")

ACEPTA = ResultadoPrueba(
    exito=True, documentos_detectados=12, mensaje="Conexión exitosa. Se detectaron 12 hojas de vida."
)


@pytest.fixture
def cliente(db, administrador):
    """TestClient con la sesión de pruebas y el administrador ya autenticado."""
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: administrador
    # Sin gestor de contexto no se ejecuta el startup de la aplicación: las
    # pruebas no deben disparar la semilla del repositorio ni el planificador.
    yield TestClient(app)
    app.dependency_overrides.clear()


def _registrar(cliente) -> dict:
    respuesta = cliente.put(
        "/configuracion/repositorio",
        json={
            "tipo": TIPO_GDRIVE,
            "carpeta": "carpeta-de-hojas-de-vida",
            "credenciales": {"credenciales_json": SECRETO_DE_PRUEBA},
        },
    )
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["guardado"] is True
    return cuerpo


def test_el_secreto_no_sale_en_claro_por_la_api(cliente, db, origen):
    origen(ACEPTA)

    # 1. La respuesta del guardado ya viene enmascarada.
    cuerpo = _registrar(cliente)
    devuelto = cuerpo["configuracion"]["credenciales"]["credenciales_json"]
    assert devuelto == "•" * 12
    assert SECRETO_DE_PRUEBA not in json.dumps(cuerpo)

    # 2. Y la consulta posterior, que es la que alimenta la pantalla, también.
    respuesta = cliente.get("/configuracion/repositorio")
    assert respuesta.status_code == 200
    consulta = respuesta.json()

    assert consulta["configurado"] is True
    assert consulta["tipo"] == TIPO_GDRIVE
    assert consulta["carpeta"] == "carpeta-de-hojas-de-vida"
    assert consulta["documentos_detectados"] == 12
    # El secreto se reporta como legible: está cifrado, pero se puede descifrar.
    assert consulta["secreto_legible"] is True
    assert consulta["credenciales"]["credenciales_json"] == "•" * 12

    # Ni el cuerpo completo de ninguna de las dos respuestas deja escapar un
    # trozo reconocible de la llave.
    for crudo in (json.dumps(cuerpo), respuesta.text):
        for trozo in TROZOS_DEL_SECRETO:
            assert trozo not in crudo


def test_el_secreto_queda_cifrado_en_la_tabla(cliente, db, origen):
    origen(ACEPTA)
    _registrar(cliente)

    almacenado = db.query(ConfiguracionRepositorioModel).one().credenciales_cifradas

    # Token Fernet, no el JSON original ni nada que se le parezca.
    assert almacenado.startswith("gAAAAA")
    assert SECRETO_DE_PRUEBA not in almacenado
    for trozo in TROZOS_DEL_SECRETO:
        assert trozo not in almacenado
