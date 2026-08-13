"""Exportación de la preselección en PDF o XLSX (HU-25)."""

from pathlib import Path

from sqlalchemy.orm import Session

from backend.config import STORAGE_DIR
from backend.domain.services.resultado_service import ResultadoService


class ExportService:
    def __init__(self, db: Session):
        self.db = db
        self.resultados = ResultadoService(db)

    def exportar(self, busqueda_id: str, formato: str = "PDF") -> Path:
        resultado = self.resultados.resultados(busqueda_id)
        if not resultado:
            raise ValueError("La búsqueda no existe.")

        preseleccionados = [r for r in resultado.recomendaciones if r.preseleccionado]
        if not preseleccionados:
            raise ValueError("No hay candidatos preseleccionados para exportar.")

        if formato.upper() == "XLSX":
            return self._exportar_xlsx(busqueda_id, preseleccionados)
        return self._exportar_pdf(busqueda_id, preseleccionados)

    def _exportar_xlsx(self, busqueda_id: str, recomendaciones) -> Path:
        from openpyxl import Workbook

        libro = Workbook()
        hoja = libro.active
        hoja.title = "Preselección"
        hoja.append(["#", "Candidato", "Rol", "Años", "Afinidad", "Tecnologías", "Hoja de vida"])

        for r in recomendaciones:
            hoja.append(
                [
                    r.posicion,
                    r.nombre,
                    r.rol_principal,
                    r.anios_experiencia,
                    f"{r.puntaje_afinidad}%",
                    ", ".join(r.tecnologias),
                    r.ruta_hoja_vida,
                ]
            )

        destino = STORAGE_DIR / f"preseleccion_{busqueda_id}.xlsx"
        libro.save(destino)
        return destino

    def _exportar_pdf(self, busqueda_id: str, recomendaciones) -> Path:
        """
        TODO(Sprint 3): render con WeasyPrint a partir de una plantilla HTML.
        Debe incluir el desglose de coincidencias, no solo el puntaje.
        """
        raise NotImplementedError("Exportación a PDF pendiente del Sprint 3.")
