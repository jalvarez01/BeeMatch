"""
HU-08, registro de solicitud en lenguaje natural. Criterios de aceptación:

    2. Al ejecutar la búsqueda el texto ingresado se envía al servicio de IA
       como criterio de análisis.
    3. Si el texto tiene menos de 15 caracteres se solicita una descripción
       más detallada del perfil.
    4. El campo admite máximo 1.000 caracteres.

El criterio 1 (campo de texto libre) y el contador del criterio 4 son de
interfaz y se verifican a mano en NuevaBusqueda. Nada aquí sale a la red: el
servicio de IA se sustituye por un doble que solo guarda lo que recibe.
"""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from backend.domain.matching.reranker import Reranker
from backend.domain.services.busqueda_service import BusquedaService
from backend.domain.services.solicitud_service import (
    MENSAJE_DESCRIPCION_CORTA,
    descripcion_insuficiente,
)
from backend.infrastructure.llm.llm_provider import RespuestaIA
from backend.schemas.solicitud import (
    DESCRIPCION_MAX_CARACTERES,
    DESCRIPCION_MIN_CARACTERES,
    SolicitudCreate,
    SolicitudUpdate,
)

DESCRIPCION = (
    "Necesito un desarrollador Backend Java Senior con mínimo 5 años de experiencia, "
    "conocimientos en Spring Boot y AWS, experiencia en el sector bancario e inglés B2."
)


class ProveedorLLMFalso:
    """Guarda el prompt que recibiría el modelo, sin llamar a ningún servicio."""

    def __init__(self):
        self.system = None
        self.prompt = None

    def completar_json(self, system, prompt, max_reintentos=3):
        self.system = system
        self.prompt = prompt
        return RespuestaIA(datos={"candidatos": []})


def test_la_descripcion_llega_al_prompt_que_recibe_el_modelo():
    solicitud = SimpleNamespace(descripcion_libre=DESCRIPCION, rol_buscado=None, experiencia_min=None)

    consulta = BusquedaService(db=None)._construir_consulta(solicitud, [])

    proveedor = ProveedorLLMFalso()
    finalistas = [
        {
            "candidato_id": "c-1",
            "nombre": "Candidata de prueba",
            "fragmentos": [{"id": "f-1", "texto": "Desarrolladora Java con Spring Boot."}],
        }
    ]
    Reranker(proveedor).ordenar_y_explicar(consulta, [], finalistas)

    assert DESCRIPCION in proveedor.prompt


def test_la_descripcion_encabeza_la_consulta_que_se_vectoriza():
    solicitud = SimpleNamespace(
        descripcion_libre=DESCRIPCION, rol_buscado="Backend Developer", experiencia_min=5
    )

    consulta = BusquedaService(db=None)._construir_consulta(solicitud, [])

    assert consulta.startswith(DESCRIPCION)
    assert "Rol: Backend Developer" in consulta


@pytest.mark.parametrize(
    "texto",
    [
        pytest.param("Java", id="una_palabra"),
        pytest.param("a" * (DESCRIPCION_MIN_CARACTERES - 1), id="un_caracter_menos_que_el_minimo"),
        pytest.param("   Java Senior   ", id="los_espacios_de_los_bordes_no_cuentan"),
    ],
)
def test_un_texto_por_debajo_del_minimo_es_insuficiente(texto):
    assert descripcion_insuficiente(texto) is True


@pytest.mark.parametrize(
    "texto",
    [
        pytest.param("a" * DESCRIPCION_MIN_CARACTERES, id="exactamente_el_minimo"),
        pytest.param("  " + "a" * DESCRIPCION_MIN_CARACTERES + "  ", id="el_minimo_entre_espacios"),
        pytest.param(DESCRIPCION, id="descripcion_realista"),
        pytest.param("a" * DESCRIPCION_MAX_CARACTERES, id="exactamente_el_maximo"),
    ],
)
def test_un_texto_desde_el_minimo_es_suficiente(texto):
    assert descripcion_insuficiente(texto) is False


@pytest.mark.parametrize(
    "texto",
    [
        pytest.param("", id="vacio"),
        pytest.param("     ", id="solo_espacios"),
        pytest.param(None, id="sin_valor"),
    ],
)
def test_el_texto_vacio_lo_resuelve_hu10_y_no_este_criterio(texto):
    assert descripcion_insuficiente(texto) is False


def test_el_mensaje_pide_una_descripcion_mas_detallada_e_indica_el_minimo():
    assert "más detalle" in MENSAJE_DESCRIPCION_CORTA
    assert str(DESCRIPCION_MIN_CARACTERES) in MENSAJE_DESCRIPCION_CORTA


def test_el_limite_de_caracteres_es_mil():
    assert DESCRIPCION_MAX_CARACTERES == 1000


@pytest.mark.parametrize("esquema", [SolicitudCreate, SolicitudUpdate])
def test_se_acepta_una_descripcion_de_exactamente_mil_caracteres(esquema):
    datos = esquema(descripcion_libre="a" * DESCRIPCION_MAX_CARACTERES)

    assert len(datos.descripcion_libre) == DESCRIPCION_MAX_CARACTERES


@pytest.mark.parametrize("esquema", [SolicitudCreate, SolicitudUpdate])
def test_se_rechaza_una_descripcion_de_mas_de_mil_caracteres(esquema):
    with pytest.raises(ValidationError):
        esquema(descripcion_libre="a" * (DESCRIPCION_MAX_CARACTERES + 1))
