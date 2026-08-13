"""Extracción de texto de documentos Word."""

import io

from backend.infrastructure.loaders.pdf_loader import ExtraccionError


def extraer_texto_docx(contenido: bytes) -> str:
    try:
        from docx import Document
    except ImportError as exc:  # pragma: no cover
        raise ExtraccionError(f"python-docx no disponible: {exc}")

    try:
        documento = Document(io.BytesIO(contenido))
    except Exception as exc:
        raise ExtraccionError(f"DOCX ilegible: {exc}")

    partes = [p.text.strip() for p in documento.paragraphs if p.text.strip()]

    # Muchas hojas de vida ponen la experiencia dentro de tablas.
    for tabla in documento.tables:
        for fila in tabla.rows:
            celdas = [c.text.strip() for c in fila.cells if c.text.strip()]
            if celdas:
                partes.append(" | ".join(celdas))

    texto = "\n".join(partes).strip()
    if not texto:
        raise ExtraccionError("El documento no contiene texto.")
    return texto
