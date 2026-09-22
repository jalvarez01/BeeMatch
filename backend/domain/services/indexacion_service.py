"""
Indexación de hojas de vida (componentes C8 + C9).

Se ejecuta una sola vez por versión de documento (RNF03). El worker de ingesta
llama a `indexar_hoja` por cada documento encolado.
"""

import logging

from sqlalchemy.orm import Session

from backend.infrastructure.llm.embeddings import ProveedorEmbeddings, serializar
from backend.infrastructure.loaders.chunker import dividir_en_fragmentos
from backend.infrastructure.loaders.errores import ExtraccionError
from backend.infrastructure.loaders.extractor import extraer_texto
from backend.domain.services.repositorio_config_service import RepositorioConfigService
from backend.infrastructure.persistence.models.hoja_vida import ESTADO_INDEXADA
from backend.infrastructure.repositorio.base import RepositorioError
from backend.infrastructure.persistence.repositories.candidato_repo import CandidatoRepository
from backend.infrastructure.persistence.repositories.hoja_vida_repo import HojaDeVidaRepository

logger = logging.getLogger(__name__)


class IndexacionService:
    def __init__(self, db: Session):
        self.db = db
        self.hojas = HojaDeVidaRepository(db)
        self.candidatos = CandidatoRepository(db)
        self.embeddings = ProveedorEmbeddings()
        # Cliente del origen registrado por el administrador (HU-05): OneDrive
        # o Google Drive, indistinto para esta clase.
        self.repositorio = RepositorioConfigService(db).cliente_activo()

    def indexar_hoja(self, hoja_id: str) -> bool:
        """
        Descarga, extrae, fragmenta e indexa. Retorna True si quedó indexada.
        RNF19: un documento que falla se marca y no interrumpe la corrida.
        """
        hoja = self.hojas.get_by_id(hoja_id)
        if not hoja:
            return False
        if hoja.estado_procesamiento == ESTADO_INDEXADA:
            # Un cambio en el documento la devuelve a PENDIENTE, así que si
            # llega aquí ya indexada es un trabajo repetido en la cola.
            return True

        try:
            contenido = self.repositorio.descargar(hoja.id_documento)
        except RepositorioError as exc:
            self.hojas.marcar_no_procesable(hoja_id, f"No se pudo descargar: {exc}")
            return False

        # HU-17: el formato real sale del contenido (PDF, .docx o .doc), no de
        # la extensión. Un documento dañado o con contraseña se marca y la
        # corrida sigue con el siguiente.
        try:
            texto = extraer_texto(contenido)
        except ExtraccionError as exc:
            self.hojas.marcar_no_procesable(hoja_id, str(exc))
            return False
        except Exception as exc:  # noqa: BLE001
            # Un fallo inesperado al leer un documento lo marca a él; no debe
            # tumbar la sincronización ni dejarlo PENDIENTE para siempre.
            logger.exception("Error inesperado extrayendo el texto de %s", hoja.nombre_archivo)
            self.hojas.marcar_no_procesable(hoja_id, f"Error inesperado al leer el documento: {exc}")
            return False

        fragmentos = dividir_en_fragmentos(texto)
        if not fragmentos:
            self.hojas.marcar_no_procesable(hoja_id, "El documento no produjo fragmentos de texto.")
            return False

        vectores = self.embeddings.generar([f["texto"] for f in fragmentos])
        for fragmento, vector in zip(fragmentos, vectores):
            fragmento["embedding"] = serializar(vector)

        self.candidatos.reemplazar_fragmentos(hoja_id, fragmentos)
        self.candidatos.crear_o_reemplazar(hoja_id, self._perfil_desde_texto(texto, hoja.nombre_archivo))
        self.hojas.marcar_indexada(hoja_id)
        return True

    @staticmethod
    def _perfil_desde_texto(texto: str, nombre_archivo: str) -> dict:
        """
        Extrae el perfil estructurado del CV.

        TODO(Sprint 2): reemplazar la heurística por extracción con el LLM
        (RF02). Por ahora el nombre sale del archivo, que es como está
        organizado el repositorio de Bee.
        """
        nombre = nombre_archivo.rsplit(".", 1)[0].replace("_", " ").strip()
        return {
            "nombre": nombre or "Sin nombre",
            "rol_principal": None,
            "anios_experiencia": None,
            "resumen": texto[:500],
        }
