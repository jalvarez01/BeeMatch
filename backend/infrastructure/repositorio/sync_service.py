"""
Sincronización con el repositorio configurado (componente C7).

RF01: no duplica ni migra información. Registra la referencia del documento y
encola para indexación solo lo que cambió (RD5). Lo que desapareció del origen
se da de baja, para que no siga saliendo en las búsquedas (HU-16).

El origen es siempre el que el administrador configuró (HU-05) —OneDrive o
Google Drive—, no una variable de entorno. Este servicio trabaja contra la
interfaz RepositorioDocumentos y no conoce al proveedor.
"""

import logging

from sqlalchemy.orm import Session

from backend.domain.services.repositorio_config_service import RepositorioConfigService
from backend.infrastructure.persistence.models.hoja_vida import ESTADO_PENDIENTE
from backend.infrastructure.persistence.repositories.configuracion_repo import (
    RepositorioConfigRepository,
)
from backend.infrastructure.persistence.repositories.hoja_vida_repo import HojaDeVidaRepository

logger = logging.getLogger(__name__)


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
        presentes: set[str] = set()
        for documento in documentos:
            presentes.add(documento.id_documento)
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

        eliminadas = self._dar_de_baja_ausentes(presentes, cursor_previo, len(documentos))

        # Los orígenes sin delta (Google Drive) devuelven None: se conserva el
        # cursor anterior en lugar de borrarlo.
        if nuevo_cursor:
            self.config_repo.actualizar_cursor(nuevo_cursor)

        return {
            "documentos_detectados": len(documentos),
            "hojas_a_indexar": a_indexar,
            "hojas_eliminadas": eliminadas,
        }

    def _dar_de_baja_ausentes(
        self, presentes: set[str], cursor_previo: str | None, total_listado: int
    ) -> int:
        """
        Olvida las hojas de vida cuyo documento ya no está en el origen (HU-16).

        Si Bee retira una hoja de vida de la carpeta, normalmente es porque la
        persona pidió no ser considerada o porque el dato caducó: seguir
        recomendándola sería lo contrario de lo pedido. Se borra la referencia y
        todo lo derivado —fragmentos, candidato y habilidades—, que es lo mismo
        que hace el derecho de supresión (RNF16).

        Dos salvaguardas, porque un borrado no se deshace:

        1. Solo con listado completo. Si se pidió un listado incremental —hay
           cursor previo, como el delta link de OneDrive—, lo que no vino no es
           lo que se borró, es lo que no cambió.
        2. Nunca con listado vacío. Que el origen no devuelva nada se parece
           mucho más a una carpeta mal configurada o a una falla del proveedor
           que a que hayan borrado todas las hojas de vida a la vez.
        """
        if cursor_previo is not None or total_listado == 0:
            return 0

        ausentes = self.repo.listar_ausentes(presentes)
        for hoja in ausentes:
            logger.info(
                "La hoja de vida %s ya no está en el origen: se da de baja.", hoja.nombre_archivo
            )
            self.repo.eliminar_indice(hoja.id)
            self.repo.eliminar(hoja.id)
        return len(ausentes)
