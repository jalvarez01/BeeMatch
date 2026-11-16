"""
Las cuentas las crea la superadministradora; nadie se registra solo.

    1. No existe el autorregistro: la ruta pública se retiró.
    2. El correo tiene la forma nombre.apellido@beeconsultoria.com.
    3. La superadministradora (o un administrador) borra el perfil de una persona.
    4. Borrar un perfil no borra su historial: sus solicitudes siguen mostrando
       quién las hizo, aunque esa cuenta ya no exista.
    5. Cada quien cambia su contraseña y la superadministradora no puede leerla.
"""

import pytest

from backend.infrastructure.persistence.models.solicitud import SolicitudModel
from backend.infrastructure.persistence.models.usuario import UsuarioModel
from tests.conftest import CLAVE_DE_PRUEBA

DOMINIO = "beeconsultoria.com"


@pytest.fixture
def diana(crear_usuario):
    return crear_usuario(f"diana.alvarez@{DOMINIO}", rol="SUPERADMINISTRADOR", nombre="Diana")


def _nuevo(correo, **extra):
    return {"nombre": "Rick Gómez", "correo": correo, "password": "Segura1234", **extra}


# --- Sin autorregistro ---------------------------------------------------------


def test_el_autorregistro_ya_no_existe(cliente):
    respuesta = cliente.post(
        "/auth/registro",
        json={"nombre": "Pedro Gil", "correo": f"pedro.gil@{DOMINIO}", "password": "Segura1234"},
    )

    assert respuesta.status_code in (404, 405)


# --- Forma del correo ----------------------------------------------------------


@pytest.mark.parametrize(
    "correo",
    [
        f"rick@{DOMINIO}",  # sin apellido
        f"rick.gomez.perez@{DOMINIO}",  # tres partes
        "rick.gomez@gmail.com",  # otro dominio
        "rick.gomez@bee.com.co",  # el dominio anterior
        f"rick gomez@{DOMINIO}",
    ],
)
def test_un_correo_que_no_es_nombre_apellido_se_rechaza(cliente, diana, entrar, correo):
    respuesta = cliente.post("/auth/usuarios", json=_nuevo(correo), headers=entrar(diana.correo))

    assert respuesta.status_code == 422


def test_el_correo_correcto_se_acepta_y_se_guarda_en_minuscula(cliente, diana, entrar):
    respuesta = cliente.post(
        "/auth/usuarios", json=_nuevo(f"Rick.Gomez@{DOMINIO}"), headers=entrar(diana.correo)
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["correo"] == f"rick.gomez@{DOMINIO}"


def test_cambiar_el_correo_tambien_exige_la_forma(cliente, diana, crear_usuario, entrar):
    objetivo = crear_usuario(f"rick.gomez@{DOMINIO}")

    respuesta = cliente.patch(
        f"/auth/usuarios/{objetivo.id}", json={"correo": f"rick@{DOMINIO}"}, headers=entrar(diana.correo)
    )

    assert respuesta.status_code == 422


# --- Contraseñas ---------------------------------------------------------------


def test_la_persona_cambia_su_contrasena_y_la_superadministradora_no_la_ve(cliente, diana, entrar):
    cliente.post(
        "/auth/usuarios", json=_nuevo(f"rick.gomez@{DOMINIO}"), headers=entrar(diana.correo)
    )
    cabeceras_rick = entrar(f"rick.gomez@{DOMINIO}", "Segura1234")

    cambio = cliente.post(
        "/auth/cambiar-password",
        json={"password_actual": "Segura1234", "password_nueva": "Otra-Clave-9876"},
        headers=cabeceras_rick,
    )
    assert cambio.status_code == 200

    # Diana no recibe la contraseña en ninguna respuesta: solo se guarda su hash.
    usuarios = cliente.get("/auth/usuarios", headers=entrar(diana.correo)).json()
    assert all("password" not in u and "password_hash" not in u for u in usuarios)
    assert cliente.post(
        "/auth/login", json={"correo": f"rick.gomez@{DOMINIO}", "password": "Otra-Clave-9876"}
    ).status_code == 200
    assert cliente.post(
        "/auth/login", json={"correo": f"rick.gomez@{DOMINIO}", "password": "Segura1234"}
    ).status_code == 401


def test_cambiar_la_contrasena_exige_la_actual_y_una_distinta(cliente, diana, entrar):
    cliente.post(
        "/auth/usuarios", json=_nuevo(f"rick.gomez@{DOMINIO}"), headers=entrar(diana.correo)
    )
    cabeceras = entrar(f"rick.gomez@{DOMINIO}", "Segura1234")

    equivocada = cliente.post(
        "/auth/cambiar-password",
        json={"password_actual": "No-es-esta-1", "password_nueva": "Otra-Clave-9876"},
        headers=cabeceras,
    )
    igual = cliente.post(
        "/auth/cambiar-password",
        json={"password_actual": "Segura1234", "password_nueva": "Segura1234"},
        headers=cabeceras,
    )

    assert equivocada.status_code == 400
    assert igual.status_code == 400


def test_la_clave_inicial_obliga_a_cambiarla_y_cambiarla_lo_levanta(cliente, diana, entrar):
    cliente.post(
        "/auth/usuarios", json=_nuevo(f"rick.gomez@{DOMINIO}"), headers=entrar(diana.correo)
    )
    cabeceras = entrar(f"rick.gomez@{DOMINIO}", "Segura1234")
    assert cliente.get("/auth/yo", headers=cabeceras).json()["debe_cambiar_password"] is True

    cliente.post(
        "/auth/cambiar-password",
        json={"password_actual": "Segura1234", "password_nueva": "Otra-Clave-9876"},
        headers=cabeceras,
    )

    assert cliente.get("/auth/yo", headers=cabeceras).json()["debe_cambiar_password"] is False


# --- Borrar un perfil ---------------------------------------------------------


def test_la_superadministradora_borra_el_perfil(cliente, diana, crear_usuario, entrar, db):
    objetivo = crear_usuario(f"rick.gomez@{DOMINIO}")

    respuesta = cliente.delete(f"/auth/usuarios/{objetivo.id}", headers=entrar(diana.correo))

    assert respuesta.status_code == 204
    db.expire_all()
    assert db.query(UsuarioModel).filter_by(correo=f"rick.gomez@{DOMINIO}").first() is None
    intento = cliente.post(
        "/auth/login", json={"correo": f"rick.gomez@{DOMINIO}", "password": CLAVE_DE_PRUEBA}
    )
    assert intento.status_code == 401


def test_borrar_un_perfil_conserva_las_solicitudes_y_dice_quien_las_hizo(
    cliente, diana, crear_usuario, entrar, db
):
    rick = crear_usuario(f"rick.gomez@{DOMINIO}", nombre="Rick Gómez")
    solicitud = cliente.post(
        "/solicitudes/",
        json={
            "descripcion_libre": "Desarrollador Backend Java con Spring Boot y experiencia en banca.",
            "rol_buscado": "Desarrollador Backend",
            "cliente": "Bancolombia",
        },
        headers=entrar(rick.correo),
    ).json()
    cabeceras_diana = entrar(diana.correo)

    cliente.delete(f"/auth/usuarios/{rick.id}", headers=cabeceras_diana)

    fila = cliente.get(f"/solicitudes/{solicitud['id']}", headers=cabeceras_diana).json()
    assert fila["usuario_nombre"] == "Rick Gómez"
    assert fila["usuario_eliminado"] is True
    db.expire_all()
    guardada = db.get(SolicitudModel, solicitud["id"])
    assert guardada.usuario_id is None
    assert guardada.autor_nombre == "Rick Gómez"


def test_el_historial_de_una_cuenta_activa_no_se_marca_como_eliminada(
    cliente, crear_usuario, entrar
):
    ana = crear_usuario(f"ana.perez@{DOMINIO}", rol="DIRECTOR", nombre="Ana Pérez")
    cliente.post(
        "/solicitudes/",
        json={
            "descripcion_libre": "Desarrollador Backend Java con Spring Boot y experiencia en banca.",
            "rol_buscado": "Desarrollador Backend",
            "cliente": "Bancolombia",
        },
        headers=entrar(ana.correo),
    )

    fila = cliente.get("/solicitudes/", headers=entrar(ana.correo)).json()["solicitudes"][0]

    assert (fila["usuario_nombre"], fila["usuario_eliminado"]) == ("Ana Pérez", False)


def test_borrar_un_perfil_queda_en_la_bitacora(cliente, diana, crear_usuario, entrar):
    objetivo = crear_usuario(f"rick.gomez@{DOMINIO}", nombre="Rick Gómez")
    cabeceras = entrar(diana.correo)

    cliente.delete(f"/auth/usuarios/{objetivo.id}", headers=cabeceras)

    eventos = cliente.get("/configuracion/bitacora", headers=cabeceras).json()["items"]
    borrado = next(e for e in eventos if e["accion"] == "USUARIO_ELIMINADO")
    assert "Rick Gómez" in borrado["detalle"]


def test_no_se_puede_borrar_la_propia_cuenta(cliente, diana, entrar):
    respuesta = cliente.delete(f"/auth/usuarios/{diana.id}", headers=entrar(diana.correo))

    assert respuesta.status_code == 400


def test_un_administrador_no_borra_a_la_superadministradora_ni_a_otro_administrador(
    cliente, diana, crear_usuario, entrar
):
    admin = crear_usuario(f"luis.mora@{DOMINIO}", rol="ADMINISTRADOR")
    otro = crear_usuario(f"marta.rios@{DOMINIO}", rol="ADMINISTRADOR")
    cabeceras = entrar(admin.correo)

    assert cliente.delete(f"/auth/usuarios/{diana.id}", headers=cabeceras).status_code == 403
    assert cliente.delete(f"/auth/usuarios/{otro.id}", headers=cabeceras).status_code == 403


def test_un_coordinador_no_borra_perfiles(cliente, crear_usuario, entrar):
    coord = crear_usuario(f"ana.perez@{DOMINIO}")
    otro = crear_usuario(f"pedro.gil@{DOMINIO}")

    respuesta = cliente.delete(f"/auth/usuarios/{otro.id}", headers=entrar(coord.correo))

    assert respuesta.status_code == 403


def test_borrar_un_usuario_que_no_existe_da_404(cliente, diana, entrar):
    respuesta = cliente.delete("/auth/usuarios/no-existe", headers=entrar(diana.correo))

    assert respuesta.status_code == 404
