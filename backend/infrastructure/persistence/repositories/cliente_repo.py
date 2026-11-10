from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.infrastructure.persistence.models.cliente import ClienteModel, ProyectoModel
from backend.infrastructure.persistence.normalizacion import limpiar_nombre, normalizar_nombre

LIMITE_SUGERENCIAS = 8


def _escapar_like(texto: str) -> str:
    """Los comodines de LIKE escritos por la persona se buscan literalmente."""
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class ClienteRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, cliente_id: str) -> Optional[ClienteModel]:
        return self.db.get(ClienteModel, cliente_id)

    def get_por_nombre(self, nombre: str) -> Optional[ClienteModel]:
        """HU-12: el cliente con ese nombre, sin distinguir mayúsculas ni espacios de más."""
        return (
            self.db.query(ClienteModel)
            .filter(ClienteModel.nombre_normalizado == normalizar_nombre(nombre))
            .first()
        )

    def get_o_crear(self, nombre: str, sector: Optional[str] = None) -> ClienteModel:
        """
        Devuelve el cliente registrado con ese nombre o lo crea (HU-12).

        "ACME", "acme" y " Acme  " son el mismo cliente: se conserva el nombre
        con el que se registró por primera vez.
        """
        existente = self.get_por_nombre(nombre)
        if existente:
            return existente

        cliente = ClienteModel(
            nombre=limpiar_nombre(nombre), nombre_normalizado=normalizar_nombre(nombre), sector=sector
        )
        self.db.add(cliente)
        try:
            self.db.commit()
        except IntegrityError:
            # Otra petición lo registró entre la consulta y el guardado.
            self.db.rollback()
            existente = self.get_por_nombre(nombre)
            if existente:
                return existente
            raise
        self.db.refresh(cliente)
        return cliente

    def listar(self) -> list[ClienteModel]:
        return self.db.query(ClienteModel).order_by(ClienteModel.nombre).all()

    def sugerir(self, texto: str = "", limite: int = LIMITE_SUGERENCIAS) -> list[ClienteModel]:
        """
        HU-12: clientes registrados cuyo nombre empieza por lo escrito, o cuyas
        palabras empiezan por ello ("bank" encuentra "Grupo Bank"). Primero los
        que empiezan por el texto. Sin texto devuelve los primeros por orden alfabético.
        """
        consulta = self.db.query(ClienteModel)
        buscado = normalizar_nombre(texto)
        if not buscado:
            return consulta.order_by(ClienteModel.nombre).limit(limite).all()

        patron = _escapar_like(buscado)
        coincidencias = consulta.filter(
            ClienteModel.nombre_normalizado.like(f"{patron}%", escape="\\")
            | ClienteModel.nombre_normalizado.like(f"% {patron}%", escape="\\")
        ).all()
        coincidencias.sort(
            key=lambda c: (not (c.nombre_normalizado or "").startswith(buscado), c.nombre_normalizado)
        )
        return coincidencias[:limite]


class ProyectoRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, proyecto_id: str) -> Optional[ProyectoModel]:
        return self.db.get(ProyectoModel, proyecto_id)

    def get_o_crear(self, nombre: str, cliente_id: str) -> ProyectoModel:
        """Un proyecto es único por cliente, también sin distinguir mayúsculas ni espacios (HU-12)."""
        proyecto = (
            self.db.query(ProyectoModel)
            .filter(
                ProyectoModel.nombre_normalizado == normalizar_nombre(nombre),
                ProyectoModel.cliente_id == cliente_id,
            )
            .first()
        )
        if proyecto:
            return proyecto
        proyecto = ProyectoModel(
            nombre=limpiar_nombre(nombre),
            nombre_normalizado=normalizar_nombre(nombre),
            cliente_id=cliente_id,
        )
        self.db.add(proyecto)
        self.db.commit()
        self.db.refresh(proyecto)
        return proyecto

    def listar_por_cliente(self, cliente_id: str) -> list[ProyectoModel]:
        return self.db.query(ProyectoModel).filter(ProyectoModel.cliente_id == cliente_id).all()
