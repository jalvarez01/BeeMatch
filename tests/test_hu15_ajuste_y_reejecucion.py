"""
HU-15, edición de la solicitud y nueva ejecución de la búsqueda. Criterios:

    1. Los criterios usados en una ejecución se pueden consultar y son el punto de
       partida de la edición (incluidos el cliente y el proyecto).
    2. Al confirmar se ejecuta de nuevo el análisis con los criterios ajustados.
    3. La ejecución nueva no sobrescribe la anterior: cada una conserva fecha,
       criterios, cliente, proyecto y resultados, y se distinguen entre sí.
    4. Errores del análisis y ausencia de resultados se manejan como en el resto
       del proyecto, sin perder las ejecuciones anteriores.
    5. Un doble envío no lanza dos ejecuciones.

Los criterios 1 y 3 también tienen su parte de interfaz (formulario con los valores
iniciales, selector de ejecuciones): su lógica pura se prueba en `frontend/tests`.
Aquí se prueba la API completa y el motor de matching con dobles del buscador y del
servicio de IA, así que no hace falta red ni credenciales.
"""

from datetime import timedelta

import pytest

from backend.infrastructure.llm.llm_provider import ServicioIAError
from backend.infrastructure.persistence.models._base import utcnow
from backend.infrastructure.persistence.models.busqueda import (
    BUSQUEDA_COMPLETADA,
    BUSQUEDA_EJECUTANDO,
    BUSQUEDA_ERROR,
    BusquedaModel,
)
from backend.infrastructure.persistence.models.cliente import ClienteModel
from backend.infrastructure.persistence.models.solicitud import (
    ESTADO_ERROR,
    ESTADO_PROCESADA,
    ESTADO_SIN_COINCIDENCIAS,
    CriterioModel,
    SolicitudModel,
)
from backend.infrastructure.persistence.repositories.busqueda_repo import BusquedaRepository
from tests.test_top5_candidatos import RecuperadorFalso, _crear_candidatos, _servicio

DESCRIPCION = "Desarrollador Backend Java con Spring Boot y experiencia en banca."
ROL = "Desarrollador Backend"
AJUSTADA = "Desarrollador Backend Python con FastAPI y experiencia en seguros."


@pytest.fixture
def cabeceras(crear_usuario, entrar):
    crear_usuario("ana@bee.com.co")
    return entrar("ana@bee.com.co")


@pytest.fixture
def despachos(monkeypatch):
    """La búsqueda se encola pero el worker no corre: cada prueba decide cuándo analizar."""
    import backend.api.busquedas as router

    enviados = []
    monkeypatch.setattr(router, "despachar", lambda tareas, funcion, *args: enviados.append(args))
    return enviados


class GrabadorDeConsultas:
    """Doble de los embeddings: guarda la consulta que el motor decide analizar."""

    def __init__(self):
        self.consultas = []

    def generar_uno(self, texto):
        self.consultas.append(texto)
        return [0.1, 0.2, 0.3]


class EmbeddingsCaidos:
    def generar_uno(self, texto):
        raise ServicioIAError("timeout")


def _solicitud(http, cabeceras, /, **datos) -> dict:
    cuerpo = {
        "descripcion_libre": DESCRIPCION,
        "rol_buscado": ROL,
        "experiencia_min": 5,
        "cliente": "Bancolombia",
        "proyecto": "Core Bancario",
        "criterios": [{"tipo": "TECNOLOGIA", "valor": "Java"}],
        **datos,
    }
    respuesta = http.post("/solicitudes/", json=cuerpo, headers=cabeceras)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _ajuste(**cambios) -> dict:
    """El ajuste completo que envía el formulario: parte de los criterios originales."""
    return {
        "descripcion_libre": DESCRIPCION,
        "rol_buscado": ROL,
        "experiencia_min": 5,
        "cliente": "Bancolombia",
        "proyecto": "Core Bancario",
        "criterios": [{"tipo": "TECNOLOGIA", "valor": "Java"}],
        **cambios,
    }


def _ejecutar(http, cabeceras, solicitud_id: str) -> str:
    respuesta = http.post(f"/busquedas/solicitud/{solicitud_id}", headers=cabeceras)
    assert respuesta.status_code == 202, respuesta.text
    return respuesta.json()["id"]


def _reejecutar(http, cabeceras, solicitud_id: str, ajuste: dict):
    return http.post(f"/busquedas/solicitud/{solicitud_id}/reejecutar", json=ajuste, headers=cabeceras)


def _analizar(
    db, busqueda_id: str, ids: list[str], puntaje: float = 90.0, **cambios
) -> GrabadorDeConsultas:
    """Corre el motor de matching real de esa ejecución con candidatos de prueba."""
    servicio = _servicio(db, {cid: puntaje for cid in ids}, ids)
    grabador = GrabadorDeConsultas()
    servicio.embeddings = grabador
    for nombre, valor in cambios.items():
        setattr(servicio, nombre, valor)
    servicio.ejecutar(busqueda_id)
    return grabador


def _resultados(http, cabeceras, busqueda_id: str) -> dict:
    respuesta = http.get(f"/busquedas/{busqueda_id}", headers=cabeceras)
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def _ejecuciones(http, cabeceras, solicitud_id: str) -> list[dict]:
    respuesta = http.get(f"/busquedas/solicitud/{solicitud_id}/ejecuciones", headers=cabeceras)
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def _terminar(db, busqueda_id: str) -> None:
    """Marca terminada la ejecución, como haría el worker, para poder ajustar de nuevo."""
    BusquedaRepository(db).finalizar(busqueda_id, estado=BUSQUEDA_COMPLETADA)


def _valores(criterios: list[dict]) -> list[str]:
    return sorted(c["valor"] for c in criterios)


# --- Criterio 1: criterios de la ejecución como punto de partida ---------------


def test_hu15_criterio1_la_ejecucion_expone_los_criterios_con_los_que_corrio(
    cliente, cabeceras, despachos
):
    solicitud = _solicitud(
        cliente,
        cabeceras,
        criterios=[{"tipo": "TECNOLOGIA", "valor": "Java"}, {"tipo": "IDIOMA", "valor": "Inglés B2"}],
    )

    busqueda_id = _ejecutar(cliente, cabeceras, solicitud["id"])

    parametros = _resultados(cliente, cabeceras, busqueda_id)["parametros"]
    assert parametros["descripcion_libre"] == DESCRIPCION
    assert parametros["rol_buscado"] == ROL
    assert parametros["experiencia_min"] == 5
    assert parametros["cliente"] == "Bancolombia"
    assert parametros["proyecto"] == "Core Bancario"
    assert sorted((c["tipo"], c["valor"]) for c in parametros["criterios"]) == [
        ("IDIOMA", "Inglés B2"),
        ("TECNOLOGIA", "Java"),
    ]


def test_hu15_criterio1_se_conservan_el_tipo_el_peso_y_lo_obligatorio_de_cada_criterio(
    cliente, cabeceras, despachos
):
    solicitud = _solicitud(
        cliente,
        cabeceras,
        criterios=[{"tipo": "FRAMEWORK", "valor": "Spring Boot", "obligatorio": True, "peso": 2.5}],
    )

    busqueda_id = _ejecutar(cliente, cabeceras, solicitud["id"])

    criterio = _resultados(cliente, cabeceras, busqueda_id)["parametros"]["criterios"][0]
    assert criterio == {"tipo": "FRAMEWORK", "valor": "Spring Boot", "obligatorio": True, "peso": 2.5}


def test_hu15_criterio1_una_ejecucion_anterior_a_hu15_no_trae_criterios_y_no_rompe_nada(
    cliente, cabeceras, db
):
    solicitud = _solicitud(cliente, cabeceras)
    anterior = BusquedaModel(solicitud_id=solicitud["id"], estado=BUSQUEDA_COMPLETADA)
    db.add(anterior)
    db.commit()

    resultado = _resultados(cliente, cabeceras, anterior.id)
    listado = _ejecuciones(cliente, cabeceras, solicitud["id"])

    assert resultado["parametros"] is None
    assert len(listado) == 1
    assert listado[0]["parametros"] is None


# --- Criterio 2: ajustar y volver a ejecutar -----------------------------------


def test_hu15_criterio2_confirmar_el_ajuste_lanza_una_nueva_ejecucion_con_los_criterios_nuevos(
    cliente, cabeceras, despachos, db
):
    solicitud = _solicitud(cliente, cabeceras)
    primera = _ejecutar(cliente, cabeceras, solicitud["id"])
    _terminar(db, primera)

    respuesta = _reejecutar(
        cliente,
        cabeceras,
        solicitud["id"],
        _ajuste(
            descripcion_libre=AJUSTADA,
            experiencia_min=3,
            criterios=[{"tipo": "TECNOLOGIA", "valor": "Python"}, {"tipo": "IDIOMA", "valor": "Inglés"}],
        ),
    )

    assert respuesta.status_code == 202
    nueva = respuesta.json()
    assert nueva["id"] != primera
    assert nueva["solicitud_id"] == solicitud["id"]
    assert nueva["estado"] == "EN_COLA"
    assert despachos == [(primera,), (nueva["id"],)]

    parametros = _resultados(cliente, cabeceras, nueva["id"])["parametros"]
    assert parametros["descripcion_libre"] == AJUSTADA
    assert parametros["experiencia_min"] == 3
    assert _valores(parametros["criterios"]) == ["Inglés", "Python"]


def test_hu15_criterio2_la_solicitud_queda_con_los_criterios_ajustados_y_en_analisis(
    cliente, cabeceras, despachos
):
    solicitud = _solicitud(cliente, cabeceras)

    ajuste = _ajuste(criterios=[{"tipo": "TECNOLOGIA", "valor": "Go"}])
    _reejecutar(cliente, cabeceras, solicitud["id"], ajuste)

    guardada = cliente.get(f"/solicitudes/{solicitud['id']}", headers=cabeceras).json()
    assert _valores(guardada["criterios"]) == ["Go"]
    assert guardada["estado"] == "EN_ANALISIS"


def test_hu15_criterio2_el_ajuste_reemplaza_por_completo_lo_que_se_quita_se_borra(
    cliente, cabeceras, despachos
):
    solicitud = _solicitud(cliente, cabeceras)

    respuesta = _reejecutar(
        cliente,
        cabeceras,
        solicitud["id"],
        _ajuste(experiencia_min=None, proyecto=None, criterios=[]),
    )

    assert respuesta.status_code == 202
    guardada = cliente.get(f"/solicitudes/{solicitud['id']}", headers=cabeceras).json()
    assert guardada["experiencia_min"] is None
    assert guardada["proyecto_nombre"] is None
    assert guardada["criterios"] == []
    assert guardada["cliente_nombre"] == "Bancolombia"


def test_hu15_criterio2_cliente_y_proyecto_tambien_se_pueden_ajustar(cliente, cabeceras, despachos, db):
    solicitud = _solicitud(cliente, cabeceras)

    nueva = _reejecutar(
        cliente, cabeceras, solicitud["id"], _ajuste(cliente="Davivienda", proyecto="Canales")
    ).json()

    parametros = _resultados(cliente, cabeceras, nueva["id"])["parametros"]
    assert (parametros["cliente"], parametros["proyecto"]) == ("Davivienda", "Canales")
    guardada = cliente.get(f"/solicitudes/{solicitud['id']}", headers=cabeceras).json()
    assert guardada["cliente_nombre"] == "Davivienda"
    assert guardada["proyecto_nombre"] == "Canales"


def test_hu15_criterio2_ajustar_el_cliente_con_otras_mayusculas_no_crea_otro_cliente(
    cliente, cabeceras, despachos, db
):
    solicitud = _solicitud(cliente, cabeceras)

    _reejecutar(cliente, cabeceras, solicitud["id"], _ajuste(cliente="  BANCOLOMBIA "))

    assert db.query(ClienteModel).count() == 1


def test_hu15_criterio2_el_analisis_usa_los_criterios_ajustados(cliente, cabeceras, despachos, db):
    solicitud = _solicitud(cliente, cabeceras)
    _terminar(db, _ejecutar(cliente, cabeceras, solicitud["id"]))
    nueva = _reejecutar(
        cliente,
        cabeceras,
        solicitud["id"],
        _ajuste(descripcion_libre=AJUSTADA, criterios=[{"tipo": "TECNOLOGIA", "valor": "FastAPI"}]),
    ).json()

    grabador = _analizar(db, nueva["id"], _crear_candidatos(db, 2))

    assert len(grabador.consultas) == 1
    assert AJUSTADA in grabador.consultas[0]
    assert "FastAPI" in grabador.consultas[0]
    assert "Java" not in grabador.consultas[0]


def test_hu15_criterio2_el_listado_se_actualiza_con_los_candidatos_de_la_nueva_ejecucion(
    cliente, cabeceras, despachos, db
):
    solicitud = _solicitud(cliente, cabeceras)
    primera = _ejecutar(cliente, cabeceras, solicitud["id"])
    _analizar(db, primera, _crear_candidatos(db, 3))
    nueva = _reejecutar(cliente, cabeceras, solicitud["id"], _ajuste(experiencia_min=2)).json()
    _analizar(db, nueva["id"], _crear_candidatos(db, 1))

    assert len(_resultados(cliente, cabeceras, nueva["id"])["recomendaciones"]) == 1
    assert cliente.get(f"/solicitudes/{solicitud['id']}", headers=cabeceras).json()["estado"] == (
        ESTADO_PROCESADA
    )


# --- Criterio 3: la ejecución anterior se conserva y se distingue --------------


def test_hu15_criterio3_la_ejecucion_anterior_conserva_sus_criterios_cliente_y_proyecto(
    cliente, cabeceras, despachos, db
):
    solicitud = _solicitud(cliente, cabeceras)
    primera = _ejecutar(cliente, cabeceras, solicitud["id"])
    _terminar(db, primera)

    _reejecutar(
        cliente,
        cabeceras,
        solicitud["id"],
        _ajuste(
            descripcion_libre=AJUSTADA,
            cliente="Davivienda",
            proyecto="Canales",
            criterios=[{"tipo": "TECNOLOGIA", "valor": "Python"}],
        ),
    )

    anterior = _resultados(cliente, cabeceras, primera)["parametros"]
    assert anterior["descripcion_libre"] == DESCRIPCION
    assert anterior["cliente"] == "Bancolombia"
    assert anterior["proyecto"] == "Core Bancario"
    assert _valores(anterior["criterios"]) == ["Java"]


def test_hu15_criterio3_los_resultados_de_la_ejecucion_anterior_no_se_tocan(
    cliente, cabeceras, despachos, db
):
    solicitud = _solicitud(cliente, cabeceras)
    primera = _ejecutar(cliente, cabeceras, solicitud["id"])
    _analizar(db, primera, _crear_candidatos(db, 3))
    antes = _resultados(cliente, cabeceras, primera)["recomendaciones"]

    nueva = _reejecutar(cliente, cabeceras, solicitud["id"], _ajuste(experiencia_min=2)).json()
    _analizar(db, nueva["id"], _crear_candidatos(db, 2))

    despues = _resultados(cliente, cabeceras, primera)["recomendaciones"]
    assert len(antes) == 3
    assert despues == antes
    assert db.query(BusquedaModel).filter(BusquedaModel.solicitud_id == solicitud["id"]).count() == 2


def test_hu15_criterio3_cada_ejecucion_tiene_su_fecha_y_hora(cliente, cabeceras, despachos, db):
    solicitud = _solicitud(cliente, cabeceras)
    primera = _ejecutar(cliente, cabeceras, solicitud["id"])
    _terminar(db, primera)
    nueva = _reejecutar(cliente, cabeceras, solicitud["id"], _ajuste()).json()

    primera_resultado = _resultados(cliente, cabeceras, primera)
    nueva_resultado = _resultados(cliente, cabeceras, nueva["id"])

    assert primera_resultado["created_at"] is not None
    assert nueva_resultado["created_at"] is not None
    assert nueva_resultado["created_at"] >= primera_resultado["created_at"]


def test_hu15_criterio3_las_ejecuciones_se_listan_de_la_mas_reciente_a_la_mas_antigua(
    cliente, cabeceras, despachos, db
):
    solicitud = _solicitud(cliente, cabeceras)
    primera = _ejecutar(cliente, cabeceras, solicitud["id"])
    _analizar(db, primera, _crear_candidatos(db, 3), puntaje=80.0)
    segunda = _reejecutar(
        cliente, cabeceras, solicitud["id"], _ajuste(criterios=[{"tipo": "TECNOLOGIA", "valor": "Go"}])
    ).json()["id"]
    _analizar(db, segunda, _crear_candidatos(db, 1), puntaje=95.0)

    listado = _ejecuciones(cliente, cabeceras, solicitud["id"])

    assert [e["id"] for e in listado] == [segunda, primera]
    assert [e["numero"] for e in listado] == [2, 1]
    assert [e["es_mas_reciente"] for e in listado] == [True, False]
    assert [e["total_candidatos"] for e in listado] == [1, 3]
    assert [e["mejor_afinidad"] for e in listado] == [95.0, 80.0]
    assert [_valores(e["parametros"]["criterios"]) for e in listado] == [["Go"], ["Java"]]
    assert all(e["created_at"] for e in listado)
    assert {e["estado"] for e in listado} == {BUSQUEDA_COMPLETADA}


def test_hu15_criterio3_los_resultados_dicen_que_ejecucion_son_entre_las_de_la_solicitud(
    cliente, cabeceras, despachos, db
):
    solicitud = _solicitud(cliente, cabeceras)
    primera = _ejecutar(cliente, cabeceras, solicitud["id"])
    _terminar(db, primera)
    nueva = _reejecutar(cliente, cabeceras, solicitud["id"], _ajuste(experiencia_min=2)).json()["id"]

    en_primera = _resultados(cliente, cabeceras, primera)
    en_nueva = _resultados(cliente, cabeceras, nueva)

    assert (en_primera["numero_ejecucion"], en_primera["total_ejecuciones"]) == (1, 2)
    assert (en_nueva["numero_ejecucion"], en_nueva["total_ejecuciones"]) == (2, 2)


def test_hu15_criterio3_el_historial_cuenta_las_ejecuciones_de_cada_solicitud(
    cliente, cabeceras, crear_usuario, entrar, despachos, db
):
    solicitud = _solicitud(cliente, cabeceras)
    _terminar(db, _ejecutar(cliente, cabeceras, solicitud["id"]))
    _reejecutar(cliente, cabeceras, solicitud["id"], _ajuste(experiencia_min=2))
    otra = _solicitud(cliente, cabeceras, rol_buscado="QA")
    crear_usuario("dario@bee.com.co", rol="DIRECTOR")

    historial = cliente.get("/solicitudes/", headers=entrar("dario@bee.com.co")).json()

    por_id = {s["id"]: s for s in historial["solicitudes"]}
    assert por_id[solicitud["id"]]["total_ejecuciones"] == 2
    assert por_id[otra["id"]]["total_ejecuciones"] == 0


# --- La ejecución analiza su copia, no la solicitud viva -----------------------


def test_hu15_una_edicion_posterior_a_encolar_no_cambia_lo_que_analiza_esa_ejecucion(
    cliente, cabeceras, despachos, db
):
    solicitud = _solicitud(cliente, cabeceras)
    busqueda_id = _ejecutar(cliente, cabeceras, solicitud["id"])
    # Mientras la ejecución espera su turno alguien edita la solicitud.
    cliente.put(
        f"/solicitudes/{solicitud['id']}",
        json={
            "descripcion_libre": AJUSTADA,
            "criterios": [{"tipo": "TECNOLOGIA", "valor": "Rust"}],
        },
        headers=cabeceras,
    )

    grabador = _analizar(db, busqueda_id, _crear_candidatos(db, 1))

    assert DESCRIPCION in grabador.consultas[0]
    assert "Java" in grabador.consultas[0]
    assert "Rust" not in grabador.consultas[0]


def test_hu15_una_ejecucion_anterior_a_hu15_se_analiza_con_la_solicitud_como_antes(
    cliente, cabeceras, db
):
    solicitud = _solicitud(cliente, cabeceras)
    anterior = BusquedaRepository(db).crear(solicitud["id"])  # sin copia de parámetros

    grabador = _analizar(db, anterior.id, _crear_candidatos(db, 1))

    assert DESCRIPCION in grabador.consultas[0]
    assert "Java" in grabador.consultas[0]


# --- Criterio 4: validación, errores y ausencia de resultados ------------------


@pytest.mark.parametrize(
    ("cambios", "mensaje"),
    [
        pytest.param({"cliente": None}, "cliente", id="sin_cliente"),
        pytest.param({"cliente": "   "}, "cliente", id="cliente_en_blanco"),
        pytest.param({"rol_buscado": ""}, "rol requerido", id="sin_rol"),
        pytest.param({"descripcion_libre": ""}, "descripción del perfil", id="sin_descripcion"),
        pytest.param({"descripcion_libre": "Corta"}, "muy corta", id="descripcion_corta"),
    ],
)
def test_hu15_criterio4_un_ajuste_incompleto_se_rechaza_con_un_mensaje_claro_y_no_cambia_nada(
    cliente, cabeceras, despachos, db, cambios, mensaje
):
    solicitud = _solicitud(cliente, cabeceras)

    respuesta = _reejecutar(cliente, cabeceras, solicitud["id"], _ajuste(**cambios))

    assert respuesta.status_code == 422
    assert mensaje in respuesta.json()["detail"]
    assert db.query(BusquedaModel).count() == 0
    assert despachos == []
    guardada = cliente.get(f"/solicitudes/{solicitud['id']}", headers=cabeceras).json()
    assert guardada["descripcion_libre"] == DESCRIPCION
    assert _valores(guardada["criterios"]) == ["Java"]
    assert guardada["cliente_nombre"] == "Bancolombia"


@pytest.mark.parametrize("anios", [0, -1, 51, "cinco"])
def test_hu15_criterio4_la_experiencia_minima_ajustada_debe_ser_un_entero_positivo(
    cliente, cabeceras, despachos, db, anios
):
    solicitud = _solicitud(cliente, cabeceras)

    respuesta = _reejecutar(cliente, cabeceras, solicitud["id"], _ajuste(experiencia_min=anios))

    assert respuesta.status_code == 422
    assert db.query(BusquedaModel).count() == 0


def test_hu15_criterio4_un_ajuste_a_una_solicitud_inexistente_es_404(cliente, cabeceras, despachos):
    assert _reejecutar(cliente, cabeceras, "no-existe", _ajuste()).status_code == 404
    assert cliente.get("/busquedas/solicitud/no-existe/ejecuciones", headers=cabeceras).status_code == 404


def test_hu15_criterio4_si_el_analisis_falla_la_ejecucion_queda_en_error_y_la_anterior_intacta(
    cliente, cabeceras, despachos, db
):
    solicitud = _solicitud(cliente, cabeceras)
    primera = _ejecutar(cliente, cabeceras, solicitud["id"])
    _analizar(db, primera, _crear_candidatos(db, 2))
    nueva = _reejecutar(cliente, cabeceras, solicitud["id"], _ajuste(experiencia_min=2)).json()["id"]

    _analizar(db, nueva, [], embeddings=EmbeddingsCaidos())

    estado = cliente.get(f"/busquedas/{nueva}/estado", headers=cabeceras).json()
    assert estado["estado"] == BUSQUEDA_ERROR
    assert "Puedes reintentar" in estado["mensaje_error"]
    assert cliente.get(f"/solicitudes/{solicitud['id']}", headers=cabeceras).json()["estado"] == ESTADO_ERROR
    # La ejecución anterior sigue ahí, con sus candidatos y sus criterios.
    anterior = _resultados(cliente, cabeceras, primera)
    assert len(anterior["recomendaciones"]) == 2
    assert [e["estado"] for e in _ejecuciones(cliente, cabeceras, solicitud["id"])] == [
        BUSQUEDA_ERROR,
        BUSQUEDA_COMPLETADA,
    ]


def test_hu15_criterio4_reintentar_tras_un_error_vuelve_a_analizar_los_criterios_ajustados(
    cliente, cabeceras, despachos, db
):
    solicitud = _solicitud(cliente, cabeceras)
    fallida = _reejecutar(
        cliente,
        cabeceras,
        solicitud["id"],
        _ajuste(descripcion_libre=AJUSTADA, criterios=[{"tipo": "TECNOLOGIA", "valor": "FastAPI"}]),
    ).json()["id"]
    _analizar(db, fallida, [], embeddings=EmbeddingsCaidos())

    reintento = _ejecutar(cliente, cabeceras, solicitud["id"])
    grabador = _analizar(db, reintento, _crear_candidatos(db, 1))

    assert reintento != fallida
    assert AJUSTADA in grabador.consultas[0]
    assert "FastAPI" in grabador.consultas[0]


def test_hu15_criterio4_una_ejecucion_con_error_aparece_en_el_historial_con_enlace_a_sus_resultados(
    cliente, cabeceras, crear_usuario, entrar, despachos, db
):
    solicitud = _solicitud(cliente, cabeceras)
    fallida = _ejecutar(cliente, cabeceras, solicitud["id"])
    _analizar(db, fallida, [], embeddings=EmbeddingsCaidos())
    crear_usuario("dario@bee.com.co", rol="DIRECTOR")

    fila = cliente.get("/solicitudes/", headers=entrar("dario@bee.com.co")).json()["solicitudes"][0]

    assert fila["estado"] == ESTADO_ERROR
    assert fila["busqueda_id"] == fallida


def test_hu15_criterio4_si_la_nueva_ejecucion_no_encuentra_candidatos_la_anterior_se_conserva(
    cliente, cabeceras, despachos, db
):
    solicitud = _solicitud(cliente, cabeceras)
    primera = _ejecutar(cliente, cabeceras, solicitud["id"])
    _analizar(db, primera, _crear_candidatos(db, 2))
    nueva = _reejecutar(cliente, cabeceras, solicitud["id"], _ajuste(experiencia_min=30)).json()["id"]

    _analizar(db, nueva, [], recuperador=RecuperadorFalso([]))

    sin_resultados = _resultados(cliente, cabeceras, nueva)
    assert sin_resultados["estado"] == BUSQUEDA_COMPLETADA
    assert sin_resultados["recomendaciones"] == []
    assert cliente.get(f"/solicitudes/{solicitud['id']}", headers=cabeceras).json()["estado"] == (
        ESTADO_SIN_COINCIDENCIAS
    )
    assert len(_resultados(cliente, cabeceras, primera)["recomendaciones"]) == 2
    assert [e["total_candidatos"] for e in _ejecuciones(cliente, cabeceras, solicitud["id"])] == [0, 2]


# --- Criterio 5: el doble envío no lanza dos ejecuciones -----------------------


def test_hu15_criterio5_un_segundo_envio_mientras_se_procesa_se_rechaza_y_no_cambia_la_solicitud(
    cliente, cabeceras, despachos, db
):
    solicitud = _solicitud(cliente, cabeceras)

    primero = _reejecutar(cliente, cabeceras, solicitud["id"], _ajuste(descripcion_libre=AJUSTADA))
    segundo = _reejecutar(
        cliente,
        cabeceras,
        solicitud["id"],
        _ajuste(descripcion_libre=AJUSTADA, criterios=[{"tipo": "TECNOLOGIA", "valor": "Go"}]),
    )

    assert primero.status_code == 202
    assert segundo.status_code == 409
    assert "ya se está analizando" in segundo.json()["detail"]
    assert db.query(BusquedaModel).filter(BusquedaModel.solicitud_id == solicitud["id"]).count() == 1
    assert despachos == [(primero.json()["id"],)]
    # El segundo envío tampoco pisó los criterios de la ejecución en curso.
    guardada = cliente.get(f"/solicitudes/{solicitud['id']}", headers=cabeceras).json()
    assert _valores(guardada["criterios"]) == ["Java"]


def test_hu15_criterio5_ejecutar_dos_veces_seguidas_devuelve_la_misma_ejecucion(
    cliente, cabeceras, despachos, db
):
    solicitud = _solicitud(cliente, cabeceras)

    primera = _ejecutar(cliente, cabeceras, solicitud["id"])
    segunda = _ejecutar(cliente, cabeceras, solicitud["id"])

    assert segunda == primera
    assert len(despachos) == 1


def test_hu15_criterio5_ajustar_mientras_corre_otra_ejecucion_se_rechaza(cliente, cabeceras, despachos, db):
    solicitud = _solicitud(cliente, cabeceras)
    en_curso = _ejecutar(cliente, cabeceras, solicitud["id"])
    BusquedaRepository(db).finalizar(en_curso, estado=BUSQUEDA_EJECUTANDO)

    respuesta = _reejecutar(cliente, cabeceras, solicitud["id"], _ajuste())

    assert respuesta.status_code == 409
    assert len(despachos) == 1


def test_hu15_criterio5_cuando_la_ejecucion_termina_ya_se_puede_ajustar(cliente, cabeceras, despachos, db):
    solicitud = _solicitud(cliente, cabeceras)
    primera = _ejecutar(cliente, cabeceras, solicitud["id"])
    _analizar(db, primera, _crear_candidatos(db, 1))

    respuesta = _reejecutar(cliente, cabeceras, solicitud["id"], _ajuste(experiencia_min=2))

    assert respuesta.status_code == 202
    assert len(despachos) == 2


def test_hu15_criterio5_una_ejecucion_abandonada_no_bloquea_el_ajuste_para_siempre(
    cliente, cabeceras, despachos, db
):
    solicitud = _solicitud(cliente, cabeceras)
    abandonada = BusquedaRepository(db).crear(solicitud["id"])
    BusquedaRepository(db).finalizar(abandonada.id, estado=BUSQUEDA_EJECUTANDO)
    abandonada.created_at = utcnow() - timedelta(minutes=30)
    db.commit()

    respuesta = _reejecutar(cliente, cabeceras, solicitud["id"], _ajuste())

    assert respuesta.status_code == 202


def test_hu15_criterio5_el_ajuste_de_una_solicitud_no_bloquea_el_de_otra(cliente, cabeceras, despachos):
    una = _solicitud(cliente, cabeceras)
    otra = _solicitud(cliente, cabeceras, rol_buscado="QA Automation")

    assert _reejecutar(cliente, cabeceras, una["id"], _ajuste()).status_code == 202
    ajuste_de_otra = _ajuste(rol_buscado="QA Automation")
    assert _reejecutar(cliente, cabeceras, otra["id"], ajuste_de_otra).status_code == 202


# --- Permisos (HU-04) -----------------------------------------------------------


def test_hu15_un_coordinador_no_ajusta_ni_consulta_las_ejecuciones_de_otro(
    cliente, cabeceras, crear_usuario, entrar, despachos, db
):
    solicitud = _solicitud(cliente, cabeceras)
    crear_usuario("beto@bee.com.co")
    ajeno = entrar("beto@bee.com.co")

    ajuste = _reejecutar(cliente, ajeno, solicitud["id"], _ajuste(descripcion_libre=AJUSTADA))
    listado = cliente.get(f"/busquedas/solicitud/{solicitud['id']}/ejecuciones", headers=ajeno)

    assert ajuste.status_code == 403
    assert listado.status_code == 403
    assert db.query(BusquedaModel).count() == 0
    guardada = cliente.get(f"/solicitudes/{solicitud['id']}", headers=cabeceras).json()
    assert guardada["descripcion_libre"] == DESCRIPCION


def test_hu15_un_director_si_puede_ajustar_y_consultar_las_ejecuciones_del_area(
    cliente, cabeceras, crear_usuario, entrar, despachos
):
    solicitud = _solicitud(cliente, cabeceras)
    crear_usuario("dario@bee.com.co", rol="DIRECTOR")
    director = entrar("dario@bee.com.co")

    assert _reejecutar(cliente, director, solicitud["id"], _ajuste()).status_code == 202
    assert len(_ejecuciones(cliente, director, solicitud["id"])) == 1


def test_hu15_las_ejecuciones_exigen_sesion(cliente, cabeceras, despachos):
    solicitud = _solicitud(cliente, cabeceras)

    assert cliente.get(f"/busquedas/solicitud/{solicitud['id']}/ejecuciones").status_code in (401, 403)
    assert cliente.post(
        f"/busquedas/solicitud/{solicitud['id']}/reejecutar", json=_ajuste()
    ).status_code in (401, 403)


def test_hu15_los_criterios_de_otra_solicitud_no_se_mezclan(cliente, cabeceras, despachos, db):
    una = _solicitud(cliente, cabeceras)
    otra = _solicitud(cliente, cabeceras, criterios=[{"tipo": "TECNOLOGIA", "valor": "Cobol"}])

    _reejecutar(cliente, cabeceras, una["id"], _ajuste(criterios=[{"tipo": "TECNOLOGIA", "valor": "Go"}]))

    assert [c.valor for c in db.query(CriterioModel).filter_by(solicitud_id=otra["id"])] == ["Cobol"]
    assert db.get(SolicitudModel, otra["id"]).estado == "BORRADOR"
