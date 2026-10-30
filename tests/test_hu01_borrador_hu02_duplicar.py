"""Cobertura de borrado seguro de borradores y aislamiento al duplicar."""

from backend.infrastructure.persistence.models.busqueda import BusquedaModel
from backend.infrastructure.persistence.models.solicitud import CriterioModel, SolicitudModel


def _crear_solicitud(cliente, cabeceras, estado="BORRADOR"):
    respuesta = cliente.post(
        "/solicitudes/",
        json={
            "descripcion_libre": "Perfil backend para un proyecto nuevo",
            "rol_buscado": "Backend",
            "criterios": [
                {"tipo": "TECNOLOGIA", "valor": "Python", "obligatorio": True, "peso": 2}
            ],
        },
        headers=cabeceras,
    )
    assert respuesta.status_code == 201, respuesta.text
    solicitud = respuesta.json()
    if estado != "BORRADOR":
        # La API de actualización no modifica el estado; fijarlo aquí permite
        # comprobar la protección del endpoint de borrado.
        from backend.infrastructure.persistence.database import SessionLocal

        db = SessionLocal()
        try:
            db.get(SolicitudModel, solicitud["id"]).estado = estado
            db.commit()
        finally:
            db.close()
    return solicitud["id"]


def test_eliminar_borrador_borra_solicitud_y_criterios(cliente, db, crear_usuario, entrar):
    usuario = crear_usuario("borrador@example.com")
    cabeceras = entrar(usuario.correo)
    solicitud_id = _crear_solicitud(cliente, cabeceras)
    criterio_id = db.query(CriterioModel).filter_by(solicitud_id=solicitud_id).one().id

    respuesta = cliente.delete(f"/solicitudes/{solicitud_id}", headers=cabeceras)

    assert respuesta.status_code == 204
    assert db.get(SolicitudModel, solicitud_id) is None
    assert db.get(CriterioModel, criterio_id) is None


def test_no_se_puede_eliminar_solicitud_que_no_es_borrador(cliente, db, crear_usuario, entrar):
    usuario = crear_usuario("procesada@example.com")
    cabeceras = entrar(usuario.correo)
    solicitud_id = _crear_solicitud(cliente, cabeceras, estado="PROCESADA")

    respuesta = cliente.delete(f"/solicitudes/{solicitud_id}", headers=cabeceras)

    assert respuesta.status_code == 409
    assert db.get(SolicitudModel, solicitud_id) is not None


def test_no_se_puede_eliminar_borrador_con_busqueda_historial(cliente, db, crear_usuario, entrar):
    usuario = crear_usuario("historial@example.com")
    cabeceras = entrar(usuario.correo)
    solicitud_id = _crear_solicitud(cliente, cabeceras)
    busqueda = BusquedaModel(solicitud_id=solicitud_id)
    db.add(busqueda)
    db.commit()

    respuesta = cliente.delete(f"/solicitudes/{solicitud_id}", headers=cabeceras)

    assert respuesta.status_code == 409
    assert db.get(SolicitudModel, solicitud_id) is not None
    assert db.get(BusquedaModel, busqueda.id) is not None


def test_duplicado_tiene_id_y_criterios_independientes_y_busqueda_nueva(
    cliente, db, crear_usuario, entrar, monkeypatch
):
    usuario = crear_usuario("duplicar@example.com")
    cabeceras = entrar(usuario.correo)
    original_id = _crear_solicitud(cliente, cabeceras, estado="PROCESADA")

    respuesta_copia = cliente.post(f"/solicitudes/{original_id}/duplicar", headers=cabeceras)
    assert respuesta_copia.status_code == 201, respuesta_copia.text
    copia = respuesta_copia.json()
    copia_id = copia["id"]
    assert copia_id != original_id
    assert copia["estado"] == "BORRADOR"
    original_criterio = db.query(CriterioModel).filter_by(solicitud_id=original_id).one()
    copia_criterio = db.query(CriterioModel).filter_by(solicitud_id=copia_id).one()
    assert copia_criterio.id != original_criterio.id
    assert copia_criterio.valor == original_criterio.valor

    actualizada = cliente.put(
        f"/solicitudes/{copia_id}",
        json={
            "descripcion_libre": "Perfil Python modificado para otra búsqueda",
            "criterios": [{"tipo": "TECNOLOGIA", "valor": "Rust"}],
        },
        headers=cabeceras,
    )
    assert actualizada.status_code == 200, actualizada.text
    db.refresh(original_criterio)
    assert original_criterio.valor == "Python"
    assert db.query(CriterioModel).filter_by(solicitud_id=copia_id).one().valor == "Rust"

    import backend.api.busquedas as api_busquedas

    monkeypatch.setattr(api_busquedas, "despachar", lambda *args, **kwargs: None)
    ejecucion = cliente.post(f"/busquedas/solicitud/{copia_id}", headers=cabeceras)
    assert ejecucion.status_code == 202, ejecucion.text
    busqueda_copia = db.get(BusquedaModel, ejecucion.json()["id"])
    assert busqueda_copia is not None
    assert busqueda_copia.solicitud_id == copia_id
    assert db.query(BusquedaModel).filter_by(solicitud_id=original_id).count() == 0
    assert db.get(SolicitudModel, original_id).descripcion_libre == "Perfil backend para un proyecto nuevo"
