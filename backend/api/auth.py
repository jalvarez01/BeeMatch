from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.domain.services.bitacora_service import (
    ACCION_LOGIN,
    ACCION_LOGOUT,
    ACCION_USUARIO_ELIMINADO,
    BitacoraService,
)
from backend.domain.services.bloqueo_login_service import BloqueoLoginService
from backend.infrastructure.persistence.database import get_db
from backend.infrastructure.persistence.models.usuario import UsuarioModel
from backend.infrastructure.persistence.repositories.usuario_repo import UsuarioRepository
from backend.schemas.auth import (
    CambiarPasswordRequest,
    LoginRequest,
    LoginResponse,
    UsuarioCreate,
    UsuarioResponse,
    UsuarioUpdate,
)
from backend.security import (
    ROL_ADMINISTRADOR,
    ROLES_QUE_GESTIONA,
    crear_token,
    exigir_rol,
    get_current_user,
    hashear_password,
    puede_gestionar,
    validar_fortaleza,
    verificar_password,
)

router = APIRouter()

MENSAJE_CREDENCIALES = "Usuario o contraseña incorrectos"


@router.post("/login", response_model=LoginResponse)
def iniciar_sesion(datos: LoginRequest, db: Session = Depends(get_db)):
    """
    HU-01.

    El mensaje de error es el mismo para correo inexistente, contraseña errada
    y cuenta inactiva: decir cuál de los tres falló le daría a un atacante una
    forma de averiguar qué correos están registrados (HU-01-CP2). Por la misma
    razón los fallos se cuentan por correo aunque no exista el usuario, y tras
    cinco el acceso se bloquea 15 minutos (HU-01-CP4), incluso con la clave
    correcta.
    """
    repo = UsuarioRepository(db)
    bloqueo = BloqueoLoginService(db)

    restantes = bloqueo.minutos_restantes(datos.correo)
    if restantes:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Demasiados intentos fallidos. El acceso está bloqueado temporalmente; "
                f"intenta de nuevo en {restantes} minuto{'s' if restantes != 1 else ''}."
            ),
        )

    usuario = repo.get_by_correo(datos.correo)
    if not usuario or not verificar_password(datos.password, usuario.password_hash):
        bloqueo.registrar_fallo(datos.correo)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=MENSAJE_CREDENCIALES)

    # Ya se probó que conoce la contraseña, así que decirle el estado de su
    # cuenta no filtra nada a un tercero.
    if usuario.pendiente:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cuenta está pendiente de aprobación por el administrador.",
        )

    if not usuario.activo:
        bloqueo.registrar_fallo(datos.correo)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=MENSAJE_CREDENCIALES)

    bloqueo.reiniciar(datos.correo)
    repo.marcar_acceso(usuario)
    BitacoraService(db).registrar(ACCION_LOGIN, usuario_id=usuario.id)

    return LoginResponse(
        access_token=crear_token(usuario.id, usuario.correo, usuario.rol),
        usuario=UsuarioResponse.model_validate(usuario),
    )


@router.post("/renovar", response_model=LoginResponse)
def renovar_sesion(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """
    HU-02: el navegador pide un token nuevo mientras el usuario está activo.
    Si deja de hacerlo, el token vence a los 30 minutos y la sesión se cierra.

    HU-04: el rol del token se respeta durante la sesión, pero el token nuevo se
    emite con el rol que hoy tiene la cuenta. Sin esto, un usuario activo
    renovaría siempre el rol viejo y un cambio de permisos no le llegaría nunca.
    """
    usuario = UsuarioRepository(db).get_by_id(current_user.id)
    return LoginResponse(
        access_token=crear_token(usuario.id, usuario.correo, usuario.rol),
        usuario=UsuarioResponse.model_validate(usuario),
    )


@router.post("/logout", status_code=204)
def cerrar_sesion(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """HU-02: deja constancia en la bitácora; el token lo descarta el navegador."""
    BitacoraService(db).registrar(ACCION_LOGOUT, usuario_id=current_user.id)


@router.get("/yo", response_model=UsuarioResponse)
def usuario_actual(current_user=Depends(get_current_user)):
    return current_user


@router.post("/cambiar-password", response_model=UsuarioResponse)
def cambiar_password(
    datos: CambiarPasswordRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Cambio de contraseña propio. Exige la actual para evitar el secuestro de sesión.

    Solo se guarda el hash: ni la superadministradora, que crea la cuenta con una
    clave inicial, puede leer la que la persona elige después.
    """
    repo = UsuarioRepository(db)
    # `current_user` es una copia de la sesión; el cambio se guarda en la cuenta real.
    usuario = repo.get_by_id(current_user.id)
    if not verificar_password(datos.password_actual, usuario.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="La contraseña actual no es correcta."
        )
    if datos.password_actual == datos.password_nueva:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña nueva debe ser distinta de la actual.",
        )

    validar_fortaleza(datos.password_nueva)
    return repo.actualizar_password(usuario, hashear_password(datos.password_nueva))


# --- Gestión de usuarios (HU-03, HU-04) -------------------------------------
#
# Jerarquía: la superusuaria gestiona a todos menos a otra superusuaria; un
# administrador gestiona solo Coordinadores y Directores. Nadie puede tocar a
# la superusuaria, y solo ella da o retira el rol de administrador.


def _exigir_poder_sobre(actor, objetivo_rol: str) -> None:
    if not puede_gestionar(actor.rol, objetivo_rol):
        raise HTTPException(
            status_code=403, detail="No tienes permiso para gestionar a este usuario."
        )


@router.get("/usuarios", response_model=list[UsuarioResponse])
def listar_usuarios(db: Session = Depends(get_db), _=Depends(exigir_rol(ROL_ADMINISTRADOR))):
    return UsuarioRepository(db).listar()


@router.post("/usuarios", response_model=UsuarioResponse, status_code=201)
def crear_usuario(
    datos: UsuarioCreate,
    db: Session = Depends(get_db),
    current_user=Depends(exigir_rol(ROL_ADMINISTRADOR)),
):
    if datos.rol not in ROLES_QUE_GESTIONA[current_user.rol]:
        raise HTTPException(status_code=403, detail="No puedes crear usuarios con ese rol.")

    repo = UsuarioRepository(db)
    if repo.get_by_correo(datos.correo):
        raise HTTPException(status_code=409, detail="Ya existe un usuario con ese correo.")

    validar_fortaleza(datos.password)
    return repo.crear(
        nombre=datos.nombre,
        correo=datos.correo,
        rol=datos.rol,
        password_hash=hashear_password(datos.password),
        id_entra=datos.id_entra,
        debe_cambiar_password=True,
    )


@router.patch("/usuarios/{usuario_id}", response_model=UsuarioResponse)
def actualizar_usuario(
    usuario_id: str,
    datos: UsuarioUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(exigir_rol(ROL_ADMINISTRADOR)),
):
    """HU-03/HU-04: edición, aprobación de registros, cambio de rol e inactivación."""
    repo = UsuarioRepository(db)
    usuario = repo.get_by_id(usuario_id)

    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    # Evitar que un usuario desactive su propia cuenta.
    if usuario.id == current_user.id and datos.activo is False:
        raise HTTPException(
            status_code=400,
            detail="No puedes desactivar tu propia cuenta.",
        )

    # Proteger al último administrador activo.
    es_admin_activo = usuario.activo and usuario.rol == ROL_ADMINISTRADOR
    pierde_rol_admin = (
        datos.rol is not None and datos.rol != ROL_ADMINISTRADOR
    )
    se_desactiva = datos.activo is False

    if (
        current_user.rol != "SUPERADMINISTRADOR"
        and es_admin_activo
        and (pierde_rol_admin or se_desactiva)
    ):
        otros_admins_activos = (
            db.query(UsuarioModel)
            .filter(
                UsuarioModel.rol == ROL_ADMINISTRADOR,
                UsuarioModel.activo.is_(True),
                UsuarioModel.id != usuario_id,
            )
            .count()
        )

        if otros_admins_activos == 0:
            raise HTTPException(
                status_code=400,
                detail="No se puede quitar o desactivar al último administrador activo.",
            )

    _exigir_poder_sobre(current_user, usuario.rol)

    cambios: dict = {}

    if datos.rol is not None:
        if datos.rol not in ROLES_QUE_GESTIONA[current_user.rol]:
            raise HTTPException(
                status_code=403,
                detail="No puedes asignar ese rol.",
            )
        cambios["rol"] = datos.rol

    if datos.nombre is not None:
        cambios["nombre"] = datos.nombre

    if datos.correo is not None and datos.correo.lower() != usuario.correo:
        if repo.get_by_correo(datos.correo):
            raise HTTPException(
                status_code=409,
                detail="Ya existe un usuario con ese correo.",
            )
        cambios["correo"] = datos.correo

    if datos.activo is not None:
        # Aprobar o rechazar una cuenta pendiente la saca de ese estado.
        cambios["activo"] = datos.activo
        cambios["pendiente"] = False

    return repo.actualizar(usuario, **cambios)


@router.delete("/usuarios/{usuario_id}", status_code=204)
def eliminar_usuario(
    usuario_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(exigir_rol(ROL_ADMINISTRADOR)),
):
    """
    Borra el perfil de una persona. Su historial de solicitudes se conserva y sigue
    mostrando quién las hizo: la solicitud guarda el nombre de su autor, así que no
    depende de que la cuenta exista. Para suspender el acceso sin borrar, se inactiva.
    """
    repo = UsuarioRepository(db)
    usuario = repo.get_by_id(usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    if usuario.id == current_user.id:
        raise HTTPException(status_code=400, detail="No puedes borrar tu propia cuenta.")
    _exigir_poder_sobre(current_user, usuario.rol)

    detalle = f"{usuario.nombre} ({usuario.correo})"
    repo.eliminar(usuario)
    BitacoraService(db).registrar(
        ACCION_USUARIO_ELIMINADO,
        usuario_id=current_user.id,
        entidad="usuario",
        entidad_id=usuario_id,
        detalle=detalle,
    )
