"""
Cifrado simétrico para secretos almacenados en base de datos (RNF10).

Se usa para el client secret de Microsoft Graph: la credencial nunca queda en
claro en la tabla ni aparece en los logs. El algoritmo es Fernet (AES-128-CBC
con autenticación HMAC).

La clave sale de ENCRYPTION_KEY. Si no está definida se deriva del JWT_SECRET,
de modo que el entorno de desarrollo funcione sin configuración adicional; en
producción debe definirse explícitamente y vivir en el gestor de secretos.
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from backend.config import ENCRYPTION_KEY, JWT_SECRET

SAL_DERIVACION = b"beematch-cifrado-v1"


class CifradoError(Exception):
    """El valor almacenado no pudo descifrarse: cambió la clave o el dato está corrupto."""


def _clave() -> bytes:
    if ENCRYPTION_KEY:
        return ENCRYPTION_KEY.encode("utf-8")

    derivada = hashlib.pbkdf2_hmac("sha256", JWT_SECRET.encode("utf-8"), SAL_DERIVACION, 100_000)
    return base64.urlsafe_b64encode(derivada)


def cifrar(texto: str) -> str:
    return Fernet(_clave()).encrypt(texto.encode("utf-8")).decode("ascii")


def descifrar(cifrado: str) -> str:
    try:
        return Fernet(_clave()).decrypt(cifrado.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise CifradoError(
            "No fue posible descifrar la credencial almacenada. "
            "Vuelve a registrar la configuración de OneDrive."
        ) from exc


def enmascarar(secreto: str, visibles: int = 4) -> str:
    """Representación segura para mostrar en la interfaz: nunca el valor completo."""
    if not secreto:
        return ""
    if len(secreto) <= visibles:
        return "•" * len(secreto)
    return "•" * 12 + secreto[-visibles:]
