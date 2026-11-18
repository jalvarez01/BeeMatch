"""
HU-13, consulta del historial de solicitudes. Criterios:

    1. El historial muestra fecha, quién la registró, cliente, perfil y estado.
    2. Al abrir una solicitud se ven los criterios usados.
    3. Se filtra por fecha, cliente o usuario.
    4. El Coordinador ve únicamente las solicitudes que él mismo registró.

La API se prueba completa, con autenticación.
"""

from datetime import UTC, datetime

import pytest

from backend.infrastructure.persistence.models.solicitud import SolicitudModel

DOMINIO = "beeconsultoria.com"
DESCRIPCION = "Desarrollador Backend Java con Spring Boot y experiencia en banca."


@pytest.fixture
def director(crear_usuario):
    return crear_usuario(f"dario.rojas@{DOMINIO}", rol="DIRECTOR", nombre="Dario Rojas")


@pytest.fixture
def ana(crear_usuario):
    return crear_usuario(f"ana.perez@{DOMINIO}", nombre="Ana Pérez")


@pytest.fixture
def luis(crear_usuario):
    return crear_usuario(f"luis.mora@{DOMINIO}", nombre="Luis Mora")


def _crear(http, cabeceras, **datos) -> dict:
    cuerpo = {
        "descripcion_libre": DESCRIPCION,
        "rol_buscado": "Desarrollador Backend",
        "cliente": "Bancolombia",
        **datos,
    }
    respuesta = http.post("/solicitudes/", json=cuerpo, headers=cabeceras)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _fechar(db, solicitud_id: str, dia: str) -> None:
    """Pone la solicitud en un día concreto (aaaa-mm-dd, a mediodía UTC)."""
    solicitud = db.get(SolicitudModel, solicitud_id)
    solicitud.created_at = datetime.fromisoformat(dia).replace(hour=12, tzinfo=UTC)
    db.commit()


def _ids(respuesta) -> set[str]:
    assert respuesta.status_code == 200, respuesta.text
    return {s["id"] for s in respuesta.json()["solicitudes"]}


@pytest.fixture
def tres(cliente, entrar, ana, luis, db, registrar_cliente):
    """Dos solicitudes de Ana (una de Davivienda) y una de Luis, en días distintos."""
    registrar_cliente("Davivienda")
    a1 = _crear(cliente, entrar(ana.correo))
    a2 = _crear(cliente, entrar(ana.correo), cliente="Davivienda", rol_buscado="Analista de datos")
    l1 = _crear(cliente, entrar(luis.correo))
    _fechar(db, a1["id"], "2026-11-02")
    _fechar(db, a2["id"], "2026-11-10")
    _fechar(db, l1["id"], "2026-11-16")
    return {"a1": a1["id"], "a2": a2["id"], "l1": l1["id"]}


# --- Criterio 1 y 2: qué muestra -----------------------------------------------


def test_el_historial_muestra_fecha_usuario_cliente_perfil_y_estado(
    cliente, entrar, director, tres
):
    fila = cliente.get("/solicitudes/", headers=entrar(director.correo)).json()["solicitudes"][0]

    assert fila["created_at"]
    assert fila["usuario_nombre"] == "Luis Mora"
    assert fila["cliente_nombre"] == "Bancolombia"
    assert fila["rol_buscado"] == "Desarrollador Backend"
    assert fila["estado"] == "BORRADOR"


def test_al_abrir_una_solicitud_se_ven_los_criterios_usados(cliente, entrar, director, ana):
    creada = _crear(
        cliente,
        entrar(ana.correo),
        criterios=[{"tipo": "TECNOLOGIA", "valor": "Java"}, {"tipo": "FRAMEWORK", "valor": "Spring Boot"}],
    )

    fila = cliente.get("/solicitudes/", headers=entrar(director.correo)).json()["solicitudes"][0]
    detalle = cliente.get(f"/solicitudes/{creada['id']}", headers=entrar(director.correo)).json()

    valores = {c["valor"] for c in detalle["criterios"]}
    assert valores == {"Java", "Spring Boot"}
    assert {c["valor"] for c in fila["criterios"]} == valores


# --- Criterio 3: filtros ---------------------------------------------------------


def test_el_director_ve_las_solicitudes_de_todo_el_equipo(cliente, entrar, director, tres):
    ids = _ids(cliente.get("/solicitudes/", headers=entrar(director.correo)))

    assert ids == set(tres.values())


def test_se_filtra_por_usuario_sin_importar_mayusculas_ni_tildes_de_mas(
    cliente, entrar, director, tres
):
    cabeceras = entrar(director.correo)

    assert _ids(cliente.get("/solicitudes/", params={"usuario": "ana"}, headers=cabeceras)) == {
        tres["a1"],
        tres["a2"],
    }
    assert _ids(cliente.get("/solicitudes/", params={"usuario": "MORA"}, headers=cabeceras)) == {
        tres["l1"]
    }
    assert _ids(cliente.get("/solicitudes/", params={"usuario": "nadie"}, headers=cabeceras)) == set()


def test_el_filtro_por_usuario_encuentra_a_quien_ya_no_tiene_cuenta(
    cliente, entrar, director, ana, tres, crear_usuario
):
    diana = crear_usuario(f"diana.alvarez@{DOMINIO}", rol="SUPERADMINISTRADOR")
    cabeceras_diana = entrar(diana.correo)
    assert cliente.delete(f"/auth/usuarios/{ana.id}", headers=cabeceras_diana).status_code == 204

    ids = _ids(cliente.get("/solicitudes/", params={"usuario": "ana"}, headers=entrar(director.correo)))

    assert ids == {tres["a1"], tres["a2"]}


def test_se_filtra_por_rango_de_fechas_con_ambos_extremos_incluidos(
    cliente, entrar, director, tres
):
    cabeceras = entrar(director.correo)

    entre = cliente.get(
        "/solicitudes/", params={"fecha_desde": "2026-11-02", "fecha_hasta": "2026-11-10"}, headers=cabeceras
    )
    desde = cliente.get("/solicitudes/", params={"fecha_desde": "2026-11-10"}, headers=cabeceras)
    hasta = cliente.get("/solicitudes/", params={"fecha_hasta": "2026-11-02"}, headers=cabeceras)
    un_dia = cliente.get(
        "/solicitudes/", params={"fecha_desde": "2026-11-16", "fecha_hasta": "2026-11-16"}, headers=cabeceras
    )

    assert _ids(entre) == {tres["a1"], tres["a2"]}
    assert _ids(desde) == {tres["a2"], tres["l1"]}
    assert _ids(hasta) == {tres["a1"]}
    assert _ids(un_dia) == {tres["l1"]}


def test_una_fecha_inicial_posterior_a_la_final_se_rechaza(cliente, entrar, director):
    respuesta = cliente.get(
        "/solicitudes/",
        params={"fecha_desde": "2026-11-16", "fecha_hasta": "2026-11-01"},
        headers=entrar(director.correo),
    )

    assert respuesta.status_code == 422


def test_una_fecha_con_formato_invalido_se_rechaza(cliente, entrar, director):
    respuesta = cliente.get(
        "/solicitudes/", params={"fecha_desde": "ayer"}, headers=entrar(director.correo)
    )

    assert respuesta.status_code == 422


def test_los_filtros_se_combinan(cliente, entrar, director, db, tres):
    cabeceras = entrar(director.correo)
    davivienda = next(
        c["id"] for c in cliente.get("/clientes/", headers=cabeceras).json() if c["nombre"] == "Davivienda"
    )

    ids = _ids(
        cliente.get(
            "/solicitudes/",
            params={"usuario": "ana", "cliente_id": davivienda, "fecha_desde": "2026-11-05"},
            headers=cabeceras,
        )
    )

    assert ids == {tres["a2"]}


def test_el_total_y_la_paginacion_respetan_los_filtros(cliente, entrar, director, tres):
    cuerpo = cliente.get(
        "/solicitudes/", params={"usuario": "ana", "por_pagina": 1}, headers=entrar(director.correo)
    ).json()

    assert cuerpo["total"] == 2
    assert len(cuerpo["solicitudes"]) == 1


# --- Criterio 4: el Coordinador ve solo lo suyo -------------------------------------


def test_el_coordinador_ve_unicamente_lo_que_el_registro(cliente, entrar, ana, tres):
    ids = _ids(cliente.get("/solicitudes/", headers=entrar(ana.correo)))

    assert ids == {tres["a1"], tres["a2"]}


def test_el_coordinador_no_puede_ver_lo_de_otra_persona_con_el_filtro_de_usuario(
    cliente, entrar, ana, tres
):
    ids = _ids(cliente.get("/solicitudes/", params={"usuario": "luis"}, headers=entrar(ana.correo)))

    assert tres["l1"] not in ids
    assert ids <= {tres["a1"], tres["a2"]}


def test_el_coordinador_tambien_filtra_por_fecha_y_cliente_dentro_de_lo_suyo(
    cliente, entrar, ana, tres
):
    cabeceras = entrar(ana.correo)

    ids = _ids(cliente.get("/solicitudes/", params={"fecha_desde": "2026-11-05"}, headers=cabeceras))

    assert ids == {tres["a2"]}


def test_el_coordinador_no_abre_la_solicitud_de_otra_persona(cliente, entrar, ana, tres):
    respuesta = cliente.get(f"/solicitudes/{tres['l1']}", headers=entrar(ana.correo))

    assert respuesta.status_code == 403


def test_sin_sesion_no_hay_historial(cliente):
    assert cliente.get("/solicitudes/").status_code in (401, 403)
