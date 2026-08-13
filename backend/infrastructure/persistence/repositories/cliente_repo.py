from typing import Optional

from sqlalchemy.orm import Session

from backend.infrastructure.persistence.models.cliente import ClienteModel, ProyectoModel


class ClienteRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, cliente_id: str) -> Optional[ClienteModel]:
        return self.db.get(ClienteModel, cliente_id)

    def get_o_crear(self, nombre: str, sector: Optional[str] = None) -> ClienteModel:
        cliente = self.db.query(ClienteModel).filter(ClienteModel.nombre == nombre).first()
        if cliente:
            return cliente
        cliente = ClienteModel(nombre=nombre, sector=sector)
        self.db.add(cliente)
        self.db.commit()
        self.db.refresh(cliente)
        return cliente

    def listar(self) -> list[ClienteModel]:
        return self.db.query(ClienteModel).order_by(ClienteModel.nombre).all()


class ProyectoRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, proyecto_id: str) -> Optional[ProyectoModel]:
        return self.db.get(ProyectoModel, proyecto_id)

    def get_o_crear(self, nombre: str, cliente_id: str) -> ProyectoModel:
        proyecto = (
            self.db.query(ProyectoModel)
            .filter(ProyectoModel.nombre == nombre, ProyectoModel.cliente_id == cliente_id)
            .first()
        )
        if proyecto:
            return proyecto
        proyecto = ProyectoModel(nombre=nombre, cliente_id=cliente_id)
        self.db.add(proyecto)
        self.db.commit()
        self.db.refresh(proyecto)
        return proyecto

    def listar_por_cliente(self, cliente_id: str) -> list[ProyectoModel]:
        return self.db.query(ProyectoModel).filter(ProyectoModel.cliente_id == cliente_id).all()
