"""Inyección de dependencias centralizada."""

from backend.infrastructure.persistence.database import get_db
from backend.security import exigir_rol, get_current_user

__all__ = ["get_db", "get_current_user", "exigir_rol"]
