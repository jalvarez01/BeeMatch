"""Exportación de la preselección en PDF o XLSX (HU-25)."""

import io
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from backend.domain.matching.scorer import NIVEL_ALTA, NIVEL_BAJA, NIVEL_MEDIA
from backend.domain.services.resultado_service import ResultadoService
from backend.domain.services.solicitud_service import SolicitudService

MENSAJE_SIN_PRESELECCION = "Debes seleccionar al menos un candidato para exportar."

ETIQUETA_NIVEL = {NIVEL_ALTA: "Alta", NIVEL_MEDIA: "Media", NIVEL_BAJA: "Baja"}
COLUMNAS = ["#", "Candidato", "Rol", "Años", "Afinidad", "Nivel", "Tecnologías", "Hoja de vida"]
# Ancho en milímetros de cada columna del PDF (A4 horizontal: 277 mm útiles).
ANCHOS_PDF = (8, 40, 36, 12, 18, 14, 85, 64)

# Las fuentes base del PDF solo cubren Latin-1; DejaVu muestra cualquier nombre (Łukasz, Ödön…).
FUENTES = Path(__file__).resolve().parents[2] / "assets" / "fonts"
FUENTE_PDF = "DejaVu"

TIPO_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
TIPO_PDF = "application/pdf"


@dataclass
class ArchivoExportado:
    """El archivo se arma en memoria: no queda en el servidor con datos de candidatos."""

    contenido: bytes
    nombre: str
    tipo: str


class ExportService:
    def __init__(self, db: Session):
        self.db = db
        self.resultados = ResultadoService(db)
        self.solicitudes = SolicitudService(db)

    def exportar(self, busqueda_id: str, formato: str = "PDF") -> ArchivoExportado:
        resultado = self.resultados.resultados(busqueda_id)
        if not resultado:
            raise ValueError("La búsqueda no existe.")

        preseleccionados = [r for r in resultado.recomendaciones if r.preseleccionado]
        if not preseleccionados:
            raise ValueError(MENSAJE_SIN_PRESELECCION)

        encabezado = self._encabezado(resultado.solicitud_id)
        filas = [self._fila(r) for r in preseleccionados]

        if formato.upper() == "XLSX":
            contenido = self._exportar_xlsx(encabezado, filas)
            return ArchivoExportado(contenido, f"preseleccion_{busqueda_id}.xlsx", TIPO_XLSX)
        contenido = self._exportar_pdf(encabezado, filas)
        return ArchivoExportado(contenido, f"preseleccion_{busqueda_id}.pdf", TIPO_PDF)

    def _encabezado(self, solicitud_id: str) -> list[tuple[str, str]]:
        """Perfil solicitado, cliente y fecha: lo que el cliente necesita para ubicar el listado."""
        solicitud = self.solicitudes.obtener(solicitud_id)
        perfil = (solicitud.rol_buscado or solicitud.descripcion_libre or "").strip() if solicitud else ""

        requisitos = [c.valor for c in solicitud.criterios] if solicitud else []
        if solicitud and solicitud.experiencia_min:
            requisitos.append(f"{solicitud.experiencia_min}+ años de experiencia")

        return [
            ("Perfil solicitado", perfil or "Sin perfil definido"),
            ("Requisitos", ", ".join(requisitos) or "Sin requisitos adicionales"),
            ("Cliente", (solicitud.cliente_nombre if solicitud else None) or "Sin cliente asignado"),
            ("Proyecto", (solicitud.proyecto_nombre if solicitud else None) or "Sin proyecto asignado"),
            ("Fecha", datetime.now().strftime("%d/%m/%Y")),
        ]

    @staticmethod
    def _fila(r) -> list:
        return [
            r.posicion,
            r.nombre or "Sin nombre",
            r.rol_principal or "",
            r.anios_experiencia if r.anios_experiencia is not None else "",
            f"{r.puntaje_afinidad:g}%",
            ETIQUETA_NIVEL.get(r.nivel, r.nivel),
            ", ".join(r.tecnologias),
            r.ruta_hoja_vida or "",
        ]

    def _exportar_xlsx(self, encabezado, filas) -> bytes:
        from openpyxl import Workbook
        from openpyxl.styles import Font

        libro = Workbook()
        hoja = libro.active
        hoja.title = "Preselección"

        hoja.append(["Preselección de candidatos"])
        hoja["A1"].font = Font(bold=True, size=14)
        for etiqueta, valor in encabezado:
            hoja.append([etiqueta, valor])
            hoja.cell(row=hoja.max_row, column=1).font = Font(bold=True)
        hoja.append([])

        hoja.append(COLUMNAS)
        for celda in hoja[hoja.max_row]:
            celda.font = Font(bold=True)
        for fila in filas:
            hoja.append(fila)

        for letra, ancho in zip("ABCDEFGH", (18, 30, 28, 8, 10, 10, 50, 50), strict=True):
            hoja.column_dimensions[letra].width = ancho

        # Los textos vienen de las hojas de vida y openpyxl guarda como fórmula lo que
        # empieza por "=": en el archivo para el cliente todo queda como texto.
        for fila_celdas in hoja.iter_rows():
            for celda in fila_celdas:
                if celda.data_type == "f":
                    celda.data_type = "s"

        salida = io.BytesIO()
        libro.save(salida)
        return salida.getvalue()

    def _exportar_pdf(self, encabezado, filas) -> bytes:
        from fpdf import FPDF

        pdf = FPDF(orientation="L", format="A4")
        pdf.add_font(FUENTE_PDF, "", str(FUENTES / "DejaVuSans.ttf"))
        pdf.add_font(FUENTE_PDF, "B", str(FUENTES / "DejaVuSans-Bold.ttf"))
        pdf.set_auto_page_break(auto=True, margin=12)
        pdf.add_page()

        pdf.set_font(FUENTE_PDF, "B", 16)
        pdf.cell(0, 10, "Preselección de candidatos", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        for etiqueta, valor in encabezado:
            pdf.set_font(FUENTE_PDF, "B", 10)
            pdf.cell(38, 6, f"{etiqueta}:")
            pdf.set_font(FUENTE_PDF, "", 10)
            pdf.multi_cell(0, 6, valor, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

        pdf.set_font(FUENTE_PDF, "", 8)
        with pdf.table(col_widths=ANCHOS_PDF, text_align="LEFT", line_height=5) as tabla:
            tabla.row(COLUMNAS)
            for fila in filas:
                tabla.row([str(valor) for valor in fila])

        return bytes(pdf.output())
