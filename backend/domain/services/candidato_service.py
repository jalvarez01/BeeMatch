"""Consulta del repositorio de candidatos indexados."""

from typing import Optional

from sqlalchemy.orm import Session

from backend.infrastructure.persistence.repositories.candidato_repo import CandidatoRepository
from backend.infrastructure.persistence.repositories.hoja_vida_repo import HojaDeVidaRepository
from backend.schemas.candidato import CandidatoResponse, HabilidadResponse


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

        hoja = self.hojas.get_by_id(candidato.hoja_de_vida_id)
        if hoja:
            respuesta.nombre_archivo = hoja.nombre_archivo
            respuesta.ruta_hoja_vida = f"{hoja.ruta}/{hoja.nombre_archivo}".replace("//", "/")
            respuesta.url_hoja_vida = hoja.url_web

        return respuesta

    def listar(self, pagina: int = 1, por_pagina: int = 20) -> list[CandidatoResponse]:
        candidatos = self.repo.listar(limite=por_pagina, desplazamiento=(pagina - 1) * por_pagina)
        return [CandidatoResponse.model_validate(c) for c in candidatos]
