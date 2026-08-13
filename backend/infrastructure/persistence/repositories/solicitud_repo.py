from typing import Optional

from sqlalchemy.orm import Session

from backend.infrastructure.persistence.models.solicitud import CriterioModel, SolicitudModel


class SolicitudRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, solicitud_id: str) -> Optional[SolicitudModel]:
        return self.db.get(SolicitudModel, solicitud_id)

    def crear(self, **campos) -> SolicitudModel:
        solicitud = SolicitudModel(**campos)
        self.db.add(solicitud)
        self.db.commit()
        self.db.refresh(solicitud)
        return solicitud

    def actualizar(self, solicitud: SolicitudModel, **campos) -> SolicitudModel:
        for clave, valor in campos.items():
            if valor is not None and hasattr(solicitud, clave):
                setattr(solicitud, clave, valor)
        self.db.commit()
        self.db.refresh(solicitud)
        return solicitud

    def cambiar_estado(self, solicitud_id: str, estado: str) -> Optional[SolicitudModel]:
        solicitud = self.get_by_id(solicitud_id)
        if not solicitud:
            return None
        solicitud.estado = estado
        self.db.commit()
        self.db.refresh(solicitud)
        return solicitud

    def listar(
        self,
        estado: Optional[str] = None,
        texto: Optional[str] = None,
        limite: int = 20,
        desplazamiento: int = 0,
    ) -> list[SolicitudModel]:
        consulta = self.db.query(SolicitudModel)
        if estado:
            consulta = consulta.filter(SolicitudModel.estado == estado)
        if texto:
            patron = f"%{texto.lower()}%"
            consulta = consulta.filter(SolicitudModel.rol_buscado.ilike(patron))
        return (
            consulta.order_by(SolicitudModel.created_at.desc())
            .offset(desplazamiento)
            .limit(limite)
            .all()
        )

    def contar(self, estado: Optional[str] = None) -> int:
        consulta = self.db.query(SolicitudModel)
        if estado:
            consulta = consulta.filter(SolicitudModel.estado == estado)
        return consulta.count()

    # --- Criterios -----------------------------------------------------------

    def reemplazar_criterios(self, solicitud_id: str, criterios: list[dict]) -> list[CriterioModel]:
        self.db.query(CriterioModel).filter(CriterioModel.solicitud_id == solicitud_id).delete()
        creados = [CriterioModel(solicitud_id=solicitud_id, **c) for c in criterios]
        self.db.add_all(creados)
        self.db.commit()
        return creados

    def listar_criterios(self, solicitud_id: str) -> list[CriterioModel]:
        return self.db.query(CriterioModel).filter(CriterioModel.solicitud_id == solicitud_id).all()
