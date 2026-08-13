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

    # El planificador solo arranca si APScheduler está instalado y hay
    # credenciales de Graph configuradas.
    from backend.config import MS_CLIENT_ID

    if MS_CLIENT_ID:
        from backend.workers.scheduler import iniciar_planificador

        iniciar_planificador()


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


@app.get("/health")
def health():
    return {"status": "ok"}
