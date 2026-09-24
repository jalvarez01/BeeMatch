from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.domain.services.bitacora_service import ACCION_SINCRONIZACION, BitacoraService
from backend.domain.services.repositorio_config_service import RepositorioNoConfiguradoError
from backend.infrastructure.persistence.database import get_db
from backend.infrastructure.persistence.models.hoja_vida import (
    ESTADO_INDEXADA,
    ESTADO_NO_PROCESABLE,
    ESTADO_PENDIENTE,
)
from backend.infrastructure.persistence.repositories.hoja_vida_repo import HojaDeVidaRepository
from backend.schemas.hoja_vida import (
    EstadoIndiceResponse,
    HojaDeVidaResponse,
    SincronizacionResponse,
)
from backend.security import ROL_ADMINISTRADOR, exigir_rol, get_current_user
from backend.workers.scheduler import sincronizar_y_encolar

router = APIRouter()


def _plural(cantidad: int, singular: str, plural: str) -> str:
    return f"{cantidad} {singular if cantidad == 1 else plural}"


def resumen_de_analisis(indexadas: int, no_procesables: int) -> str:
    """HU-17: cierre del análisis, con cuántos se leyeron y cuántos no."""
    analizados = _plural(indexadas, "documento fue analizado", "documentos fueron analizados")
    fallidos = _plural(no_procesables, "no pudo procesarse", "no pudieron procesarse")
    return f"Análisis finalizado: {analizados} y {fallidos}."


@router.get("/estado", response_model=EstadoIndiceResponse)
def estado_indice(db: Session = Depends(get_db), _=Depends(get_current_user)):
    """HU-17: cuántas hojas de vida hay indexadas y cuántas no se pudieron procesar."""
    repo = HojaDeVidaRepository(db)
    indexadas = repo.contar_por_estado(ESTADO_INDEXADA)
    pendientes = repo.contar_por_estado(ESTADO_PENDIENTE)
    no_procesables = repo.contar_por_estado(ESTADO_NO_PROCESABLE)
    en_proceso = pendientes > 0
    total = indexadas + pendientes + no_procesables
    return EstadoIndiceResponse(
        total=total,
        indexadas=indexadas,
        pendientes=pendientes,
        no_procesables=no_procesables,
        en_proceso=en_proceso,
        resumen=None if en_proceso or total == 0 else resumen_de_analisis(indexadas, no_procesables),
    )


@router.get("/no-procesables", response_model=list[HojaDeVidaResponse])
def listar_no_procesables(db: Session = Depends(get_db), _=Depends(get_current_user)):
    """HU-17: documentos que no se pudieron leer y por qué (dañado, con contraseña...)."""
    return HojaDeVidaRepository(db).listar_por_estado(ESTADO_NO_PROCESABLE)


@router.post("/sincronizar", response_model=SincronizacionResponse)
def sincronizar(
    db: Session = Depends(get_db),
    current_user=Depends(exigir_rol(ROL_ADMINISTRADOR)),
):
    """HU-05, HU-16: sincronización bajo demanda contra la carpeta configurada."""
    try:
        resultado = sincronizar_y_encolar()
    except RepositorioNoConfiguradoError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        # HU-26: el error se explica, no se traga.
        raise HTTPException(status_code=502, detail=f"No fue posible sincronizar: {exc}")
    BitacoraService(db).registrar(ACCION_SINCRONIZACION, usuario_id=current_user.id)

    aplazados = resultado["documentos_aplazados"]
    if aplazados:
        # La sincronización sí ocurrió: los documentos quedaron registrados y
        # pendientes. Se dice cuántos y por qué, en vez de reportar un fallo
        # que no fue (HU-26).
        mensaje = (
            f"Sincronización completada: {resultado['documentos_detectados']} documentos "
            f"registrados. {aplazados} quedaron pendientes de indexar. "
            f"{resultado['motivo_aplazamiento']}"
        )
    else:
        mensaje = "Sincronización iniciada. La indexación continúa en segundo plano."

    return SincronizacionResponse(
        documentos_detectados=resultado["documentos_detectados"],
        documentos_encolados=resultado["documentos_encolados"],
        documentos_aplazados=aplazados,
        mensaje=mensaje,
    )
