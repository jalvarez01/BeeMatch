"""
HU-20: visualización del nivel de afinidad del candidato.

Criterio 1 — cada candidato llega con su afinidad en porcentaje (0 a 100).
Criterio 2 — el listado se ordena de mayor a menor afinidad.
Criterio 3 — cada candidato trae su nivel (alta, media o baja), que la
             interfaz pinta con un color y una etiqueta distintos.

A diferencia de HU-18, aquí se usa el Reranker real: solo se sustituye el
proveedor del LLM, que a propósito responde en desorden y con puntajes fuera de
rango, para probar que el orden y la normalización los pone el sistema.
"""

import pytest

from backend.domain.matching.reranker import Reranker
from backend.domain.matching.scorer import (
    NIVEL_ALTA,
    NIVEL_BAJA,
    NIVEL_MEDIA,
    PUNTAJE_MINIMO_ALTA,
    PUNTAJE_MINIMO_MEDIA,
    nivel_de,
)
from backend.domain.services.resultado_service import ResultadoService
from backend.infrastructure.llm.llm_provider import RespuestaIA
from tests.test_top5_candidatos import _crear_candidatos, _crear_solicitud, _servicio


class ProveedorLLMFalso:
    """Devuelve la respuesta del LLM que el caso necesite, sin salir a la red."""

    def __init__(self, candidatos: list[dict]):
        self.candidatos = candidatos

    def completar_json(self, system, prompt):
        return RespuestaIA(datos={"candidatos": self.candidatos}, modelo="modelo-de-prueba")


def _finalistas(ids: list[str]) -> list[dict]:
    return [
        {"candidato_id": cid, "nombre": f"Candidato {cid}", "fragmentos": [{"id": "f", "texto": "Java"}]}
        for cid in ids
    ]


def _respuesta_llm(puntajes: dict[str, float]) -> list[dict]:
    return [
        {"candidato_id": cid, "puntaje_afinidad": p, "resumen": "", "coincidencias": []}
        for cid, p in puntajes.items()
    ]


def _rerankear(puntajes: dict[str, float]) -> list[dict]:
    reranker = Reranker(proveedor=ProveedorLLMFalso(_respuesta_llm(puntajes)))
    resultados, _ = reranker.ordenar_y_explicar("perfil", [], _finalistas(list(puntajes)))
    return resultados


# --- Criterio 3: los cortes de cada nivel -----------------------------------


@pytest.mark.parametrize(
    ("puntaje", "nivel"),
    [
        (100, NIVEL_ALTA),
        (PUNTAJE_MINIMO_ALTA, NIVEL_ALTA),
        (PUNTAJE_MINIMO_ALTA - 0.1, NIVEL_MEDIA),
        (PUNTAJE_MINIMO_MEDIA, NIVEL_MEDIA),
        (PUNTAJE_MINIMO_MEDIA - 0.1, NIVEL_BAJA),
        (0, NIVEL_BAJA),
    ],
)
def test_cada_puntaje_cae_en_su_nivel(puntaje, nivel):
    assert nivel_de(puntaje) == nivel


def test_los_cortes_coinciden_con_la_leyenda_de_la_interfaz():
    """Badges.tsx anuncia 85% y 70%: si cambian aquí, hay que cambiar la leyenda."""
    assert (PUNTAJE_MINIMO_ALTA, PUNTAJE_MINIMO_MEDIA) == (85, 70)


# --- Criterios 1 y 2: el re-ranking real ordena y normaliza -----------------


def test_el_reranker_ordena_de_mayor_a_menor_aunque_el_llm_responda_en_desorden():
    resultados = _rerankear({"a": 65.0, "b": 92.0, "c": 78.0})

    assert [r["candidato_id"] for r in resultados] == ["b", "c", "a"]
    assert [r["nivel"] for r in resultados] == [NIVEL_ALTA, NIVEL_MEDIA, NIVEL_BAJA]


def test_el_porcentaje_siempre_queda_entre_0_y_100():
    resultados = _rerankear({"a": 130.0, "b": -5.0, "c": 77.777})

    assert [r["puntaje_afinidad"] for r in resultados] == [100.0, 77.8, 0.0]


# --- Los tres criterios vistos desde la respuesta de la API -----------------


def test_la_api_entrega_cada_candidato_con_porcentaje_y_nivel_ordenados(db):
    ids = _crear_candidatos(db, 3)
    solicitud_id = _crear_solicitud(db)
    # El LLM responde en desorden; los tres superan el umbral y caen en
    # niveles distintos.
    puntajes = dict(zip(ids, [65.0, 92.0, 78.0], strict=True))

    servicio = _servicio(db, puntajes, ids)
    servicio.reranker = Reranker(proveedor=ProveedorLLMFalso(_respuesta_llm(puntajes)))
    busqueda_id = servicio.encolar(solicitud_id)
    servicio.ejecutar(busqueda_id)

    recomendaciones = ResultadoService(db).resultados(busqueda_id).recomendaciones
    assert [(r.puntaje_afinidad, r.nivel) for r in recomendaciones] == [
        (92.0, NIVEL_ALTA),
        (78.0, NIVEL_MEDIA),
        (65.0, NIVEL_BAJA),
    ]
    assert [r.posicion for r in recomendaciones] == [1, 2, 3]
