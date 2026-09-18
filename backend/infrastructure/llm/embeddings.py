"""Generación de embeddings. Aislada para poder cambiar de proveedor (RNF33)."""

import json

from backend.config import EMBEDDING_DIMENSIONES, EMBEDDING_MODELO, USA_PGVECTOR


class ProveedorEmbeddingsNoDisponibleError(RuntimeError):
    """
    Todavía no hay un proveedor de embeddings conectado.

    No es un error del documento ni de la conexión al repositorio: es una pieza
    del sistema que falta. Se distingue con su propio tipo para que la
    sincronización pueda registrar los documentos y dejar la indexación
    aplazada, en vez de marcar como ilegibles hojas de vida que están bien.
    """


class ProveedorEmbeddings:
    def __init__(self, modelo: str = EMBEDDING_MODELO):
        self.modelo = modelo
        self.dimensiones = EMBEDDING_DIMENSIONES

    def generar(self, textos: list[str]) -> list[list[float]]:
        """
        Genera un vector por texto.

        TODO(Sprint 1): reemplazar por la llamada real al proveedor. La firma no
        debe cambiar: el resto del sistema solo conoce este método.
        """
        raise ProveedorEmbeddingsNoDisponibleError(
            "Falta conectar el proveedor de embeddings (pendiente del Sprint 1). "
            "Los documentos quedan registrados y se indexarán cuando esté disponible."
        )

    def generar_uno(self, texto: str) -> list[float]:
        return self.generar([texto])[0]


def serializar(vector: list[float]) -> object:
    """pgvector acepta la lista directamente; SQLite la guarda como JSON."""
    return vector if USA_PGVECTOR else json.dumps(vector)


def deserializar(valor: object) -> list[float]:
    if valor is None:
        return []
    if isinstance(valor, str):
        return json.loads(valor)
    return list(valor)
