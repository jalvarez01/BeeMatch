from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.domain.services.bitacora_service import (
    ACCION_CONFIG_CAMBIADA,
    BitacoraService,
)
from backend.domain.services.onedrive_config_service import OneDriveConfigService
from backend.domain.services.repositorio_config_service import RepositorioConfigService
from backend.infrastructure.persistence.database import get_db
from backend.infrastructure.persistence.repositories.configuracion_repo import ParametroRepository
from backend.schemas.configuracion import BitacoraResponse, ParametroResponse, ParametroUpdate
from backend.schemas.onedrive import (
    ConexionOneDriveRequest,
    ConexionOneDriveResponse,
    GuardarConexionResponse,
    PruebaConexionResponse,
)
from backend.schemas.repositorio import (
    ConexionRepositorioRequest,
    ConexionRepositorioResponse,
    GuardarRepositorioResponse,
)
from backend.security import ROL_ADMINISTRADOR, exigir_rol

router = APIRouter()

ACCION_ONEDRIVE_CONFIGURADO = "ONEDRIVE_CONFIGURADO"
ACCION_ONEDRIVE_PROBADO = "ONEDRIVE_PROBADO"
ACCION_REPOSITORIO_CONFIGURADO = "REPOSITORIO_CONFIGURADO"
ACCION_REPOSITORIO_PROBADO = "REPOSITORIO_PROBADO"


# =============================================================================
# Conexión con OneDrive (HU-05) — solo administrador (RNF08)
# =============================================================================


@router.get("/onedrive", response_model=ConexionOneDriveResponse)
def obtener_conexion(db: Session = Depends(get_db), _=Depends(exigir_rol(ROL_ADMINISTRADOR))):
    """Configuración vigente. El Client Secret viaja enmascarado."""
    config = OneDriveConfigService(db).obtener()
    return config or ConexionOneDriveResponse(configurado=False)


@router.post("/onedrive/probar", response_model=PruebaConexionResponse)
def probar_conexion(
    datos: ConexionOneDriveRequest,
    db: Session = Depends(get_db),
    current_user=Depends(exigir_rol(ROL_ADMINISTRADOR)),
):
    """
    Valida credenciales y ruta sin guardar nada.

    Responde siempre 200: el resultado va en el cuerpo, con el motivo del error
    cuando la conexión falla.
    """
    resultado = OneDriveConfigService(db).probar(
        tenant_id=datos.tenant_id,
        client_id=datos.client_id,
        client_secret=datos.client_secret,
        drive_id=datos.drive_id,
        carpeta_cv=datos.carpeta_cv,
    )

    BitacoraService(db).registrar(
        ACCION_ONEDRIVE_PROBADO,
        usuario_id=current_user.id,
        entidad="configuracion_onedrive",
        detalle="exitosa" if resultado.exito else f"fallida: {resultado.mensaje}",
    )

    return PruebaConexionResponse(**vars(resultado))


@router.post("/onedrive/probar-guardada", response_model=PruebaConexionResponse)
def probar_conexion_guardada(
    db: Session = Depends(get_db),
    _=Depends(exigir_rol(ROL_ADMINISTRADOR)),
):
    """Revalida la conexión que ya está en uso y actualiza el conteo de documentos."""
    resultado = OneDriveConfigService(db).probar_configuracion_guardada()
    return PruebaConexionResponse(**vars(resultado))


@router.put("/onedrive", response_model=GuardarConexionResponse)
def guardar_conexion(
    datos: ConexionOneDriveRequest,
    db: Session = Depends(get_db),
    current_user=Depends(exigir_rol(ROL_ADMINISTRADOR)),
):
    """
    Guarda la configuración solo si la conexión es válida.

    Si las credenciales fallan responde `guardado: false` con el motivo, y la
    configuración anterior queda intacta.
    """
    servicio = OneDriveConfigService(db)
    guardado, resultado = servicio.guardar(
        tenant_id=datos.tenant_id,
        client_id=datos.client_id,
        client_secret=datos.client_secret,
        drive_id=datos.drive_id,
        carpeta_cv=datos.carpeta_cv,
        usuario_id=current_user.id,
    )

    if guardado:
        BitacoraService(db).registrar(
            ACCION_ONEDRIVE_CONFIGURADO,
            usuario_id=current_user.id,
            entidad="configuracion_onedrive",
            detalle=f"carpeta={datos.carpeta_cv}, documentos={resultado.documentos_detectados}",
        )

    return GuardarConexionResponse(
        guardado=guardado,
        prueba=PruebaConexionResponse(**vars(resultado)),
        configuracion=servicio.obtener() if guardado else None,
    )


# =============================================================================
# Conexión con el repositorio de hojas de vida, cualquier proveedor (HU-05)
#
# Equivalente a los endpoints /onedrive de arriba, pero con el origen como
# dato. Los de OneDrive se conservan porque el frontend actual los usa; este
# es el camino para registrar Google Drive.
# =============================================================================


@router.get("/repositorio", response_model=ConexionRepositorioResponse)
def obtener_repositorio(db: Session = Depends(get_db), _=Depends(exigir_rol(ROL_ADMINISTRADOR))):
    """Configuración vigente del origen activo, con los secretos enmascarados."""
    config = RepositorioConfigService(db).obtener()
    return config or ConexionRepositorioResponse(configurado=False)


@router.post("/repositorio/probar", response_model=PruebaConexionResponse)
def probar_repositorio(
    datos: ConexionRepositorioRequest,
    db: Session = Depends(get_db),
    current_user=Depends(exigir_rol(ROL_ADMINISTRADOR)),
):
    """
    Valida credenciales y carpeta sin guardar nada.

    Responde siempre 200: el resultado va en el cuerpo, con el motivo del error
    cuando la conexión falla.
    """
    resultado = RepositorioConfigService(db).probar(datos.tipo, datos.carpeta, datos.credenciales)

    BitacoraService(db).registrar(
        ACCION_REPOSITORIO_PROBADO,
        usuario_id=current_user.id,
        entidad="configuracion_repositorio",
        detalle=(
            f"{datos.tipo}: exitosa" if resultado.exito else f"{datos.tipo}: fallida: {resultado.mensaje}"
        ),
    )

    return PruebaConexionResponse(**vars(resultado))


@router.post("/repositorio/probar-guardada", response_model=PruebaConexionResponse)
def probar_repositorio_guardado(
    db: Session = Depends(get_db),
    _=Depends(exigir_rol(ROL_ADMINISTRADOR)),
):
    """Revalida el origen que ya está en uso y actualiza el conteo de documentos."""
    resultado = RepositorioConfigService(db).probar_configuracion_guardada()
    return PruebaConexionResponse(**vars(resultado))


@router.put("/repositorio", response_model=GuardarRepositorioResponse)
def guardar_repositorio(
    datos: ConexionRepositorioRequest,
    db: Session = Depends(get_db),
    current_user=Depends(exigir_rol(ROL_ADMINISTRADOR)),
):
    """
    Guarda la configuración solo si la conexión es válida.

    Si las credenciales fallan responde `guardado: false` con el motivo, y la
    configuración anterior queda intacta.
    """
    servicio = RepositorioConfigService(db)
    guardado, resultado = servicio.guardar(
        tipo=datos.tipo,
        carpeta=datos.carpeta,
        credenciales=datos.credenciales,
        usuario_id=current_user.id,
    )

    if guardado:
        BitacoraService(db).registrar(
            ACCION_REPOSITORIO_CONFIGURADO,
            usuario_id=current_user.id,
            entidad="configuracion_repositorio",
            detalle=f"tipo={datos.tipo}, carpeta={datos.carpeta}, documentos={resultado.documentos_detectados}",
        )

    return GuardarRepositorioResponse(
        guardado=guardado,
        prueba=PruebaConexionResponse(**vars(resultado)),
        configuracion=servicio.obtener() if guardado else None,
    )


# =============================================================================
# Parámetros del motor (HU-07) y bitácora (HU-06)
# =============================================================================


@router.get("/parametros", response_model=list[ParametroResponse])
def listar_parametros(db: Session = Depends(get_db), _=Depends(exigir_rol(ROL_ADMINISTRADOR))):
    return ParametroRepository(db).listar()


@router.put("/parametros/{clave}", response_model=ParametroResponse)
def actualizar_parametro(
    clave: str,
    datos: ParametroUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(exigir_rol(ROL_ADMINISTRADOR)),
):
    parametro = ParametroRepository(db).establecer(clave, datos.valor, current_user.id)
    BitacoraService(db).registrar(
        ACCION_CONFIG_CAMBIADA, usuario_id=current_user.id, entidad="parametro", entidad_id=clave
    )
    return parametro


@router.get("/bitacora", response_model=list[BitacoraResponse])
def bitacora(
    limite: int = Query(default=100, ge=1, le=500),
    desplazamiento: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _=Depends(exigir_rol(ROL_ADMINISTRADOR)),
):
    return BitacoraService(db).listar(limite, desplazamiento)
