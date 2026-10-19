"""HU-17/RNF19: un fallo puntual del proveedor de embeddings no tumba la corrida."""

import pytest

from backend.infrastructure.llm.embeddings import (
    EmbeddingsError,
    ProveedorEmbeddingsNoDisponibleError,
)
from backend.workers import scheduler


class SincronizacionFalsa:
    def __init__(self, db):
        pass

    def sincronizar(self):
        return {"documentos_detectados": 4, "hojas_a_indexar": ["a", "b", "c", "d"]}


class _SesionFalsa:
    def close(self):
        pass


@pytest.fixture(autouse=True)
def _sin_db_real(monkeypatch):
    monkeypatch.setattr(scheduler, "SessionLocal", _SesionFalsa)
    monkeypatch.setattr(scheduler, "SincronizacionService", SincronizacionFalsa)


def test_un_fallo_de_red_puntual_no_detiene_las_demas(monkeypatch):
    """Como el caso real: falla el documento 3 de 4 con un error de conexión."""
    llamadas = []

    def encolar_falso(funcion, hoja_id):
        llamadas.append(hoja_id)
        if hoja_id == "c":
            raise EmbeddingsError("No fue posible contactar al proveedor de embeddings: [Errno 11001]")

    monkeypatch.setattr(scheduler, "encolar", encolar_falso)

    resultado = scheduler.sincronizar_y_encolar()

    # Se intentó con las cuatro, no se detuvo en la que falló.
    assert llamadas == ["a", "b", "c", "d"]
    assert resultado["documentos_encolados"] == 3
    assert resultado["documentos_aplazados"] == 1
    assert "11001" in resultado["motivo_aplazamiento"]


def test_falta_la_clave_si_detiene_las_demas(monkeypatch):
    """Este error es del sistema, no del documento: reintentar no cambiaría nada."""
    llamadas = []

    def encolar_falso(funcion, hoja_id):
        llamadas.append(hoja_id)
        raise ProveedorEmbeddingsNoDisponibleError("Falta configurar EMBEDDING_API_KEY.")

    monkeypatch.setattr(scheduler, "encolar", encolar_falso)

    resultado = scheduler.sincronizar_y_encolar()

    assert llamadas == ["a"]  # ni intenta con las demás
    assert resultado["documentos_encolados"] == 0
    assert resultado["documentos_aplazados"] == 4
