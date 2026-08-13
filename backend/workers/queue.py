"""
Cola de trabajos (componente C15).

Las operaciones largas no pueden vivir dentro de una petición HTTP: una búsqueda
puede tardar hasta 2 minutos y la ingesta inicial decenas (RNF04).
"""

from typing import Callable, Optional

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

        _cola = Queue("beematch", connection=Redis.from_url(REDIS_URL))
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
