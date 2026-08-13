"""
Orquestación del motor de matching (componente C10).

Ejecuta las tres etapas y persiste el Top-N con su desglose explicable.
Lo invoca el worker de búsqueda, nunca la petición HTTP directamente (RNF04).
"""

import time

from sqlalchemy.orm import Session

from backend.config import FINALISTAS_RERANK, TOP_N_RESULTADOS
from backend.domain.matching.filtros import FiltroDuro
from backend.domain.matching.reranker import Reranker
from backend.domain.matching.retriever import RecuperadorHibrido
from backend.domain.matching.scorer import supera_umbral
from backend.infrastructure.llm.embeddings import ProveedorEmbeddings
from backend.infrastructure.llm.llm_provider import ServicioIAError
from backend.infrastructure.persistence.models.busqueda import (
    BUSQUEDA_COMPLETADA,
    BUSQUEDA_EJECUTANDO,
    BUSQUEDA_ERROR,
)
from backend.infrastructure.persistence.models.hoja_vida import (
    ESTADO_INDEXADA,
    ESTADO_NO_PROCESABLE,
)
from backend.infrastructure.persistence.models.solicitud import ESTADO_ERROR, ESTADO_PROCESADA
from backend.infrastructure.persistence.repositories.busqueda_repo import BusquedaRepository
from backend.infrastructure.persistence.repositories.candidato_repo import CandidatoRepository
from backend.infrastructure.persistence.repositories.hoja_vida_repo import HojaDeVidaRepository
from backend.infrastructure.persistence.repositories.solicitud_repo import SolicitudRepository


class BusquedaService:
    def __init__(self, db: Session):
        self.db = db
        self.busquedas = BusquedaRepository(db)
        self.solicitudes = SolicitudRepository(db)
        self.candidatos = CandidatoRepository(db)
        self.hojas = HojaDeVidaRepository(db)
        self.recuperador = RecuperadorHibrido(db)
        self.filtro = FiltroDuro(db)
        self.reranker = Reranker()
        self.embeddings = ProveedorEmbeddings()

    def encolar(self, solicitud_id: str) -> str:
        """Crea la búsqueda y devuelve su id para que el frontend haga polling."""
        busqueda = self.busquedas.crear(solicitud_id)
        return busqueda.id

    def ejecutar(self, busqueda_id: str) -> None:
        """Camino crítico. Se ejecuta dentro del worker."""
        inicio = time.monotonic()
        busqueda = self.busquedas.get_by_id(busqueda_id)
        if not busqueda:
            return

        solicitud = self.solicitudes.get_by_id(busqueda.solicitud_id)
        if not solicitud:
            return

        try:
            self.busquedas.finalizar(busqueda_id, estado=BUSQUEDA_EJECUTANDO)
            self.busquedas.actualizar_progreso(busqueda_id, "Preparando la consulta", 10)

            criterios = self.solicitudes.listar_criterios(solicitud.id)
            consulta = self._construir_consulta(solicitud, criterios)
            requisitos = [c.valor for c in criterios]

            # Etapa 1: recuperación híbrida
            self.busquedas.actualizar_progreso(busqueda_id, "Buscando en las hojas de vida", 35)
            embedding = self.embeddings.generar_uno(consulta)
            fragmentos = self.recuperador.recuperar(consulta, embedding)

            # Etapa 2: filtrado duro
            self.busquedas.actualizar_progreso(busqueda_id, "Aplicando requisitos obligatorios", 55)
            finalistas = self._agrupar_por_candidato(fragmentos)
            ids_filtrados = self.filtro.aplicar(
                [f["candidato_id"] for f in finalistas], solicitud.experiencia_min
            )
            finalistas = [f for f in finalistas if f["candidato_id"] in ids_filtrados][:FINALISTAS_RERANK]

            if not finalistas:
                self._finalizar_sin_candidatos(busqueda_id, solicitud.id, inicio)
                return

            # Etapa 3: re-ranking y explicación con IA
            self.busquedas.actualizar_progreso(busqueda_id, "Analizando los perfiles finalistas", 80)
            resultados, respuesta_ia = self.reranker.ordenar_y_explicar(consulta, requisitos, finalistas)

            recomendaciones = [
                {
                    "candidato_id": r["candidato_id"],
                    "puntaje_afinidad": r["puntaje_afinidad"],
                    "nivel": r["nivel"],
                    "resumen_ia": r["resumen_ia"],
                    "coincidencias": r["coincidencias"],
                }
                for r in resultados
                if supera_umbral(r["puntaje_afinidad"])
            ][:TOP_N_RESULTADOS]

            self.busquedas.guardar_recomendaciones(busqueda_id, recomendaciones)
            self.busquedas.actualizar_progreso(busqueda_id, "Listo", 100)
            self.busquedas.finalizar(
                busqueda_id,
                estado=BUSQUEDA_COMPLETADA,
                duracion_ms=int((time.monotonic() - inicio) * 1000),
                cv_analizados=self.hojas.contar_por_estado(ESTADO_INDEXADA),
                cv_no_procesables=self.hojas.contar_por_estado(ESTADO_NO_PROCESABLE),
                modelo_ia=respuesta_ia.modelo,
                tokens_entrada=respuesta_ia.tokens_entrada,
                tokens_salida=respuesta_ia.tokens_salida,
            )
            self.solicitudes.cambiar_estado(solicitud.id, ESTADO_PROCESADA)

        except ServicioIAError as exc:
            # HU-26: el error se informa con claridad y la solicitud no se pierde.
            self.busquedas.finalizar(busqueda_id, estado=BUSQUEDA_ERROR, mensaje_error=str(exc))
            self.solicitudes.cambiar_estado(solicitud.id, ESTADO_ERROR)
        except Exception as exc:  # noqa: BLE001
            self.busquedas.finalizar(
                busqueda_id, estado=BUSQUEDA_ERROR, mensaje_error=f"Error inesperado: {exc}"
            )
            self.solicitudes.cambiar_estado(solicitud.id, ESTADO_ERROR)

    # --- Internos ------------------------------------------------------------

    def _construir_consulta(self, solicitud, criterios) -> str:
        partes = [solicitud.descripcion_libre or ""]
        if solicitud.rol_buscado:
            partes.append(f"Rol: {solicitud.rol_buscado}")
        if solicitud.experiencia_min:
            partes.append(f"Experiencia mínima: {solicitud.experiencia_min} años")
        if criterios:
            partes.append("Requisitos: " + ", ".join(c.valor for c in criterios))
        return "\n".join(p for p in partes if p)

    def _agrupar_por_candidato(self, fragmentos) -> list[dict]:
        """Un candidato entra al re-ranking con sus mejores fragmentos."""
        por_hoja: dict[str, list] = {}
        for fragmento in fragmentos:
            por_hoja.setdefault(fragmento.hoja_de_vida_id, []).append(fragmento)

        finalistas = []
        for hoja_id, lista in por_hoja.items():
            candidato = self.candidatos.get_by_hoja(hoja_id)
            if not candidato:
                continue
            finalistas.append(
                {
                    "candidato_id": candidato.id,
                    "nombre": candidato.nombre,
                    "puntaje_recuperacion": sum(f.puntaje for f in lista),
                    "fragmentos": [
                        {"id": f.fragmento_id, "texto": f.texto} for f in lista[:4]
                    ],
                }
            )

        finalistas.sort(key=lambda f: f["puntaje_recuperacion"], reverse=True)
        return finalistas

    def _finalizar_sin_candidatos(self, busqueda_id: str, solicitud_id: str, inicio: float) -> None:
        """HU-23: mensaje explícito cuando ningún perfil supera el umbral."""
        self.busquedas.finalizar(
            busqueda_id,
            estado=BUSQUEDA_COMPLETADA,
            duracion_ms=int((time.monotonic() - inicio) * 1000),
            cv_analizados=self.hojas.contar_por_estado(ESTADO_INDEXADA),
            cv_no_procesables=self.hojas.contar_por_estado(ESTADO_NO_PROCESABLE),
        )
        self.solicitudes.cambiar_estado(solicitud_id, ESTADO_PROCESADA)
