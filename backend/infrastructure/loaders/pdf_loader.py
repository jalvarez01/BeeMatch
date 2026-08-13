"""Extracción de texto de PDF. OCR de respaldo para escaneados (RNF19)."""

import io


class ExtraccionError(Exception):
    """El documento no pudo procesarse. El motivo se registra, no se aborta todo."""


def extraer_texto_pdf(contenido: bytes) -> tuple[str, list[int]]:
    """
    Retorna (texto, paginas) donde paginas[i] es el número de página del bloque i.
    Si el PDF no tiene texto seleccionable, intenta OCR.
    """
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise ExtraccionError(f"pypdf no disponible: {exc}")

    try:
        lector = PdfReader(io.BytesIO(contenido))
    except Exception as exc:
        raise ExtraccionError(f"PDF ilegible o protegido: {exc}")

    bloques: list[str] = []
    paginas: list[int] = []
    for numero, pagina in enumerate(lector.pages, start=1):
        texto = (pagina.extract_text() or "").strip()
        if texto:
            bloques.append(texto)
            paginas.append(numero)

    if not bloques:
        texto_ocr = _ocr(contenido)
        if not texto_ocr:
            raise ExtraccionError("PDF sin texto seleccionable y OCR sin resultado.")
        return texto_ocr, [1]

    return "\n\n".join(bloques), paginas


def _ocr(contenido: bytes) -> str:
    """Respaldo OCR. Se usa solo cuando la extracción directa no devuelve nada."""
    try:
        import pytesseract
        from pdf2image import convert_from_bytes
    except ImportError:
        return ""

    try:
        imagenes = convert_from_bytes(contenido, dpi=200)
        return "\n\n".join(pytesseract.image_to_string(img, lang="spa") for img in imagenes).strip()
    except Exception:
        return ""
