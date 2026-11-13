"""
Cola de trabajos con Redis (componente C15).

Redis puede estar arriba sin worker: lo encolado esperaría para siempre y la
búsqueda se quedaría "en cola". Estas pruebas fijan que en ese caso el trabajo
corre dentro de la API y que, con worker, sí va a la cola.
"""

from types import SimpleNamespace

import pytest

from backend.workers import queue


class TareasFalsas:
    def __init__(self):
        self.agregadas = []

    def add_task(self, funcion, *args):
        self.agregadas.append((funcion, args))


class ColaFalsa:
    def __init__(self):
        self.encoladas = []

    def enqueue(self, funcion, *args, job_timeout):
        self.encoladas.append((funcion, args))
        return SimpleNamespace(id="trabajo-1")


def test_con_redis_pero_sin_worker_la_busqueda_corre_en_segundo_plano(monkeypatch):
    cola = ColaFalsa()
    monkeypatch.setattr(queue, "get_cola", lambda: cola)
    monkeypatch.setattr(queue, "hay_workers", lambda _: False)
    tareas = TareasFalsas()

    resultado = queue.despachar(tareas, print, "busqueda-1")

    assert resultado is None
    assert cola.encoladas == []
    assert tareas.agregadas == [(print, ("busqueda-1",))]


def test_con_redis_y_worker_el_trabajo_va_a_la_cola(monkeypatch):
    cola = ColaFalsa()
    monkeypatch.setattr(queue, "get_cola", lambda: cola)
    monkeypatch.setattr(queue, "hay_workers", lambda _: True)
    tareas = TareasFalsas()

    resultado = queue.despachar(tareas, print, "busqueda-1")

    assert resultado == "trabajo-1"
    assert cola.encoladas == [(print, ("busqueda-1",))]
    assert tareas.agregadas == []


def test_encolar_sin_worker_ejecuta_directo_en_lugar_de_dejarlo_esperando(monkeypatch):
    cola = ColaFalsa()
    monkeypatch.setattr(queue, "get_cola", lambda: cola)
    monkeypatch.setattr(queue, "hay_workers", lambda _: False)
    ejecutadas = []

    resultado = queue.encolar(ejecutadas.append, "hoja-1")

    assert resultado is None
    assert ejecutadas == ["hoja-1"]
    assert cola.encoladas == []


def test_si_no_se_puede_contar_workers_se_asume_que_hay(monkeypatch):
    """Una cola que no responde a la consulta no debe desviar trabajos que sí tienen worker."""
    assert queue.hay_workers(object()) is True


# --- Redis se cae con la API ya en marcha ------------------------------------


class ColaCaida:
    """Una cola que se conectó bien al arrancar y luego dejó de responder."""

    def enqueue(self, funcion, *args, job_timeout):
        from redis.exceptions import ConnectionError as ErrorDeConexion

        raise ErrorDeConexion("Connection refused")


def test_si_redis_se_cae_despues_de_conectar_la_busqueda_corre_en_la_api(monkeypatch):
    monkeypatch.setattr(queue, "_cola", ColaCaida())
    monkeypatch.setattr(queue, "hay_workers", lambda _: True)
    tareas = TareasFalsas()

    resultado = queue.despachar(tareas, print, "busqueda-1")

    assert resultado is None
    assert tareas.agregadas == [(print, ("busqueda-1",))]
    # Se olvida la conexión: la siguiente llamada vuelve a comprobar Redis.
    assert queue._cola is None


def test_encolar_con_redis_caido_ejecuta_el_trabajo_en_linea(monkeypatch):
    monkeypatch.setattr(queue, "_cola", ColaCaida())
    monkeypatch.setattr(queue, "hay_workers", lambda _: True)
    ejecutados = []

    resultado = queue.encolar(lambda valor: ejecutados.append(valor), "indexar-1")

    assert resultado is None
    assert ejecutados == ["indexar-1"]


def test_un_error_que_no_es_de_conexion_no_se_traga(monkeypatch):
    class ColaConFallo:
        def enqueue(self, funcion, *args, job_timeout):
            raise ValueError("argumentos invalidos")

    monkeypatch.setattr(queue, "_cola", ColaConFallo())
    monkeypatch.setattr(queue, "hay_workers", lambda _: True)

    with pytest.raises(ValueError, match="argumentos invalidos"):
        queue.despachar(TareasFalsas(), print, "x")


def test_si_comprobar_los_workers_falla_por_conexion_se_asume_que_no_hay_cola(monkeypatch):
    from redis.exceptions import ConnectionError as ErrorDeConexion
    from rq import Worker

    def sin_conexion(**kwargs):
        raise ErrorDeConexion("Connection refused")

    monkeypatch.setattr(Worker, "count", staticmethod(sin_conexion))
    monkeypatch.setattr(queue, "_cola", object())

    assert queue.hay_workers(object()) is False
    assert queue._cola is None
