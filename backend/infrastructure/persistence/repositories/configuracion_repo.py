from typing import Optional

from sqlalchemy.orm import Session

from backend.infrastructure.persistence.models.configuracion import (
    ParametroRecomendacionModel,
    RegistroBitacoraModel,
)


class ParametroRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, clave: str) -> Optional[ParametroRecomendacionModel]:
        return (
            self.db.query(ParametroRecomendacionModel)
            .filter(ParametroRecomendacionModel.clave == clave)
            .first()
        )

    def listar(self) -> list[ParametroRecomendacionModel]:
        return self.db.query(ParametroRecomendacionModel).order_by(ParametroRecomendacionModel.clave).all()

    def establecer(self, clave: str, valor: str, usuario_id: Optional[str] = None) -> ParametroRecomendacionModel:
        parametro = self.get(clave)
        if parametro:
            parametro.valor = valor
            parametro.actualizado_por = usuario_id
        else:
            parametro = ParametroRecomendacionModel(clave=clave, valor=valor, actualizado_por=usuario_id)
            self.db.add(parametro)
        self.db.commit()
        self.db.refresh(parametro)
        return parametro


class BitacoraRepository:
    def __init__(self, db: Session):
        self.db = db

    def registrar(self, **datos) -> RegistroBitacoraModel:
        registro = RegistroBitacoraModel(**datos)
        self.db.add(registro)
        self.db.commit()
        self.db.refresh(registro)
        return registro

    def listar(self, limite: int = 100, desplazamiento: int = 0) -> list[RegistroBitacoraModel]:
        return (
            self.db.query(RegistroBitacoraModel)
            .order_by(RegistroBitacoraModel.created_at.desc())
            .offset(desplazamiento)
            .limit(limite)
            .all()
        )
