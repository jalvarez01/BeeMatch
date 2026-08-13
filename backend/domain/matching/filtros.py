"""
Etapa 2 del motor: filtrado duro.

Lo que se puede decidir con una condición no se le pregunta a un modelo. Los
criterios obligatorios y la experiencia mínima se resuelven en SQL: es
determinista, gratis e instantáneo.
"""

from sqlalchemy.orm import Session

from backend.infrastructure.persistence.models.hoja_vida import CandidatoModel


class FiltroDuro:
    def __init__(self, db: Session):
        self.db = db

    def aplicar(
        self,
        candidatos_ids: list[str],
        experiencia_min: int | None = None,
    ) -> list[str]:
        if not candidatos_ids:
            return []

        consulta = self.db.query(CandidatoModel.id).filter(CandidatoModel.id.in_(candidatos_ids))
        if experiencia_min:
            consulta = consulta.filter(CandidatoModel.anios_experiencia >= experiencia_min)

        return [c[0] for c in consulta.all()]
