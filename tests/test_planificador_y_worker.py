"""El planificador (C18) corre en un solo lugar: la API en desarrollo, el worker al desplegar."""

import logging

import pytest

from backend import main
from backend.domain.services.repositorio_config_service import RepositorioNoConfiguradoError
from backend.workers import run_worker, scheduler


def test_sin_repositorio_configurado_la_sincronizacion_programada_no_falla(monkeypatch, caplog):
    def sin_repositorio():
        raise RepositorioNoConfiguradoError("no hay repositorio")

    monkeypatch.setattr(scheduler, "sincronizar_y_encolar", sin_repositorio)
    with caplog.at_level(logging.INFO):
        scheduler.sincronizacion_programada()  # no lanza
    assert "no hay repositorio configurado" in caplog.text


def test_otros_errores_de_la_sincronizacion_programada_si_se_propagan(monkeypatch):
    def falla():
        raise RuntimeError("Drive caído")

    monkeypatch.setattr(scheduler, "sincronizar_y_encolar", falla)
    with pytest.raises(RuntimeError, match="Drive caído"):
        scheduler.sincronizacion_programada()


def _arrancar_api(monkeypatch, en_api: bool) -> list:
    arrancados = []
    monkeypatch.setattr(main, "init_db", lambda: None)
    monkeypatch.setattr(main, "_informar_cola", lambda: None)
    monkeypatch.setattr(main, "_sembrar_parametros", lambda: None)
    monkeypatch.setattr(main, "_sembrar_superusuario", lambda: None)
    monkeypatch.setattr(main, "_sembrar_repositorio", lambda: None)
    monkeypatch.setattr(main, "_hay_origen_configurado", lambda: True)
    monkeypatch.setattr(main, "PLANIFICADOR_EN_API", en_api)
    monkeypatch.setattr(scheduler, "iniciar_planificador", lambda: arrancados.append(1))
    main.on_startup()
    return arrancados


def test_la_api_arranca_el_planificador_por_defecto(monkeypatch):
    assert _arrancar_api(monkeypatch, en_api=True) == [1]


def test_con_planificador_en_api_apagado_la_api_no_lo_arranca(monkeypatch):
    assert _arrancar_api(monkeypatch, en_api=False) == []


class WorkerFalso:
    def __init__(self, *args, **kwargs):
        pass

    def work(self):
        pass


@pytest.fixture
def worker_falso(monkeypatch):
    monkeypatch.setattr(run_worker, "SimpleWorker", WorkerFalso)
    monkeypatch.setattr(run_worker.Redis, "from_url", staticmethod(lambda *a, **k: object()))
    monkeypatch.setattr(run_worker, "Queue", lambda *a, **k: object())


def test_el_worker_arranca_el_planificador_solo_con_la_opcion(monkeypatch, worker_falso):
    arrancados = []
    monkeypatch.setattr(scheduler, "iniciar_planificador", lambda: arrancados.append(1) or object())

    monkeypatch.setattr("sys.argv", ["run_worker"])
    run_worker.main()
    assert arrancados == []

    monkeypatch.setattr("sys.argv", ["run_worker", "--planificador"])
    run_worker.main()
    assert arrancados == [1]
