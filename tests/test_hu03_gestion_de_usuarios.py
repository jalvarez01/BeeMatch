"""
HU-03 — criterios de aceptación y jerarquía de la superusuaria.

Jerarquía: la superusuaria (Diana) gestiona a todos; un administrador gestiona
solo Coordinadores y Directores; nadie toca a la superusuaria.
"""

import pytest

from tests.conftest import CLAVE_DE_PRUEBA

NUEVO = {
    "nombre": "Marta Ríos",
    "correo": "marta.prueba@beeconsultoria.com",
    "password": "Segura1234",
    "rol": "COORDINADOR",
}


@pytest.fixture
def diana(crear_usuario):
    return crear_usuario("diana.prueba@beeconsultoria.com", rol="SUPERADMINISTRADOR", nombre="Diana")


@pytest.fixture
def admin(crear_usuario):
    return crear_usuario("admin.prueba@beeconsultoria.com", rol="ADMINISTRADOR")


def test_hu03_criterio1_el_administrador_registra_usuario_con_nombre_correo_y_rol(
    cliente, admin, entrar
):
    respuesta = cliente.post("/auth/usuarios", json=NUEVO, headers=entrar(admin.correo))

    assert respuesta.status_code == 201
    creado = respuesta.json()
    assert (creado["nombre"], creado["correo"], creado["rol"]) == (
        "Marta Ríos",
        "marta.prueba@beeconsultoria.com",
        "COORDINADOR",
    )


def test_hu03_criterio2_el_usuario_creado_inicia_sesion_de_inmediato(cliente, admin, entrar):
    cliente.post("/auth/usuarios", json=NUEVO, headers=entrar(admin.correo))

    respuesta = cliente.post(
        "/auth/login", json={"correo": NUEVO["correo"], "password": NUEVO["password"]}
    )

    assert respuesta.status_code == 200


def test_hu03_criterio3_inactivar_impide_el_acceso_y_conserva_el_historial(
    cliente, admin, crear_usuario, entrar, db
):
    from backend.infrastructure.persistence.models.usuario import UsuarioModel

    objetivo = crear_usuario("marta.prueba@beeconsultoria.com")
    cabeceras_marta = entrar(objetivo.correo)  # genera su registro de LOGIN en la bitácora

    respuesta = cliente.patch(
        f"/auth/usuarios/{objetivo.id}", json={"activo": False}, headers=entrar(admin.correo)
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["activo"] is False
    # No puede volver a entrar, ni con la sesión que ya tenía abierta.
    assert (
        cliente.post(
            "/auth/login", json={"correo": objetivo.correo, "password": CLAVE_DE_PRUEBA}
        ).status_code
        == 401
    )
    assert cliente.get("/auth/yo", headers=cabeceras_marta).status_code == 401
    # Se conserva la fila: no se borra.
    assert db.get(UsuarioModel, objetivo.id) is not None


def test_hu03_criterio4_correo_duplicado_muestra_mensaje(cliente, admin, crear_usuario, entrar):
    crear_usuario("marta.prueba@beeconsultoria.com")

    respuesta = cliente.post("/auth/usuarios", json=NUEVO, headers=entrar(admin.correo))

    assert respuesta.status_code == 409
    assert "Ya existe un usuario con ese correo" in respuesta.json()["detail"]


@pytest.mark.parametrize("rol", ["COORDINADOR", "DIRECTOR"])
def test_hu03_criterio5_coordinador_y_director_no_acceden_a_la_gestion(
    cliente, crear_usuario, entrar, rol
):
    usuario = crear_usuario(f"{rol.lower()}@bee.com.co", rol=rol)
    cabeceras = entrar(usuario.correo)

    assert cliente.get("/auth/usuarios", headers=cabeceras).status_code == 403
    assert cliente.post("/auth/usuarios", json=NUEVO, headers=cabeceras).status_code == 403


# --- Jerarquía de la superusuaria -------------------------------------------


def test_hu03_la_superusuaria_nombra_administradores(cliente, diana, crear_usuario, entrar):
    objetivo = crear_usuario("luis.prueba@beeconsultoria.com")

    respuesta = cliente.patch(
        f"/auth/usuarios/{objetivo.id}", json={"rol": "ADMINISTRADOR"}, headers=entrar(diana.correo)
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["rol"] == "ADMINISTRADOR"


def test_hu03_la_superusuaria_revoca_el_rol_de_administrador(
    cliente, diana, admin, entrar
):
    respuesta = cliente.patch(
        f"/auth/usuarios/{admin.id}", json={"rol": "COORDINADOR"}, headers=entrar(diana.correo)
    )

    assert respuesta.json()["rol"] == "COORDINADOR"


def test_hu03_un_administrador_no_puede_tocar_a_la_superusuaria(cliente, diana, admin, entrar):
    cabeceras = entrar(admin.correo)

    for cambio in ({"rol": "COORDINADOR"}, {"activo": False}, {"nombre": "Otra"}):
        respuesta = cliente.patch(f"/auth/usuarios/{diana.id}", json=cambio, headers=cabeceras)
        assert respuesta.status_code == 403, cambio


def test_hu03_ni_la_propia_superusuaria_puede_degradarse_o_inactivarse(cliente, diana, entrar):
    cabeceras = entrar(diana.correo)

    assert cliente.patch(
        f"/auth/usuarios/{diana.id}", json={"rol": "COORDINADOR"}, headers=cabeceras
    ).status_code == 403
    assert cliente.patch(
        f"/auth/usuarios/{diana.id}", json={"activo": False}, headers=cabeceras
    ).status_code == 400


def test_hu03_un_administrador_no_revoca_a_otro_administrador(
    cliente, admin, crear_usuario, entrar
):
    otro = crear_usuario("otro.prueba@beeconsultoria.com", rol="ADMINISTRADOR")

    respuesta = cliente.patch(
        f"/auth/usuarios/{otro.id}", json={"activo": False}, headers=entrar(admin.correo)
    )

    assert respuesta.status_code == 403


def test_hu03_un_administrador_no_otorga_el_rol_de_administrador(
    cliente, admin, crear_usuario, entrar
):
    objetivo = crear_usuario("luis.prueba@beeconsultoria.com")
    cabeceras = entrar(admin.correo)

    editar = cliente.patch(
        f"/auth/usuarios/{objetivo.id}", json={"rol": "ADMINISTRADOR"}, headers=cabeceras
    )
    crear = cliente.post("/auth/usuarios", json={**NUEVO, "rol": "ADMINISTRADOR"}, headers=cabeceras)

    assert (editar.status_code, crear.status_code) == (403, 403)


def test_hu03_el_rol_superadministrador_no_se_asigna_por_la_api(
    cliente, diana, crear_usuario, entrar
):
    objetivo = crear_usuario("luis.prueba@beeconsultoria.com")
    cabeceras = entrar(diana.correo)

    editar = cliente.patch(
        f"/auth/usuarios/{objetivo.id}", json={"rol": "SUPERADMINISTRADOR"}, headers=cabeceras
    )
    crear = cliente.post(
        "/auth/usuarios", json={**NUEVO, "rol": "SUPERADMINISTRADOR"}, headers=cabeceras
    )

    assert (editar.status_code, crear.status_code) == (422, 422)


def test_hu03_la_superusuaria_conserva_todos_los_permisos_de_administrador(
    cliente, diana, entrar
):
    """Un endpoint exclusivo de ADMINISTRADOR (HU-05) no le cierra la puerta."""
    respuesta = cliente.get("/configuracion/repositorio", headers=entrar(diana.correo))

    assert respuesta.status_code not in (401, 403)


def test_hu03_se_puede_editar_nombre_y_correo(cliente, admin, crear_usuario, entrar):
    objetivo = crear_usuario("luis.prueba@beeconsultoria.com")

    respuesta = cliente.patch(
        f"/auth/usuarios/{objetivo.id}",
        json={"nombre": "Luis Pérez", "correo": "lperez.prueba@beeconsultoria.com"},
        headers=entrar(admin.correo),
    )

    assert (respuesta.json()["nombre"], respuesta.json()["correo"]) == (
        "Luis Pérez",
        "lperez.prueba@beeconsultoria.com",
    )


def test_hu03_editar_a_un_correo_ya_usado_avisa_duplicado(
    cliente, admin, crear_usuario, entrar
):
    objetivo = crear_usuario("luis.prueba@beeconsultoria.com")
    crear_usuario("marta.prueba@beeconsultoria.com")

    respuesta = cliente.patch(
        f"/auth/usuarios/{objetivo.id}",
        json={"correo": "marta.prueba@beeconsultoria.com"},
        headers=entrar(admin.correo),
    )

    assert respuesta.status_code == 409
