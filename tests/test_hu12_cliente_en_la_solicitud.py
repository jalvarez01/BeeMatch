"""
HU-12, registro del cliente asociado a la solicitud. Criterios:

    1. El cliente es obligatorio: sin él no se guarda ni se ejecuta la solicitud,
       y el mensaje lo dice con claridad.
    2. Al escribir las primeras letras se sugieren los clientes ya registrados.
    3. Un cliente no se duplica por diferencias de mayúsculas o de espacios.
    4. Cliente y proyecto se guardan junto con los criterios de búsqueda.
    5. El historial muestra el cliente y se puede filtrar por él.
    6. Las solicitudes anteriores, sin cliente, siguen funcionando.

La API se prueba completa (autenticación incluida). El worker no corre:
`despachar` se sustituye por un doble.
"""

import pytest

from backend.domain.services.solicitud_service import (
    CAMPO_CLIENTE,
    CAMPO_DESCRIPCION,
    CAMPO_ROL,
    MENSAJE_CLIENTE_OBLIGATORIO,
    campos_faltantes_busqueda,
    cliente_en_blanco,
)
from backend.infrastructure.persistence import database
from backend.infrastructure.persistence.models.busqueda import BusquedaModel
from backend.infrastructure.persistence.models.cliente import ClienteModel, ProyectoModel
from backend.infrastructure.persistence.models.solicitud import SolicitudModel
from backend.infrastructure.persistence.normalizacion import limpiar_nombre, normalizar_nombre
from backend.infrastructure.persistence.repositories.cliente_repo import ClienteRepository

DESCRIPCION = "Desarrollador Backend Java con Spring Boot y experiencia en banca."
ROL = "Desarrollador Backend"


@pytest.fixture
def cabeceras(crear_usuario, entrar):
    crear_usuario("ana@bee.com.co")
    return entrar("ana@bee.com.co")


@pytest.fixture
def cabeceras_director(crear_usuario, entrar):
    crear_usuario("dario@bee.com.co", rol="DIRECTOR")
    return entrar("dario@bee.com.co")


@pytest.fixture
def sin_worker(monkeypatch):
    import backend.api.busquedas as router

    despachos = []
    monkeypatch.setattr(router, "despachar", lambda tareas, funcion, *args: despachos.append(args))
    return despachos


def _solicitud(http, cabeceras, /, **datos) -> dict:
    """`http` es solo posicional: así `cliente=` llega a los datos y no choca con la fixture."""
    cuerpo = {"descripcion_libre": DESCRIPCION, "rol_buscado": ROL, "cliente": "Bancolombia", **datos}
    respuesta = http.post("/solicitudes/", json=cuerpo, headers=cabeceras)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _sugerencias(cliente, cabeceras, texto: str | None = None, **params) -> list[str]:
    consulta = {"q": texto, **params} if texto is not None else params
    respuesta = cliente.get("/clientes/", params=consulta, headers=cabeceras)
    assert respuesta.status_code == 200, respuesta.text
    return [c["nombre"] for c in respuesta.json()]


# --- Criterio 1: el cliente es obligatorio ------------------------------------


@pytest.mark.parametrize("cliente_enviado", [None, "", "   "], ids=["ausente", "vacio", "solo_espacios"])
def test_hu12_criterio1_no_se_guarda_una_solicitud_sin_cliente(
    cliente, cabeceras, db, cliente_enviado
):
    cuerpo = {"descripcion_libre": DESCRIPCION, "rol_buscado": ROL, "cliente": cliente_enviado}

    respuesta = cliente.post("/solicitudes/", json=cuerpo, headers=cabeceras)

    assert respuesta.status_code == 422
    assert respuesta.json()["detail"] == MENSAJE_CLIENTE_OBLIGATORIO
    assert db.query(SolicitudModel).count() == 0


def test_hu12_criterio1_tampoco_se_guarda_un_borrador_sin_cliente(cliente, cabeceras, db):
    cuerpo = {"descripcion_libre": DESCRIPCION, "guardar_como_borrador": True}

    respuesta = cliente.post("/solicitudes/", json=cuerpo, headers=cabeceras)

    assert respuesta.status_code == 422
    assert db.query(SolicitudModel).count() == 0


def test_hu12_criterio1_al_editar_no_se_puede_dejar_la_solicitud_sin_cliente(cliente, cabeceras):
    solicitud = _solicitud(cliente, cabeceras)

    respuesta = cliente.put(
        f"/solicitudes/{solicitud['id']}", json={"cliente": "   "}, headers=cabeceras
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["detail"] == MENSAJE_CLIENTE_OBLIGATORIO
    assert cliente.get(f"/solicitudes/{solicitud['id']}", headers=cabeceras).json()["cliente_nombre"] == (
        "Bancolombia"
    )


def test_hu12_criterio1_una_solicitud_sin_cliente_no_se_ejecuta(cliente, cabeceras, db, sin_worker):
    # Una solicitud anterior a HU-12: se creó sin cliente.
    usuario_id = cliente.get("/auth/yo", headers=cabeceras).json()["id"]
    anterior = SolicitudModel(descripcion_libre=DESCRIPCION, rol_buscado=ROL, usuario_id=usuario_id)
    db.add(anterior)
    db.commit()

    respuesta = cliente.post(f"/busquedas/solicitud/{anterior.id}", headers=cabeceras)

    assert respuesta.status_code == 422
    assert CAMPO_CLIENTE in respuesta.json()["detail"]
    assert db.query(BusquedaModel).count() == 0
    assert sin_worker == []


def test_hu12_criterio1_el_aviso_nombra_todo_lo_que_falta_en_el_orden_del_formulario():
    assert campos_faltantes_busqueda("", "", "") == [CAMPO_DESCRIPCION, CAMPO_CLIENTE, CAMPO_ROL]
    assert campos_faltantes_busqueda(DESCRIPCION, ROL, "Bancolombia") == []
    assert campos_faltantes_busqueda(DESCRIPCION, ROL, "  ") == [CAMPO_CLIENTE]


@pytest.mark.parametrize(("texto", "vacio"), [(None, True), ("", True), (" \t ", True), ("Acme", False)])
def test_hu12_criterio1_un_cliente_de_solo_espacios_cuenta_como_vacio(texto, vacio):
    assert cliente_en_blanco(texto) is vacio


def test_hu12_criterio1_al_completar_el_cliente_la_solicitud_se_ejecuta(
    cliente, cabeceras, db, sin_worker
):
    usuario_id = cliente.get("/auth/yo", headers=cabeceras).json()["id"]
    anterior = SolicitudModel(descripcion_libre=DESCRIPCION, rol_buscado=ROL, usuario_id=usuario_id)
    db.add(anterior)
    db.commit()
    assert cliente.post(f"/busquedas/solicitud/{anterior.id}", headers=cabeceras).status_code == 422

    completada = cliente.put(
        f"/solicitudes/{anterior.id}", json={"cliente": "Bancolombia"}, headers=cabeceras
    )
    assert completada.status_code == 200

    respuesta = cliente.post(f"/busquedas/solicitud/{anterior.id}", headers=cabeceras)

    assert respuesta.status_code == 202
    assert len(sin_worker) == 1


# --- Criterio 2: sugerencias de clientes registrados ---------------------------


@pytest.fixture
def clientes_registrados(db):
    repo = ClienteRepository(db)
    for nombre in ("Bancolombia", "Banco Agrario", "Davivienda", "Grupo Bancolombia Seguros"):
        repo.get_o_crear(nombre)


def test_hu12_criterio2_las_primeras_letras_sugieren_los_clientes_registrados(
    cliente, cabeceras, clientes_registrados
):
    assert _sugerencias(cliente, cabeceras, "ban") == [
        "Banco Agrario",
        "Bancolombia",
        "Grupo Bancolombia Seguros",
    ]


def test_hu12_criterio2_las_sugerencias_no_distinguen_mayusculas_ni_espacios_de_mas(
    cliente, cabeceras, clientes_registrados
):
    assert _sugerencias(cliente, cabeceras, "  DAVI ") == ["Davivienda"]


def test_hu12_criterio2_los_que_empiezan_por_el_texto_van_antes_que_los_de_una_palabra_interna(
    cliente, cabeceras, clientes_registrados
):
    assert _sugerencias(cliente, cabeceras, "bancol") == ["Bancolombia", "Grupo Bancolombia Seguros"]


def test_hu12_criterio2_sin_coincidencias_no_hay_sugerencias(cliente, cabeceras, clientes_registrados):
    assert _sugerencias(cliente, cabeceras, "zzz") == []


def test_hu12_criterio2_los_comodines_de_sql_se_buscan_literalmente(
    cliente, cabeceras, clientes_registrados
):
    assert _sugerencias(cliente, cabeceras, "%") == []
    assert _sugerencias(cliente, cabeceras, "_") == []


def test_hu12_criterio2_las_sugerencias_respetan_el_limite(cliente, cabeceras, clientes_registrados):
    assert len(_sugerencias(cliente, cabeceras, "ban", limite=2)) == 2


def test_hu12_criterio2_sin_texto_se_listan_los_clientes_por_orden_alfabetico(
    cliente, cabeceras, clientes_registrados
):
    assert _sugerencias(cliente, cabeceras) == [
        "Banco Agrario",
        "Bancolombia",
        "Davivienda",
        "Grupo Bancolombia Seguros",
    ]


def test_hu12_criterio2_las_sugerencias_exigen_sesion(cliente, clientes_registrados):
    assert cliente.get("/clientes/", params={"q": "ban"}).status_code in (401, 403)


def test_hu12_criterio2_seleccionar_una_sugerencia_reutiliza_ese_cliente(
    cliente, cabeceras, clientes_registrados, db
):
    elegido = cliente.get("/clientes/", params={"q": "davi"}, headers=cabeceras).json()[0]
    antes = db.query(ClienteModel).count()

    solicitud = _solicitud(cliente, cabeceras, cliente=elegido["nombre"])

    assert solicitud["cliente_id"] == elegido["id"]
    assert db.query(ClienteModel).count() == antes


# --- Criterio 3: sin duplicados por mayúsculas ni espacios ---------------------


@pytest.mark.parametrize(
    "variante", ["ACME S.A.S.", "acme s.a.s.", "  Acme   S.A.S.  ", "Acme\tS.A.S."]
)
def test_hu12_criterio3_las_variantes_de_un_cliente_no_crean_otro_registro(
    cliente, cabeceras, db, variante
):
    primera = _solicitud(cliente, cabeceras, cliente="Acme S.A.S.")

    segunda = _solicitud(cliente, cabeceras, cliente=variante)

    assert segunda["cliente_id"] == primera["cliente_id"]
    assert segunda["cliente_nombre"] == "Acme S.A.S."
    assert db.query(ClienteModel).count() == 1


def test_hu12_criterio3_se_conserva_el_nombre_con_el_que_se_registro_limpio_de_espacios(
    cliente, cabeceras
):
    solicitud = _solicitud(cliente, cabeceras, cliente="   Banco    de   Bogotá ")

    assert solicitud["cliente_nombre"] == "Banco de Bogotá"


def test_hu12_criterio3_clientes_distintos_siguen_siendo_distintos(cliente, cabeceras, db):
    _solicitud(cliente, cabeceras, cliente="Banco Uno")
    _solicitud(cliente, cabeceras, cliente="Banco Dos")

    assert db.query(ClienteModel).count() == 2


def test_hu12_criterio3_el_proyecto_tampoco_se_duplica_dentro_del_mismo_cliente(
    cliente, cabeceras, db
):
    primera = _solicitud(cliente, cabeceras, cliente="Acme", proyecto="Core Bancario")
    segunda = _solicitud(cliente, cabeceras, cliente="ACME", proyecto="  core   bancario ")

    assert segunda["proyecto_id"] == primera["proyecto_id"]
    assert segunda["proyecto_nombre"] == "Core Bancario"
    assert db.query(ProyectoModel).count() == 1


def test_hu12_criterio3_el_mismo_nombre_de_proyecto_en_otro_cliente_es_otro_proyecto(
    cliente, cabeceras, db
):
    uno = _solicitud(cliente, cabeceras, cliente="Acme", proyecto="Migración")
    otro = _solicitud(cliente, cabeceras, cliente="Beta", proyecto="Migración")

    assert uno["proyecto_id"] != otro["proyecto_id"]
    assert db.query(ProyectoModel).count() == 2


@pytest.mark.parametrize(
    ("nombre", "limpio", "normalizado"),
    [
        ("  Banco   X ", "Banco X", "banco x"),
        ("ACME", "ACME", "acme"),
        ("Straße", "Straße", "strasse"),
        ("", "", ""),
        (None, "", ""),
    ],
)
def test_hu12_criterio3_normalizacion_de_nombres(nombre, limpio, normalizado):
    assert limpiar_nombre(nombre) == limpio
    assert normalizar_nombre(nombre) == normalizado


def test_hu12_criterio3_dos_altas_simultaneas_del_mismo_cliente_terminan_en_un_registro(db, monkeypatch):
    """La segunda alta pierde la carrera contra el índice único y devuelve el registro ganador."""
    repo = ClienteRepository(db)
    ganador = repo.get_o_crear("Acme")

    # La primera consulta no ve al ganador (todavía no se había guardado); la segunda sí.
    consultas = iter([None, ganador])
    monkeypatch.setattr(repo, "get_por_nombre", lambda nombre: next(consultas))

    assert repo.get_o_crear("Acme").id == ganador.id
    assert db.query(ClienteModel).count() == 1


# --- Criterio 4: cliente y proyecto junto con los criterios --------------------


def test_hu12_criterio4_cliente_y_proyecto_se_guardan_con_los_criterios(cliente, cabeceras):
    solicitud = _solicitud(
        cliente,
        cabeceras,
        cliente="Bancolombia",
        proyecto="Core Bancario",
        experiencia_min=5,
        criterios=[{"tipo": "TECNOLOGIA", "valor": "Java"}, {"tipo": "IDIOMA", "valor": "Inglés B2"}],
    )

    guardada = cliente.get(f"/solicitudes/{solicitud['id']}", headers=cabeceras).json()

    assert guardada["cliente_nombre"] == "Bancolombia"
    assert guardada["proyecto_nombre"] == "Core Bancario"
    assert guardada["experiencia_min"] == 5
    assert sorted(c["valor"] for c in guardada["criterios"]) == ["Inglés B2", "Java"]


def test_hu12_criterio4_el_proyecto_es_opcional(cliente, cabeceras):
    solicitud = _solicitud(cliente, cabeceras, cliente="Bancolombia")

    assert solicitud["proyecto_id"] is None
    assert solicitud["proyecto_nombre"] is None


def test_hu12_criterio4_al_ejecutar_la_ejecucion_guarda_cliente_y_proyecto(
    cliente, cabeceras, sin_worker
):
    solicitud = _solicitud(cliente, cabeceras, cliente="Bancolombia", proyecto="Core Bancario")

    busqueda = cliente.post(f"/busquedas/solicitud/{solicitud['id']}", headers=cabeceras).json()

    parametros = cliente.get(f"/busquedas/{busqueda['id']}", headers=cabeceras).json()["parametros"]
    assert parametros["cliente"] == "Bancolombia"
    assert parametros["proyecto"] == "Core Bancario"


def test_hu12_criterio4_al_editar_sin_enviar_cliente_se_conserva(cliente, cabeceras):
    solicitud = _solicitud(cliente, cabeceras, cliente="Bancolombia", proyecto="Core Bancario")

    editada = cliente.put(
        f"/solicitudes/{solicitud['id']}", json={"experiencia_min": 3}, headers=cabeceras
    ).json()

    assert editada["cliente_nombre"] == "Bancolombia"
    assert editada["proyecto_nombre"] == "Core Bancario"


def test_hu12_criterio4_al_cambiar_de_cliente_se_descarta_el_proyecto_del_cliente_anterior(
    cliente, cabeceras
):
    solicitud = _solicitud(cliente, cabeceras, cliente="Bancolombia", proyecto="Core Bancario")

    editada = cliente.put(
        f"/solicitudes/{solicitud['id']}", json={"cliente": "Davivienda"}, headers=cabeceras
    ).json()

    assert editada["cliente_nombre"] == "Davivienda"
    assert editada["proyecto_nombre"] is None


def test_hu12_criterio4_se_puede_cambiar_el_proyecto_sin_tocar_el_cliente(cliente, cabeceras):
    solicitud = _solicitud(cliente, cabeceras, cliente="Bancolombia", proyecto="Core Bancario")

    editada = cliente.put(
        f"/solicitudes/{solicitud['id']}", json={"proyecto": "Canales Digitales"}, headers=cabeceras
    ).json()

    assert editada["cliente_nombre"] == "Bancolombia"
    assert editada["proyecto_nombre"] == "Canales Digitales"


def test_hu12_criterio4_un_proyecto_vacio_quita_el_proyecto(cliente, cabeceras):
    solicitud = _solicitud(cliente, cabeceras, cliente="Bancolombia", proyecto="Core Bancario")

    editada = cliente.put(
        f"/solicitudes/{solicitud['id']}", json={"proyecto": "  "}, headers=cabeceras
    ).json()

    assert editada["proyecto_nombre"] is None
    assert editada["cliente_nombre"] == "Bancolombia"


def test_hu12_criterio4_duplicar_conserva_cliente_y_proyecto(cliente, cabeceras):
    solicitud = _solicitud(cliente, cabeceras, cliente="Bancolombia", proyecto="Core Bancario")

    copia = cliente.post(f"/solicitudes/{solicitud['id']}/duplicar", headers=cabeceras).json()

    assert copia["cliente_nombre"] == "Bancolombia"
    assert copia["proyecto_nombre"] == "Core Bancario"


# --- Criterio 5: el cliente en el historial ------------------------------------


@pytest.fixture
def historial_con_clientes(cliente, cabeceras):
    return {
        "banco_1": _solicitud(cliente, cabeceras, cliente="Bancolombia", proyecto="Core"),
        "banco_2": _solicitud(cliente, cabeceras, cliente="bancolombia", rol_buscado="QA Automation"),
        "retail": _solicitud(cliente, cabeceras, cliente="Éxito", proyecto="Tienda Online"),
    }


def test_hu12_criterio5_el_historial_muestra_el_cliente_y_el_proyecto(
    cliente, cabeceras_director, historial_con_clientes
):
    respuesta = cliente.get("/solicitudes/", headers=cabeceras_director).json()

    por_id = {s["id"]: s for s in respuesta["solicitudes"]}
    assert por_id[historial_con_clientes["banco_1"]["id"]]["cliente_nombre"] == "Bancolombia"
    assert por_id[historial_con_clientes["banco_1"]["id"]]["proyecto_nombre"] == "Core"
    assert por_id[historial_con_clientes["retail"]["id"]]["cliente_nombre"] == "Éxito"


def test_hu12_criterio5_se_filtra_el_historial_por_cliente(
    cliente, cabeceras_director, historial_con_clientes
):
    cliente_id = historial_con_clientes["banco_1"]["cliente_id"]

    respuesta = cliente.get(
        "/solicitudes/", params={"cliente_id": cliente_id}, headers=cabeceras_director
    ).json()

    assert respuesta["total"] == 2
    assert {s["id"] for s in respuesta["solicitudes"]} == {
        historial_con_clientes["banco_1"]["id"],
        historial_con_clientes["banco_2"]["id"],
    }
    assert {s["cliente_nombre"] for s in respuesta["solicitudes"]} == {"Bancolombia"}


def test_hu12_criterio5_el_filtro_por_cliente_se_combina_con_el_estado_y_el_total_es_el_filtrado(
    cliente, cabeceras_director, historial_con_clientes
):
    cliente_id = historial_con_clientes["banco_1"]["cliente_id"]

    con_estado = cliente.get(
        "/solicitudes/",
        params={"cliente_id": cliente_id, "estado": "PROCESADA"},
        headers=cabeceras_director,
    ).json()
    paginado = cliente.get(
        "/solicitudes/",
        params={"cliente_id": cliente_id, "por_pagina": 1},
        headers=cabeceras_director,
    ).json()

    assert con_estado["total"] == 0
    assert con_estado["solicitudes"] == []
    assert paginado["total"] == 2
    assert len(paginado["solicitudes"]) == 1


def test_hu12_criterio5_un_cliente_sin_solicitudes_devuelve_el_historial_vacio(
    cliente, cabeceras_director, historial_con_clientes
):
    respuesta = cliente.get(
        "/solicitudes/", params={"cliente_id": "no-existe"}, headers=cabeceras_director
    ).json()

    assert respuesta["total"] == 0
    assert respuesta["solicitudes"] == []


@pytest.mark.parametrize(
    ("texto", "esperadas"),
    [("banco", 2), ("tienda", 1), ("qa auto", 1), ("xyz", 0)],
    ids=["por_cliente", "por_proyecto", "por_rol", "sin_coincidencias"],
)
def test_hu12_criterio5_el_buscador_del_historial_encuentra_por_rol_cliente_o_proyecto(
    cliente, cabeceras_director, historial_con_clientes, texto, esperadas
):
    respuesta = cliente.get(
        "/solicitudes/", params={"texto": texto}, headers=cabeceras_director
    ).json()

    assert respuesta["total"] == esperadas
    assert len(respuesta["solicitudes"]) == esperadas


# --- Criterio 6: compatibilidad con solicitudes anteriores ---------------------


def test_hu12_criterio6_una_solicitud_anterior_sin_cliente_sigue_en_el_historial(
    cliente, cabeceras_director, db, historial_con_clientes
):
    usuario_id = cliente.get("/auth/yo", headers=cabeceras_director).json()["id"]
    anterior = SolicitudModel(descripcion_libre=DESCRIPCION, rol_buscado=ROL, usuario_id=usuario_id)
    db.add(anterior)
    db.commit()

    respuesta = cliente.get("/solicitudes/", headers=cabeceras_director).json()

    fila = next(s for s in respuesta["solicitudes"] if s["id"] == anterior.id)
    assert respuesta["total"] == 4
    assert fila["cliente_id"] is None
    assert fila["cliente_nombre"] is None


def test_hu12_criterio6_los_clientes_registrados_antes_de_la_columna_se_normalizan_al_arrancar(db):
    # Un cliente y un proyecto de antes de HU-12: sin nombre comparable.
    antiguo = ClienteModel(nombre="Acme")
    db.add(antiguo)
    db.commit()
    db.add(ProyectoModel(nombre="Core", cliente_id=antiguo.id))
    db.commit()

    database._rellenar_nombres_normalizados()

    db.expire_all()
    assert db.get(ClienteModel, antiguo.id).nombre_normalizado == "acme"
    assert db.query(ProyectoModel).one().nombre_normalizado == "core"
    # Y ya cuentan para no duplicar.
    assert ClienteRepository(db).get_o_crear("  ACME ").id == antiguo.id
    assert db.query(ClienteModel).count() == 1


def test_hu12_criterio6_las_columnas_nuevas_se_agregan_a_una_base_existente(db):
    from sqlalchemy import inspect, text

    # Se simula una base creada antes de HU-12 y HU-15 quitándole las columnas nuevas.
    with database.engine.begin() as conexion:
        conexion.execute(text("DROP INDEX IF EXISTS ix_clientes_nombre_normalizado"))
        conexion.execute(text("ALTER TABLE clientes DROP COLUMN nombre_normalizado"))
        conexion.execute(text("ALTER TABLE busquedas DROP COLUMN parametros_json"))
    db.close()
    # SQLite no avisa a las otras conexiones del pool de que el esquema cambió: una que ya
    # lo había leído (por ejemplo, la de otra prueba que arrancó la app) lo devolvería viejo.
    database.engine.dispose()

    database._agregar_columnas_faltantes()

    columnas_clientes = {c["name"] for c in inspect(database.engine).get_columns("clientes")}
    columnas_busquedas = {c["name"] for c in inspect(database.engine).get_columns("busquedas")}
    assert "nombre_normalizado" in columnas_clientes
    assert "parametros_json" in columnas_busquedas
