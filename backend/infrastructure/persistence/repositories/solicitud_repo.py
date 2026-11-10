from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Query, Session

from backend.infrastructure.persistence.models.busqueda import BusquedaModel
from backend.infrastructure.persistence.models.cliente import ClienteModel, ProyectoModel
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

    def eliminar_borrador(self, solicitud: SolicitudModel) -> None:
        """Elimina una solicitud en borrador y sus criterios sin tocar el historial."""
        tiene_busquedas = (
            self.db.query(BusquedaModel.id)
            .filter(BusquedaModel.solicitud_id == solicitud.id)
            .first()
        )
        if tiene_busquedas:
            raise ValueError("La solicitud tiene búsquedas asociadas y no se puede eliminar.")

        try:
            self.db.query(CriterioModel).filter(
                CriterioModel.solicitud_id == solicitud.id
            ).delete(synchronize_session=False)
            self.db.delete(solicitud)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def reemplazar(self, solicitud: SolicitudModel, **campos) -> SolicitudModel:
        """
        Fija los campos tal cual vienen, también los nulos (HU-15). `actualizar`
        ignora los nulos y por eso no permite quitar, por ejemplo, la experiencia mínima.
        """
        for clave, valor in campos.items():
            if hasattr(solicitud, clave):
                setattr(solicitud, clave, valor)
        self.db.commit()
        self.db.refresh(solicitud)
        return solicitud

    def asociar_cliente(
        self, solicitud: SolicitudModel, cliente_id: Optional[str], proyecto_id: Optional[str]
    ) -> SolicitudModel:
        """
        Fija cliente y proyecto tal cual vienen (HU-12). `actualizar` ignora los
        valores nulos, así que no sirve para quitar el proyecto.
        """
        solicitud.cliente_id = cliente_id
        solicitud.proyecto_id = proyecto_id
        self.db.commit()
        self.db.refresh(solicitud)
        return solicitud

    def _filtrada(
        self,
        estado: Optional[str] = None,
        texto: Optional[str] = None,
        cliente_id: Optional[str] = None,
    ) -> Query:
        consulta = self.db.query(SolicitudModel)
        if estado:
            consulta = consulta.filter(SolicitudModel.estado == estado)
        if cliente_id:
            consulta = consulta.filter(SolicitudModel.cliente_id == cliente_id)
        if texto:
            # HU-12: el texto busca por rol, cliente o proyecto, como promete el buscador.
            patron = f"%{texto.strip().lower()}%"
            ids_cliente = select(ClienteModel.id).where(ClienteModel.nombre.ilike(patron))
            ids_proyecto = select(ProyectoModel.id).where(ProyectoModel.nombre.ilike(patron))
            consulta = consulta.filter(
                or_(
                    SolicitudModel.rol_buscado.ilike(patron),
                    SolicitudModel.cliente_id.in_(ids_cliente),
                    SolicitudModel.proyecto_id.in_(ids_proyecto),
                )
            )
        return consulta

    def listar(
        self,
        estado: Optional[str] = None,
        texto: Optional[str] = None,
        limite: int = 20,
        desplazamiento: int = 0,
        cliente_id: Optional[str] = None,
    ) -> list[SolicitudModel]:
        return (
            self._filtrada(estado, texto, cliente_id)
            .order_by(SolicitudModel.created_at.desc())
            .offset(desplazamiento)
            .limit(limite)
            .all()
        )

    def contar(
        self,
        estado: Optional[str] = None,
        texto: Optional[str] = None,
        cliente_id: Optional[str] = None,
    ) -> int:
        return self._filtrada(estado, texto, cliente_id).count()

    # --- Criterios -----------------------------------------------------------

    def reemplazar_criterios(self, solicitud_id: str, criterios: list[dict]) -> list[CriterioModel]:
        self.db.query(CriterioModel).filter(CriterioModel.solicitud_id == solicitud_id).delete()
        creados = [CriterioModel(solicitud_id=solicitud_id, **c) for c in criterios]
        self.db.add_all(creados)
        self.db.commit()
        return creados

    def listar_criterios(self, solicitud_id: str) -> list[CriterioModel]:
        return self.db.query(CriterioModel).filter(CriterioModel.solicitud_id == solicitud_id).all()
