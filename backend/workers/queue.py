"""
Cola de trabajos (componente C15).

Las operaciones largas no pueden vivir dentro de una petición HTTP: una búsqueda
puede tardar hasta 2 minutos y la ingesta inicial decenas (RNF04).
"""

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Optional

from backend.config import REDIS_URL

if TYPE_CHECKING:
    from fastapi import BackgroundTasks

logger = logging.getLogger(__name__)

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


def hay_workers(cola) -> bool:
    """
    ¿Hay algún worker escuchando esta cola?

    Redis puede estar arriba sin que nadie procese lo que se encola: el trabajo
    se quedaría esperando para siempre y la búsqueda mostraría "en cola" sin
    avanzar. Si no se puede averiguar se asume que sí, para no desviar trabajos
    que sí tienen quien los atienda.
    """
    try:
        from rq import Worker

        return Worker.count(queue=cola) > 0
    except Exception as exc:
        if _redis_caido(exc):
            _olvidar_cola()
            return False
        return True


def _redis_caido(error: Exception) -> bool:
    """¿El error es de conexión con Redis (y no un fallo del trabajo)?"""
    try:
        from redis.exceptions import ConnectionError as ErrorDeConexion
        from redis.exceptions import TimeoutError as ErrorDeTiempo

        return isinstance(error, (ErrorDeConexion, ErrorDeTiempo, OSError))
    except ImportError:
        return False


def _olvidar_cola() -> None:
    """Descarta la conexión guardada para que la siguiente llamada vuelva a comprobar."""
    global _cola
    _cola = None


def _enviar_a_la_cola(cola, funcion: Callable, args: tuple, timeout: int) -> Optional[str]:
    """
    Encola el trabajo. Si Redis dejó de responder después de haberse conectado
    (se cayó con la API ya en marcha), devuelve None en vez de propagar el error
    para que quien llama ejecute el trabajo por su cuenta: una búsqueda no debe
    fallar con 500 porque la cola no esté.
    """
    try:
        return cola.enqueue(funcion, *args, job_timeout=timeout).id
    except Exception as exc:
        if not _redis_caido(exc):
            raise
        logger.warning("Redis dejó de responder al encolar, el trabajo corre en la API: %s", exc)
        _olvidar_cola()
        return None


def encolar(funcion: Callable, *args, timeout: int = 900) -> Optional[str]:
    """
    Encola el trabajo y devuelve su id. Sin Redis, o con Redis pero sin worker
    que lo atienda, ejecuta directo.
    """
    cola = get_cola()
    if cola is not None and hay_workers(cola):
        id_trabajo = _enviar_a_la_cola(cola, funcion, args, timeout)
        if id_trabajo is not None:
            return id_trabajo
    funcion(*args)
    return None


def despachar(
    tareas: "BackgroundTasks", funcion: Callable, *args, timeout: int = 900
) -> Optional[str]:
    """
    Como `encolar`, pero sin Redis (o sin worker) el trabajo corre en segundo plano en vez de en línea.

    `encolar` ejecuta directo, y dentro de una petición eso deja la respuesta
    esperando todo el análisis: el frontend no recibe el 202 hasta que termina y
    nunca llega a mostrar el indicador de progreso (HU-22). Con `tareas` la
    respuesta sale primero y el trabajo corre después.
    """
    cola = get_cola()
    if cola is not None and hay_workers(cola):
        id_trabajo = _enviar_a_la_cola(cola, funcion, args, timeout)
        if id_trabajo is not None:
            return id_trabajo
    tareas.add_task(funcion, *args)
    return None
