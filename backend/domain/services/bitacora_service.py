"""Registro de auditoría transversal (HU-06, RNF32)."""

from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from backend.infrastructure.persistence.repositories.configuracion_repo import BitacoraRepository
from backend.infrastructure.persistence.repositories.usuario_repo import UsuarioRepository

ACCION_LOGIN = "LOGIN"
ACCION_LOGOUT = "LOGOUT"
ACCION_SOLICITUD_CREADA = "SOLICITUD_CREADA"
ACCION_BUSQUEDA_EJECUTADA = "BUSQUEDA_EJECUTADA"
ACCION_PRESELECCION = "PRESELECCION"
ACCION_EXPORTACION = "EXPORTACION"
ACCION_CONFIG_CAMBIADA = "CONFIG_CAMBIADA"
ACCION_SINCRONIZACION = "SINCRONIZACION"
ACCION_ERROR_SERVICIO = "ERROR_SERVICIO"


class RangoDeFechasInvalidoError(ValueError):
    """`fecha_desde` es posterior a `fecha_hasta`."""


class BitacoraService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = BitacoraRepository(db)

    def registrar(
        self,
        accion: str,
        usuario_id: Optional[str] = None,
        entidad: Optional[str] = None,
        entidad_id: Optional[str] = None,
        detalle: Optional[str] = None,
    ):
        return self.repo.registrar(
            accion=accion,
            usuario_id=usuario_id,
            rol=self._rol_de(usuario_id),
            entidad=entidad,
            entidad_id=entidad_id,
            detalle=detalle,
        )

    def _rol_de(self, usuario_id: Optional[str]) -> Optional[str]:
        """Rol del usuario en este momento, para dejarlo fijo en el registro."""
        if not usuario_id:
            return None
        usuario = UsuarioRepository(self.db).get_by_id(usuario_id)
        return usuario.rol if usuario else None

    def listar(
        self,
        limite: int = 100,
        desplazamiento: int = 0,
        usuario_id: Optional[str] = None,
        fecha_desde: Optional[date] = None,
        fecha_hasta: Optional[date] = None,
    ) -> tuple[int, list[dict]]:
        """Más recientes primero. Las fechas son inclusivas y se toman en UTC."""
        if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
            raise RangoDeFechasInvalidoError(
                "La fecha inicial no puede ser posterior a la fecha final."
            )
        return self.repo.consultar(limite, desplazamiento, usuario_id, fecha_desde, fecha_hasta)
