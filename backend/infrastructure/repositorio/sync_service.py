"""
Sincronización con el repositorio configurado (componente C7).

RF01: no duplica ni migra información. Registra la referencia del documento y
encola para indexación solo lo que cambió (RD5).

El origen es siempre el que el administrador configuró (HU-05) —OneDrive o
Google Drive—, no una variable de entorno. Este servicio trabaja contra la
interfaz RepositorioDocumentos y no conoce al proveedor.
"""

from sqlalchemy.orm import Session

from backend.domain.services.repositorio_config_service import RepositorioConfigService
from backend.infrastructure.persistence.models.hoja_vida import ESTADO_PENDIENTE
from backend.infrastructure.persistence.repositories.configuracion_repo import (
    RepositorioConfigRepository,
)
from backend.infrastructure.persistence.repositories.hoja_vida_repo import HojaDeVidaRepository


class SincronizacionService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = HojaDeVidaRepository(db)
        self.config_repo = RepositorioConfigRepository(db)
        self.config_service = RepositorioConfigService(db)

    def sincronizar(self) -> dict:
        """
        Detecta cambios en la carpeta configurada y devuelve los ids de hojas de
        vida que deben reindexarse.
        """
        config = self.config_repo.get_activa()
        cliente = self.config_service.cliente_activo()

        cursor_previo = config.cursor_sincronizacion if config else None
        documentos, nuevo_cursor = cliente.listar_documentos(cursor_previo)

        a_indexar: list[str] = []
        for documento in documentos:
            hoja, necesita_reindexar = self.repo.registrar_o_actualizar(
                {
                    "id_documento": documento.id_documento,
                    "nombre_archivo": documento.nombre_archivo,
                    "ruta": documento.ruta,
                    "url_web": documento.url_web,
                    "formato": documento.formato,
                    "hash_contenido": documento.hash_contenido,
                    "fecha_modificacion": documento.fecha_modificacion,
                }
            )

            if documento.formato == "NO_SOPORTADO": # Registrar como no procesados archivos con formato no soportado.
                self.repo.marcar_no_procesable(
                    hoja.id,
                    f"Formato no soportado: {documento.nombre_archivo}",
                )
                continue

            # Además de lo nuevo o modificado, se reintenta lo que quedó PENDIENTE
            # de una corrida anterior (cola caída, proveedor de embeddings sin
            # clave...): si no, un documento sin cambios no se analizaría nunca.
            if necesita_reindexar or hoja.estado_procesamiento == ESTADO_PENDIENTE:
                a_indexar.append(hoja.id)

        # Los orígenes sin delta (Google Drive) devuelven None: se conserva el
        # cursor anterior en lugar de borrarlo.
        if nuevo_cursor:
            self.config_repo.actualizar_cursor(nuevo_cursor)

        return {
            "documentos_detectados": len(documentos),
            "hojas_a_indexar": a_indexar,
        }
