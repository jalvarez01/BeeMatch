"""
HU-06: consulta de la bitácora de actividad.

Criterio 1 - se muestran fecha, hora, usuario, rol y acción.
Criterio 2 - se filtra por usuario o por rango de fechas.
Criterio 3 - cada búsqueda de candidatos queda registrada.
Criterio 4 - Coordinador y Director no entran al módulo.

Todo entra por la API con sesiones reales. La búsqueda se despacha a un doble
para no depender del servicio de IA; el camino del worker se prueba aparte.
"""

from datetime import UTC, date, datetime, timedelta

import pytest

from backend.domain.services.bitacora_service import (
    ACCION_BUSQUEDA_EJECUTADA,
    ACCION_LOGIN,
    ACCION_SOLICITUD_CREADA,
    BitacoraService,
)
from backend.infrastructure.persistence.models.configuracion import RegistroBitacoraModel
from backend.infrastructure.persistence.repositories.usuario_repo import UsuarioRepository

RUTA = "/configuracion/bitacora"
DESCRIPCION = "Backend Java para un core bancario con Spring Boot."
ROL = "Desarrollador Backend"


@pytest.fixture
def admin(crear_usuario, entrar):
    crear_usuario("admin@bee.com.co", rol="ADMINISTRADOR", nombre="Admin Bee")
    return entrar("admin@bee.com.co")


@pytest.fixture
def sin_worker(monkeypatch):
    """La búsqueda se crea pero no corre: no hay servicio de IA en las pruebas."""
    import backend.api.busquedas as router

    monkeypatch.setattr(router, "despachar", lambda *args, **kwargs: None)


def _eventos(cliente, cabeceras, **filtros):
    respuesta = cliente.get(RUTA, params=filtros, headers=cabeceras)
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def _fijar_fecha(db, registro_id: str, fecha: datetime):
    registro = db.get(RegistroBitacoraModel, registro_id)
    registro.created_at = fecha
    db.commit()


# --- Criterio 1: fecha, hora, usuario, rol y acción --------------------------


def test_hu06_criterio1_cada_evento_trae_fecha_hora_usuario_rol_y_accion(cliente, admin):
    cuerpo = _eventos(cliente, admin)

    login = next(e for e in cuerpo["items"] if e["accion"] == ACCION_LOGIN)
    momento = datetime.fromisoformat(login["created_at"])
    assert momento.date() == datetime.now(UTC).date()
    # La fecha viaja con zona (UTC) para que el navegador la muestre en hora local.
    assert momento.utcoffset() == timedelta(0)
    assert momento.time() is not None
    assert login["usuario_nombre"] == "Admin Bee"
    assert login["usuario_correo"] == "admin@bee.com.co"
    assert login["rol"] == "ADMINISTRADOR"


def test_hu06_criterio1_el_rol_es_el_que_tenia_al_momento_del_evento(cliente, admin, db):
    admin_id = _eventos(cliente, admin)["items"][0]["usuario_id"]
    UsuarioRepository(db).actualizar_rol(admin_id, "DIRECTOR")

    login = next(e for e in _eventos_en_base(db) if e["accion"] == ACCION_LOGIN)

    assert login["rol"] == "ADMINISTRADOR"


def _eventos_en_base(db):
    _, items = BitacoraService(db).listar(limite=100)
    return items


def test_hu06_criterio1_un_evento_anterior_sin_rol_guardado_usa_el_rol_actual(db, crear_usuario):
    usuario = crear_usuario("vieja@bee.com.co", rol="DIRECTOR")
    db.add(RegistroBitacoraModel(usuario_id=usuario.id, accion="LOGIN"))
    db.commit()

    evento = _eventos_en_base(db)[0]

    assert evento["rol"] == "DIRECTOR"


def test_hu06_criterio1_la_lista_va_del_evento_mas_reciente_al_mas_antiguo(cliente, admin, db):
    ahora = datetime.now(UTC)
    for minutos, accion in [(30, "ACCION_A"), (10, "ACCION_B"), (20, "ACCION_C")]:
        registro = BitacoraService(db).registrar(accion)
        _fijar_fecha(db, registro.id, ahora - timedelta(minutes=minutos))

    acciones = [e["accion"] for e in _eventos(cliente, admin)["items"] if e["accion"].startswith("ACCION_")]

    assert acciones == ["ACCION_B", "ACCION_C", "ACCION_A"]


def test_hu06_criterio1_la_lista_se_pagina_e_informa_el_total(cliente, admin, db):
    for i in range(7):
        BitacoraService(db).registrar(f"EVENTO_{i}")
    total = _eventos(cliente, admin)["total"]

    pagina = _eventos(cliente, admin, limite=3, desplazamiento=3)

    assert pagina["total"] == total
    assert len(pagina["items"]) == 3
    assert pagina["limite"] == 3
    assert pagina["desplazamiento"] == 3


# --- Criterio 2: filtros por usuario y por fechas ----------------------------


def test_hu06_criterio2_filtra_por_usuario(cliente, admin, crear_usuario, entrar):
    crear_usuario("ana@bee.com.co", rol="COORDINADOR", nombre="Ana")
    entrar("ana@bee.com.co")
    todos = _eventos(cliente, admin)["items"]
    ana = next(e for e in todos if e["usuario_correo"] == "ana@bee.com.co")

    solo_ana = _eventos(cliente, admin, usuario_id=ana["usuario_id"])

    assert solo_ana["total"] == 1
    assert {e["usuario_correo"] for e in solo_ana["items"]} == {"ana@bee.com.co"}
    assert solo_ana["total"] < len(todos)


def test_hu06_criterio2_un_usuario_sin_eventos_devuelve_una_lista_vacia(cliente, admin):
    cuerpo = _eventos(cliente, admin, usuario_id="no-existe")

    assert cuerpo["total"] == 0
    assert cuerpo["items"] == []


def test_hu06_criterio2_filtra_por_rango_de_fechas_con_extremos_inclusivos(cliente, admin, db):
    dia = lambda d: datetime(2026, 3, d, 12, 0, tzinfo=UTC)  # noqa: E731
    for d, accion in [
        (9, "FUERA_ANTES"),
        (10, "BORDE_INICIO"),
        (12, "DENTRO"),
        (15, "BORDE_FIN"),
        (16, "FUERA_DESPUES"),
    ]:
        _fijar_fecha(db, BitacoraService(db).registrar(accion).id, dia(d))

    cuerpo = _eventos(cliente, admin, fecha_desde="2026-03-10", fecha_hasta="2026-03-15")

    assert {e["accion"] for e in cuerpo["items"]} == {"BORDE_INICIO", "DENTRO", "BORDE_FIN"}


def test_hu06_criterio2_la_fecha_final_incluye_todo_ese_dia(cliente, admin, db):
    tarde = datetime(2026, 3, 15, 23, 59, tzinfo=UTC)
    _fijar_fecha(db, BitacoraService(db).registrar("TARDE").id, tarde)

    cuerpo = _eventos(cliente, admin, fecha_desde="2026-03-15", fecha_hasta="2026-03-15")

    assert [e["accion"] for e in cuerpo["items"]] == ["TARDE"]


def test_hu06_criterio2_se_combinan_usuario_y_fechas(cliente, admin, db, crear_usuario):
    otro = crear_usuario("otro@bee.com.co", rol="DIRECTOR")
    dia = datetime(2026, 4, 2, 9, 0, tzinfo=UTC)
    _fijar_fecha(db, BitacoraService(db).registrar("DEL_OTRO", usuario_id=otro.id).id, dia)
    _fijar_fecha(db, BitacoraService(db).registrar("SIN_USUARIO").id, dia)

    cuerpo = _eventos(cliente, admin, usuario_id=otro.id, fecha_desde="2026-04-02", fecha_hasta="2026-04-02")

    assert [e["accion"] for e in cuerpo["items"]] == ["DEL_OTRO"]


def test_hu06_criterio2_un_rango_invertido_responde_422(cliente, admin):
    respuesta = cliente.get(
        RUTA, params={"fecha_desde": "2026-03-20", "fecha_hasta": "2026-03-10"}, headers=admin
    )

    assert respuesta.status_code == 422
    assert "fecha inicial" in respuesta.json()["detail"]


def test_hu06_criterio2_una_sola_fecha_es_valida(cliente, admin):
    hoy = date.today().isoformat()

    assert cliente.get(RUTA, params={"fecha_desde": hoy}, headers=admin).status_code == 200
    assert cliente.get(RUTA, params={"fecha_hasta": hoy}, headers=admin).status_code == 200


def test_hu06_criterio2_una_fecha_mal_escrita_responde_422(cliente, admin):
    assert cliente.get(RUTA, params={"fecha_desde": "ayer"}, headers=admin).status_code == 422


# --- Criterio 3: cada búsqueda queda registrada ------------------------------


def _preparar_busqueda(cliente, crear_usuario, entrar, correo="ana@bee.com.co"):
    usuario = crear_usuario(correo, rol="COORDINADOR", nombre="Ana")
    cabeceras = entrar(correo)
    solicitud = cliente.post(
        "/solicitudes/",
        json={"descripcion_libre": DESCRIPCION, "rol_buscado": ROL},
        headers=cabeceras,
    ).json()["id"]
    return usuario, cabeceras, solicitud


def _busquedas_registradas(db):
    return (
        db.query(RegistroBitacoraModel)
        .filter(RegistroBitacoraModel.accion == ACCION_BUSQUEDA_EJECUTADA)
        .all()
    )


def test_hu06_criterio3_ejecutar_una_busqueda_deja_un_evento_con_su_id(
    cliente, admin, crear_usuario, entrar, sin_worker, db
):
    usuario, cabeceras, solicitud = _preparar_busqueda(cliente, crear_usuario, entrar)

    busqueda_id = cliente.post(f"/busquedas/solicitud/{solicitud}", headers=cabeceras).json()["id"]

    eventos = _busquedas_registradas(db)
    assert len(eventos) == 1
    assert eventos[0].entidad == "busqueda"
    assert eventos[0].entidad_id == busqueda_id
    assert eventos[0].usuario_id == usuario.id
    assert eventos[0].rol == "COORDINADOR"
    visto = [e for e in _eventos(cliente, admin)["items"] if e["accion"] == ACCION_BUSQUEDA_EJECUTADA]
    assert [e["usuario_nombre"] for e in visto] == ["Ana"]


def test_hu06_criterio3_dos_busquedas_dejan_dos_eventos(cliente, crear_usuario, entrar, sin_worker, db):
    _, cabeceras, solicitud = _preparar_busqueda(cliente, crear_usuario, entrar)
    primera = cliente.post(f"/busquedas/solicitud/{solicitud}", headers=cabeceras).json()["id"]
    # Mientras la primera sigue viva no se lanza otra encima (HU-22); se da por terminada.
    from backend.infrastructure.persistence.models.busqueda import BUSQUEDA_COMPLETADA
    from backend.infrastructure.persistence.repositories.busqueda_repo import BusquedaRepository

    BusquedaRepository(db).finalizar(primera, estado=BUSQUEDA_COMPLETADA)

    segunda = cliente.post(f"/busquedas/solicitud/{solicitud}", headers=cabeceras).json()["id"]

    assert segunda != primera
    assert {e.entidad_id for e in _busquedas_registradas(db)} == {primera, segunda}


def test_hu06_criterio3_un_doble_clic_no_registra_la_misma_busqueda_dos_veces(
    cliente, crear_usuario, entrar, sin_worker, db
):
    _, cabeceras, solicitud = _preparar_busqueda(cliente, crear_usuario, entrar)

    cliente.post(f"/busquedas/solicitud/{solicitud}", headers=cabeceras)
    cliente.post(f"/busquedas/solicitud/{solicitud}", headers=cabeceras)

    assert len(_busquedas_registradas(db)) == 1


def test_hu06_criterio3_una_busqueda_rechazada_por_validacion_no_se_registra(
    cliente, crear_usuario, entrar, sin_worker, db
):
    crear_usuario("ana@bee.com.co")
    cabeceras = entrar("ana@bee.com.co")
    solicitud = cliente.post(
        "/solicitudes/", json={"descripcion_libre": DESCRIPCION}, headers=cabeceras
    ).json()["id"]

    assert cliente.post(f"/busquedas/solicitud/{solicitud}", headers=cabeceras).status_code == 422

    assert _busquedas_registradas(db) == []


def test_hu06_criterio3_el_worker_no_duplica_el_evento_de_la_busqueda(
    cliente, crear_usuario, entrar, sin_worker, db, monkeypatch
):
    """Camino del worker: ejecutar la búsqueda ya creada no agrega otro evento."""
    import backend.workers.busqueda_worker as worker

    _, cabeceras, solicitud = _preparar_busqueda(cliente, crear_usuario, entrar)
    busqueda_id = cliente.post(f"/busquedas/solicitud/{solicitud}", headers=cabeceras).json()["id"]
    ejecutadas = []
    monkeypatch.setattr(worker, "_sincronizar_repositorio", lambda: None)
    monkeypatch.setattr(worker.BusquedaService, "ejecutar", lambda self, bid: ejecutadas.append(bid))

    worker.ejecutar_busqueda(busqueda_id)

    assert ejecutadas == [busqueda_id]
    assert len(_busquedas_registradas(db)) == 1


def test_hu06_criterio3_la_solicitud_tambien_queda_en_la_bitacora(
    cliente, admin, crear_usuario, entrar, sin_worker
):
    _preparar_busqueda(cliente, crear_usuario, entrar)

    acciones = {e["accion"] for e in _eventos(cliente, admin)["items"]}

    assert ACCION_SOLICITUD_CREADA in acciones


# --- Criterio 4: solo el administrador ---------------------------------------


@pytest.mark.parametrize("rol", ["DIRECTOR", "COORDINADOR"])
def test_hu06_criterio4_director_y_coordinador_reciben_403(cliente, crear_usuario, entrar, rol):
    crear_usuario("otro@bee.com.co", rol=rol)
    cabeceras = entrar("otro@bee.com.co")

    respuesta = cliente.get(RUTA, headers=cabeceras)

    assert respuesta.status_code == 403


def test_hu06_criterio4_sin_token_responde_401(cliente):
    assert cliente.get(RUTA).status_code == 401


def test_hu06_criterio4_el_administrador_si_entra(cliente, admin):
    assert cliente.get(RUTA, headers=admin).status_code == 200


def test_hu06_criterio4_la_superadministradora_tambien_entra(cliente, crear_usuario, entrar):
    crear_usuario("diana@bee.com.co", rol="SUPERADMINISTRADOR")

    assert cliente.get(RUTA, headers=entrar("diana@bee.com.co")).status_code == 200
