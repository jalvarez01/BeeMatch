"""
HU-09, registro de la solicitud con campos estructurados. Criterios:

    1. El sistema ofrece los campos rol, tecnologías, frameworks, años de
       experiencia y otros conocimientos.
    2. El campo de tecnologías permite registrar múltiples valores.
    3. Al ejecutar la búsqueda el sistema combina todos los criterios
       diligenciados en el análisis.
    4. Los criterios utilizados quedan visibles al consultar la solicitud en el
       historial.

Los campos del formulario y su agrupación en pantalla también tienen su parte de
interfaz: su lógica pura se prueba en `frontend/tests/criterios.test.ts`. Aquí se
prueba la API y el motor de matching con los mismos dobles de HU-15 (buscador y
servicio de IA falsos), así que no hace falta red ni credenciales.
"""

from types import SimpleNamespace

import pytest

from backend.domain.matching.criterios import agrupar_por_tipo, lineas_de_criterios
from backend.domain.services.busqueda_service import BusquedaService
from tests.test_hu15_ajuste_y_reejecucion import (
    _ajuste,
    _analizar,
    _ejecuciones,
    _ejecutar,
    _reejecutar,
    _resultados,
    _terminar,
)
from tests.test_top5_candidatos import RerankerFalso, _crear_candidatos

DESCRIPCION = "Desarrollador Backend Java para el core bancario de un cliente financiero."
ROL = "Desarrollador Backend"

# Lo que diligencia la coordinadora cuando el cliente entrega requisitos detallados.
CRITERIOS_COMPLETOS = [
    {"tipo": "TECNOLOGIA", "valor": "Java"},
    {"tipo": "TECNOLOGIA", "valor": "PostgreSQL"},
    {"tipo": "TECNOLOGIA", "valor": "AWS"},
    {"tipo": "FRAMEWORK", "valor": "Spring Boot"},
    {"tipo": "FRAMEWORK", "valor": "Hibernate"},
    {"tipo": "OTRO", "valor": "Sector bancario"},
    {"tipo": "OTRO", "valor": "Scrum"},
    {"tipo": "IDIOMA", "valor": "Inglés B2"},
]


@pytest.fixture
def cabeceras(crear_usuario, entrar):
    crear_usuario("coordinadora@bee.com.co")
    return entrar("coordinadora@bee.com.co")


@pytest.fixture
def despachos(monkeypatch):
    """La búsqueda se encola pero el worker no corre: cada prueba decide cuándo analizar."""
    import backend.api.busquedas as router

    enviados = []
    monkeypatch.setattr(router, "despachar", lambda tareas, funcion, *args: enviados.append(args))
    return enviados


class RerankerQueGraba(RerankerFalso):
    """Doble del re-ranking que además guarda los requisitos que el motor le pide evaluar."""

    def __init__(self, puntajes):
        super().__init__(puntajes)
        self.requisitos = []

    def ordenar_y_explicar(self, consulta, requisitos, finalistas):
        self.requisitos.append(list(requisitos))
        return super().ordenar_y_explicar(consulta, requisitos, finalistas)


def _registrar(http, cabeceras, /, **datos) -> dict:
    cuerpo = {
        "descripcion_libre": DESCRIPCION,
        "rol_buscado": ROL,
        "experiencia_min": 5,
        "cliente": "Bancolombia",
        "proyecto": "Core Bancario",
        "criterios": CRITERIOS_COMPLETOS,
        **datos,
    }
    respuesta = http.post("/solicitudes/", json=cuerpo, headers=cabeceras)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _pares(criterios: list[dict]) -> list[tuple[str, str]]:
    return sorted((c["tipo"], c["valor"]) for c in criterios)


# --- Criterio 1: los campos estructurados ---------------------------------------


def test_hu09_criterio1_la_solicitud_guarda_rol_experiencia_tecnologias_frameworks_y_otros(
    cliente, cabeceras
):
    solicitud = _registrar(cliente, cabeceras)

    assert solicitud["rol_buscado"] == ROL
    assert solicitud["experiencia_min"] == 5
    assert _pares(solicitud["criterios"]) == _pares(CRITERIOS_COMPLETOS)


def test_hu09_criterio1_otros_conocimientos_es_un_tipo_de_criterio_valido(cliente, cabeceras):
    solicitud = _registrar(cliente, cabeceras, criterios=[{"tipo": "OTRO", "valor": "ISO 27001"}])

    criterio = solicitud["criterios"][0]
    assert (criterio["tipo"], criterio["valor"]) == ("OTRO", "ISO 27001")
    assert criterio["obligatorio"] is False
    assert criterio["peso"] == 1.0


def test_hu09_criterio1_un_tipo_de_criterio_inexistente_se_rechaza(cliente, cabeceras):
    respuesta = cliente.post(
        "/solicitudes/",
        json={
            "descripcion_libre": DESCRIPCION,
            "rol_buscado": ROL,
            "cliente": "Bancolombia",
            "criterios": [{"tipo": "HOBBY", "valor": "Ajedrez"}],
        },
        headers=cabeceras,
    )

    assert respuesta.status_code == 422


def test_hu09_criterio1_los_campos_estructurados_son_opcionales(cliente, cabeceras):
    """Si el cliente no da requisitos detallados, basta con la descripción, el cliente y el rol."""
    solicitud = _registrar(cliente, cabeceras, experiencia_min=None, criterios=[])

    assert solicitud["experiencia_min"] is None
    assert solicitud["criterios"] == []


# --- Criterio 2: tecnologías con múltiples valores ------------------------------


def test_hu09_criterio2_se_registran_varias_tecnologias_en_la_misma_solicitud(cliente, cabeceras):
    tecnologias = ["Java", "Python", "Go", "Kotlin", "AWS"]
    solicitud = _registrar(
        cliente, cabeceras, criterios=[{"tipo": "TECNOLOGIA", "valor": v} for v in tecnologias]
    )

    guardadas = [c["valor"] for c in solicitud["criterios"] if c["tipo"] == "TECNOLOGIA"]
    assert sorted(guardadas) == sorted(tecnologias)


# --- Criterio 3: el análisis combina todos los criterios ------------------------


def test_hu09_criterio3_la_consulta_combina_todos_los_campos_diligenciados(
    cliente, cabeceras, despachos, db
):
    solicitud = _registrar(cliente, cabeceras)
    busqueda_id = _ejecutar(cliente, cabeceras, solicitud["id"])

    grabador = _analizar(db, busqueda_id, _crear_candidatos(db, 2))

    consulta = grabador.consultas[0]
    assert consulta.startswith(DESCRIPCION)
    assert f"Rol: {ROL}" in consulta
    assert "Experiencia mínima: 5 años" in consulta
    assert "Tecnologías: Java, PostgreSQL, AWS" in consulta
    assert "Frameworks: Spring Boot, Hibernate" in consulta
    assert "Otros conocimientos: Sector bancario, Scrum" in consulta
    assert "Idiomas: Inglés B2" in consulta


def test_hu09_criterio3_el_reranking_evalua_cada_criterio_diligenciado(
    cliente, cabeceras, despachos, db
):
    """Cada criterio llega como requisito propio, para que la explicación (HU-19) lo valide."""
    solicitud = _registrar(cliente, cabeceras)
    busqueda_id = _ejecutar(cliente, cabeceras, solicitud["id"])
    ids = _crear_candidatos(db, 2)
    reranker = RerankerQueGraba({cid: 90.0 for cid in ids})

    _analizar(db, busqueda_id, ids, reranker=reranker)

    requisitos = reranker.requisitos[0]
    assert ROL in requisitos
    assert "5+ años de experiencia" in requisitos
    for criterio in CRITERIOS_COMPLETOS:
        assert criterio["valor"] in requisitos


def test_hu09_criterio3_los_grupos_vacios_no_aparecen_en_la_consulta(
    cliente, cabeceras, despachos, db
):
    solicitud = _registrar(cliente, cabeceras, criterios=[{"tipo": "FRAMEWORK", "valor": "Django"}])
    busqueda_id = _ejecutar(cliente, cabeceras, solicitud["id"])

    consulta = _analizar(db, busqueda_id, _crear_candidatos(db, 1)).consultas[0]

    assert "Frameworks: Django" in consulta
    assert "Tecnologías:" not in consulta
    assert "Otros conocimientos:" not in consulta


def test_hu09_criterio3_la_consulta_agrupa_en_el_orden_del_formulario():
    criterios = [
        SimpleNamespace(tipo="IDIOMA", valor="Inglés"),
        SimpleNamespace(tipo="OTRO", valor="Banca"),
        SimpleNamespace(tipo="FRAMEWORK", valor="React"),
        SimpleNamespace(tipo="TECNOLOGIA", valor="TypeScript"),
    ]
    solicitud = SimpleNamespace(descripcion_libre="Frontend", rol_buscado=None, experiencia_min=None)

    consulta = BusquedaService(db=None)._construir_consulta(solicitud, criterios)

    assert consulta.split("\n") == [
        "Frontend",
        "Tecnologías: TypeScript",
        "Frameworks: React",
        "Otros conocimientos: Banca",
        "Idiomas: Inglés",
    ]


def test_hu09_criterio3_agrupar_no_repite_valores_ni_pierde_tipos_desconocidos():
    criterios = [
        SimpleNamespace(tipo="TECNOLOGIA", valor="Java"),
        SimpleNamespace(tipo="TECNOLOGIA", valor=" Java "),
        SimpleNamespace(tipo="TECNOLOGIA", valor=""),
        SimpleNamespace(tipo="DOMINIO", valor="Seguros"),
        SimpleNamespace(tipo="NUEVO", valor="Algo"),
    ]

    assert agrupar_por_tipo(criterios) == [
        ("Tecnologías", ["Java"]),
        ("Dominio", ["Seguros"]),
        ("Nuevo", ["Algo"]),
    ]
    assert lineas_de_criterios([]) == []


# --- Criterio 4: criterios visibles en el historial -----------------------------


def test_hu09_criterio4_el_historial_muestra_los_criterios_de_cada_solicitud(
    cliente, cabeceras, crear_usuario, entrar
):
    solicitud = _registrar(cliente, cabeceras)
    # HU-04: el historial completo lo consultan Director y Administrador.
    crear_usuario("director@bee.com.co", rol="DIRECTOR")

    respuesta = cliente.get("/solicitudes/", headers=entrar("director@bee.com.co"))

    assert respuesta.status_code == 200, respuesta.text
    fila = next(s for s in respuesta.json()["solicitudes"] if s["id"] == solicitud["id"])
    assert fila["rol_buscado"] == ROL
    assert fila["experiencia_min"] == 5
    assert _pares(fila["criterios"]) == _pares(CRITERIOS_COMPLETOS)


def test_hu09_criterio4_un_borrador_tambien_muestra_sus_criterios(cliente, cabeceras):
    borrador = _registrar(cliente, cabeceras, guardar_como_borrador=True)

    detalle = cliente.get(f"/solicitudes/{borrador['id']}", headers=cabeceras).json()

    assert detalle["estado"] == "BORRADOR"
    assert _pares(detalle["criterios"]) == _pares(CRITERIOS_COMPLETOS)


def test_hu09_criterio4_la_ejecucion_conserva_los_criterios_con_su_tipo(
    cliente, cabeceras, despachos
):
    solicitud = _registrar(cliente, cabeceras)

    busqueda_id = _ejecutar(cliente, cabeceras, solicitud["id"])

    parametros = _resultados(cliente, cabeceras, busqueda_id)["parametros"]
    assert parametros["rol_buscado"] == ROL
    assert parametros["experiencia_min"] == 5
    assert _pares(parametros["criterios"]) == _pares(CRITERIOS_COMPLETOS)


# --- HU-09 con HU-15: los campos estructurados se ajustan y quedan en el historial


def test_hu09_hu15_ajustar_frameworks_y_otros_conocimientos_lanza_un_analisis_con_ellos(
    cliente, cabeceras, despachos, db
):
    solicitud = _registrar(cliente, cabeceras)
    primera = _ejecutar(cliente, cabeceras, solicitud["id"])
    _terminar(db, primera)
    ajustados = [
        {"tipo": "TECNOLOGIA", "valor": "Python"},
        {"tipo": "FRAMEWORK", "valor": "FastAPI"},
        {"tipo": "OTRO", "valor": "Sector asegurador"},
    ]

    nueva = _reejecutar(
        cliente, cabeceras, solicitud["id"], _ajuste(descripcion_libre=DESCRIPCION, criterios=ajustados)
    ).json()
    consulta = _analizar(db, nueva["id"], _crear_candidatos(db, 1)).consultas[0]

    assert "Frameworks: FastAPI" in consulta
    assert "Otros conocimientos: Sector asegurador" in consulta
    assert "Spring Boot" not in consulta


def test_hu09_hu15_el_historial_de_ejecuciones_conserva_los_criterios_de_cada_una(
    cliente, cabeceras, despachos, db
):
    solicitud = _registrar(cliente, cabeceras)
    primera = _ejecutar(cliente, cabeceras, solicitud["id"])
    _terminar(db, primera)
    ajustados = [{"tipo": "FRAMEWORK", "valor": "Quarkus"}, {"tipo": "OTRO", "valor": "Kanban"}]
    nueva = _reejecutar(cliente, cabeceras, solicitud["id"], _ajuste(criterios=ajustados)).json()

    listado = {e["id"]: e for e in _ejecuciones(cliente, cabeceras, solicitud["id"])}

    assert set(listado) == {primera, nueva["id"]}
    assert _pares(listado[primera]["parametros"]["criterios"]) == _pares(CRITERIOS_COMPLETOS)
    assert _pares(listado[nueva["id"]]["parametros"]["criterios"]) == _pares(ajustados)
