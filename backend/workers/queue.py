"""
Cola de trabajos (componente C15).

Las operaciones largas no pueden vivir dentro de una petición HTTP: una búsqueda
puede tardar hasta 2 minutos y la ingesta inicial decenas (RNF04).
"""

from collections.abc import Callable
from typing import Optional

from backend.config import REDIS_URL

_cola = None


def get_cola():
    """Cola RQ. Si Redis no está disponible, se devuelve None y se ejecuta en línea."""
    global _cola
    if _cola is not None:
        return _cola

    try:
        from redis import Redis
        from rq import Queue

        conexion = Redis.from_url(REDIS_URL, socket_connect_timeout=2)
        # Redis.from_url no abre la conexión: sin el ping, un Redis caído no se
        # detecta aquí y el error aparece recién al encolar, tumbando la
        # sincronización en vez de ejecutar en línea como dice esta función.
        conexion.ping()
        _cola = Queue("beematch", connection=conexion)
        return _cola
    except Exception:
        return None


def encolar(funcion: Callable, *args, timeout: int = 900) -> Optional[str]:
    """Encola el trabajo y devuelve su id. En desarrollo sin Redis, ejecuta directo."""
    cola = get_cola()
    if cola is None:
        funcion(*args)
        return None
    return cola.enqueue(funcion, *args, job_timeout=timeout).id
