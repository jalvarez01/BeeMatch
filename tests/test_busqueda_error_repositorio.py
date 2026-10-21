from types import SimpleNamespace

from backend.domain.services import busqueda_service
from backend.domain.services.bitacora_service import ACCION_ERROR_SERVICIO
from backend.infrastructure.persistence.models.busqueda import BUSQUEDA_ERROR
from backend.infrastructure.persistence.models.solicitud import ESTADO_ERROR


def test_error_repositorio_se_registra_y_actualiza_estados(monkeypatch):
    eventos = {}

    busqueda = SimpleNamespace(
        id="busqueda-123",
        solicitud_id="solicitud-456",
    )
    solicitud = SimpleNamespace(
        id="solicitud-456",
        usuario_id="usuario-789",
    )

    class BusquedasFalsas:
        def get_by_id(self, busqueda_id):
            assert busqueda_id == "busqueda-123"
            return busqueda

        def finalizar(self, busqueda_id, **kwargs):
            eventos["finalizar"] = (busqueda_id, kwargs)

    class SolicitudesFalsas:
        def get_by_id(self, solicitud_id):
            assert solicitud_id == "solicitud-456"
            return solicitud

        def cambiar_estado(self, solicitud_id, estado):
            eventos["estado"] = (solicitud_id, estado)

    class BitacoraFalsa:
        def __init__(self, db):
            pass

        def registrar(self, **kwargs):
            eventos["bitacora"] = kwargs

    monkeypatch.setattr(
        busqueda_service,
        "BitacoraService",
        BitacoraFalsa,
    )

    servicio = busqueda_service.BusquedaService.__new__(
        busqueda_service.BusquedaService
    )
    servicio.db = None
    servicio.busquedas = BusquedasFalsas()
    servicio.solicitudes = SolicitudesFalsas()

    servicio.marcar_error_repositorio(
        "busqueda-123",
        "Error de conexión",
    )

    assert eventos["estado"] == ("solicitud-456", ESTADO_ERROR)

    busqueda_finalizada, datos = eventos["finalizar"]
    assert busqueda_finalizada == "busqueda-123"
    assert datos["estado"] == BUSQUEDA_ERROR
    assert datos["mensaje_error"] == (
        "No fue posible acceder al repositorio de hojas de vida. "
        "Contacte al administrador"
    )

    registro = eventos["bitacora"]
    assert registro["accion"] == ACCION_ERROR_SERVICIO
    assert registro["usuario_id"] == "usuario-789"
    assert registro["entidad_id"] == "solicitud-456"
    assert "REPOSITORIO_NO_DISPONIBLE" in registro["detalle"]
    assert "Error de conexión" in registro["detalle"]
