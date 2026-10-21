import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.api.solicitudes import _verificar_acceso_solicitud
from backend.infrastructure.persistence.database import get_db
from backend.infrastructure.persistence.models.solicitud import SolicitudModel
from backend.infrastructure.persistence.models.usuario import UsuarioModel
from backend.main import app
from backend.security import get_current_user


def crear_usuario(db, nombre, correo, rol):
    usuario = UsuarioModel(
        nombre=nombre,
        correo=correo,
        rol=rol,
        activo=True,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def crear_solicitud(db, usuario_id, descripcion):
    solicitud = SolicitudModel(
        descripcion_libre=descripcion,
        usuario_id=usuario_id,
    )
    db.add(solicitud)
    db.commit()
    db.refresh(solicitud)
    return solicitud


def test_coordinador_puede_acceder_a_su_solicitud(db):
    coordinador = crear_usuario(
        db, "Coordinador", "coordinador@beematch.test", "COORDINADOR"
    )
    solicitud = crear_solicitud(db, coordinador.id, "Solicitud propia")

    # No debe lanzar una excepción.
    _verificar_acceso_solicitud(solicitud, coordinador)


def test_coordinador_no_puede_acceder_a_solicitud_ajena(db):
    coordinador = crear_usuario(
        db, "Coordinador", "coordinador@beematch.test", "COORDINADOR"
    )
    otro_usuario = crear_usuario(
        db, "Otro coordinador", "otro@beematch.test", "COORDINADOR"
    )
    solicitud = crear_solicitud(db, otro_usuario.id, "Solicitud ajena")

    with pytest.raises(HTTPException) as error:
        _verificar_acceso_solicitud(solicitud, coordinador)

    assert error.value.status_code == 403


@pytest.mark.parametrize("rol", ["DIRECTOR", "ADMINISTRADOR"])
def test_director_y_admin_pueden_acceder_a_solicitud_ajena(db, rol):
    usuario = crear_usuario(
        db, "Usuario propietario", "propietario@beematch.test", "COORDINADOR"
    )
    supervisor = crear_usuario(
        db, f"Supervisor {rol}", f"{rol.lower()}@beematch.test", rol
    )
    solicitud = crear_solicitud(db, usuario.id, "Solicitud de otro usuario")

    # No debe lanzar una excepción.
    _verificar_acceso_solicitud(solicitud, supervisor)


@pytest.mark.parametrize(
    ("metodo", "ruta", "datos"),
    [
        ("get", "/solicitudes/{id}", None),
        ("put", "/solicitudes/{id}", {"descripcion_libre": "Descripción actualizada"}),
        ("post", "/solicitudes/{id}/duplicar", None),
    ],
)
def test_coordinador_no_puede_operar_sobre_solicitud_ajena(
    db, metodo, ruta, datos
):
    coordinador = crear_usuario(
        db, "Coordinador", "coordinador@beematch.test", "COORDINADOR"
    )
    propietario = crear_usuario(
        db, "Otro coordinador", "otro@beematch.test", "COORDINADOR"
    )
    solicitud = crear_solicitud(db, propietario.id, "Solicitud de otra persona")

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: coordinador

    try:
        with TestClient(app) as cliente:
            url = ruta.format(id=solicitud.id)
            respuesta = getattr(cliente, metodo)(
                url, **({"json": datos} if datos is not None else {})
            )

        assert respuesta.status_code == 403
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
