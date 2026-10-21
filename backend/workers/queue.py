"""
Cola de trabajos (componente C15).

Las operaciones largas no pueden vivir dentro de una petición HTTP: una búsqueda
puede tardar hasta 2 minutos y la ingesta inicial decenas (RNF04).
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Optional

from backend.config import REDIS_URL

if TYPE_CHECKING:
    from fastapi import BackgroundTasks

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


def despachar(
    tareas: "BackgroundTasks", funcion: Callable, *args, timeout: int = 900
) -> Optional[str]:
    """
    Como `encolar`, pero sin Redis el trabajo corre en segundo plano en vez de en línea.

    `encolar` ejecuta directo, y dentro de una petición eso deja la respuesta
    esperando todo el análisis: el frontend no recibe el 202 hasta que termina y
    nunca llega a mostrar el indicador de progreso (HU-22). Con `tareas` la
    respuesta sale primero y el trabajo corre después.
    """
    cola = get_cola()
    if cola is None:
        tareas.add_task(funcion, *args)
        return None
    return cola.enqueue(funcion, *args, job_timeout=timeout).id
