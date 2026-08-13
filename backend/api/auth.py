from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.domain.services.bitacora_service import ACCION_LOGIN, BitacoraService
from backend.infrastructure.persistence.database import get_db
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
    crear_token,
    exigir_rol,
    get_current_user,
    hashear_password,
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
    forma de averiguar qué correos están registrados (HU-01-CP2).
    """
    repo = UsuarioRepository(db)
    usuario = repo.get_by_correo(datos.correo)

    if not usuario or not usuario.activo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=MENSAJE_CREDENCIALES)

    if not verificar_password(datos.password, usuario.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=MENSAJE_CREDENCIALES)

    repo.marcar_acceso(usuario)
    BitacoraService(db).registrar(ACCION_LOGIN, usuario_id=usuario.id)

    return LoginResponse(
        access_token=crear_token(usuario.id, usuario.correo, usuario.rol),
        usuario=UsuarioResponse.model_validate(usuario),
    )


@router.get("/yo", response_model=UsuarioResponse)
def usuario_actual(current_user=Depends(get_current_user)):
    return current_user


@router.post("/cambiar-password", response_model=UsuarioResponse)
def cambiar_password(
    datos: CambiarPasswordRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Cambio de contraseña propio. Exige la actual para evitar el secuestro de sesión."""
    if not verificar_password(datos.password_actual, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="La contraseña actual no es correcta."
        )

    validar_fortaleza(datos.password_nueva)
    return UsuarioRepository(db).actualizar_password(
        current_user, hashear_password(datos.password_nueva)
    )


# --- Gestión de usuarios (solo administrador, HU-03, HU-04) ------------------


@router.get("/usuarios", response_model=list[UsuarioResponse])
def listar_usuarios(db: Session = Depends(get_db), _=Depends(exigir_rol(ROL_ADMINISTRADOR))):
    return UsuarioRepository(db).listar()


@router.post("/usuarios", response_model=UsuarioResponse, status_code=201)
def crear_usuario(
    datos: UsuarioCreate,
    db: Session = Depends(get_db),
    _=Depends(exigir_rol(ROL_ADMINISTRADOR)),
):
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
    """HU-04: cambio de rol o desactivación."""
    if usuario_id == current_user.id and datos.activo is False:
        raise HTTPException(status_code=400, detail="No puedes desactivar tu propia cuenta.")

    repo = UsuarioRepository(db)
    usuario = repo.get_by_id(usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    if datos.rol:
        repo.actualizar_rol(usuario_id, datos.rol)
    if datos.activo is False:
        repo.desactivar(usuario_id)

    return repo.get_by_id(usuario_id)