"""
Cola de trabajos con Redis (componente C15).

Redis puede estar arriba sin worker: lo encolado esperaría para siempre y la
búsqueda se quedaría "en cola". Estas pruebas fijan que en ese caso el trabajo
corre dentro de la API y que, con worker, sí va a la cola.
"""

from types import SimpleNamespace

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
