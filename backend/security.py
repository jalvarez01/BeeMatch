"""
Autenticación y autorización.

Contraseñas: PBKDF2-HMAC-SHA256 con salt aleatorio por usuario y 260.000
iteraciones. La contraseña en claro nunca se almacena ni se registra en la
bitácora. La comparación usa `hmac.compare_digest` para evitar filtrar
información por el tiempo de respuesta.

Sesión: JWT firmado, con expiración configurable (RNF12).
Autorización: control de acceso por roles (RNF08).

Cuando se active el SSO con Microsoft Entra ID, los usuarios federados quedan
con `password_hash` nulo y el token lo emite Entra; este módulo seguirá
sirviendo para las cuentas locales de administración.
"""

import base64
import hashlib
import hmac
import os
from datetime import UTC, datetime, timedelta
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.config import JWT_ALGORITHM, JWT_EXPIRACION_MINUTOS, JWT_SECRET
from backend.infrastructure.persistence.database import get_db
from backend.infrastructure.persistence.repositories.usuario_repo import UsuarioRepository
from types import SimpleNamespace

security_scheme = HTTPBearer(auto_error=False)

ROL_COORDINADOR = "COORDINADOR"
ROL_DIRECTOR = "DIRECTOR"
ROL_ADMINISTRADOR = "ADMINISTRADOR"
ROL_SUPERADMINISTRADOR = "SUPERADMINISTRADOR"
ROLES_VALIDOS = {ROL_COORDINADOR, ROL_DIRECTOR, ROL_ADMINISTRADOR, ROL_SUPERADMINISTRADOR}

# HU-03: roles que un actor puede otorgar o retirar. La superusuaria nunca
# aparece como objetivo: su rol no se puede dar ni quitar desde la aplicación,
# así que ningún administrador, por poderoso que sea, llega a igualarla.
ROLES_QUE_GESTIONA = {
    ROL_SUPERADMINISTRADOR: {ROL_COORDINADOR, ROL_DIRECTOR, ROL_ADMINISTRADOR},
    ROL_ADMINISTRADOR: {ROL_COORDINADOR, ROL_DIRECTOR},
}


def puede_gestionar(actor_rol: str, objetivo_rol: str) -> bool:
    """¿Puede `actor_rol` editar o inactivar a un usuario con `objetivo_rol`?"""
    return objetivo_rol in ROLES_QUE_GESTIONA.get(actor_rol, set())

# --- Contraseñas -------------------------------------------------------------

ALGORITMO_HASH = "pbkdf2_sha256"
ITERACIONES = 260_000
LONGITUD_SALT = 16
LONGITUD_MINIMA_PASSWORD = 8


def hashear_password(password: str) -> str:
    """
    Deriva el hash de una contraseña. El resultado incluye el algoritmo, las
    iteraciones y el salt, de modo que se puedan subir las iteraciones más
    adelante sin invalidar las contraseñas existentes.
    """
    salt = os.urandom(LONGITUD_SALT)
    derivada = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERACIONES)
    return "${}${}${}${}".format(
        ALGORITMO_HASH,
        ITERACIONES,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(derivada).decode("ascii"),
    ).lstrip("$")


def verificar_password(password: str, almacenado: Optional[str]) -> bool:
    """Compara una contraseña contra el hash guardado. Nunca lanza excepción."""
    if not almacenado:
        return False

    try:
        algoritmo, iteraciones, salt_b64, hash_b64 = almacenado.split("$")
    except ValueError:
        return False

    if algoritmo != ALGORITMO_HASH:
        return False

    try:
        salt = base64.b64decode(salt_b64)
        esperado = base64.b64decode(hash_b64)
        derivada = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iteraciones))
    except (ValueError, TypeError):
        return False

    return hmac.compare_digest(derivada, esperado)


def validar_fortaleza(password: str) -> None:
    """Reglas mínimas al crear o cambiar una contraseña."""
    if len(password) < LONGITUD_MINIMA_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"La contraseña debe tener al menos {LONGITUD_MINIMA_PASSWORD} caracteres.",
        )
    if password.isdigit() or password.isalpha():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La contraseña debe combinar letras y números.",
        )


# --- Tokens ------------------------------------------------------------------


def crear_token(usuario_id: str, correo: str, rol: str) -> str:
    payload = {
        "sub": usuario_id,
        "correo": correo,
        "rol": rol,
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=JWT_EXPIRACION_MINUTOS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decodificar_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La sesión expiró. Inicia sesión nuevamente.",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido.")


# --- Dependencias ------------------------------------------------------------

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db),
):
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Se requiere autenticación."
        )

    payload = decodificar_token(credentials.credentials)
    usuario = UsuarioRepository(db).get_by_id(payload.get("sub", ""))
    if not usuario or not usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado o inactivo."
        )

    # El rol del token se mantiene hasta que el usuario inicie sesión de nuevo.
    rol_sesion = payload.get("rol")
    if rol_sesion not in ROLES_VALIDOS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido."
        )

    
    # Crear una copia independiente para no modificar el objeto de SQLAlchemy.
    datos_usuario = {
        columna.name: getattr(usuario, columna.name)
        for columna in usuario.__table__.columns
    }
    usuario_sesion = SimpleNamespace(**datos_usuario)

    # El rol del token se aplica solo a esta sesión.
    usuario_sesion.rol = rol_sesion
    return usuario_sesion

def exigir_rol(*roles: str):
    """Restringe un endpoint a ciertos roles (RNF08)."""

    def _verificar(current_user=Depends(get_current_user)):
        # La superusuaria tiene todos los permisos (HU-03).
        if current_user.rol != ROL_SUPERADMINISTRADOR and current_user.rol not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para realizar esta acción.",
            )
        return current_user

    return _verificar
