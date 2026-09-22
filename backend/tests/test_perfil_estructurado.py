"""
HU-18, criterio 2: cada resultado presenta nombre, rol, tecnologías y años.

Esos cuatro datos salen de la extracción del perfil durante la indexación
(RF02). Aquí se prueba esa extracción aislada del proveedor de IA: lo que
importa es cómo se normaliza y persiste lo que el modelo devuelve, incluido
cuando devuelve basura o cuando no responde.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.domain.services.indexacion_service import (
    MAX_TECNOLOGIAS,
    IndexacionService,
)
from backend.infrastructure.llm.llm_provider import RespuestaIA, ServicioIAError
from backend.infrastructure.persistence import models  # noqa: F401
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models.hoja_vida import (
    ESTADO_INDEXADA,
    HojaDeVidaModel,
)
from backend.infrastructure.persistence.repositories.candidato_repo import CandidatoRepository
from backend.infrastructure.persistence.repositories.hoja_vida_repo import HojaDeVidaRepository
from backend.tests.conftest import crear_pdf

PERFIL_COMPLETO = {
    "nombre": "Ana Maria Restrepo",
    "rol_principal": "Desarrolladora Backend Java",
    "anios_experiencia": 7,
    "ubicacion": "Medellin",
    "resumen": "Backend con foco en core bancario.",
    "tecnologias": [
        {"nombre": "Java", "categoria": "TECNOLOGIA", "evidencia_texto": "Java 17"},
        {"nombre": "Spring Boot", "categoria": "FRAMEWORK", "evidencia_texto": "Spring Boot 3"},
        {"nombre": "PostgreSQL", "categoria": "BASE_DATOS", "evidencia_texto": "PostgreSQL"},
    ],
}


class RepositorioFalso:
    def __init__(self, documentos: dict[str, bytes]):
        self.documentos = documentos

    def descargar(self, id_documento: str) -> bytes:
        return self.documentos[id_documento]


class EmbeddingsFalso:
    def generar(self, textos):
        return [[0.1, 0.2, 0.3] for _ in textos]


class LLMFalso:
    def __init__(self, datos: dict):
        self.datos = datos

    def completar_json(self, system, prompt, max_reintentos=3):
        return RespuestaIA(datos=self.datos)


class LLMCaido:
    """El proveedor no está disponible: ni clave, ni red, ni respuesta."""

    def completar_json(self, system, prompt, max_reintentos=3):
        raise ServicioIAError("El servicio de IA no respondió.")


@pytest.fixture()
def db():
    motor = create_engine("sqlite://")
    Base.metadata.create_all(bind=motor)
    sesion = sessionmaker(bind=motor)()
    yield sesion
    sesion.close()


def _servicio(db, llm, documentos: dict[str, bytes]) -> IndexacionService:
    servicio = IndexacionService.__new__(IndexacionService)  # sin tocar Drive ni OpenAI
    servicio.db = db
    servicio.hojas = HojaDeVidaRepository(db)
    servicio.candidatos = CandidatoRepository(db)
    servicio.embeddings = EmbeddingsFalso()
    servicio.llm = llm
    servicio.repositorio = RepositorioFalso(documentos)
    return servicio


def _registrar(db, nombre_archivo: str) -> str:
    hoja = HojaDeVidaModel(
        id_documento=nombre_archivo, nombre_archivo=nombre_archivo, formato="PDF"
    )
    db.add(hoja)
    db.commit()
    return hoja.id


# --- Camino feliz ------------------------------------------------------------


def test_el_perfil_extraido_llena_los_cuatro_datos_de_la_tarjeta(db):
    documentos = {"hv_ana.pdf": crear_pdf()}
    hoja_id = _registrar(db, "hv_ana.pdf")

    assert _servicio(db, LLMFalso(PERFIL_COMPLETO), documentos).indexar_hoja(hoja_id) is True

    candidato = CandidatoRepository(db).get_by_hoja(hoja_id)
    assert candidato.nombre == "Ana Maria Restrepo"
    assert candidato.rol_principal == "Desarrolladora Backend Java"
    assert candidato.anios_experiencia == 7
    assert candidato.ubicacion == "Medellin"

    tecnologias = [h.nombre for h, _ in CandidatoRepository(db).listar_habilidades(candidato.id)]
    assert sorted(tecnologias) == ["Java", "PostgreSQL", "Spring Boot"]


def test_la_evidencia_de_cada_tecnologia_queda_guardada(db):
    """RNF28: una habilidad afirmada tiene que poder señalar dónde aparece."""
    documentos = {"hv_ana.pdf": crear_pdf()}
    hoja_id = _registrar(db, "hv_ana.pdf")
    _servicio(db, LLMFalso(PERFIL_COMPLETO), documentos).indexar_hoja(hoja_id)

    candidato = CandidatoRepository(db).get_by_hoja(hoja_id)
    evidencias = {
        habilidad.nombre: relacion.evidencia_texto
        for habilidad, relacion in CandidatoRepository(db).listar_habilidades(candidato.id)
    }
    assert evidencias["Java"] == "Java 17"
    assert evidencias["Spring Boot"] == "Spring Boot 3"


# --- Degradación cuando la IA no está --------------------------------------


def test_sin_servicio_de_ia_la_hoja_igual_queda_indexada(db):
    """
    RNF19: los fragmentos y sus embeddings ya están, así que la búsqueda
    funciona. El perfil queda incompleto, pero el documento no se pierde.
    """
    documentos = {"Ana_Restrepo.pdf": crear_pdf()}
    hoja_id = _registrar(db, "Ana_Restrepo.pdf")

    assert _servicio(db, LLMCaido(), documentos).indexar_hoja(hoja_id) is True

    hoja = HojaDeVidaRepository(db).get_by_id(hoja_id)
    assert hoja.estado_procesamiento == ESTADO_INDEXADA

    candidato = CandidatoRepository(db).get_by_hoja(hoja_id)
    assert candidato.nombre == "Ana Restrepo"  # del nombre del archivo
    assert candidato.rol_principal is None
    assert candidato.anios_experiencia is None


def test_un_fallo_de_la_ia_no_borra_las_tecnologias_ya_extraidas(db):
    """
    Reindexar con el proveedor caído no debe dejar al candidato peor que
    antes: las habilidades de la corrida buena se conservan.
    """
    documentos = {"hv_ana.pdf": crear_pdf()}
    hoja_id = _registrar(db, "hv_ana.pdf")
    _servicio(db, LLMFalso(PERFIL_COMPLETO), documentos).indexar_hoja(hoja_id)

    # El documento cambió: vuelve a PENDIENTE y se reindexa, ahora sin IA.
    HojaDeVidaRepository(db).get_by_id(hoja_id).estado_procesamiento = "PENDIENTE"
    db.commit()
    _servicio(db, LLMCaido(), documentos).indexar_hoja(hoja_id)

    candidato = CandidatoRepository(db).get_by_hoja(hoja_id)
    tecnologias = [h.nombre for h, _ in CandidatoRepository(db).listar_habilidades(candidato.id)]
    assert sorted(tecnologias) == ["Java", "PostgreSQL", "Spring Boot"]


def test_una_lista_vacia_de_tecnologias_si_limpia_las_anteriores(db):
    """Distinto del caso anterior: el modelo respondió y no encontró ninguna."""
    documentos = {"hv_ana.pdf": crear_pdf()}
    hoja_id = _registrar(db, "hv_ana.pdf")
    _servicio(db, LLMFalso(PERFIL_COMPLETO), documentos).indexar_hoja(hoja_id)

    HojaDeVidaRepository(db).get_by_id(hoja_id).estado_procesamiento = "PENDIENTE"
    db.commit()
    sin_tecnologias = dict(PERFIL_COMPLETO, tecnologias=[])
    _servicio(db, LLMFalso(sin_tecnologias), documentos).indexar_hoja(hoja_id)

    candidato = CandidatoRepository(db).get_by_hoja(hoja_id)
    assert CandidatoRepository(db).listar_habilidades(candidato.id) == []


# --- Normalización de lo que devuelve el modelo ------------------------------


@pytest.mark.parametrize(
    "crudo, esperado",
    [
        (7, 7),
        ("7", 7),
        (7.0, 7),
        (0, 0),  # un recién graduado declara cero, y es un dato válido
        (None, None),
        ("siete", None),
        (-3, None),
        (2015, None),  # un año mal leído como años de experiencia
        (True, None),
    ],
)
def test_los_anios_de_experiencia_se_normalizan_a_entero(crudo, esperado):
    assert IndexacionService._entero(crudo) == esperado


@pytest.mark.parametrize("crudo", ["null", "None", "N/A", "no especificado", "", "   "])
def test_el_modelo_escribiendo_nulo_en_texto_se_trata_como_ausente(crudo):
    assert IndexacionService._texto(crudo, 120) is None


def test_el_texto_se_recorta_al_ancho_de_la_columna():
    assert IndexacionService._texto("x" * 500, 120) == "x" * 120


def test_las_tecnologias_repetidas_se_descartan_sin_importar_mayusculas():
    crudo = [
        {"nombre": "Java"},
        {"nombre": "java"},
        {"nombre": "JAVA"},
        {"nombre": "Python"},
    ]
    assert [t["nombre"] for t in IndexacionService._tecnologias(crudo)] == ["Java", "Python"]


def test_una_categoria_inventada_cae_a_tecnologia():
    crudo = [{"nombre": "Kafka", "categoria": "MENSAJERIA_ASINCRONA"}]
    assert IndexacionService._tecnologias(crudo)[0]["categoria"] == "TECNOLOGIA"


def test_se_ignora_lo_que_no_sea_una_tecnologia_con_nombre():
    crudo = ["Java", None, {"categoria": "FRAMEWORK"}, {"nombre": ""}, {"nombre": "Go"}]
    assert [t["nombre"] for t in IndexacionService._tecnologias(crudo)] == ["Go"]


def test_la_lista_de_tecnologias_tiene_tope():
    crudo = [{"nombre": f"Tecnologia{i}"} for i in range(MAX_TECNOLOGIAS + 25)]
    assert len(IndexacionService._tecnologias(crudo)) == MAX_TECNOLOGIAS


def test_una_respuesta_sin_la_lista_de_tecnologias_no_revienta():
    assert IndexacionService._tecnologias(None) == []
    assert IndexacionService._tecnologias("Java, Python") == []


def test_si_el_modelo_no_da_el_nombre_se_usa_el_del_archivo(db):
    documentos = {"Carlos_Mejia.pdf": crear_pdf()}
    hoja_id = _registrar(db, "Carlos_Mejia.pdf")
    sin_nombre = dict(PERFIL_COMPLETO, nombre=None)

    _servicio(db, LLMFalso(sin_nombre), documentos).indexar_hoja(hoja_id)

    assert CandidatoRepository(db).get_by_hoja(hoja_id).nombre == "Carlos Mejia"
