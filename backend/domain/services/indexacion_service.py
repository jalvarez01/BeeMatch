"""
Indexación de hojas de vida (componentes C8 + C9).

Se ejecuta una sola vez por versión de documento (RNF03). El worker de ingesta
llama a `indexar_hoja` por cada documento encolado.
"""

from sqlalchemy.orm import Session

from backend.infrastructure.llm.embeddings import ProveedorEmbeddings, serializar
from backend.infrastructure.loaders.chunker import dividir_en_fragmentos
from backend.infrastructure.loaders.docx_loader import extraer_texto_docx
from backend.infrastructure.loaders.pdf_loader import ExtraccionError, extraer_texto_pdf
from backend.domain.services.onedrive_config_service import OneDriveConfigService
from backend.infrastructure.onedrive.graph_client import OneDriveError
from backend.infrastructure.persistence.repositories.candidato_repo import CandidatoRepository
from backend.infrastructure.persistence.repositories.hoja_vida_repo import HojaDeVidaRepository


class IndexacionService:
    def __init__(self, db: Session):
        self.db = db
        self.hojas = HojaDeVidaRepository(db)
        self.candidatos = CandidatoRepository(db)
        self.embeddings = ProveedorEmbeddings()
        # Cliente construido con la configuración registrada por el administrador (HU-05).
        self.onedrive = OneDriveConfigService(db).cliente_activo()

    def indexar_hoja(self, hoja_id: str) -> bool:
        """
        Descarga, extrae, fragmenta e indexa. Retorna True si quedó indexada.
        RNF19: un documento que falla se marca y no interrumpe la corrida.
        """
        hoja = self.hojas.get_by_id(hoja_id)
        if not hoja:
            return False

        try:
            contenido = self.onedrive.descargar(hoja.id_onedrive)
        except OneDriveError as exc:
            self.hojas.marcar_no_procesable(hoja_id, f"No se pudo descargar: {exc}")
            return False

        try:
            if hoja.formato == "PDF":
                texto, _ = extraer_texto_pdf(contenido)
            else:
                texto = extraer_texto_docx(contenido)
        except ExtraccionError as exc:
            self.hojas.marcar_no_procesable(hoja_id, str(exc))
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
