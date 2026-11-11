"""Logs estructurados, identificador de petición y Sentry opcional (C27)."""

import json
import logging

from backend import config, logging_config
from backend.logging_config import FormatoJson


def _registro(mensaje="hola", **extra):
    registro = logging.LogRecord("backend.prueba", logging.WARNING, __file__, 1, mensaje, (), None)
    registro.__dict__.update(extra)
    return registro


def test_el_formato_json_es_una_linea_con_los_campos_esperados():
    linea = FormatoJson().format(_registro("algo pasó", estado=500))
    evento = json.loads(linea)
    assert "\n" not in linea
    assert evento["mensaje"] == "algo pasó"
    assert evento["nivel"] == "WARNING"
    assert evento["logger"] == "backend.prueba"
    assert evento["estado"] == 500
    assert evento["hora"].endswith("+00:00")


def test_una_excepcion_queda_en_el_mismo_evento():
    try:
        raise ValueError("fallo")
    except ValueError:
        import sys

        registro = _registro("con error")
        registro.exc_info = sys.exc_info()
    evento = json.loads(FormatoJson().format(registro))
    assert "ValueError: fallo" in evento["excepcion"]


def test_la_respuesta_trae_un_id_de_peticion_nuevo(cliente):
    respuesta = cliente.get("/health")
    assert len(respuesta.headers["x-request-id"]) == 12


def test_se_respeta_el_id_que_manda_el_proxy(cliente):
    respuesta = cliente.get("/health", headers={"X-Request-ID": "abc-123"})
    assert respuesta.headers["x-request-id"] == "abc-123"


def test_cada_peticion_se_registra_con_ruta_estado_y_duracion(cliente, caplog):
    with caplog.at_level(logging.INFO, logger="backend.peticiones"):
        cliente.get("/auth/yo")
    registro = next(r for r in caplog.records if r.name == "backend.peticiones")
    assert registro.ruta == "/auth/yo"
    assert registro.estado in (401, 403)
    assert registro.duracion_ms >= 0


def test_ni_la_query_string_ni_el_cuerpo_llegan_al_log(cliente, caplog):
    with caplog.at_level(logging.INFO, logger="backend.peticiones"):
        cliente.post(
            "/auth/login?token=SECRETO-EN-URL",
            json={"correo": "x@bee.com.co", "password": "CLAVE-EN-CUERPO"},
        )
    nuestros = [r for r in caplog.records if r.name == "backend.peticiones"]
    assert nuestros
    texto = " ".join(str(r.__dict__) for r in nuestros)
    assert "SECRETO-EN-URL" not in texto
    assert "CLAVE-EN-CUERPO" not in texto


def test_httpx_no_registra_las_urls_de_las_llamadas_salientes():
    logging_config.configurar_logging()
    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING


def test_los_health_checks_no_llenan_el_log(cliente, caplog):
    with caplog.at_level(logging.INFO, logger="backend.peticiones"):
        cliente.get("/health")
    assert not [r for r in caplog.records if r.name == "backend.peticiones"]


def test_sin_dsn_sentry_queda_apagado(monkeypatch):
    monkeypatch.setattr(config, "SENTRY_DSN", "")
    assert logging_config.iniciar_sentry() is False


def test_con_dsn_se_inicializa_sentry_sin_datos_personales(monkeypatch):
    import sentry_sdk

    llamadas = []
    monkeypatch.setattr(config, "SENTRY_DSN", "https://clave@sentry.example/1")
    monkeypatch.setattr(sentry_sdk, "init", lambda **kw: llamadas.append(kw))
    assert logging_config.iniciar_sentry() is True
    assert llamadas[0]["send_default_pii"] is False
