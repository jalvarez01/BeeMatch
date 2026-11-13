"""
Observabilidad (C27): logs estructurados, identificador de petición y Sentry opcional.

- En producción los logs salen en JSON, una línea por evento, para que se puedan
  filtrar (`docker compose logs api | jq`) o enviar a CloudWatch sin parsear texto.
  En desarrollo siguen siendo legibles. Se fuerza con LOG_FORMATO=json|texto.
- Cada petición lleva un identificador (`X-Request-ID`, el que mande el proxy o
  uno nuevo) que aparece en todos sus logs y en la respuesta: con el id que ve el
  usuario se encuentra qué pasó en el servidor.
- Solo se registra método, ruta, estado y duración. Nunca el cuerpo ni la query
  string: ahí viajan contraseñas y tokens.
- Sentry se activa únicamente si SENTRY_DSN está definido.
"""

import contextvars
import json
import logging
import time
import uuid
from datetime import UTC, datetime

from starlette.middleware.base import BaseHTTPMiddleware

from backend import config

id_de_peticion: contextvars.ContextVar[str] = contextvars.ContextVar("id_de_peticion", default="-")

CAMPOS_ESTANDAR = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}


class FormatoJson(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        evento = {
            "hora": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "nivel": record.levelname,
            "logger": record.name,
            "mensaje": record.getMessage(),
            "peticion": id_de_peticion.get(),
        }
        evento.update({k: v for k, v in record.__dict__.items() if k not in CAMPOS_ESTANDAR})
        if record.exc_info:
            evento["excepcion"] = self.formatException(record.exc_info)
        return json.dumps(evento, ensure_ascii=False, default=str)


class FiltroDePeticion(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.peticion = id_de_peticion.get()
        return True


def configurar_logging() -> None:
    usar_json = config.LOG_FORMATO == "json" or (config.LOG_FORMATO == "auto" and config.ES_PRODUCCION)
    manejador = logging.StreamHandler()
    if usar_json:
        manejador.setFormatter(FormatoJson())
    else:
        manejador.addFilter(FiltroDePeticion())
        manejador.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(peticion)s] %(name)s: %(message)s")
        )

    raiz = logging.getLogger()
    raiz.handlers = [manejador]
    raiz.setLevel(config.LOG_NIVEL)
    # uvicorn trae su propio formato; se unifica con el nuestro.
    for nombre in ("uvicorn", "uvicorn.error"):
        registro = logging.getLogger(nombre)
        registro.handlers = []
        registro.propagate = True
    logging.getLogger("uvicorn.access").disabled = True  # lo reemplaza el middleware
    # httpx escribe a nivel INFO la URL completa de cada llamada saliente, query
    # incluida (Drive, Graph, OpenAI): ahí pueden ir identificadores o tokens.
    for nombre in ("httpx", "httpcore"):
        logging.getLogger(nombre).setLevel(logging.WARNING)


def iniciar_sentry() -> bool:
    """Activa Sentry si hay DSN y el paquete está instalado. Devuelve si quedó activo."""
    if not config.SENTRY_DSN:
        return False
    try:
        import sentry_sdk
    except ImportError:
        logging.getLogger(__name__).warning("SENTRY_DSN definido pero sentry-sdk no está instalado.")
        return False
    sentry_sdk.init(
        dsn=config.SENTRY_DSN,
        environment=config.ENTORNO,
        traces_sample_rate=0.0,
        # Sin datos personales: el correo y el cuerpo de las peticiones no salen del servidor.
        send_default_pii=False,
    )
    return True


class RegistroDePeticiones(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        identificador = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        marca = id_de_peticion.set(identificador)
        inicio = time.perf_counter()
        logger = logging.getLogger("backend.peticiones")
        try:
            respuesta = await call_next(request)
        except Exception:
            logger.exception(
                "Petición con error no controlado",
                extra={"metodo": request.method, "ruta": request.url.path},
            )
            raise
        finally:
            duracion = round((time.perf_counter() - inicio) * 1000)
        respuesta.headers["X-Request-ID"] = identificador
        if request.url.path not in ("/health", "/health/ready"):
            logger.info(
                "%s %s %s",
                request.method,
                request.url.path,
                respuesta.status_code,
                extra={
                    "metodo": request.method,
                    "ruta": request.url.path,
                    "estado": respuesta.status_code,
                    "duracion_ms": duracion,
                },
            )
        id_de_peticion.reset(marca)
        return respuesta
