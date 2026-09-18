import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import (
    auth,
    busquedas,
    candidatos,
    configuracion,
    dashboard,
    hojas_vida,
    preseleccion,
    solicitudes,
)
from backend.config import ALLOWED_ORIGINS
from backend.infrastructure.persistence import models  # noqa: F401  (registra las tablas)
from backend.infrastructure.persistence.database import init_db

logger = logging.getLogger(__name__)

app = FastAPI(
    title="BeeMatch API",
    description="Asistente inteligente de preselección de talento para Bee Consultoría y Negocios",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["Autenticación"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
app.include_router(solicitudes.router, prefix="/solicitudes", tags=["Solicitudes"])
app.include_router(busquedas.router, prefix="/busquedas", tags=["Búsquedas"])
app.include_router(preseleccion.router, prefix="/preseleccion", tags=["Preselección"])
app.include_router(candidatos.router, prefix="/candidatos", tags=["Candidatos"])
app.include_router(hojas_vida.router, prefix="/hojas-vida", tags=["Hojas de vida"])
app.include_router(configuracion.router, prefix="/configuracion", tags=["Configuración"])


@app.on_event("startup")
def on_startup():
    init_db()
    _sembrar_parametros()
    _sembrar_repositorio()

    # El planificador solo arranca si APScheduler está instalado y hay un
    # origen de hojas de vida configurado, sea cual sea el proveedor.
    if _hay_origen_configurado():
        from backend.workers.scheduler import iniciar_planificador

        iniciar_planificador()


def _hay_origen_configurado() -> bool:
    """Configuración registrada desde la aplicación (HU-05), o semilla de entorno."""
    from backend.config import MS_CLIENT_ID
    from backend.infrastructure.persistence.database import SessionLocal
    from backend.infrastructure.persistence.repositories.configuracion_repo import (
        RepositorioConfigRepository,
    )

    db = SessionLocal()
    try:
        if RepositorioConfigRepository(db).get_activa():
            return True
    finally:
        db.close()

    return bool(MS_CLIENT_ID)


def _sembrar_parametros():
    """Valores por defecto del motor de recomendación (HU-07)."""
    from backend.config import FINALISTAS_RERANK, TOP_N_RESULTADOS, UMBRAL_AFINIDAD_MINIMA
    from backend.infrastructure.persistence.database import SessionLocal
    from backend.infrastructure.persistence.repositories.configuracion_repo import ParametroRepository

    defaults = {
        "top_n_resultados": str(TOP_N_RESULTADOS),
        "finalistas_rerank": str(FINALISTAS_RERANK),
        "umbral_afinidad_minima": str(UMBRAL_AFINIDAD_MINIMA),
    }

    db = SessionLocal()
    try:
        repo = ParametroRepository(db)
        for clave, valor in defaults.items():
            if not repo.get(clave):
                repo.establecer(clave, valor)
    finally:
        db.close()


def _sembrar_repositorio():
    """
    Semilla de la conexión al repositorio de hojas de vida (HU-05).

    Registra Google Drive con el archivo de cuenta de servicio que vive en la
    raíz del proyecto, para que el equipo no tenga que configurar la conexión a
    mano en cada máquina. Pasa por el servicio de dominio, así que se aplican
    la validación contra Drive y el cifrado de credenciales de siempre.

    La configuración que un administrador registró desde la interfaz manda: si
    ya hay una activa, esta función no toca nada. Cualquier fallo se registra y
    la aplicación arranca igual, sin origen configurado.
    """
    import json

    from backend.config import GDRIVE_ARCHIVO_CREDENCIALES, GDRIVE_CARPETA_ID
    from backend.domain.services.repositorio_config_service import RepositorioConfigService
    from backend.infrastructure.persistence.database import SessionLocal
    from backend.infrastructure.persistence.repositories.configuracion_repo import (
        RepositorioConfigRepository,
    )
    from backend.infrastructure.repositorio.base import TIPO_GDRIVE

    db = SessionLocal()
    try:
        if RepositorioConfigRepository(db).get_activa():
            return

        ruta = GDRIVE_ARCHIVO_CREDENCIALES
        if not ruta.is_file():
            logger.info(
                "Sin semilla de repositorio: no existe %s. Registra la conexión desde "
                "Configuración.",
                ruta,
            )
            return

        contenido = ruta.read_text(encoding="utf-8")
        try:
            json.loads(contenido)
        except ValueError as exc:
            logger.warning(
                "La semilla de repositorio %s no es un JSON válido (%s). Se omite.", ruta, exc
            )
            return

        guardado, resultado = RepositorioConfigService(db).guardar(
            TIPO_GDRIVE,
            GDRIVE_CARPETA_ID,
            {"credenciales_json": contenido},
        )

        if guardado:
            logger.info(
                "Repositorio sembrado desde %s: Google Drive, carpeta %s, %s documentos.",
                ruta,
                GDRIVE_CARPETA_ID,
                resultado.documentos_detectados,
            )
        else:
            logger.warning(
                "La semilla de repositorio %s no pasó la validación con Google Drive: %s %s",
                ruta,
                resultado.mensaje,
                resultado.detalle or "",
            )
    except Exception:  # la aplicación arranca aunque la semilla falle
        logger.exception("No se pudo sembrar la configuración del repositorio de hojas de vida.")
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok"}
