"""
Sincronización con OneDrive (componente C7).

RF01: no duplica ni migra información. Registra la referencia del documento y
encola para indexación solo lo que cambió (RD5).

El origen es siempre la ruta que el administrador configuró (HU-05), no una
variable de entorno.
"""

from sqlalchemy.orm import Session

from backend.domain.services.onedrive_config_service import OneDriveConfigService
from backend.infrastructure.persistence.repositories.configuracion_repo import (
    OneDriveConfigRepository,
)
from backend.infrastructure.persistence.repositories.hoja_vida_repo import HojaDeVidaRepository


class SincronizacionService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = HojaDeVidaRepository(db)
        self.config_repo = OneDriveConfigRepository(db)
        self.config_service = OneDriveConfigService(db)

    def sincronizar(self) -> dict:
        """
        Detecta cambios en la carpeta configurada y devuelve los ids de hojas de
        vida que deben reindexarse.
        """
        config = self.config_repo.get_activa()
        cliente = self.config_service.cliente_activo()

        documentos, nuevo_delta = cliente.listar_documentos(config.delta_link if config else None)

        a_indexar: list[str] = []
        for documento in documentos:
            hoja, necesita_reindexar = self.repo.registrar_o_actualizar(
                {
                    "id_onedrive": documento.id_onedrive,
                    "nombre_archivo": documento.nombre_archivo,
                    "ruta": documento.ruta,
                    "url_web": documento.url_web,
                    "formato": documento.formato,
                    "hash_contenido": documento.hash_contenido,
                    "fecha_modificacion": documento.fecha_modificacion,
                }
            )
            if necesita_reindexar:
                a_indexar.append(hoja.id)

        if nuevo_delta:
            self.config_repo.actualizar_delta(nuevo_delta)

        return {
            "documentos_detectados": len(documentos),
            "hojas_a_indexar": a_indexar,
        }
