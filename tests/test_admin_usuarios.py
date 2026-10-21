import pytest
from fastapi import HTTPException

from backend.api.auth import actualizar_usuario
from backend.infrastructure.persistence.models.usuario import UsuarioModel
from backend.infrastructure.persistence.repositories.usuario_repo import UsuarioRepository
from backend.schemas.auth import UsuarioUpdate
from backend.security import ROL_ADMINISTRADOR


def test_no_se_puede_desactivar_al_ultimo_administrador(db, administrador):
    """El sistema debe conservar al menos un administrador activo."""
    with pytest.raises(HTTPException) as error:
        actualizar_usuario(
            usuario_id=administrador.id,
            datos=UsuarioUpdate(activo=False),
            db=db,
            current_user=administrador,
        )

    assert error.value.status_code == 400
    assert db.get(UsuarioModel, administrador.id).activo is True


def test_no_se_puede_quitar_el_rol_al_ultimo_administrador(db, administrador):
    """El último administrador activo no puede perder su rol."""
    with pytest.raises(HTTPException) as error:
        actualizar_usuario(
            usuario_id=administrador.id,
            datos=UsuarioUpdate(rol="COORDINADOR"),
            db=db,
            current_user=administrador,
        )

    assert error.value.status_code == 400
    assert db.get(UsuarioModel, administrador.id).rol == ROL_ADMINISTRADOR

def test_el_rol_del_token_se_conserva_durante_la_sesion(db, administrador):
    from backend.security import crear_token, get_current_user

    token = crear_token(administrador.id, administrador.correo, ROL_ADMINISTRADOR)

    administrador.rol = "COORDINADOR"
    db.commit()

    class Credenciales:
        credentials = token

    usuario_sesion = get_current_user(credentials=Credenciales(), db=db)

    assert usuario_sesion.rol == ROL_ADMINISTRADOR

def test_consultar_sesion_no_modifica_el_rol_guardado(db, administrador):
    from backend.security import crear_token, get_current_user

    token = crear_token(administrador.id, administrador.correo, ROL_ADMINISTRADOR)

    administrador.rol = "COORDINADOR"
    db.commit()

    class Credenciales:
        credentials = token

    get_current_user(credentials=Credenciales(), db=db)

    db.refresh(administrador)
    assert administrador.rol == "COORDINADOR"

def test_coordinador_no_puede_consultar_historial_completo(db, administrador):
    from fastapi.testclient import TestClient

    from backend.infrastructure.persistence.database import get_db
    from backend.main import app
    from backend.security import get_current_user

    coordinador = UsuarioModel(
        nombre="Coordinador de prueba",
        correo="coordinador@beematch.test",
        rol="COORDINADOR",
        activo=True,
    )
    db.add(coordinador)
    db.commit()
    db.refresh(coordinador)

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: coordinador
    try:
        with TestClient(app) as cliente:
            respuesta = cliente.get("/solicitudes/")
        assert respuesta.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_director_puede_consultar_historial_completo(db, administrador):
    from fastapi.testclient import TestClient

    from backend.infrastructure.persistence.database import get_db
    from backend.main import app
    from backend.security import get_current_user

    director = UsuarioModel(
        nombre="Director de prueba",
        correo="director@beematch.test",
        rol="DIRECTOR",
        activo=True,
    )
    db.add(director)
    db.commit()
    db.refresh(director)

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: director
    try:
        with TestClient(app) as cliente:
            respuesta = cliente.get("/solicitudes/")
        assert respuesta.status_code == 200
    finally:
        app.dependency_overrides.clear()
