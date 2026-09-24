"""
Adaptador del servicio de IA (componente C11 de la arquitectura).

Concentra en un solo punto: construcción de prompts, control de tokens,
reintentos con backoff, validación del JSON de salida y registro de consumo.
Cambiar de modelo o de proveedor es configuración, no refactorización (RNF33).

El proveedor utiliza la API oficial de OpenAI. El SDK ya reintenta los
errores transitorios (429 y 5xx); el bucle de `completar_json` cubre además
el caso de que el modelo devuelva un JSON que no parsea.
"""

import json
import time
from dataclasses import dataclass, field
from typing import Any

from backend.config import LLM_API_KEY, LLM_MODELO

# Techo de salida por respuesta. El re-ranking devuelve un JSON con los
# finalistas y su explicación, no un texto largo.
MAX_TOKENS = 16000


class ServicioIAError(Exception):
    """Fallo al consultar el servicio de IA. El worker reintenta (RNF18)."""


class ServicioIANoConfiguradoError(ServicioIAError):
    """Falta LLM_API_KEY. Se distingue para poder explicarlo en la interfaz."""


class ServicioIARechazoError(ServicioIAError):
    """El modelo declinó la solicitud. Reintentar daría el mismo resultado."""


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
        self._cliente = None

    @property
    def cliente(self):
        """Cliente perezoso: crearlo no debe exigir la clave hasta que se use."""
        if self._cliente is None:
            if not self.api_key:
                raise ServicioIANoConfiguradoError(
                    "Falta configurar LLM_API_KEY, la clave del servicio de IA."
                )
            try:
                from openai import OpenAI
            except ImportError as exc:  # pragma: no cover
                raise ServicioIAError(
                    "Falta la dependencia openai. Instálala con: pip install openai"
                ) from exc

            self._cliente = OpenAI(api_key=self.api_key)
        return self._cliente

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
            except (ServicioIANoConfiguradoError, ServicioIARechazoError):
                # Ninguno de los dos se arregla reintentando.
                raise
            except Exception as exc:
                ultimo_error = exc
                if intento < max_reintentos - 1:
                    time.sleep(2**intento)

        raise ServicioIAError(f"El servicio de IA no respondió tras {max_reintentos} intentos: {ultimo_error}")

    def _llamar(self, system: str, prompt: str) -> tuple[str, int, int]:
        """Una llamada al modelo. Retorna (texto, tokens_entrada, tokens_salida)."""
        # `cliente` valida la clave y la presencia del SDK, así que a partir
        # de aquí se puede importar el tipo de error sin miedo.
        cliente = self.cliente
        from openai import AuthenticationError

        try:
            respuesta = cliente.chat.completions.create(
                model=self.modelo,
                # RNF33: cambiar de modelo es configuración. `max_tokens` quedó
                # deprecado y los modelos de razonamiento lo rechazan con 400;
                # `max_completion_tokens` lo aceptan todos.
                max_completion_tokens=MAX_TOKENS,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            )
        except AuthenticationError as exc:
            # La clave es inválida o no tiene acceso al modelo: reintentar no
            # cambia nada y la interfaz lo explica como configuración faltante.
            raise ServicioIANoConfiguradoError(
                f"El servicio de IA rechazó la credencial: {exc}"
            ) from exc

        choice = respuesta.choices[0]
        if getattr(choice, "finish_reason", None) == "content_filter":
            raise ServicioIARechazoError("El modelo declinó procesar la solicitud por filtros de contenido.")

        texto = choice.message.content
        if not texto:
            raise ServicioIAError("El modelo no devolvió contenido de texto.")

        usage = respuesta.usage
        return texto, usage.prompt_tokens, usage.completion_tokens

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
