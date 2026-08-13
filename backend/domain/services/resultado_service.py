"""Lectura de resultados de una búsqueda: Top 5, detalle y preselección."""

from typing import Optional

from sqlalchemy.orm import Session

from backend.infrastructure.persistence.repositories.busqueda_repo import BusquedaRepository
from backend.infrastructure.persistence.repositories.candidato_repo import CandidatoRepository
from backend.infrastructure.persistence.repositories.hoja_vida_repo import HojaDeVidaRepository
from backend.schemas.busqueda import (
    BusquedaResultadoResponse,
    CoincidenciaResponse,
    RecomendacionResponse,
)


class ResultadoService:
    def __init__(self, db: Session):
        self.db = db
        self.busquedas = BusquedaRepository(db)
        self.candidatos = CandidatoRepository(db)
        self.hojas = HojaDeVidaRepository(db)

    def resultados(self, busqueda_id: str) -> Optional[BusquedaResultadoResponse]:
        busqueda = self.busquedas.get_by_id(busqueda_id)
        if not busqueda:
            return None

        respuesta = BusquedaResultadoResponse.model_validate(busqueda)
        respuesta.recomendaciones = [
            self._enriquecer(r) for r in self.busquedas.listar_recomendaciones(busqueda_id)
        ]
        return respuesta

    def detalle_recomendacion(self, recomendacion_id: str) -> Optional[RecomendacionResponse]:
        recomendacion = self.busquedas.get_recomendacion(recomendacion_id)
        return self._enriquecer(recomendacion) if recomendacion else None

    def marcar_preseleccion(self, recomendacion_id: str, valor: bool) -> Optional[RecomendacionResponse]:
        """HU-24: el estado de preselección persiste al volver al detalle."""
        recomendacion = self.busquedas.marcar_preseleccion(recomendacion_id, valor)
        return self._enriquecer(recomendacion) if recomendacion else None

    # --- Internos ------------------------------------------------------------

    def _enriquecer(self, recomendacion) -> RecomendacionResponse:
        respuesta = RecomendacionResponse.model_validate(recomendacion)

        candidato = self.candidatos.get_by_id(recomendacion.candidato_id)
        if candidato:
            respuesta.nombre = candidato.nombre
            respuesta.rol_principal = candidato.rol_principal
            respuesta.anios_experiencia = candidato.anios_experiencia
            respuesta.ubicacion = candidato.ubicacion
            respuesta.tecnologias = [
                habilidad.nombre for habilidad, _ in self.candidatos.listar_habilidades(candidato.id)
            ]

            # HU-21: ubicación de la hoja de vida en el repositorio.
            hoja = self.hojas.get_by_id(candidato.hoja_de_vida_id)
            if hoja:
                respuesta.ruta_hoja_vida = f"{hoja.ruta}/{hoja.nombre_archivo}".replace("//", "/")
                respuesta.url_hoja_vida = hoja.url_web

        respuesta.coincidencias = [
            CoincidenciaResponse.model_validate(c)
            for c in self.busquedas.listar_coincidencias(recomendacion.id)
        ]
        return respuesta
