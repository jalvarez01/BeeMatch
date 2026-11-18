from datetime import UTC, date, datetime, time, timedelta
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Query, Session

from backend.infrastructure.persistence.models.busqueda import BusquedaModel
from backend.infrastructure.persistence.models.cliente import ClienteModel, ProyectoModel
from backend.infrastructure.persistence.models.solicitud import CriterioModel, SolicitudModel
from backend.infrastructure.persistence.models.usuario import UsuarioModel


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
        usuario: Optional[str] = None,
        usuario_id: Optional[str] = None,
        fecha_desde: Optional[date] = None,
        fecha_hasta: Optional[date] = None,
    ) -> Query:
        consulta = self.db.query(SolicitudModel)
        if estado:
            consulta = consulta.filter(SolicitudModel.estado == estado)
        if cliente_id:
            consulta = consulta.filter(SolicitudModel.cliente_id == cliente_id)
        if usuario_id:
            # HU-13: el Coordinador solo ve lo que él mismo registró.
            consulta = consulta.filter(SolicitudModel.usuario_id == usuario_id)
        if usuario and usuario.strip():
            # HU-13: por el nombre de quien la registró. Se busca también en el nombre
            # guardado en la solicitud, para encontrar a quien ya no tiene cuenta.
            patron = f"%{usuario.strip().lower()}%"
            ids_usuario = select(UsuarioModel.id).where(UsuarioModel.nombre.ilike(patron))
            consulta = consulta.filter(
                or_(
                    SolicitudModel.autor_nombre.ilike(patron),
                    SolicitudModel.usuario_id.in_(ids_usuario),
                )
            )
        # HU-13: rango de fechas, inclusivo en ambos extremos y en UTC.
        if fecha_desde:
            consulta = consulta.filter(
                SolicitudModel.created_at >= datetime.combine(fecha_desde, time.min, tzinfo=UTC)
            )
        if fecha_hasta:
            consulta = consulta.filter(
                SolicitudModel.created_at
                < datetime.combine(fecha_hasta + timedelta(days=1), time.min, tzinfo=UTC)
            )
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
        **filtros,
    ) -> list[SolicitudModel]:
        return (
            self._filtrada(estado, texto, cliente_id, **filtros)
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
        **filtros,
    ) -> int:
        return self._filtrada(estado, texto, cliente_id, **filtros).count()

    # --- Criterios -----------------------------------------------------------

    def reemplazar_criterios(self, solicitud_id: str, criterios: list[dict]) -> list[CriterioModel]:
        self.db.query(CriterioModel).filter(CriterioModel.solicitud_id == solicitud_id).delete()
        creados = [CriterioModel(solicitud_id=solicitud_id, **c) for c in criterios]
        self.db.add_all(creados)
        self.db.commit()
        return creados

    def listar_criterios(self, solicitud_id: str) -> list[CriterioModel]:
        return self.db.query(CriterioModel).filter(CriterioModel.solicitud_id == solicitud_id).all()
