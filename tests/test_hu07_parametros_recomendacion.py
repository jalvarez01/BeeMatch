"""
HU-07: configuración de los parámetros de recomendación.

Criterio 1 - el administrador fija cuántos candidatos se sugieren (3 a 10).
Criterio 2 - el administrador fija el porcentaje mínimo de afinidad.
Criterio 3 - un valor fuera de rango muestra un mensaje y se conserva el anterior.
Criterio 4 - sin cambios, el sistema usa 5 candidatos.

Las pruebas por la API entran con sesiones reales. Las del motor reutilizan los
dobles de `test_top5_candidatos` (recuperador, embeddings y re-ranking falsos):
lo que se prueba es que la búsqueda lea los parámetros, no la calidad del modelo.
"""

import pytest

from backend.config import TOP_N_RESULTADOS, UMBRAL_AFINIDAD_MINIMA
from backend.domain.services.parametros_service import (
    CLAVE_NUM_CANDIDATOS,
    CLAVE_UMBRAL_AFINIDAD,
    ParametrosInvalidosError,
    ParametrosRecomendacionService,
)
from backend.domain.services.resultado_service import ResultadoService
from backend.infrastructure.persistence.repositories.configuracion_repo import ParametroRepository
from tests.test_top5_candidatos import _crear_candidatos, _crear_solicitud, _servicio

RUTA = "/configuracion/recomendacion"


@pytest.fixture
def admin(crear_usuario, entrar):
    crear_usuario("admin@bee.com.co", rol="ADMINISTRADOR")
    return entrar("admin@bee.com.co")


def _guardados(db) -> dict[str, str]:
    return {p.clave: p.valor for p in ParametroRepository(db).listar()}


# --- Criterio 4: sin cambios rige el valor por defecto -----------------------


def test_hu07_criterio4_sin_configuracion_se_sugieren_cinco_candidatos(cliente, admin):
    respuesta = cliente.get(RUTA, headers=admin)

    assert respuesta.status_code == 200
    assert respuesta.json()["num_candidatos"] == TOP_N_RESULTADOS
    assert TOP_N_RESULTADOS == 5


def test_hu07_criterio4_sin_configuracion_el_minimo_de_afinidad_es_el_de_config(cliente, admin):
    cuerpo = cliente.get(RUTA, headers=admin).json()

    # El valor sale de config.py (60 salvo que el .env local lo cambie).
    assert cuerpo["umbral_afinidad"] == int(UMBRAL_AFINIDAD_MINIMA)
    assert cuerpo["num_candidatos_por_defecto"] == TOP_N_RESULTADOS
    assert cuerpo["umbral_afinidad_por_defecto"] == int(UMBRAL_AFINIDAD_MINIMA)


def test_hu07_criterio4_consultar_no_escribe_nada_en_la_base(cliente, admin, db):
    cliente.get(RUTA, headers=admin)

    assert _guardados(db) == {}


# --- Criterios 1 y 2: el administrador cambia los valores --------------------


def test_hu07_criterio1_un_valor_valido_se_guarda_y_persiste(cliente, admin, db):
    respuesta = cliente.put(RUTA, json={"num_candidatos": 7, "umbral_afinidad": 75}, headers=admin)

    assert respuesta.status_code == 200
    assert respuesta.json()["num_candidatos"] == 7
    assert respuesta.json()["umbral_afinidad"] == 75
    # Una consulta posterior (otra petición, otra sesión) ve los valores nuevos.
    assert cliente.get(RUTA, headers=admin).json()["num_candidatos"] == 7
    assert _guardados(db)[CLAVE_NUM_CANDIDATOS] == "7"


@pytest.mark.parametrize("valor", [3, 10])
def test_hu07_criterio1_los_limites_3_y_10_se_aceptan(cliente, admin, valor):
    respuesta = cliente.put(RUTA, json={"num_candidatos": valor, "umbral_afinidad": 60}, headers=admin)

    assert respuesta.status_code == 200
    assert respuesta.json()["num_candidatos"] == valor


@pytest.mark.parametrize("valor", [0, 2, 11])
def test_hu07_criterio3_fuera_del_rango_de_candidatos_se_rechaza_con_mensaje(cliente, admin, valor):
    respuesta = cliente.put(RUTA, json={"num_candidatos": valor, "umbral_afinidad": 60}, headers=admin)

    assert respuesta.status_code == 422
    assert "candidatos sugeridos" in respuesta.json()["detail"]
    assert "entre 3 y 10" in respuesta.json()["detail"]


@pytest.mark.parametrize("valor", [0, 100])
def test_hu07_criterio2_los_limites_0_y_100_del_porcentaje_se_aceptan(cliente, admin, valor):
    respuesta = cliente.put(RUTA, json={"num_candidatos": 5, "umbral_afinidad": valor}, headers=admin)

    assert respuesta.status_code == 200
    assert respuesta.json()["umbral_afinidad"] == valor


@pytest.mark.parametrize("valor", [-1, 101])
def test_hu07_criterio3_fuera_del_rango_del_porcentaje_se_rechaza_con_mensaje(cliente, admin, valor):
    respuesta = cliente.put(RUTA, json={"num_candidatos": 5, "umbral_afinidad": valor}, headers=admin)

    assert respuesta.status_code == 422
    assert "porcentaje mínimo de afinidad" in respuesta.json()["detail"]
    assert "entre 0 y 100" in respuesta.json()["detail"]


def test_hu07_criterio3_si_ambos_estan_fuera_de_rango_el_mensaje_nombra_los_dos(cliente, admin):
    respuesta = cliente.put(RUTA, json={"num_candidatos": 2, "umbral_afinidad": 101}, headers=admin)

    assert respuesta.status_code == 422
    assert "candidatos sugeridos" in respuesta.json()["detail"]
    assert "porcentaje mínimo" in respuesta.json()["detail"]


# --- Criterio 3: al rechazar se conserva el valor anterior -------------------


def test_hu07_criterio3_al_rechazar_los_valores_anteriores_no_cambian(cliente, admin, db):
    cliente.put(RUTA, json={"num_candidatos": 8, "umbral_afinidad": 70}, headers=admin)
    antes = _guardados(db)

    # Un valor válido junto a uno inválido: se rechaza el conjunto completo.
    respuesta = cliente.put(RUTA, json={"num_candidatos": 4, "umbral_afinidad": 150}, headers=admin)

    assert respuesta.status_code == 422
    db.expire_all()
    assert _guardados(db) == antes
    vigentes = cliente.get(RUTA, headers=admin).json()
    assert (vigentes["num_candidatos"], vigentes["umbral_afinidad"]) == (8, 70)


def test_hu07_criterio3_el_endpoint_generico_aplica_los_mismos_limites(cliente, admin, db):
    respuesta = cliente.put(
        f"/configuracion/parametros/{CLAVE_NUM_CANDIDATOS}", json={"valor": "50"}, headers=admin
    )

    assert respuesta.status_code == 422
    assert _guardados(db) == {}


def test_hu07_criterio3_el_endpoint_generico_rechaza_un_texto_que_no_es_numero(cliente, admin):
    respuesta = cliente.put(
        f"/configuracion/parametros/{CLAVE_UMBRAL_AFINIDAD}", json={"valor": "alto"}, headers=admin
    )

    assert respuesta.status_code == 422


def test_hu07_criterio3_un_valor_guardado_corrupto_vuelve_al_defecto(db):
    ParametroRepository(db).establecer(CLAVE_NUM_CANDIDATOS, "muchos")
    ParametroRepository(db).establecer(CLAVE_UMBRAL_AFINIDAD, "500")

    vigentes = ParametrosRecomendacionService(db).obtener()

    assert (vigentes.num_candidatos, vigentes.umbral_afinidad) == (
        TOP_N_RESULTADOS,
        int(UMBRAL_AFINIDAD_MINIMA),
    )


def test_hu07_criterio3_el_servicio_no_escribe_nada_si_hay_un_error(db):
    servicio = ParametrosRecomendacionService(db)
    servicio.actualizar(6, 65)

    with pytest.raises(ParametrosInvalidosError):
        servicio.actualizar(9, -5)

    vigentes = servicio.obtener()
    assert (vigentes.num_candidatos, vigentes.umbral_afinidad) == (6, 65)


# --- Solo el administrador ---------------------------------------------------


@pytest.mark.parametrize("rol", ["DIRECTOR", "COORDINADOR"])
def test_hu07_solo_el_administrador_configura_los_parametros(cliente, crear_usuario, entrar, db, rol):
    crear_usuario("otro@bee.com.co", rol=rol)
    cabeceras = entrar("otro@bee.com.co")

    assert cliente.get(RUTA, headers=cabeceras).status_code == 403
    intento = cliente.put(RUTA, json={"num_candidatos": 9, "umbral_afinidad": 90}, headers=cabeceras)
    assert intento.status_code == 403
    assert _guardados(db) == {}


def test_hu07_sin_sesion_los_parametros_responden_401(cliente):
    assert cliente.get(RUTA).status_code == 401
    assert cliente.put(RUTA, json={"num_candidatos": 5, "umbral_afinidad": 60}).status_code == 401


def test_hu07_el_cambio_queda_en_la_bitacora(cliente, admin):
    cliente.put(RUTA, json={"num_candidatos": 6, "umbral_afinidad": 65}, headers=admin)

    eventos = cliente.get("/configuracion/bitacora", headers=admin).json()["items"]
    cambio = next(e for e in eventos if e["accion"] == "CONFIG_CAMBIADA")
    assert f"{TOP_N_RESULTADOS} a 6" in cambio["detalle"]
    assert f"{int(UMBRAL_AFINIDAD_MINIMA)} a 65" in cambio["detalle"]


# --- El motor lee los parámetros al ejecutar la búsqueda ---------------------


def _buscar(db, puntajes: list[float]):
    ids = _crear_candidatos(db, len(puntajes))
    servicio = _servicio(db, dict(zip(ids, puntajes, strict=True)), ids)
    busqueda_id = servicio.encolar(_crear_solicitud(db))
    servicio.ejecutar(busqueda_id)
    return ResultadoService(db).resultados(busqueda_id).recomendaciones


def test_hu07_criterio1_con_tres_candidatos_configurados_la_busqueda_devuelve_a_lo_sumo_tres(db):
    ParametrosRecomendacionService(db).actualizar(3, 60)

    resultado = _buscar(db, [95, 90, 85, 80, 75, 70, 65])

    assert len(resultado) == 3


def test_hu07_criterio1_con_diez_candidatos_configurados_la_busqueda_devuelve_hasta_diez(db):
    ParametrosRecomendacionService(db).actualizar(10, 60)

    resultado = _buscar(db, [99 - i for i in range(12)])

    assert len(resultado) == 10


def test_hu07_criterio4_sin_configurar_la_busqueda_devuelve_cinco(db):
    resultado = _buscar(db, [99 - i for i in range(8)])

    assert len(resultado) == 5


def test_hu07_criterio2_un_minimo_mas_alto_excluye_a_los_candidatos_por_debajo(db):
    ParametrosRecomendacionService(db).actualizar(10, 80)

    resultado = _buscar(db, [95, 85, 79, 70, 65])

    afinidades = [r.puntaje_afinidad for r in resultado]
    assert afinidades == [95, 85]


def test_hu07_criterio2_un_minimo_mas_bajo_deja_pasar_candidatos_que_antes_no_pasaban(db):
    ParametrosRecomendacionService(db).actualizar(10, 40)

    resultado = _buscar(db, [90, 55, 45, 30])

    assert [r.puntaje_afinidad for r in resultado] == [90, 55, 45]


def test_hu07_el_cambio_aplica_a_busquedas_nuevas_y_no_a_resultados_ya_generados(db):
    ids = _crear_candidatos(db, 8)
    servicio = _servicio(db, {cid: 95.0 - i for i, cid in enumerate(ids)}, ids)
    solicitud_id = _crear_solicitud(db)
    primera = servicio.encolar(solicitud_id)
    servicio.ejecutar(primera)

    ParametrosRecomendacionService(db).actualizar(3, 60)
    segunda = servicio.encolar(solicitud_id)
    servicio.ejecutar(segunda)

    assert len(ResultadoService(db).resultados(primera).recomendaciones) == 5
    assert len(ResultadoService(db).resultados(segunda).recomendaciones) == 3
