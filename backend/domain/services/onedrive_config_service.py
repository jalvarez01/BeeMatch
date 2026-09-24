"""
Fachada de OneDrive sobre la configuración genérica de repositorio (HU-05).

La lógica vive ahora en RepositorioConfigService, que administra cualquier
origen. Este módulo conserva la firma que ya consumen la API y el frontend
—campos sueltos de Entra ID en lugar de un diccionario de credenciales— para
que el flujo de OneDrive siga comportándose exactamente igual.
"""

from typing import Optional

from sqlalchemy.orm import Session

from backend.domain.services.repositorio_config_service import (
    RepositorioConfigService,
    RepositorioNoConfiguradoError,
)
from backend.infrastructure.repositorio.base import TIPO_ONEDRIVE, ResultadoPrueba

# El nombre anterior del error: lo capturan las capas superiores.
OneDriveNoConfiguradoError = RepositorioNoConfiguradoError


class OneDriveConfigService:
    def __init__(self, db: Session):
        self.db = db
        self.servicio = RepositorioConfigService(db)

    # --- Lectura -------------------------------------------------------------

    def obtener(self) -> Optional[dict]:
        """
        Configuración de OneDrive con el secreto enmascarado.

        Devuelve None si no hay nada configurado o si el origen activo es otro
        proveedor: desde la pantalla de OneDrive, eso es "sin configurar".
        """
        config = self.servicio.obtener()
        if not config or config["tipo"] != TIPO_ONEDRIVE:
            return None

        credenciales = config["credenciales"]
        return {
            "configurado": True,
            "tenant_id": credenciales.get("tenant_id"),
            "client_id": credenciales.get("client_id"),
            "client_secret_enmascarado": credenciales.get("client_secret", ""),
            "secreto_legible": config["secreto_legible"],
            "drive_id": credenciales.get("drive_id"),
            "carpeta_cv": config["carpeta"],
            "ultima_validacion": config["ultima_validacion"],
            "documentos_detectados": config["documentos_detectados"],
        }

    def cliente_activo(self):
        """Cliente del origen activo, sea OneDrive u otro proveedor."""
        return self.servicio.cliente_activo()

    # --- Prueba y guardado ---------------------------------------------------

    def probar(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: Optional[str],
        drive_id: str,
        carpeta_cv: str,
    ) -> ResultadoPrueba:
        """Valida una configuración de OneDrive sin guardarla."""
        return self.servicio.probar(
            TIPO_ONEDRIVE, carpeta_cv, self._credenciales(tenant_id, client_id, client_secret, drive_id)
        )

    def guardar(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: Optional[str],
        drive_id: str,
        carpeta_cv: str,
        usuario_id: Optional[str] = None,
    ) -> tuple[bool, ResultadoPrueba]:
        """Valida y, solo si la validación pasa, persiste la configuración."""
        return self.servicio.guardar(
            TIPO_ONEDRIVE,
            carpeta_cv,
            self._credenciales(tenant_id, client_id, client_secret, drive_id),
            usuario_id=usuario_id,
        )

    def probar_configuracion_guardada(self) -> ResultadoPrueba:
        return self.servicio.probar_configuracion_guardada()

    # --- Internos ------------------------------------------------------------

    @staticmethod
    def _credenciales(
        tenant_id: str, client_id: str, client_secret: Optional[str], drive_id: str
    ) -> dict:
        return {
            "tenant_id": tenant_id,
            "client_id": client_id,
            "client_secret": client_secret or "",
            "drive_id": drive_id,
        }
