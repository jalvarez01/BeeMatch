"""
Generación de embeddings. Aislada para poder cambiar de proveedor (RNF33).

El proveedor es el endpoint de embeddings de OpenAI, el mismo que atiende el
re-ranking. Las llamadas van con httpx y no con el SDK, igual que las de
Microsoft Graph y Google Drive, para no sumar otro cliente HTTP.
"""

import json

import httpx

from backend.config import (
    EMBEDDING_API_KEY,
    EMBEDDING_DIMENSIONES,
    EMBEDDING_LOTE,
    EMBEDDING_MODELO,
    EMBEDDING_URL,
    USA_PGVECTOR,
)

TIMEOUT = 60


class ProveedorEmbeddingsNoDisponibleError(RuntimeError):
    """
    No hay un proveedor de embeddings utilizable: falta la clave.

    No es un error del documento ni de la conexión al repositorio: es una pieza
    del sistema que falta. Se distingue con su propio tipo para que la
    sincronización pueda registrar los documentos y dejar la indexación
    aplazada, en vez de marcar como ilegibles hojas de vida que están bien.
    """


class EmbeddingsError(RuntimeError):
    """El proveedor respondió con un error. El worker reintenta (RNF18)."""


class ProveedorEmbeddings:
    def __init__(self, modelo: str = EMBEDDING_MODELO, api_key: str = EMBEDDING_API_KEY):
        self.modelo = modelo
        self.api_key = api_key
        self.dimensiones = EMBEDDING_DIMENSIONES

    def generar(self, textos: list[str]) -> list[list[float]]:
        """
        Genera un vector por texto, en el mismo orden en que llegaron.

        Los textos se mandan por lotes: la ingesta inicial son miles de
        fragmentos y una llamada por fragmento multiplicaría la latencia y el
        costo sin necesidad.
        """
        if not textos:
            return []

        if not self.api_key:
            raise ProveedorEmbeddingsNoDisponibleError(
                "Falta configurar EMBEDDING_API_KEY, la clave del proveedor de embeddings. "
                "Los documentos quedan registrados y se indexarán cuando esté disponible."
            )

        vectores: list[list[float]] = []
        for inicio in range(0, len(textos), EMBEDDING_LOTE):
            vectores.extend(self._pedir_lote(textos[inicio : inicio + EMBEDDING_LOTE]))
        return vectores

    def generar_uno(self, texto: str) -> list[float]:
        return self.generar([texto])[0]

    # --- Interno -------------------------------------------------------------

    def _pedir_lote(self, lote: list[str]) -> list[list[float]]:
        cuerpo = {
            "model": self.modelo,
            "input": lote,
            "dimensions": self.dimensiones,
        }

        try:
            respuesta = httpx.post(
                EMBEDDING_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=cuerpo,
                timeout=TIMEOUT,
            )
        except httpx.HTTPError as exc:
            raise EmbeddingsError(f"No fue posible contactar al proveedor de embeddings: {exc}")

        if respuesta.status_code == 401:
            raise ProveedorEmbeddingsNoDisponibleError(
                "El proveedor de embeddings rechazó la clave (401). Revisa EMBEDDING_API_KEY."
            )
        if respuesta.status_code >= 400:
            raise EmbeddingsError(
                f"El proveedor de embeddings respondió {respuesta.status_code}: "
                f"{self._detalle_error(respuesta)}"
            )

        datos = respuesta.json().get("data", [])
        if len(datos) != len(lote):
            raise EmbeddingsError(
                f"El proveedor devolvió {len(datos)} vectores para {len(lote)} textos."
            )

        # El orden no está garantizado por contrato: cada elemento trae su
        # índice dentro del lote y es por ahí que se reordena.
        ordenados = sorted(datos, key=lambda d: d.get("index", 0))
        return [d["embedding"] for d in ordenados]

    @staticmethod
    def _detalle_error(respuesta: httpx.Response) -> str:
        try:
            return respuesta.json().get("error", {}).get("message", respuesta.text[:200])
        except ValueError:
            return respuesta.text[:200]


def serializar(vector: list[float]) -> object:
    """pgvector acepta la lista directamente; SQLite la guarda como JSON."""
    return vector if USA_PGVECTOR else json.dumps(vector)


def deserializar(valor: object) -> list[float]:
    if valor is None:
        return []
    if isinstance(valor, str):
        return json.loads(valor)
    return list(valor)
