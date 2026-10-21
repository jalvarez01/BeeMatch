"""
Orquestación del motor de matching (componente C10).

Ejecuta las tres etapas y persiste el Top-N con su desglose explicable.
Lo invoca el worker de búsqueda, nunca la petición HTTP directamente (RNF04).
"""

import time
from datetime import timedelta
from typing import Optional

from sqlalchemy.orm import Session

from backend.config import FINALISTAS_RERANK, TOP_N_RESULTADOS
from backend.domain.services.bitacora_service import (
    ACCION_ERROR_SERVICIO,
    BitacoraService,
)
from backend.domain.matching.filtros import FiltroDuro
from backend.domain.matching.reranker import Reranker
from backend.domain.matching.retriever import RecuperadorHibrido
from backend.domain.matching.scorer import supera_umbral
from backend.infrastructure.llm.embeddings import (
    ProveedorEmbeddings,
    ProveedorEmbeddingsNoDisponibleError,
)
from backend.infrastructure.llm.llm_provider import ServicioIAError
from backend.infrastructure.persistence.models._base import utcnow
from backend.infrastructure.persistence.models.busqueda import (
    BUSQUEDA_COMPLETADA,
    BUSQUEDA_EJECUTANDO,
    BUSQUEDA_ERROR,
    BusquedaModel,
)
from backend.infrastructure.persistence.models.hoja_vida import (
    ESTADO_INDEXADA,
    ESTADO_NO_PROCESABLE,
)
from backend.infrastructure.persistence.models.solicitud import (
    ESTADO_ERROR,
    ESTADO_PROCESADA,
    ESTADO_SIN_COINCIDENCIAS,
)
from backend.infrastructure.persistence.repositories.busqueda_repo import BusquedaRepository
from backend.infrastructure.persistence.repositories.candidato_repo import CandidatoRepository
from backend.infrastructure.persistence.repositories.hoja_vida_repo import HojaDeVidaRepository
from backend.infrastructure.persistence.repositories.solicitud_repo import SolicitudRepository

# Una búsqueda pendiente o ejecutándose más tiempo que esto se da por abandonada.
# Supera el job_timeout de la cola (900 s), así que ningún trabajo vivo la alcanza.
VIGENCIA_BUSQUEDA_EN_CURSO = timedelta(minutes=20)


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

    def en_curso(self, solicitud_id: str) -> Optional[BusquedaModel]:
        """HU-22: la búsqueda viva de la solicitud, para no lanzar otra encima."""
        return self.busquedas.en_curso_de_solicitud(
            solicitud_id, desde=utcnow() - VIGENCIA_BUSQUEDA_EN_CURSO
        )

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
            requisitos = self._construir_requisitos(solicitud, criterios)

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
            # HU-23: hubo finalistas, pero si ninguno superó el umbral la
            # solicitud queda en el historial como "Sin coincidencias".
            self.solicitudes.cambiar_estado(
                solicitud.id, ESTADO_PROCESADA if recomendaciones else ESTADO_SIN_COINCIDENCIAS
            )

        except ProveedorEmbeddingsNoDisponibleError as exc:
            self._registrar_error(solicitud, "IA_NO_DISPONIBLE", str(exc))
            self.busquedas.finalizar(
                busqueda_id,
                estado=BUSQUEDA_ERROR,
                mensaje_error="El servicio de IA no está disponible. Puedes reintentar el análisis.",
            )
            self.solicitudes.cambiar_estado(solicitud.id, ESTADO_ERROR)

        except ServicioIAError as exc:
            self._registrar_error(solicitud, "IA_TIMEOUT_O_ERROR", str(exc))
            self.busquedas.finalizar(
                busqueda_id,
                estado=BUSQUEDA_ERROR,
                mensaje_error="El servicio de IA no está disponible o excedió el tiempo de espera. Puedes reintentar el análisis.",
            )
            self.solicitudes.cambiar_estado(solicitud.id, ESTADO_ERROR)

        except Exception as exc:  # noqa: BLE001
            self._registrar_error(solicitud, "ERROR_INESPERADO", str(exc))
            self.busquedas.finalizar(
                busqueda_id,
                estado=BUSQUEDA_ERROR,
                mensaje_error="No fue posible completar el análisis por un error inesperado. Puedes reintentarlo.",
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

    def _construir_requisitos(self, solicitud, criterios) -> list[str]:
        """
        HU-19: el rol y la experiencia mínima se evalúan uno a uno junto con los
        criterios, para que la explicación diga si la hoja de vida los respalda.
        """
        requisitos = []
        if solicitud.rol_buscado:
            requisitos.append(solicitud.rol_buscado)
        if solicitud.experiencia_min:
            requisitos.append(f"{solicitud.experiencia_min}+ años de experiencia")
        requisitos.extend(c.valor for c in criterios)
        return requisitos

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
        self.solicitudes.cambiar_estado(solicitud_id, ESTADO_SIN_COINCIDENCIAS)

    def _registrar_error(self, solicitud, tipo_error: str, detalle: str) -> None:
        """Registra en la bitácora los errores que impiden completar una búsqueda."""
        try:
            BitacoraService(self.db).registrar(
                accion=ACCION_ERROR_SERVICIO,
                usuario_id=solicitud.usuario_id,
                entidad="solicitud",
                entidad_id=solicitud.id,
                detalle=f"tipo={tipo_error}; detalle={detalle}",
            )
        except Exception:
            self.db.rollback()

    def marcar_error_repositorio(
        self,
        busqueda_id: str,
        detalle: str,
    ) -> None:
        busqueda = self.busquedas.get_by_id(busqueda_id)
        if not busqueda:
            return

        solicitud = self.solicitudes.get_by_id(busqueda.solicitud_id)
        if not solicitud:
            return

        self._registrar_error(
            solicitud,
            "REPOSITORIO_NO_DISPONIBLE",
            detalle,
        )

        self.busquedas.finalizar(
            busqueda_id,
            estado=BUSQUEDA_ERROR,
            mensaje_error=(
                "No fue posible acceder al repositorio de hojas de vida. "
                "Contacte al administrador"
            ),
        )

        self.solicitudes.cambiar_estado(solicitud.id, ESTADO_ERROR)
