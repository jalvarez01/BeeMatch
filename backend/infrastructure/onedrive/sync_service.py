"""
Sincronización con OneDrive (componente C7).

RF01: no duplica ni migra información. Solo registra la referencia del documento
y encola para indexación lo que cambió (RD5).
"""

from sqlalchemy.orm import Session

from backend.infrastructure.onedrive.graph_client import GraphClient, OneDriveError
from backend.infrastructure.persistence.repositories.configuracion_repo import ParametroRepository
from backend.infrastructure.persistence.repositories.hoja_vida_repo import HojaDeVidaRepository

CLAVE_DELTA = "onedrive_delta_link"


class SincronizacionService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = HojaDeVidaRepository(db)
        self.parametros = ParametroRepository(db)
        self.cliente = GraphClient()

    def sincronizar(self) -> dict:
        """Detecta cambios y devuelve los ids de hojas de vida a reindexar."""
        parametro = self.parametros.get(CLAVE_DELTA)
        delta_previo = parametro.valor if parametro else None

        documentos, nuevo_delta = self.cliente.listar_documentos(delta_previo)

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
            self.parametros.establecer(CLAVE_DELTA, nuevo_delta)

        return {
            "documentos_detectados": len(documentos),
            "hojas_a_indexar": a_indexar,
        }
