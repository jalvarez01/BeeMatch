"""
Configuración de la conexión con OneDrive (HU-05).

Reglas que impone este servicio:

- El client secret se cifra antes de guardarse y nunca sale en claro por la API.
- Una configuración solo se guarda si la conexión fue validada primero; si las
  credenciales son inválidas, la configuración anterior queda intacta.
- La ruta registrada aquí es el origen que usan la sincronización y todas las
  búsquedas posteriores.
"""

from typing import Optional

from sqlalchemy.orm import Session

from backend.infrastructure.crypto import CifradoError, cifrar, descifrar, enmascarar
from backend.infrastructure.onedrive.graph_client import GraphClient, ResultadoPrueba
from backend.infrastructure.persistence.repositories.configuracion_repo import (
    OneDriveConfigRepository,
)


class OneDriveNoConfiguradoError(Exception):
    """Todavía no hay una conexión registrada. La búsqueda no puede ejecutarse."""


class OneDriveConfigService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = OneDriveConfigRepository(db)

    # --- Lectura -------------------------------------------------------------

    def obtener(self) -> Optional[dict]:
        """Configuración actual con el secreto enmascarado, apta para la interfaz."""
        config = self.repo.get_activa()
        if not config:
            return None

        try:
            secreto = descifrar(config.client_secret_cifrado)
            secreto_enmascarado = enmascarar(secreto)
            secreto_legible = True
        except CifradoError:
            secreto_enmascarado = ""
            secreto_legible = False

        return {
            "configurado": True,
            "tenant_id": config.tenant_id,
            "client_id": config.client_id,
            "client_secret_enmascarado": secreto_enmascarado,
            "secreto_legible": secreto_legible,
            "drive_id": config.drive_id,
            "carpeta_cv": config.carpeta_cv,
            "ultima_validacion": config.ultima_validacion,
            "documentos_detectados": config.documentos_detectados,
        }

    def cliente_activo(self) -> GraphClient:
        """
        Cliente de Graph construido con la configuración guardada.
        Lo usan la sincronización y la indexación.
        """
        config = self.repo.get_activa()
        if not config:
            raise OneDriveNoConfiguradoError(
                "No hay una conexión a OneDrive configurada. "
                "El administrador debe registrarla en Configuración."
            )
        return GraphClient.desde_configuracion(config, descifrar(config.client_secret_cifrado))

    # --- Prueba y guardado ---------------------------------------------------

    def probar(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: Optional[str],
        drive_id: str,
        carpeta_cv: str,
    ) -> ResultadoPrueba:
        """
        Valida una configuración sin guardarla.

        Si el secreto viene vacío se reutiliza el ya almacenado: así el
        administrador puede corregir solo la ruta sin volver a escribir la
        credencial completa.
        """
        secreto = client_secret or self._secreto_guardado()
        if not secreto:
            return ResultadoPrueba(
                exito=False,
                mensaje="Falta el Client Secret.",
                detalle="No hay una credencial almacenada que reutilizar.",
            )

        cliente = GraphClient(tenant_id, client_id, secreto, drive_id, carpeta_cv)
        return cliente.probar_conexion()

    def guardar(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: Optional[str],
        drive_id: str,
        carpeta_cv: str,
        usuario_id: Optional[str] = None,
    ) -> tuple[bool, ResultadoPrueba]:
        """
        Valida y, solo si la validación pasa, persiste la configuración.

        Retorna (guardado, resultado). Cuando `guardado` es False la
        configuración anterior no fue modificada.
        """
        resultado = self.probar(tenant_id, client_id, client_secret, drive_id, carpeta_cv)
        if not resultado.exito:
            return False, resultado

        secreto = client_secret or self._secreto_guardado()
        self.repo.guardar(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret_cifrado=cifrar(secreto),
            drive_id=drive_id,
            carpeta_cv=carpeta_cv,
            usuario_id=usuario_id,
            documentos_detectados=resultado.documentos_detectados,
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

    def _secreto_guardado(self) -> Optional[str]:
        config = self.repo.get_activa()
        if not config:
            return None
        try:
            return descifrar(config.client_secret_cifrado)
        except CifradoError:
            return None
