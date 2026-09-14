"""
Configuración del origen de hojas de vida (HU-05).

Antes este servicio era exclusivo de OneDrive. Ahora administra cualquier
origen que implemente RepositorioDocumentos; lo específico del proveedor viaja
en un diccionario de credenciales que solo interpreta su cliente.

Reglas que impone este servicio, iguales para todos los orígenes:

- Las credenciales se cifran antes de guardarse y nunca salen en claro por la API.
- Una configuración solo se guarda si la conexión fue validada primero; si las
  credenciales son inválidas, la configuración anterior queda intacta.
- La ruta registrada aquí es el origen que usan la sincronización y todas las
  búsquedas posteriores.
"""

import json
from typing import Optional

from sqlalchemy.orm import Session

from backend.infrastructure.crypto import CifradoError, cifrar, descifrar, enmascarar
from backend.infrastructure.repositorio.base import (
    TIPOS_VALIDOS,
    RepositorioDocumentos,
    ResultadoPrueba,
)
from backend.infrastructure.repositorio.factory import campos_secretos, crear_cliente
from backend.infrastructure.persistence.repositories.configuracion_repo import (
    RepositorioConfigRepository,
)

# Secretos que son un documento completo, no una cadena corta: se enmascaran
# enteros, porque mostrar su cola no ayuda a reconocerlos y sí filtra contenido.
# No se usa enmascarar(visibles=0) para esto: con 0 visibles devolvería el
# secreto íntegro.
SECRETOS_OPACOS = ("credenciales_json",)
MASCARA_COMPLETA = "•" * 12

# Nombre con el que cada secreto aparece en pantalla cuando falta.
ETIQUETA_SECRETO = {
    "client_secret": "el Client Secret",
    "credenciales_json": "el JSON de la cuenta de servicio",
}


class RepositorioNoConfiguradoError(Exception):
    """Todavía no hay una conexión registrada. La búsqueda no puede ejecutarse."""


class RepositorioConfigService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = RepositorioConfigRepository(db)

    # --- Lectura -------------------------------------------------------------

    def obtener(self) -> Optional[dict]:
        """Configuración actual con los secretos enmascarados, apta para la interfaz."""
        config = self.repo.get_activa()
        if not config:
            return None

        try:
            credenciales = self._descifrar(config.credenciales_cifradas)
            secreto_legible = True
        except CifradoError:
            credenciales = {}
            secreto_legible = False

        return {
            "configurado": True,
            "tipo": config.tipo,
            "carpeta": config.carpeta,
            "credenciales": self._enmascarar(config.tipo, credenciales),
            "secreto_legible": secreto_legible,
            "ultima_validacion": config.ultima_validacion,
            "documentos_detectados": config.documentos_detectados,
        }

    def cliente_activo(self) -> RepositorioDocumentos:
        """
        Cliente del origen guardado. Lo usan la sincronización y la indexación,
        que no saben —ni necesitan saber— de qué proveedor se trata.
        """
        config = self.repo.get_activa()
        if not config:
            raise RepositorioNoConfiguradoError(
                "No hay una conexión al repositorio de hojas de vida configurada. "
                "El administrador debe registrarla en Configuración."
            )
        credenciales = self._descifrar(config.credenciales_cifradas)
        return crear_cliente(config.tipo, config.carpeta, credenciales)

    def credenciales_guardadas(self, tipo: Optional[str] = None) -> dict:
        """
        Credenciales descifradas de la configuración activa.

        Si se indica `tipo`, solo devuelve las del proveedor pedido: los
        secretos de OneDrive no se reutilizan al registrar Google Drive.
        """
        config = self.repo.get_activa()
        if not config or (tipo and config.tipo != tipo):
            return {}
        try:
            return self._descifrar(config.credenciales_cifradas)
        except CifradoError:
            return {}

    # --- Prueba y guardado ---------------------------------------------------

    def probar(self, tipo: str, carpeta: str, credenciales: dict) -> ResultadoPrueba:
        """
        Valida una configuración sin guardarla.

        Los secretos que lleguen vacíos se reemplazan por los ya almacenados
        del mismo proveedor: así el administrador puede corregir solo la
        carpeta sin volver a escribir la credencial completa.
        """
        if tipo not in TIPOS_VALIDOS:
            return ResultadoPrueba(
                exito=False,
                mensaje="Tipo de repositorio no soportado.",
                detalle=f"'{tipo}' no es un origen válido. Usa {' o '.join(TIPOS_VALIDOS)}.",
            )

        completas, faltante = self._completar_secretos(tipo, credenciales)
        if faltante:
            return ResultadoPrueba(
                exito=False,
                mensaje=f"Falta {ETIQUETA_SECRETO.get(faltante, faltante)}.",
                detalle="No hay una credencial almacenada que reutilizar.",
            )

        return crear_cliente(tipo, carpeta, completas).probar_conexion()

    def guardar(
        self,
        tipo: str,
        carpeta: str,
        credenciales: dict,
        usuario_id: Optional[str] = None,
    ) -> tuple[bool, ResultadoPrueba]:
        """
        Valida y, solo si la validación pasa, persiste la configuración.

        Retorna (guardado, resultado). Cuando `guardado` es False la
        configuración anterior no fue modificada.
        """
        resultado = self.probar(tipo, carpeta, credenciales)
        if not resultado.exito:
            return False, resultado

        completas, _ = self._completar_secretos(tipo, credenciales)

        self.repo.guardar(
            tipo=tipo,
            carpeta=carpeta,
            credenciales_cifradas=cifrar(json.dumps(completas)),
            usuario_id=usuario_id,
            documentos_detectados=resultado.documentos_detectados,
            reiniciar_cursor=self._cambio_de_origen(tipo, completas),
        )
        return True, resultado

    def probar_configuracion_guardada(self) -> ResultadoPrueba:
        """Revalida la conexión que ya está en uso y actualiza el conteo."""
        config = self.repo.get_activa()
        if not config:
            return ResultadoPrueba(
                exito=False,
                mensaje="No hay conexión configurada.",
                detalle="Registra las credenciales antes de probar la conexión.",
            )

        resultado = self.cliente_activo().probar_conexion()
        if resultado.exito:
            self.repo.registrar_validacion(resultado.documentos_detectados)
        return resultado

    # --- Internos ------------------------------------------------------------

    @staticmethod
    def _descifrar(cifrado: str) -> dict:
        datos = json.loads(descifrar(cifrado))
        return datos if isinstance(datos, dict) else {}

    @staticmethod
    def _enmascarar(tipo: str, credenciales: dict) -> dict:
        """Los secretos se sustituyen por su versión enmascarada (RNF10)."""
        secretos = campos_secretos(tipo)

        def valor_visible(clave: str, valor: str) -> str:
            if clave not in secretos:
                return valor
            if clave in SECRETOS_OPACOS:
                return MASCARA_COMPLETA if valor else ""
            return enmascarar(valor)

        return {clave: valor_visible(clave, valor) for clave, valor in credenciales.items()}

    def _completar_secretos(self, tipo: str, credenciales: dict) -> tuple[dict, Optional[str]]:
        """
        Rellena los secretos vacíos con los guardados. Devuelve el nombre del
        primero que quedó sin valor, o None si están todos.
        """
        completas = dict(credenciales)
        guardadas = self.credenciales_guardadas(tipo)

        for campo in campos_secretos(tipo):
            if not completas.get(campo):
                completas[campo] = guardadas.get(campo, "")
            if not completas[campo]:
                return completas, campo

        return completas, None

    def _cambio_de_origen(self, tipo: str, credenciales: dict) -> bool:
        """
        True si el cursor de sincronización dejó de ser válido.

        La carpeta y el tipo los compara el repositorio; aquí se cubre lo que
        vive dentro de las credenciales, como el drive de OneDrive.
        """
        anteriores = self.credenciales_guardadas(tipo)
        if not anteriores:
            return False
        return anteriores.get("drive_id") != credenciales.get("drive_id")
