"""
HU-23: mensaje cuando no se encuentran candidatos afines.

Criterio 1 — si ningún candidato supera el mínimo, la búsqueda termina sin
             recomendaciones (el mensaje lo pinta la pantalla de resultados).
Criterio 3 — la solicitud queda en el historial con estado Sin coincidencias.

El estado nuevo no debe confundirse con ERROR: ahí falló el sistema, aquí
simplemente no hay perfiles afines.

Se reutilizan los dobles de HU-18 (embeddings, recuperador y re-ranking falsos):
lo que se prueba es el estado que deja la búsqueda, no la calidad del modelo.
"""

from backend.config import UMBRAL_AFINIDAD_MINIMA
from backend.domain.services.dashboard_service import DashboardService
from backend.domain.services.solicitud_service import SolicitudService
from backend.infrastructure.llm.llm_provider import ServicioIAError
from backend.infrastructure.persistence.models.busqueda import BUSQUEDA_COMPLETADA
from backend.infrastructure.persistence.models.solicitud import (
    ESTADO_ERROR,
    ESTADO_PROCESADA,
    ESTADO_SIN_COINCIDENCIAS,
)
from backend.infrastructure.persistence.repositories.busqueda_repo import BusquedaRepository
from backend.infrastructure.persistence.repositories.solicitud_repo import SolicitudRepository
from tests.test_top5_candidatos import (
    RecuperadorFalso,
    _crear_candidatos,
    _crear_solicitud,
    _servicio,
)

POR_DEBAJO = UMBRAL_AFINIDAD_MINIMA - 20


def _ejecutar(db, puntajes, ids, solicitud_id, recuperador=None) -> str:
    servicio = _servicio(db, puntajes, ids)
    if recuperador is not None:
        servicio.recuperador = recuperador
    busqueda_id = servicio.encolar(solicitud_id)
    servicio.ejecutar(busqueda_id)
    return busqueda_id


def _estado(db, solicitud_id) -> str:
    return SolicitudRepository(db).get_by_id(solicitud_id).estado


# --- Criterio 3: estado Sin coincidencias ------------------------------------


def test_si_ningun_finalista_supera_el_umbral_la_solicitud_queda_sin_coincidencias(db):
    ids = _crear_candidatos(db, 4)
    solicitud_id = _crear_solicitud(db)

    busqueda_id = _ejecutar(db, {cid: POR_DEBAJO for cid in ids}, ids, solicitud_id)

    assert _estado(db, solicitud_id) == ESTADO_SIN_COINCIDENCIAS
    assert BusquedaRepository(db).get_by_id(busqueda_id).estado == BUSQUEDA_COMPLETADA
    assert BusquedaRepository(db).listar_recomendaciones(busqueda_id) == []


def test_si_no_hay_ni_finalistas_la_solicitud_queda_sin_coincidencias(db):
    """Ninguna hoja de vida pasó la recuperación ni el filtro duro."""
    solicitud_id = _crear_solicitud(db)

    busqueda_id = _ejecutar(db, {}, [], solicitud_id, recuperador=RecuperadorFalso([]))

    assert _estado(db, solicitud_id) == ESTADO_SIN_COINCIDENCIAS
    assert BusquedaRepository(db).get_by_id(busqueda_id).estado == BUSQUEDA_COMPLETADA


def test_con_un_solo_candidato_afin_la_solicitud_queda_procesada(db):
    ids = _crear_candidatos(db, 3)
    solicitud_id = _crear_solicitud(db)
    puntajes = dict(zip(ids, [UMBRAL_AFINIDAD_MINIMA + 5, POR_DEBAJO, POR_DEBAJO], strict=True))

    _ejecutar(db, puntajes, ids, solicitud_id)

    assert _estado(db, solicitud_id) == ESTADO_PROCESADA


def test_una_falla_del_servicio_de_ia_no_se_registra_como_sin_coincidencias(db):
    """Antes ERROR se mostraba como "Sin coincidencias"; son casos distintos."""

    class RerankerQueFalla:
        def ordenar_y_explicar(self, consulta, requisitos, finalistas):
            raise ServicioIAError("El servicio de IA no respondió")

    ids = _crear_candidatos(db, 2)
    solicitud_id = _crear_solicitud(db)
    servicio = _servicio(db, {cid: 90.0 for cid in ids}, ids)
    servicio.reranker = RerankerQueFalla()

    servicio.ejecutar(servicio.encolar(solicitud_id))

    assert _estado(db, solicitud_id) == ESTADO_ERROR


# --- El historial y el dashboard la reconocen --------------------------------


def test_el_historial_filtra_por_sin_coincidencias_y_permite_abrir_los_resultados(db):
    ids = _crear_candidatos(db, 2)
    solicitud_id = _crear_solicitud(db)
    busqueda_id = _ejecutar(db, {cid: POR_DEBAJO for cid in ids}, ids, solicitud_id)

    solicitudes, total = SolicitudService(db).historial(estado=ESTADO_SIN_COINCIDENCIAS)

    assert total == 1
    assert solicitudes[0].id == solicitud_id
    assert solicitudes[0].busqueda_id == busqueda_id
    assert solicitudes[0].total_candidatos == 0


def test_el_dashboard_cuenta_las_solicitudes_sin_coincidencias(db):
    ids = _crear_candidatos(db, 2)
    solicitud_id = _crear_solicitud(db)
    _ejecutar(db, {cid: POR_DEBAJO for cid in ids}, ids, solicitud_id)

    assert DashboardService(db).resumen().solicitudes_sin_coincidencias == 1
