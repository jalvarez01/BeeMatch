"""
Etapa 2 del motor: filtrado duro.

Lo que se puede decidir con una condición no se le pregunta a un modelo. Los
criterios obligatorios y la experiencia mínima se resuelven en SQL: es
determinista, gratis e instantáneo.
"""

from sqlalchemy import or_
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
            # Los años desconocidos no descalifican. Un CV que no declara su
            # experiencia en años no dice que la persona no la tenga: es el
            # mismo criterio que NO_EVIDENCIADO en las coincidencias (RNF27).
            # Si se filtraran aquí, el candidato desaparecería sin que nadie
            # pueda revisarlo; dejándolo pasar, el re-ranking lo evalúa contra
            # el texto real y el reclutador ve el resultado.
            consulta = consulta.filter(
                or_(
                    CandidatoModel.anios_experiencia >= experiencia_min,
                    CandidatoModel.anios_experiencia.is_(None),
                )
            )

        return [c[0] for c in consulta.all()]
