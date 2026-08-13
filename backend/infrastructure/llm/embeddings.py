"""Generación de embeddings. Aislada para poder cambiar de proveedor (RNF33)."""

import json

from backend.config import EMBEDDING_DIMENSIONES, EMBEDDING_MODELO, USA_PGVECTOR


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
        raise NotImplementedError("Conectar el proveedor de embeddings en el Sprint 1.")

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
