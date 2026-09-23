"""Consulta del repositorio de candidatos indexados."""

from typing import Optional

from sqlalchemy.orm import Session

from backend.infrastructure.persistence.repositories.candidato_repo import CandidatoRepository
from backend.infrastructure.persistence.repositories.hoja_vida_repo import HojaDeVidaRepository
from backend.schemas.candidato import (
    CandidatoResponse,
    HabilidadResponse,
    RolDisponibleResponse,
)


class CandidatoService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = CandidatoRepository(db)
        self.hojas = HojaDeVidaRepository(db)

    def obtener(self, candidato_id: str) -> Optional[CandidatoResponse]:
        candidato = self.repo.get_by_id(candidato_id)
        if not candidato:
            return None

        respuesta = CandidatoResponse.model_validate(candidato)
        respuesta.habilidades = [
            HabilidadResponse(
                nombre=habilidad.nombre,
                categoria=habilidad.categoria,
                anios_experiencia=relacion.anios_experiencia,
                evidencia_texto=relacion.evidencia_texto,
            )
            for habilidad, relacion in self.repo.listar_habilidades(candidato_id)
        ]

        self._adjuntar_hoja(respuesta, self.hojas.get_by_id(candidato.hoja_de_vida_id))
        return respuesta

    @staticmethod
    def _adjuntar_hoja(respuesta: CandidatoResponse, hoja) -> None:
        """
        Referencia al documento original: nombre, ruta y enlace al repositorio.

        RNF14: el archivo no se copia, así que `url_hoja_vida` es la única forma
        que tiene el reclutador de abrir la hoja de vida de verdad.
        """
        if not hoja:
            return
        respuesta.nombre_archivo = hoja.nombre_archivo
        respuesta.ruta_hoja_vida = f"{hoja.ruta}/{hoja.nombre_archivo}".replace("//", "/")
        respuesta.url_hoja_vida = hoja.url_web

    def roles_disponibles(self) -> list[RolDisponibleResponse]:
        """Roles que la IA identificó en las hojas de vida ya indexadas."""
        return [
            RolDisponibleResponse(nombre=nombre, candidatos=total)
            for nombre, total in self.repo.listar_roles()
        ]

    def listar(self, pagina: int = 1, por_pagina: int = 20) -> list[CandidatoResponse]:
        candidatos = self.repo.listar(limite=por_pagina, desplazamiento=(pagina - 1) * por_pagina)
        # El listado también necesita el enlace al documento: sin él, el botón
        # "Ver CV" de la pantalla de Candidatos no lleva a ninguna parte.
        hojas = {
            hoja.id: hoja
            for hoja in self.hojas.listar_por_ids([c.hoja_de_vida_id for c in candidatos])
        }

        respuestas = []
        for candidato in candidatos:
            respuesta = CandidatoResponse.model_validate(candidato)
            self._adjuntar_hoja(respuesta, hojas.get(candidato.hoja_de_vida_id))
            respuestas.append(respuesta)
        return respuestas
