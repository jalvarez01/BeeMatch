"""Registro de auditoría transversal (HU-06, RNF32)."""

from typing import Optional

from sqlalchemy.orm import Session

from backend.infrastructure.persistence.repositories.configuracion_repo import BitacoraRepository

ACCION_LOGIN = "LOGIN"
ACCION_LOGOUT = "LOGOUT"
ACCION_SOLICITUD_CREADA = "SOLICITUD_CREADA"
ACCION_BUSQUEDA_EJECUTADA = "BUSQUEDA_EJECUTADA"
ACCION_PRESELECCION = "PRESELECCION"
ACCION_EXPORTACION = "EXPORTACION"
ACCION_CONFIG_CAMBIADA = "CONFIG_CAMBIADA"
ACCION_SINCRONIZACION = "SINCRONIZACION"


class BitacoraService:
    def __init__(self, db: Session):
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
            entidad=entidad,
            entidad_id=entidad_id,
            detalle=detalle,
        )

    def listar(self, limite: int = 100, desplazamiento: int = 0):
        return self.repo.listar(limite, desplazamiento)
