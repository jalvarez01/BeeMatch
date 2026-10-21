"""
HU-19, explicación de por qué se recomendó a cada candidato. Criterios de
aceptación:

    1. El detalle de cada candidato incluye una explicación en lenguaje natural
       de las coincidencias con el perfil solicitado.
    2. La explicación identifica qué tecnologías, frameworks y experiencia
       coinciden con lo solicitado.
    3. Los requisitos solicitados que no se encontraron en la hoja de vida se
       indican explícitamente como no evidenciados.
    4. El sistema muestra un aviso indicando que la decisión final corresponde
       al reclutador.

El criterio 4 es de interfaz y se verifica a mano en Candidato. Nada aquí sale
a la red: el servicio de IA se sustituye por un doble que devuelve una
respuesta fija y guarda el prompt que recibió.
"""

from types import SimpleNamespace

from backend.domain.matching.reranker import Reranker
from backend.domain.services.busqueda_service import BusquedaService
from backend.infrastructure.llm.llm_provider import RespuestaIA
from backend.infrastructure.llm.prompts import SYSTEM_RERANK
from backend.infrastructure.persistence.models.hoja_vida import CandidatoModel, HojaDeVidaModel
from backend.infrastructure.persistence.models.solicitud import SolicitudModel
from backend.infrastructure.persistence.repositories.busqueda_repo import BusquedaRepository

EXPLICACION = (
    "Coincide en Java, Spring Boot y 6 años como desarrolladora backend en banca. "
    "La hoja de vida no evidencia AWS."
)
FINALISTAS = [
    {
        "candidato_id": "c-1",
        "nombre": "Candidata de prueba",
        "fragmentos": [{"id": "f-1", "texto": "Desarrolladora Java con Spring Boot desde 2019."}],
    }
]


class ProveedorLLMFalso:
    """Responde siempre lo mismo y guarda el prompt que recibiría el modelo."""

    def __init__(self, coincidencias: list[dict]):
        self.coincidencias = coincidencias
        self.prompt = None

    def completar_json(self, system, prompt, max_reintentos=3):
        self.prompt = prompt
        candidato = {
            "candidato_id": "c-1",
            "puntaje_afinidad": 82,
            "resumen": EXPLICACION,
            "coincidencias": self.coincidencias,
        }
        return RespuestaIA(datos={"candidatos": [candidato]})


def _explicar(requisitos: list[str], coincidencias: list[dict]) -> dict:
    resultados, _ = Reranker(ProveedorLLMFalso(coincidencias)).ordenar_y_explicar(
        "perfil", requisitos, FINALISTAS
    )
    return resultados[0]


def _encontrado(requisito: str) -> dict:
    return {
        "requisito": requisito,
        "estado": "ENCONTRADO",
        "evidencia_texto": "Desarrolladora Java con Spring Boot",
        "fragmento_id": "f-1",
    }


# --- Criterio 1 --------------------------------------------------------------


def test_hu19_criterio1_se_pide_al_modelo_una_explicacion_en_lenguaje_natural():
    assert "explicación en lenguaje natural" in SYSTEM_RERANK


def test_hu19_criterio1_la_explicacion_del_modelo_llega_a_la_recomendacion():
    assert _explicar([], [])["resumen_ia"] == EXPLICACION


def test_hu19_criterio1_y_3_el_detalle_incluye_la_explicacion_y_lo_no_evidenciado(
    cliente, crear_usuario, entrar, db
):
    usuario = crear_usuario("ana@bee.com.co")
    cabeceras = entrar("ana@bee.com.co")
    hoja = HojaDeVidaModel(id_documento="doc-1", nombre_archivo="cv.pdf", formato="PDF")
    db.add(hoja)
    db.commit()
    candidato = CandidatoModel(hoja_de_vida_id=hoja.id, nombre="Candidata de prueba")
    solicitud = SolicitudModel(descripcion_libre="Backend Java", rol_buscado="Backend", usuario_id=usuario.id)
    db.add_all([candidato, solicitud])
    db.commit()

    explicado = _explicar(["Java", "AWS"], [_encontrado("Java")])
    repo = BusquedaRepository(db)
    busqueda = repo.crear(solicitud.id)
    [recomendacion] = repo.guardar_recomendaciones(
        busqueda.id, [{**explicado, "candidato_id": candidato.id}]
    )

    respuesta = cliente.get(f"/busquedas/recomendacion/{recomendacion.id}", headers=cabeceras)

    assert respuesta.status_code == 200
    detalle = respuesta.json()
    assert detalle["resumen_ia"] == EXPLICACION
    estados = {c["requisito"]: c["estado"] for c in detalle["coincidencias"]}
    assert estados == {"Java": "ENCONTRADO", "AWS": "NO_EVIDENCIADO"}


# --- Criterio 2 --------------------------------------------------------------


def test_hu19_criterio2_la_explicacion_debe_nombrar_tecnologias_frameworks_y_experiencia():
    for palabra in ("tecnologías", "frameworks", "experiencia"):
        assert palabra in SYSTEM_RERANK


def test_hu19_criterio2_el_rol_y_la_experiencia_se_evaluan_junto_con_los_criterios():
    solicitud = SimpleNamespace(rol_buscado="Desarrollador Backend", experiencia_min=5)
    criterios = [SimpleNamespace(valor="Java"), SimpleNamespace(valor="Spring Boot")]

    requisitos = BusquedaService(db=None)._construir_requisitos(solicitud, criterios)

    assert requisitos == ["Desarrollador Backend", "5+ años de experiencia", "Java", "Spring Boot"]


def test_hu19_criterio2_sin_rol_ni_experiencia_solo_se_evaluan_los_criterios():
    solicitud = SimpleNamespace(rol_buscado=None, experiencia_min=None)

    requisitos = BusquedaService(db=None)._construir_requisitos(solicitud, [SimpleNamespace(valor="Java")])

    assert requisitos == ["Java"]


def test_hu19_criterio2_los_requisitos_llegan_al_prompt_del_modelo():
    proveedor = ProveedorLLMFalso([])

    Reranker(proveedor).ordenar_y_explicar("perfil", ["Spring Boot", "5+ años de experiencia"], FINALISTAS)

    assert "- Spring Boot" in proveedor.prompt
    assert "- 5+ años de experiencia" in proveedor.prompt


# --- Criterio 3 --------------------------------------------------------------


def test_hu19_criterio3_un_requisito_que_el_modelo_omitio_queda_como_no_evidenciado():
    coincidencias = _explicar(["Java", "AWS"], [_encontrado("Java")])["coincidencias"]

    assert coincidencias[-1] == {
        "requisito": "AWS",
        "estado": "NO_EVIDENCIADO",
        "evidencia_texto": None,
        "fragmento_id": None,
    }


def test_hu19_criterio3_no_se_duplica_un_requisito_que_el_modelo_si_evaluo():
    coincidencias = _explicar(["java", "Java "], [_encontrado("Java")])["coincidencias"]

    assert [c["requisito"] for c in coincidencias] == ["Java"]


def test_hu19_criterio3_una_coincidencia_sin_fragmento_se_muestra_como_no_evidenciada():
    sin_respaldo = {**_encontrado("AWS"), "fragmento_id": None}

    [coincidencia] = _explicar(["AWS"], [sin_respaldo])["coincidencias"]

    assert coincidencia["estado"] == "NO_EVIDENCIADO"
    assert coincidencia["evidencia_texto"] is None
