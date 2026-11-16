"""
El catálogo de clientes lo administra la superadministradora.

    1. Solo ella registra, renombra y borra clientes.
    2. Las demás personas con sesión solo los consultan, para elegir uno.
    3. Un nombre repetido (sin distinguir mayúsculas ni espacios) se rechaza.
    4. Un cliente con solicitudes no se puede borrar: el historial conserva el suyo.
"""

import pytest

from backend.infrastructure.persistence.models.cliente import ClienteModel

DOMINIO = "beeconsultoria.com"
DESCRIPCION = "Desarrollador Backend Java con Spring Boot y experiencia en banca."


@pytest.fixture
def diana(crear_usuario):
    return crear_usuario(f"diana.alvarez@{DOMINIO}", rol="SUPERADMINISTRADOR", nombre="Diana")


@pytest.fixture
def admin(crear_usuario):
    return crear_usuario(f"luis.mora@{DOMINIO}", rol="ADMINISTRADOR")


@pytest.fixture
def coordinador(crear_usuario):
    return crear_usuario(f"ana.perez@{DOMINIO}")


def test_la_superadministradora_registra_un_cliente(cliente, diana, entrar, db):
    respuesta = cliente.post("/clientes/", json={"nombre": "  Davivienda "}, headers=entrar(diana.correo))

    assert respuesta.status_code == 201
    assert respuesta.json()["nombre"] == "Davivienda"
    assert db.query(ClienteModel).filter_by(nombre="Davivienda").count() == 1


def test_un_nombre_repetido_se_rechaza_sin_importar_mayusculas_ni_espacios(cliente, diana, entrar):
    cabeceras = entrar(diana.correo)
    cliente.post("/clientes/", json={"nombre": "Davivienda"}, headers=cabeceras)

    respuesta = cliente.post("/clientes/", json={"nombre": "  DAVIVIENDA  "}, headers=cabeceras)

    assert respuesta.status_code == 409


@pytest.mark.parametrize("rol", ["COORDINADOR", "DIRECTOR", "ADMINISTRADOR"])
def test_los_demas_roles_no_registran_ni_cambian_ni_borran_clientes(
    cliente, crear_usuario, entrar, registrar_cliente, rol
):
    persona = crear_usuario(f"rick.gomez@{DOMINIO}", rol=rol)
    existente = registrar_cliente("Davivienda")
    cabeceras = entrar(persona.correo)

    assert cliente.post("/clientes/", json={"nombre": "Nuevo"}, headers=cabeceras).status_code == 403
    assert (
        cliente.patch(f"/clientes/{existente.id}", json={"nombre": "Otro"}, headers=cabeceras).status_code
        == 403
    )
    assert cliente.delete(f"/clientes/{existente.id}", headers=cabeceras).status_code == 403


def test_cualquier_persona_con_sesion_consulta_el_catalogo(
    cliente, coordinador, entrar, registrar_cliente
):
    registrar_cliente("Davivienda")

    respuesta = cliente.get("/clientes/", headers=entrar(coordinador.correo))

    assert respuesta.status_code == 200
    assert {c["nombre"] for c in respuesta.json()} == {"Bancolombia", "Davivienda"}


def test_sin_sesion_no_se_consulta_el_catalogo(cliente):
    assert cliente.get("/clientes/").status_code in (401, 403)


def test_la_superadministradora_renombra_un_cliente(cliente, diana, entrar, registrar_cliente):
    existente = registrar_cliente("Davivienda")

    respuesta = cliente.patch(
        f"/clientes/{existente.id}", json={"nombre": "Banco Davivienda"}, headers=entrar(diana.correo)
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["nombre"] == "Banco Davivienda"


def test_renombrar_a_un_nombre_que_ya_existe_se_rechaza(cliente, diana, entrar, registrar_cliente):
    existente = registrar_cliente("Davivienda")

    respuesta = cliente.patch(
        f"/clientes/{existente.id}", json={"nombre": "bancolombia"}, headers=entrar(diana.correo)
    )

    assert respuesta.status_code == 409


def test_se_borra_un_cliente_sin_solicitudes(cliente, diana, entrar, registrar_cliente, db):
    existente = registrar_cliente("Davivienda")

    respuesta = cliente.delete(f"/clientes/{existente.id}", headers=entrar(diana.correo))

    assert respuesta.status_code == 204
    db.expire_all()
    assert db.query(ClienteModel).filter_by(nombre="Davivienda").count() == 0


def test_no_se_borra_un_cliente_con_solicitudes(cliente, diana, coordinador, entrar, db):
    cliente.post(
        "/solicitudes/",
        json={"descripcion_libre": DESCRIPCION, "rol_buscado": "Backend", "cliente": "Bancolombia"},
        headers=entrar(coordinador.correo),
    )
    bancolombia = db.query(ClienteModel).filter_by(nombre="Bancolombia").one()

    respuesta = cliente.delete(f"/clientes/{bancolombia.id}", headers=entrar(diana.correo))

    assert respuesta.status_code == 409
    db.expire_all()
    assert db.query(ClienteModel).filter_by(nombre="Bancolombia").count() == 1


def test_borrar_o_renombrar_un_cliente_que_no_existe_da_404(cliente, diana, entrar):
    cabeceras = entrar(diana.correo)

    assert cliente.delete("/clientes/no-existe", headers=cabeceras).status_code == 404
    assert (
        cliente.patch("/clientes/no-existe", json={"nombre": "Otro"}, headers=cabeceras).status_code == 404
    )


def test_la_solicitud_solo_acepta_clientes_del_catalogo_que_creo_la_superadministradora(
    cliente, diana, coordinador, entrar
):
    carga = {"descripcion_libre": DESCRIPCION, "rol_buscado": "Backend", "cliente": "Davivienda"}
    assert cliente.post("/solicitudes/", json=carga, headers=entrar(coordinador.correo)).status_code == 422

    cliente.post("/clientes/", json={"nombre": "Davivienda"}, headers=entrar(diana.correo))

    assert cliente.post("/solicitudes/", json=carga, headers=entrar(coordinador.correo)).status_code == 201
