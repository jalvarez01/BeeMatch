"""
Adaptador del servicio de IA (componente C11 de la arquitectura).

Concentra en un solo punto: construcción de prompts, control de tokens,
reintentos con backoff, validación del JSON de salida y registro de consumo.
Cambiar de modelo o de proveedor es configuración, no refactorización (RNF33).
"""

import json
import time
from dataclasses import dataclass, field
from typing import Any

from backend.config import LLM_API_KEY, LLM_MODELO


class ServicioIAError(Exception):
    """Fallo al consultar el servicio de IA. El worker reintenta (RNF18)."""


@dataclass
class RespuestaIA:
    datos: dict[str, Any] = field(default_factory=dict)
    tokens_entrada: int = 0
    tokens_salida: int = 0
    modelo: str = LLM_MODELO


class ProveedorLLM:
    def __init__(self, modelo: str = LLM_MODELO, api_key: str = LLM_API_KEY):
        self.modelo = modelo
        self.api_key = api_key

    def completar_json(
        self,
        system: str,
        prompt: str,
        max_reintentos: int = 3,
    ) -> RespuestaIA:
        """
        Llama al modelo y devuelve JSON validado. Reintenta con backoff
        exponencial ante fallos transitorios.
        """
        ultimo_error: Exception | None = None

        for intento in range(max_reintentos):
            try:
                bruto, entrada, salida = self._llamar(system, prompt)
                return RespuestaIA(
                    datos=self._parsear(bruto),
                    tokens_entrada=entrada,
                    tokens_salida=salida,
                    modelo=self.modelo,
                )
            except Exception as exc:
                ultimo_error = exc
                if intento < max_reintentos - 1:
                    time.sleep(2**intento)

        raise ServicioIAError(f"El servicio de IA no respondió tras {max_reintentos} intentos: {ultimo_error}")

    def _llamar(self, system: str, prompt: str) -> tuple[str, int, int]:
        """
        TODO(Sprint 1): implementar la llamada HTTP real al proveedor.
        Debe retornar (texto_respuesta, tokens_entrada, tokens_salida).
        """
        raise NotImplementedError("Conectar el proveedor de LLM en el Sprint 1.")

    @staticmethod
    def _parsear(bruto: str) -> dict[str, Any]:
        """Limpia posibles marcas de código y valida que sea JSON (RNF28)."""
        texto = bruto.strip()
        if texto.startswith("```"):
            texto = texto.split("```")[1]
            if texto.startswith("json"):
                texto = texto[4:]
        try:
            return json.loads(texto.strip())
        except json.JSONDecodeError as exc:
            raise ServicioIAError(f"El modelo devolvió un JSON inválido: {exc}")
