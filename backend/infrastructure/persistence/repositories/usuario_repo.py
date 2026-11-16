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
        activo: bool = True,
        pendiente: bool = False,
    ) -> UsuarioModel:
        usuario = UsuarioModel(
            nombre=nombre,
            correo=correo.lower(),
            rol=rol,
            password_hash=password_hash,
            id_entra=id_entra,
            debe_cambiar_password=debe_cambiar_password,
            activo=activo,
            pendiente=pendiente,
        )
        self.db.add(usuario)
        self.db.commit()
        self.db.refresh(usuario)
        return usuario

    def actualizar(self, usuario: UsuarioModel, **campos) -> UsuarioModel:
        """Aplica los campos dados (nombre, correo, rol, activo, pendiente)."""
        for nombre, valor in campos.items():
            setattr(usuario, nombre, valor.lower() if nombre == "correo" else valor)
        self.db.commit()
        self.db.refresh(usuario)
        return usuario

    def existe_rol(self, rol: str) -> bool:
        return self.db.query(UsuarioModel).filter(UsuarioModel.rol == rol).first() is not None

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

    def eliminar(self, usuario: UsuarioModel) -> None:
        """
        Borra la cuenta y conserva lo que hizo. Las solicitudes y preselecciones
        quedan sin cuenta asociada, pero cada solicitud ya guarda el nombre de su
        autor; si alguna no lo tenía, se completa antes de soltarla.
        """
        from backend.infrastructure.persistence.models.busqueda import PreseleccionModel
        from backend.infrastructure.persistence.models.solicitud import SolicitudModel

        self.db.query(SolicitudModel).filter(
            SolicitudModel.usuario_id == usuario.id, SolicitudModel.autor_nombre.is_(None)
        ).update({"autor_nombre": usuario.nombre}, synchronize_session=False)
        self.db.query(SolicitudModel).filter(SolicitudModel.usuario_id == usuario.id).update(
            {"usuario_id": None}, synchronize_session=False
        )
        self.db.query(PreseleccionModel).filter(PreseleccionModel.usuario_id == usuario.id).update(
            {"usuario_id": None}, synchronize_session=False
        )
        self.db.delete(usuario)
        self.db.commit()

    def marcar_acceso(self, usuario: UsuarioModel) -> None:
        usuario.ultimo_acceso = utcnow()
        self.db.commit()
