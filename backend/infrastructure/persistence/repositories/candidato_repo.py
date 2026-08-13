from typing import Optional

from sqlalchemy.orm import Session

from backend.infrastructure.persistence.models.hoja_vida import (
    CandidatoHabilidadModel,
    CandidatoModel,
    FragmentoCVModel,
    HabilidadModel,
)


class CandidatoRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, candidato_id: str) -> Optional[CandidatoModel]:
        return self.db.get(CandidatoModel, candidato_id)

    def get_by_hoja(self, hoja_de_vida_id: str) -> Optional[CandidatoModel]:
        return (
            self.db.query(CandidatoModel)
            .filter(CandidatoModel.hoja_de_vida_id == hoja_de_vida_id)
            .first()
        )

    def crear_o_reemplazar(self, hoja_de_vida_id: str, datos: dict) -> CandidatoModel:
        existente = self.get_by_hoja(hoja_de_vida_id)
        if existente:
            for clave, valor in datos.items():
                setattr(existente, clave, valor)
            self.db.commit()
            self.db.refresh(existente)
            return existente

        candidato = CandidatoModel(hoja_de_vida_id=hoja_de_vida_id, **datos)
        self.db.add(candidato)
        self.db.commit()
        self.db.refresh(candidato)
        return candidato

    def listar(self, limite: int = 50, desplazamiento: int = 0) -> list[CandidatoModel]:
        return (
            self.db.query(CandidatoModel)
            .order_by(CandidatoModel.nombre)
            .offset(desplazamiento)
            .limit(limite)
            .all()
        )

    def contar(self) -> int:
        return self.db.query(CandidatoModel).count()

    # --- Habilidades ---------------------------------------------------------

    def get_o_crear_habilidad(self, nombre: str, categoria: str = "TECNOLOGIA") -> HabilidadModel:
        normalizado = nombre.strip()
        habilidad = (
            self.db.query(HabilidadModel).filter(HabilidadModel.nombre == normalizado).first()
        )
        if habilidad:
            return habilidad
        habilidad = HabilidadModel(nombre=normalizado, categoria=categoria)
        self.db.add(habilidad)
        self.db.commit()
        self.db.refresh(habilidad)
        return habilidad

    def reemplazar_habilidades(self, candidato_id: str, habilidades: list[dict]) -> None:
        self.db.query(CandidatoHabilidadModel).filter(
            CandidatoHabilidadModel.candidato_id == candidato_id
        ).delete()
        for h in habilidades:
            habilidad = self.get_o_crear_habilidad(h["nombre"], h.get("categoria", "TECNOLOGIA"))
            self.db.add(
                CandidatoHabilidadModel(
                    candidato_id=candidato_id,
                    habilidad_id=habilidad.id,
                    anios_experiencia=h.get("anios_experiencia"),
                    evidencia_texto=h.get("evidencia_texto"),
                    fragmento_id=h.get("fragmento_id"),
                )
            )
        self.db.commit()

    def listar_habilidades(self, candidato_id: str) -> list[tuple[HabilidadModel, CandidatoHabilidadModel]]:
        return (
            self.db.query(HabilidadModel, CandidatoHabilidadModel)
            .join(CandidatoHabilidadModel, CandidatoHabilidadModel.habilidad_id == HabilidadModel.id)
            .filter(CandidatoHabilidadModel.candidato_id == candidato_id)
            .all()
        )

    # --- Fragmentos ----------------------------------------------------------

    def reemplazar_fragmentos(self, hoja_de_vida_id: str, fragmentos: list[dict]) -> list[FragmentoCVModel]:
        self.db.query(FragmentoCVModel).filter(
            FragmentoCVModel.hoja_de_vida_id == hoja_de_vida_id
        ).delete()
        creados = [FragmentoCVModel(hoja_de_vida_id=hoja_de_vida_id, **f) for f in fragmentos]
        self.db.add_all(creados)
        self.db.commit()
        return creados

    def get_fragmento(self, fragmento_id: str) -> Optional[FragmentoCVModel]:
        return self.db.get(FragmentoCVModel, fragmento_id)
