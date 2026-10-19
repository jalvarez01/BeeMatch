"""Bloqueo temporal por intentos fallidos de inicio de sesión (HU-01)."""

from datetime import UTC, datetime, timedelta
from math import ceil

from sqlalchemy.orm import Session

from backend.config import LOGIN_BLOQUEO_MINUTOS, LOGIN_MAX_INTENTOS
from backend.infrastructure.persistence.models._base import utcnow
from backend.infrastructure.persistence.models.usuario import IntentoLoginModel


def _como_utc(momento: datetime) -> datetime:
    """SQLite devuelve fechas sin zona; todas las que guardamos son UTC."""
    return momento if momento.tzinfo else momento.replace(tzinfo=UTC)


class BloqueoLoginService:
    """
    Cuenta los fallos por correo, exista o no el usuario, para que el bloqueo
    no revele qué correos están registrados. Un acceso correcto reinicia la
    cuenta; un bloqueo vencido también.
    """

    def __init__(self, db: Session):
        self.db = db

    def _fila(self, correo: str) -> IntentoLoginModel | None:
        return self.db.get(IntentoLoginModel, correo.lower())

    def minutos_restantes(self, correo: str) -> int:
        """Minutos de bloqueo que quedan; 0 si el correo puede intentar."""
        fila = self._fila(correo)
        if not fila or not fila.bloqueado_hasta:
            return 0

        faltante = _como_utc(fila.bloqueado_hasta) - utcnow()
        if faltante.total_seconds() <= 0:
            self.reiniciar(correo)
            return 0
        return ceil(faltante.total_seconds() / 60)

    def registrar_fallo(self, correo: str) -> None:
        fila = self._fila(correo)
        if not fila:
            fila = IntentoLoginModel(correo=correo.lower(), fallidos=0)
            self.db.add(fila)

        fila.fallidos += 1
        if fila.fallidos >= LOGIN_MAX_INTENTOS:
            fila.bloqueado_hasta = utcnow() + timedelta(minutes=LOGIN_BLOQUEO_MINUTOS)
        self.db.commit()

    def reiniciar(self, correo: str) -> None:
        fila = self._fila(correo)
        if fila:
            self.db.delete(fila)
            self.db.commit()
