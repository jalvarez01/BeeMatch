import pytest

from backend.domain.services.repositorio_config_service import (
    RepositorioNoConfiguradoError,
)
from backend.infrastructure.repositorio.base import RepositorioError
from backend.workers import busqueda_worker


class SesionFalsa:
    def __init__(self):
        self.cerrada = False

    def close(self):
        self.cerrada = True


@pytest.mark.parametrize(
    "error",
    [
        RepositorioError("Error de conexión"),
        RepositorioNoConfiguradoError("Repositorio no configurado"),
    ],
)
def test_error_repositorio_marca_busqueda_y_cierra_sesion(
    monkeypatch, error
):
    db = SesionFalsa()
    llamadas = []

    class ServicioBusquedaFalso:
        def __init__(self, sesion):
            assert sesion is db

        def marcar_error_repositorio(self, busqueda_id, detalle):
            llamadas.append((busqueda_id, detalle))

        def ejecutar(self, busqueda_id):
            pytest.fail("No debe ejecutarse el análisis si falla el repositorio")

    def fallar_sincronizacion():
        raise error

    monkeypatch.setattr(busqueda_worker, "SessionLocal", lambda: db)
    # HU-22: el paso previo que marca "Sincronizando" necesita la base real; aquí
    # solo interesa qué pasa cuando falla la sincronización.
    monkeypatch.setattr(busqueda_worker, "_marcar_sincronizacion", lambda sesion, busqueda_id: True)
    monkeypatch.setattr(
        busqueda_worker,
        "_sincronizar_repositorio",
        fallar_sincronizacion,
    )
    monkeypatch.setattr(
        busqueda_worker,
        "BusquedaService",
        ServicioBusquedaFalso,
    )

    busqueda_worker.ejecutar_busqueda("busqueda-123")

    assert llamadas == [("busqueda-123", str(error))]
    assert db.cerrada