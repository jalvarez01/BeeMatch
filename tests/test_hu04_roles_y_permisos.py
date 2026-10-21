"""
HU-04 — permisos por rol: quién ve qué.

El Coordinador solo trabaja con lo que él registró; Director, Administrador y la
superusuaria ven el trabajo de toda el área. Todas las pruebas pasan por la API
real con tokens reales y una base temporal.
"""

import pytest

from backend.infrastructure.persistence.models.busqueda import (
    BUSQUEDA_COMPLETADA,
    BusquedaModel,
    RecomendacionModel,
)
from backend.infrastructure.persistence.models.hoja_vida import CandidatoModel, HojaDeVidaModel
from backend.infrastructure.persistence.models.solicitud import SolicitudModel


@pytest.fixture
def escenario(db, crear_usuario):
    """Una solicitud de Ana (Coordinadora) con su búsqueda y una recomendación."""
    ana = crear_usuario("ana@bee.com.co", rol="COORDINADOR")
    solicitud = SolicitudModel(
        descripcion_libre="Desarrollador backend con Java y Spring Boot.",
        rol_buscado="Backend",
        usuario_id=ana.id,
    )
    db.add(solicitud)
    db.commit()

    busqueda = BusquedaModel(solicitud_id=solicitud.id, estado=BUSQUEDA_COMPLETADA)
    hoja = HojaDeVidaModel(id_documento="doc-1", nombre_archivo="cv.pdf", formato="PDF")
    db.add_all([busqueda, hoja])
    db.commit()

    candidato = CandidatoModel(hoja_de_vida_id=hoja.id, nombre="Candidato Uno")
    db.add(candidato)
    db.commit()

    recomendacion = RecomendacionModel(
        busqueda_id=busqueda.id,
        candidato_id=candidato.id,
        posicion=1,
        puntaje_afinidad=90.0,
        nivel="ALTA",
    )
    db.add(recomendacion)
    db.commit()

    return {"ana": ana, "solicitud": solicitud, "busqueda": busqueda, "recomendacion": recomendacion}


def _rutas_de_la_busqueda(e) -> list[tuple[str, str]]:
    b, r = e["busqueda"].id, e["recomendacion"].id
    return [
        ("get", f"/busquedas/{b}"),
        ("get", f"/busquedas/{b}/estado"),
        ("get", f"/busquedas/recomendacion/{r}"),
        ("patch", f"/busquedas/recomendacion/{r}/preseleccion"),
        ("post", f"/preseleccion/{b}/exportar"),
        ("post", f"/busquedas/solicitud/{e['solicitud'].id}"),
    ]


def _llamar(cliente, metodo, ruta, cabeceras):
    cuerpo = {"preseleccionado": True} if metodo == "patch" else {"formato": "XLSX"}
    return getattr(cliente, metodo)(ruta, headers=cabeceras, **({} if metodo == "get" else {"json": cuerpo}))


def test_hu04_un_coordinador_no_ve_los_resultados_de_otro(
    cliente, escenario, crear_usuario, entrar
):
    otro = crear_usuario("luis@bee.com.co", rol="COORDINADOR")
    cabeceras = entrar(otro.correo)

    for metodo, ruta in _rutas_de_la_busqueda(escenario):
        assert _llamar(cliente, metodo, ruta, cabeceras).status_code == 403, (metodo, ruta)


def test_hu04_el_coordinador_dueno_si_ve_sus_resultados(cliente, escenario, entrar):
    cabeceras = entrar(escenario["ana"].correo)
    e = escenario

    assert cliente.get(f"/busquedas/{e['busqueda'].id}", headers=cabeceras).status_code == 200
    assert (
        cliente.get(f"/busquedas/{e['busqueda'].id}/estado", headers=cabeceras).status_code == 200
    )
    assert (
        cliente.get(
            f"/busquedas/recomendacion/{e['recomendacion'].id}", headers=cabeceras
        ).status_code
        == 200
    )


@pytest.mark.parametrize("rol", ["DIRECTOR", "ADMINISTRADOR", "SUPERADMINISTRADOR"])
def test_hu04_los_roles_con_vista_del_area_ven_resultados_ajenos(
    cliente, escenario, crear_usuario, entrar, rol
):
    usuario = crear_usuario(f"{rol.lower()}@bee.com.co", rol=rol)
    cabeceras = entrar(usuario.correo)
    e = escenario

    assert cliente.get(f"/busquedas/{e['busqueda'].id}", headers=cabeceras).status_code == 200
    assert (
        cliente.get(
            f"/busquedas/recomendacion/{e['recomendacion'].id}", headers=cabeceras
        ).status_code
        == 200
    )


def test_hu04_la_superusuaria_abre_solicitudes_ajenas(
    cliente, escenario, crear_usuario, entrar
):
    diana = crear_usuario("diana@bee.com.co", rol="SUPERADMINISTRADOR")

    respuesta = cliente.get(
        f"/solicitudes/{escenario['solicitud'].id}", headers=entrar(diana.correo)
    )

    assert respuesta.status_code == 200


def test_hu04_una_busqueda_inexistente_sigue_siendo_404(cliente, crear_usuario, entrar):
    usuario = crear_usuario("ana@bee.com.co")

    respuesta = cliente.get("/busquedas/no-existe", headers=entrar(usuario.correo))

    assert respuesta.status_code == 404


# --- Criterio 2: el rol nuevo llega al renovar la sesión ---------------------


def test_hu04_criterio2_al_renovar_la_sesion_llega_el_rol_nuevo(
    cliente, crear_usuario, entrar, db
):
    diana = crear_usuario("diana@bee.com.co", rol="SUPERADMINISTRADOR")
    admin = crear_usuario("admin@bee.com.co", rol="ADMINISTRADOR")
    cabeceras_admin = entrar(admin.correo)

    cliente.patch(
        f"/auth/usuarios/{admin.id}", json={"rol": "COORDINADOR"}, headers=entrar(diana.correo)
    )

    # Con el token que ya tenía conserva el rol de su sesión...
    assert cliente.get("/auth/usuarios", headers=cabeceras_admin).status_code == 200
    # ...pero el token renovado ya trae el rol nuevo y pierde el permiso.
    renovado = cliente.post("/auth/renovar", headers=cabeceras_admin).json()
    assert renovado["usuario"]["rol"] == "COORDINADOR"
    nuevas = {"Authorization": f"Bearer {renovado['access_token']}"}
    assert cliente.get("/auth/usuarios", headers=nuevas).status_code == 403


# --- Otros ajustes de #50 ----------------------------------------------------


def test_hu04_duplicar_una_solicitud_responde_201(cliente, escenario, entrar):
    respuesta = cliente.post(
        f"/solicitudes/{escenario['solicitud'].id}/duplicar", headers=entrar(escenario["ana"].correo)
    )

    assert respuesta.status_code == 201


def test_hu03_el_correo_debe_ser_del_dominio_corporativo(cliente, crear_usuario, entrar):
    admin = crear_usuario("admin@bee.com.co", rol="ADMINISTRADOR")
    objetivo = crear_usuario("luis@bee.com.co")
    cabeceras = entrar(admin.correo)

    crear = cliente.post(
        "/auth/usuarios",
        json={"nombre": "Marta", "correo": "marta@gmail.com", "password": "Segura1234"},
        headers=cabeceras,
    )
    editar = cliente.patch(
        f"/auth/usuarios/{objetivo.id}", json={"correo": "luis@gmail.com"}, headers=cabeceras
    )

    assert (crear.status_code, editar.status_code) == (422, 422)
