"""
Pruebas contra un Redis de verdad (C15 y C22).

La cola y la caché se prueban en otros archivos con dobles. Aquí se comprueba
lo que los dobles no pueden: que RQ y Redis se entienden, que un worker real
toma el trabajo y que la caché guarda y vence de verdad.

Se omiten solas si no hay un Redis. Para ejecutarlas:

    docker run -d -p 56379:6379 redis:7-alpine
    PRUEBAS_REDIS_URL=redis://localhost:56379/0 python -m pytest tests/test_redis_real.py
"""

import os

import pytest

URL = os.getenv("PRUEBAS_REDIS_URL")
pytestmark = pytest.mark.skipif(not URL, reason="Requiere un Redis (PRUEBAS_REDIS_URL)")


@pytest.fixture
def conexion():
    from redis import Redis

    conexion = Redis.from_url(URL)
    conexion.flushdb()
    yield conexion
    conexion.flushdb()
    conexion.close()


@pytest.fixture
def modulos_con_redis(monkeypatch, conexion):
    """Apunta la cola y la caché al Redis de pruebas."""
    from backend.infrastructure import cache
    from backend.workers import queue

    monkeypatch.setattr(queue, "REDIS_URL", URL)
    monkeypatch.setattr(queue, "_cola", None)
    monkeypatch.setattr(cache, "REDIS_URL", URL)
    cache.reiniciar()
    yield queue, cache
    cache.reiniciar()


def tarea_de_prueba(valor):
    """Función de nivel de módulo: RQ la importa por nombre desde el worker."""
    from redis import Redis

    Redis.from_url(os.environ["PRUEBAS_REDIS_URL"]).set("beematch:prueba:resultado", valor)


def test_sin_worker_el_trabajo_corre_en_la_api_y_no_queda_en_la_cola(modulos_con_redis, conexion):
    queue, _ = modulos_con_redis
    assert queue.get_cola() is not None
    assert queue.hay_workers(queue.get_cola()) is False

    assert queue.encolar(tarea_de_prueba, "directo") is None  # corrió en línea
    assert conexion.get("beematch:prueba:resultado") == b"directo"
    assert len(queue.get_cola()) == 0


def test_con_un_worker_registrado_el_trabajo_va_a_la_cola_y_el_worker_lo_ejecuta(
    modulos_con_redis, conexion, monkeypatch
):
    from rq import SimpleWorker

    monkeypatch.setenv("PRUEBAS_REDIS_URL", URL)
    queue, _ = modulos_con_redis
    cola = queue.get_cola()

    # Un worker registrado (aunque aún no haya tomado nada) hace que `encolar`
    # confíe en la cola, como en producción.
    worker = SimpleWorker([cola], connection=conexion)
    worker.register_birth()
    try:
        assert queue.hay_workers(cola) is True
        id_trabajo = queue.encolar(tarea_de_prueba, "por la cola")
        assert id_trabajo is not None
        assert len(cola) == 1
        assert conexion.get("beematch:prueba:resultado") is None  # aún nadie lo ejecutó
    finally:
        worker.register_death()

    # El worker toma el trabajo pendiente y termina (burst).
    SimpleWorker([cola], connection=conexion).work(burst=True)
    assert conexion.get("beematch:prueba:resultado") == b"por la cola"
    assert len(cola) == 0


def test_un_trabajo_encolado_sobrevive_aunque_nadie_lo_atienda_por_un_rato(
    modulos_con_redis, conexion, monkeypatch
):
    """Es la razón de usar Redis: reiniciar la API no pierde lo encolado."""
    from rq import Queue, SimpleWorker

    monkeypatch.setenv("PRUEBAS_REDIS_URL", URL)
    cola = Queue("beematch", connection=conexion)
    cola.enqueue(tarea_de_prueba, "sobrevivio")

    # "La API se reinicia": se descarta todo el estado en memoria.
    queue, _ = modulos_con_redis
    queue._cola = None

    assert len(Queue("beematch", connection=conexion)) == 1
    SimpleWorker([Queue("beematch", connection=conexion)], connection=conexion).work(burst=True)
    assert conexion.get("beematch:prueba:resultado") == b"sobrevivio"


def test_la_cache_guarda_el_vector_y_vence(modulos_con_redis, conexion):
    _, cache = modulos_con_redis
    cache.guardar_embedding("modelo", 3, "backend", [0.1, 0.2, 0.3])

    assert cache.obtener_embedding("modelo", 3, "backend") == [0.1, 0.2, 0.3]
    [clave] = conexion.keys(f"{cache.PREFIJO}*")
    assert 0 < conexion.ttl(clave) <= cache.EMBEDDING_CACHE_TTL_HORAS * 3600
    assert cache.obtener_embedding("modelo", 3, "otra consulta") is None


def test_la_cache_no_toca_las_claves_de_la_cola(modulos_con_redis, conexion):
    _, cache = modulos_con_redis
    cache.guardar_embedding("modelo", 3, "backend", [0.1])
    assert all(k.startswith(b"beematch:emb:") for k in conexion.keys("*"))
