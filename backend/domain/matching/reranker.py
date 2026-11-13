"""
Etapa 3 del motor: re-ranking y explicación con el LLM.

Solo se le entregan los fragmentos de los finalistas, no el repositorio entero:
~30.000 tokens por búsqueda en lugar de ~300.000 (RNF02).
"""

import logging

from backend.domain.matching.scorer import nivel_de, normalizar_puntaje
from backend.infrastructure.llm.llm_provider import ProveedorLLM, RespuestaIA
from backend.infrastructure.llm.prompts import SYSTEM_RERANK, construir_prompt_rerank

logger = logging.getLogger(__name__)

ESTADOS_VALIDOS = {"ENCONTRADO", "PARCIAL", "NO_EVIDENCIADO"}

# Largo de la columna `coincidencias.requisito`. PostgreSQL rechaza lo que se pase
# (SQLite lo dejaba pasar), y el modelo no siempre respeta el largo de lo que evalúa.
REQUISITO_MAX_CARACTERES = 160


class Reranker:
    def __init__(self, proveedor: ProveedorLLM | None = None):
        self.proveedor = proveedor or ProveedorLLM()

    def ordenar_y_explicar(
        self,
        perfil: str,
        requisitos: list[str],
        finalistas: list[dict],
    ) -> tuple[list[dict], RespuestaIA]:
        prompt = construir_prompt_rerank(perfil, requisitos, finalistas)
        respuesta = self.proveedor.completar_json(SYSTEM_RERANK, prompt)

        # Lo único que el modelo puede citar: los fragmentos de cada finalista, y solo
        # los de ese finalista. Cualquier otro identificador es inventado o mal copiado.
        fragmentos_por_candidato = {
            f["candidato_id"]: {str(fragmento["id"]) for fragmento in f["fragmentos"]} for f in finalistas
        }

        resultados = []
        for item in respuesta.datos.get("candidatos", []):
            candidato_id = item.get("candidato_id")
            if candidato_id not in fragmentos_por_candidato:
                logger.warning("El modelo devolvió un candidato que no era finalista; se descarta.")
                continue
            puntaje = normalizar_puntaje(item.get("puntaje_afinidad", 0))
            resultados.append(
                {
                    "candidato_id": item.get("candidato_id"),
                    "puntaje_afinidad": puntaje,
                    "nivel": nivel_de(puntaje),
                    "resumen_ia": item.get("resumen"),
                    "coincidencias": self._completar_requisitos(
                        self._validar_coincidencias(
                            item.get("coincidencias", []), fragmentos_por_candidato[candidato_id]
                        ),
                        requisitos,
                    ),
                }
            )

        resultados.sort(key=lambda r: r["puntaje_afinidad"], reverse=True)
        return resultados, respuesta

    @staticmethod
    def _validar_coincidencias(coincidencias: list[dict], fragmentos_validos: set[str]) -> list[dict]:
        """
        RD3: una coincidencia ENCONTRADO o PARCIAL sin fragmento de respaldo se
        degrada a NO_EVIDENCIADO. Es la salvaguarda contra afirmaciones que el
        documento no sustenta (RNF28).

        "Con fragmento" quiere decir uno de los `fragmentos_validos`, los que se le
        entregaron al modelo para ese candidato: un identificador que no esté ahí
        no respalda nada, aunque sea texto con aspecto de id. Además de ser falso,
        un id inventado largo hacía fallar el guardado en PostgreSQL.
        """
        validadas = []
        for c in coincidencias:
            estado = c.get("estado", "NO_EVIDENCIADO")
            if estado not in ESTADOS_VALIDOS:
                estado = "NO_EVIDENCIADO"

            fragmento_id = c.get("fragmento_id")
            fragmento_id = str(fragmento_id) if fragmento_id is not None else None
            if estado in ("ENCONTRADO", "PARCIAL") and fragmento_id not in fragmentos_validos:
                estado = "NO_EVIDENCIADO"

            validadas.append(
                {
                    "requisito": (c.get("requisito") or "")[:REQUISITO_MAX_CARACTERES],
                    "estado": estado,
                    "evidencia_texto": c.get("evidencia_texto") if estado != "NO_EVIDENCIADO" else None,
                    "fragmento_id": fragmento_id if estado != "NO_EVIDENCIADO" else None,
                }
            )
        return validadas

    @staticmethod
    def _completar_requisitos(coincidencias: list[dict], requisitos: list[str]) -> list[dict]:
        """
        HU-19: todo requisito solicitado aparece en el desglose. Si el modelo
        omitió alguno, se agrega como NO_EVIDENCIADO en lugar de desaparecer,
        para que el reclutador vea explícitamente qué no respalda la hoja de vida.
        """
        evaluados = {c["requisito"].strip().casefold() for c in coincidencias}
        completas = list(coincidencias)
        for requisito in requisitos:
            clave = requisito.strip().casefold()
            if clave and clave not in evaluados:
                evaluados.add(clave)
                completas.append(
                    {
                        "requisito": requisito,
                        "estado": "NO_EVIDENCIADO",
                        "evidencia_texto": None,
                        "fragmento_id": None,
                    }
                )
        return completas
