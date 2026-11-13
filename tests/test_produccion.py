"""Validaciones de arranque en producción y endpoints de salud."""

import logging

import pytest
from cryptography.fernet import Fernet

from backend import config, produccion

BUENA = {
    "JWT_SECRET": "x" * 48,
    "ENCRYPTION_KEY": Fernet.generate_key().decode(),
    "USA_PGVECTOR": True,
    "SUPERUSUARIO_CORREO": "diana@bee.com.co",
    "SUPERUSUARIO_PASSWORD": "una-clave-larga-123",
    "ALLOWED_ORIGINS": ["https://beematch.ejemplo.com"],
    "EMBEDDING_API_KEY": "sk-a",
    "LLM_API_KEY": "sk-b",
}


@pytest.fixture
def ajustar(monkeypatch):
    def _ajustar(**cambios):
        for nombre, valor in {**BUENA, **cambios}.items():
            monkeypatch.setattr(config, nombre, valor)

    return _ajustar


def test_una_configuracion_correcta_no_tiene_problemas(ajustar):
    ajustar()
    assert produccion.problemas_de_configuracion() == []
    assert produccion.advertencias_de_configuracion() == []


def test_el_secreto_de_ejemplo_se_rechaza(ajustar):
    ajustar(JWT_SECRET=produccion.SECRETO_DE_EJEMPLO)
    assert any("JWT_SECRET" in p for p in produccion.problemas_de_configuracion())


def test_un_secreto_corto_se_rechaza(ajustar):
    ajustar(JWT_SECRET="corto")
    assert any("al menos 32" in p for p in produccion.problemas_de_configuracion())


def test_sin_clave_de_cifrado_propia_se_rechaza(ajustar):
    ajustar(ENCRYPTION_KEY="")
    assert any("ENCRYPTION_KEY está vacía" in p for p in produccion.problemas_de_configuracion())


def test_una_clave_de_cifrado_que_no_es_fernet_se_rechaza(ajustar):
    ajustar(ENCRYPTION_KEY="esto-no-es-una-clave-fernet")
    assert any("Fernet" in p for p in produccion.problemas_de_configuracion())


def test_sqlite_se_rechaza(ajustar):
    ajustar(USA_PGVECTOR=False)
    assert any("PostgreSQL" in p for p in produccion.problemas_de_configuracion())


def test_la_clave_debil_de_la_superusuaria_se_rechaza(ajustar):
    ajustar(SUPERUSUARIO_PASSWORD="diana123")
    assert any("SUPERUSUARIO_PASSWORD" in p for p in produccion.problemas_de_configuracion())


def test_sin_superusuaria_configurada_no_se_exige_clave(ajustar):
    ajustar(SUPERUSUARIO_CORREO="", SUPERUSUARIO_PASSWORD="")
    assert produccion.problemas_de_configuracion() == []


def test_faltar_las_claves_de_ia_solo_advierte(ajustar, caplog):
    ajustar(EMBEDDING_API_KEY="", LLM_API_KEY="")
    monkey_es_produccion = pytest.MonkeyPatch()
    monkey_es_produccion.setattr(config, "ES_PRODUCCION", True)
    try:
        with caplog.at_level(logging.WARNING):
            produccion.validar_configuracion_de_produccion()  # no lanza
    finally:
        monkey_es_produccion.undo()
    assert "EMBEDDING_API_KEY" in caplog.text


def test_en_produccion_una_configuracion_mala_impide_arrancar(ajustar, monkeypatch):
    ajustar(JWT_SECRET=produccion.SECRETO_DE_EJEMPLO)
    monkeypatch.setattr(config, "ES_PRODUCCION", True)
    with pytest.raises(produccion.ConfiguracionDeProduccionInvalida, match="JWT_SECRET"):
        produccion.validar_configuracion_de_produccion()


def test_en_desarrollo_no_se_valida_nada(ajustar, monkeypatch):
    ajustar(JWT_SECRET=produccion.SECRETO_DE_EJEMPLO, USA_PGVECTOR=False)
    monkeypatch.setattr(config, "ES_PRODUCCION", False)
    produccion.validar_configuracion_de_produccion()  # no lanza


def test_health_responde_sin_tocar_la_base(cliente):
    respuesta = cliente.get("/health")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "ok"}


def test_health_ready_informa_base_y_redis(cliente, monkeypatch):
    from backend.workers import queue

    monkeypatch.setattr(queue, "get_cola", lambda: None)
    respuesta = cliente.get("/health/ready")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "ok", "base_de_datos": "ok", "redis": "no disponible"}


def test_health_ready_con_redis_y_sin_worker(cliente, monkeypatch):
    from backend.workers import queue

    monkeypatch.setattr(queue, "get_cola", lambda: object())
    monkeypatch.setattr(queue, "hay_workers", lambda _: False)
    assert cliente.get("/health/ready").json()["redis"] == "sin worker"


def test_health_ready_devuelve_503_si_la_base_no_responde(cliente, monkeypatch):
    from backend.infrastructure.persistence import database

    class MotorRoto:
        def connect(self):
            raise ConnectionError("sin base")

    monkeypatch.setattr(database, "engine", MotorRoto())
    respuesta = cliente.get("/health/ready")
    assert respuesta.status_code == 503
    assert respuesta.json()["status"] == "error"
