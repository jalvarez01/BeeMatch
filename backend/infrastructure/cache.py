"""
Caché en Redis (componente C22).

Guarda el embedding de las consultas ya vistas: re-ejecutar una solicitud o
ajustarla (HU-15) repite el mismo texto de consulta, y cada embedding es una
llamada de pago a OpenAI y entre 200 y 800 ms de espera.

Es un acelerador, nunca un requisito: si Redis no está o falla, todo funciona
igual, solo que sin recordar. La caché de la cola (RQ) y esta comparten Redis,
pero no comparten claves: esta usa el prefijo `beematch:emb:`.
"""

import hashlib
import json
import logging
import time
from typing import Optional

from backend.config import EMBEDDING_CACHE_TTL_HORAS, REDIS_URL

logger = logging.getLogger(__name__)

PREFIJO = "beematch:emb:"
# Tras un fallo de conexión no se reintenta durante este tiempo: sin esto, cada
# búsqueda pagaría el timeout de conexión mientras Redis esté caído.
ESPERA_TRAS_FALLO_SEGUNDOS = 30

_conexion = None
_ultimo_fallo = 0.0


def obtener_redis():
    """Conexión a Redis, o None si no está disponible."""
    global _conexion, _ultimo_fallo
    if _conexion is not None:
        return _conexion
    if time.monotonic() - _ultimo_fallo < ESPERA_TRAS_FALLO_SEGUNDOS and _ultimo_fallo:
        return None
    try:
        from redis import Redis

        candidata = Redis.from_url(
            REDIS_URL, socket_connect_timeout=1, socket_timeout=1, decode_responses=True
        )
        candidata.ping()
        _conexion = candidata
        return _conexion
    except Exception:
        _ultimo_fallo = time.monotonic()
        return None


def reiniciar() -> None:
    """Olvida la conexión y el fallo anterior. Para pruebas."""
    global _conexion, _ultimo_fallo
    _conexion = None
    _ultimo_fallo = 0.0


def _clave(modelo: str, dimensiones: int, texto: str) -> str:
    huella = hashlib.sha256(texto.strip().encode("utf-8")).hexdigest()
    return f"{PREFIJO}{modelo}:{dimensiones}:{huella}"


def obtener_embedding(modelo: str, dimensiones: int, texto: str) -> Optional[list[float]]:
    redis = obtener_redis()
    if redis is None:
        return None
    try:
        valor = redis.get(_clave(modelo, dimensiones, texto))
        return json.loads(valor) if valor else None
    except Exception as exc:  # noqa: BLE001  (la caché nunca debe tumbar una búsqueda)
        logger.warning("Caché de embeddings no disponible al leer: %s", exc)
        return None


def guardar_embedding(modelo: str, dimensiones: int, texto: str, vector: list[float]) -> None:
    redis = obtener_redis()
    if redis is None:
        return
    try:
        redis.setex(
            _clave(modelo, dimensiones, texto),
            EMBEDDING_CACHE_TTL_HORAS * 3600,
            json.dumps(vector),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Caché de embeddings no disponible al escribir: %s", exc)
