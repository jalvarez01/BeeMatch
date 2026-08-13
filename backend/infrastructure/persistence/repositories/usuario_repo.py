from typing import Optional

from sqlalchemy.orm import Session

from backend.infrastructure.persistence.models._base import utcnow
from backend.infrastructure.persistence.models.usuario import UsuarioModel


class UsuarioRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, usuario_id: str) -> Optional[UsuarioModel]:
        return self.db.get(UsuarioModel, usuario_id)

    def get_by_correo(self, correo: str) -> Optional[UsuarioModel]:
        return self.db.query(UsuarioModel).filter(UsuarioModel.correo == correo.lower()).first()

    def listar(self) -> list[UsuarioModel]:
        return self.db.query(UsuarioModel).order_by(UsuarioModel.nombre).all()

    def contar(self) -> int:
        return self.db.query(UsuarioModel).count()

    def crear(
        self,
        nombre: str,
        correo: str,
        rol: str,
        password_hash: Optional[str] = None,
        id_entra: Optional[str] = None,
        debe_cambiar_password: bool = False,
    ) -> UsuarioModel:
        usuario = UsuarioModel(
            nombre=nombre,
            correo=correo.lower(),
            rol=rol,
            password_hash=password_hash,
            id_entra=id_entra,
            debe_cambiar_password=debe_cambiar_password,
        )
        self.db.add(usuario)
        self.db.commit()
        self.db.refresh(usuario)
        return usuario

    def actualizar_password(self, usuario: UsuarioModel, password_hash: str) -> UsuarioModel:
        usuario.password_hash = password_hash
        usuario.debe_cambiar_password = False
        self.db.commit()
        self.db.refresh(usuario)
        return usuario

    def actualizar_rol(self, usuario_id: str, rol: str) -> Optional[UsuarioModel]:
        usuario = self.get_by_id(usuario_id)
        if not usuario:
            return None
        usuario.rol = rol
        self.db.commit()
        self.db.refresh(usuario)
        return usuario

    def desactivar(self, usuario_id: str) -> Optional[UsuarioModel]:
        """Se desactiva, no se borra, para conservar la trazabilidad de la bitácora."""
        usuario = self.get_by_id(usuario_id)
        if not usuario:
            return None
        usuario.activo = False
        self.db.commit()
        self.db.refresh(usuario)
        return usuario

    def marcar_acceso(self, usuario: UsuarioModel) -> None:
        usuario.ultimo_acceso = utcnow()
        self.db.commit()