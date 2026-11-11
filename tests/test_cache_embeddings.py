"""
Caché de embeddings de consultas en Redis (C22).

Con un Redis de mentira se fijan las reglas; las pruebas con un Redis real
están en test_redis_real.py.
"""

import json

import pytest

from backend.infrastructure import cache
from backend.infrastructure.llm.embeddings import ProveedorEmbeddings


class RedisFalso:
    def __init__(self):
        self.datos = {}
        self.ttl = {}

    def get(self, clave):
        return self.datos.get(clave)

    def setex(self, clave, segundos, valor):
        self.datos[clave] = valor
        self.ttl[clave] = segundos


class RedisRoto:
    def get(self, clave):
        raise ConnectionError("Redis se cayó")

    def setex(self, *args):
        raise ConnectionError("Redis se cayó")


class ProveedorContador(ProveedorEmbeddings):
    """Cuenta las llamadas que llegan al proveedor de pago."""

    def __init__(self, modelo="modelo-a"):
        super().__init__(modelo=modelo, api_key="clave")
        self.llamadas = 0

    def generar(self, textos):
        self.llamadas += 1
        return [[0.25, 0.5, 0.75] for _ in textos]


@pytest.fixture
def redis(monkeypatch):
    falso = RedisFalso()
    monkeypatch.setattr(cache, "obtener_redis", lambda: falso)
    return falso


def test_la_segunda_consulta_igual_no_llega_al_proveedor(redis):
    proveedor = ProveedorContador()

    primero = proveedor.generar_uno("backend senior en Python")
    segundo = proveedor.generar_uno("backend senior en Python")

    assert primero == segundo == [0.25, 0.5, 0.75]
    assert proveedor.llamadas == 1


def test_una_consulta_distinta_si_llega_al_proveedor(redis):
    proveedor = ProveedorContador()
    proveedor.generar_uno("backend senior en Python")
    proveedor.generar_uno("analista de datos")
    assert proveedor.llamadas == 2


def test_los_espacios_alrededor_no_cambian_la_clave(redis):
    proveedor = ProveedorContador()
    proveedor.generar_uno("backend senior")
    proveedor.generar_uno("  backend senior \n")
    assert proveedor.llamadas == 1


def test_otro_modelo_no_reutiliza_el_vector_de_este(redis):
    ProveedorContador("modelo-a").generar_uno("backend")
    otro = ProveedorContador("modelo-b")
    otro.generar_uno("backend")
    assert otro.llamadas == 1


def test_el_vector_guardado_vence_segun_la_configuracion(redis, monkeypatch):
    monkeypatch.setattr(cache, "EMBEDDING_CACHE_TTL_HORAS", 2)
    ProveedorContador().generar_uno("backend")
    [clave] = redis.datos
    assert redis.ttl[clave] == 2 * 3600
    assert clave.startswith(cache.PREFIJO)
    assert json.loads(redis.datos[clave]) == [0.25, 0.5, 0.75]


def test_sin_redis_la_consulta_funciona_igual(monkeypatch):
    monkeypatch.setattr(cache, "obtener_redis", lambda: None)
    proveedor = ProveedorContador()
    assert proveedor.generar_uno("backend") == [0.25, 0.5, 0.75]
    assert proveedor.generar_uno("backend") == [0.25, 0.5, 0.75]
    assert proveedor.llamadas == 2


def test_si_redis_falla_a_mitad_de_la_busqueda_no_se_rompe(monkeypatch):
    monkeypatch.setattr(cache, "obtener_redis", lambda: RedisRoto())
    proveedor = ProveedorContador()
    assert proveedor.generar_uno("backend") == [0.25, 0.5, 0.75]


def test_tras_un_fallo_de_conexion_no_se_reintenta_de_inmediato(monkeypatch):
    cache.reiniciar()
    intentos = []

    class RedisInalcanzable:
        @staticmethod
        def from_url(*args, **kwargs):
            intentos.append(1)
            raise ConnectionError("sin Redis")

    import redis as modulo_redis

    monkeypatch.setattr(modulo_redis, "Redis", RedisInalcanzable)
    try:
        assert cache.obtener_redis() is None
        assert cache.obtener_redis() is None
        assert cache.obtener_redis() is None
        assert len(intentos) == 1
    finally:
        cache.reiniciar()
