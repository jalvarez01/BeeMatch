"""
HU-18: obtención del Top 5 de candidatos recomendados.

Criterio 1 — hasta cinco candidatos, de mayor a menor afinidad.
Criterio 3 — si menos de cinco superan el mínimo, solo se muestran esos.
Criterio 4 — el análisis se entrega en menos de dos minutos.

El re-ranking y los embeddings se sustituyen por dobles: lo que se prueba es
el ensamblado del Top-N, no la calidad del modelo.
"""

from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.config import TOP_N_RESULTADOS, UMBRAL_AFINIDAD_MINIMA
from backend.domain.matching.filtros import FiltroDuro
from backend.domain.matching.scorer import nivel_de
from backend.domain.services.busqueda_service import BusquedaService
from backend.domain.services.resultado_service import ResultadoService
from backend.infrastructure.llm.llm_provider import RespuestaIA
from backend.infrastructure.persistence import models  # noqa: F401
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models.busqueda import BUSQUEDA_COMPLETADA
from backend.infrastructure.persistence.models.hoja_vida import CandidatoModel, HojaDeVidaModel
from backend.infrastructure.persistence.models.solicitud import SolicitudModel
from backend.infrastructure.persistence.models.usuario import UsuarioModel
from backend.infrastructure.persistence.repositories.busqueda_repo import BusquedaRepository
from backend.infrastructure.persistence.repositories.candidato_repo import CandidatoRepository
from backend.infrastructure.persistence.repositories.hoja_vida_repo import HojaDeVidaRepository
from backend.infrastructure.persistence.repositories.solicitud_repo import SolicitudRepository

DOS_MINUTOS_EN_MS = 120_000


@pytest.fixture()
def db():
    motor = create_engine("sqlite://")
    Base.metadata.create_all(bind=motor)
    sesion = sessionmaker(bind=motor)()
    yield sesion
    sesion.close()


class FragmentoFalso:
    def __init__(self, hoja_id: str, puntaje: float):
        self.hoja_de_vida_id = hoja_id
        self.fragmento_id = f"frag-{hoja_id}"
        self.texto = "Experiencia en Java y Spring Boot."
        self.puntaje = puntaje


class RecuperadorFalso:
    def __init__(self, fragmentos):
        self.fragmentos = fragmentos

    def recuperar(self, consulta, embedding):
        return self.fragmentos


class EmbeddingsFalso:
    def generar_uno(self, texto):
        return [0.1, 0.2, 0.3]


class RerankerFalso:
    """Devuelve los puntajes que se le indiquen, por candidato."""

    def __init__(self, puntajes: dict[str, float]):
        self.puntajes = puntajes

    def ordenar_y_explicar(self, consulta, requisitos, finalistas):
        resultados = [
            {
                "candidato_id": f["candidato_id"],
                "puntaje_afinidad": self.puntajes[f["candidato_id"]],
                "nivel": nivel_de(self.puntajes[f["candidato_id"]]),
                "resumen_ia": f"Resumen de {f['nombre']}",
                "coincidencias": [],
            }
            for f in finalistas
        ]
        resultados.sort(key=lambda r: r["puntaje_afinidad"], reverse=True)
        return resultados, RespuestaIA(modelo="modelo-de-prueba", tokens_entrada=10, tokens_salida=5)


def _crear_candidatos(db, cuantos: int, anios: int | None = 5) -> list[str]:
    """Crea N hojas indexadas con su candidato. Devuelve los ids de candidato."""
    ids = []
    for i in range(cuantos):
        # El id del documento es único por llamada: un test puede crear dos
        # grupos de candidatos y no deben chocar entre sí.
        marca = uuid4().hex[:8]
        hoja = HojaDeVidaModel(
            id_documento=f"doc-{marca}-{i}", nombre_archivo=f"cv{i}.pdf", formato="PDF"
        )
        db.add(hoja)
        db.commit()
        candidato = CandidatoModel(
            hoja_de_vida_id=hoja.id,
            nombre=f"Candidato {i}",
            rol_principal="Desarrollador Backend",
            anios_experiencia=anios,
        )
        db.add(candidato)
        db.commit()
        ids.append(candidato.id)
    return ids


def _crear_solicitud(db, experiencia_min: int | None = None) -> str:
    usuario = UsuarioModel(
        nombre="Reclutador", correo="reclutador@bee.com.co", password_hash="x", rol="ANALISTA"
    )
    db.add(usuario)
    db.commit()
    solicitud = SolicitudModel(
        descripcion_libre="Backend Java para core bancario",
        rol_buscado="Desarrollador Backend",
        experiencia_min=experiencia_min,
        usuario_id=usuario.id,
    )
    db.add(solicitud)
    db.commit()
    return solicitud.id


def _servicio(db, puntajes: dict[str, float], candidatos_ids: list[str]) -> BusquedaService:
    servicio = BusquedaService.__new__(BusquedaService)
    servicio.db = db
    servicio.busquedas = BusquedaRepository(db)
    servicio.solicitudes = SolicitudRepository(db)
    servicio.candidatos = CandidatoRepository(db)
    servicio.hojas = HojaDeVidaRepository(db)
    servicio.filtro = FiltroDuro(db)
    servicio.embeddings = EmbeddingsFalso()
    servicio.reranker = RerankerFalso(puntajes)

    # Un fragmento por candidato, en el orden en que fueron creados.
    repo = CandidatoRepository(db)
    fragmentos = [
        FragmentoFalso(repo.get_by_id(cid).hoja_de_vida_id, puntaje=1.0) for cid in candidatos_ids
    ]
    servicio.recuperador = RecuperadorFalso(fragmentos)
    return servicio


# --- Criterio 1: hasta cinco, de mayor a menor afinidad ----------------------


def test_de_ocho_candidatos_solo_se_entregan_cinco(db):
    ids = _crear_candidatos(db, 8)
    solicitud_id = _crear_solicitud(db)
    # Puntajes descendentes y todos por encima del umbral.
    puntajes = {cid: 95.0 - i for i, cid in enumerate(ids)}

    servicio = _servicio(db, puntajes, ids)
    busqueda_id = servicio.encolar(solicitud_id)
    servicio.ejecutar(busqueda_id)

    recomendaciones = BusquedaRepository(db).listar_recomendaciones(busqueda_id)
    assert len(recomendaciones) == TOP_N_RESULTADOS


def test_los_cinco_llegan_ordenados_de_mayor_a_menor_afinidad(db):
    ids = _crear_candidatos(db, 6)
    solicitud_id = _crear_solicitud(db)
    # A propósito desordenados: el del medio es el mejor.
    valores = [72.0, 88.0, 99.0, 65.0, 94.0, 80.0]
    puntajes = dict(zip(ids, valores))

    servicio = _servicio(db, puntajes, ids)
    busqueda_id = servicio.encolar(solicitud_id)
    servicio.ejecutar(busqueda_id)

    obtenidos = [
        r.puntaje_afinidad for r in BusquedaRepository(db).listar_recomendaciones(busqueda_id)
    ]
    assert obtenidos == sorted(obtenidos, reverse=True)
    assert obtenidos == [99.0, 94.0, 88.0, 80.0, 72.0]


def test_la_posicion_guardada_refleja_el_orden(db):
    ids = _crear_candidatos(db, 3)
    solicitud_id = _crear_solicitud(db)
    puntajes = dict(zip(ids, [70.0, 90.0, 80.0]))

    servicio = _servicio(db, puntajes, ids)
    busqueda_id = servicio.encolar(solicitud_id)
    servicio.ejecutar(busqueda_id)

    recomendaciones = BusquedaRepository(db).listar_recomendaciones(busqueda_id)
    assert [r.posicion for r in recomendaciones] == [1, 2, 3]
    assert [r.puntaje_afinidad for r in recomendaciones] == [90.0, 80.0, 70.0]


# --- Criterio 3: menos de cinco que califican --------------------------------


def test_solo_se_muestran_los_que_superan_el_umbral(db):
    ids = _crear_candidatos(db, 6)
    solicitud_id = _crear_solicitud(db)
    # Tres por encima del umbral y tres por debajo.
    bajo = UMBRAL_AFINIDAD_MINIMA - 10
    valores = [92.0, 85.0, 77.0, bajo, bajo - 5, bajo - 15]
    puntajes = dict(zip(ids, valores))

    servicio = _servicio(db, puntajes, ids)
    busqueda_id = servicio.encolar(solicitud_id)
    servicio.ejecutar(busqueda_id)

    recomendaciones = BusquedaRepository(db).listar_recomendaciones(busqueda_id)
    assert len(recomendaciones) == 3
    assert all(r.puntaje_afinidad >= UMBRAL_AFINIDAD_MINIMA for r in recomendaciones)


def test_si_nadie_supera_el_umbral_la_busqueda_termina_sin_candidatos(db):
    """HU-23: completada y con la lista vacía, no en error."""
    ids = _crear_candidatos(db, 4)
    solicitud_id = _crear_solicitud(db)
    puntajes = {cid: UMBRAL_AFINIDAD_MINIMA - 20 for cid in ids}

    servicio = _servicio(db, puntajes, ids)
    busqueda_id = servicio.encolar(solicitud_id)
    servicio.ejecutar(busqueda_id)

    busqueda = BusquedaRepository(db).get_by_id(busqueda_id)
    assert busqueda.estado == BUSQUEDA_COMPLETADA
    assert BusquedaRepository(db).listar_recomendaciones(busqueda_id) == []


# --- Criterio 2 visto desde la respuesta de la API ---------------------------


def test_cada_resultado_llega_con_los_cuatro_datos_de_la_tarjeta(db):
    ids = _crear_candidatos(db, 2)
    repo = CandidatoRepository(db)
    for cid in ids:
        repo.reemplazar_habilidades(
            cid, [{"nombre": "Java"}, {"nombre": "Spring Boot", "categoria": "FRAMEWORK"}]
        )
    solicitud_id = _crear_solicitud(db)
    puntajes = dict(zip(ids, [91.0, 84.0]))

    servicio = _servicio(db, puntajes, ids)
    busqueda_id = servicio.encolar(solicitud_id)
    servicio.ejecutar(busqueda_id)

    resultado = ResultadoService(db).resultados(busqueda_id)
    for recomendacion in resultado.recomendaciones:
        assert recomendacion.nombre
        assert recomendacion.rol_principal == "Desarrollador Backend"
        assert recomendacion.anios_experiencia == 5
        assert sorted(recomendacion.tecnologias) == ["Java", "Spring Boot"]


# --- Criterio 4: menos de dos minutos ----------------------------------------


def test_la_duracion_del_analisis_queda_registrada_y_dentro_del_limite(db):
    ids = _crear_candidatos(db, 3)
    solicitud_id = _crear_solicitud(db)
    puntajes = {cid: 90.0 for cid in ids}

    servicio = _servicio(db, puntajes, ids)
    busqueda_id = servicio.encolar(solicitud_id)
    servicio.ejecutar(busqueda_id)

    busqueda = BusquedaRepository(db).get_by_id(busqueda_id)
    assert busqueda.duracion_ms is not None
    assert busqueda.duracion_ms < DOS_MINUTOS_EN_MS


# --- Filtro duro: los años desconocidos no descalifican ----------------------


def test_un_candidato_sin_anios_declarados_no_se_descarta(db):
    """
    Antes de HU-18 nadie llenaba anios_experiencia, así que el SQL descartaba
    a todo el mundo en cuanto la solicitud pedía experiencia mínima. Un dato
    ausente no es un dato que incumple (RNF27).
    """
    ids = _crear_candidatos(db, 2, anios=None)

    assert sorted(FiltroDuro(db).aplicar(ids, experiencia_min=5)) == sorted(ids)


def test_el_que_declara_menos_anios_de_los_pedidos_si_se_descarta(db):
    poco = _crear_candidatos(db, 1, anios=2)
    suficiente = _crear_candidatos(db, 1, anios=8)

    quedan = FiltroDuro(db).aplicar(poco + suficiente, experiencia_min=5)

    assert quedan == suficiente


def test_sin_experiencia_minima_pasan_todos(db):
    ids = _crear_candidatos(db, 3, anios=1)

    assert sorted(FiltroDuro(db).aplicar(ids, experiencia_min=None)) == sorted(ids)
