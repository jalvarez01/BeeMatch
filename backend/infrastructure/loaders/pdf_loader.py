"""Extracción de texto de PDF. OCR de respaldo para escaneados (RNF19)."""

import io

from backend.infrastructure.loaders.errores import (
    DocumentoDanadoError,
    DocumentoProtegidoError,
    DocumentoSinTextoError,
    ExtraccionError,  # noqa: F401  (se sigue exponiendo desde este módulo)
)


def extraer_texto_pdf(contenido: bytes) -> tuple[str, list[int]]:
    """
    Retorna (texto, paginas) donde paginas[i] es el número de página del bloque i.
    Si el PDF no tiene texto seleccionable, intenta OCR.

    HU-17: un PDF con contraseña o dañado lanza un ExtraccionError específico;
    nunca deja escapar una excepción de la librería.
    """
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise DocumentoDanadoError(f"pypdf no disponible: {exc}")

    try:
        lector = PdfReader(io.BytesIO(contenido))
    except Exception as exc:
        raise DocumentoDanadoError(f"PDF dañado o ilegible: {exc}")

    if lector.is_encrypted:
        # Muchos PDF están "cifrados" con clave de apertura vacía y solo
        # restringen copiar o imprimir: se leen sin pedir nada. Solo se rechaza
        # el que exige una contraseña real.
        try:
            abierto = lector.decrypt("") != 0
        except Exception:
            abierto = False
        if not abierto:
            raise DocumentoProtegidoError("PDF protegido con contraseña.")

    bloques: list[str] = []
    paginas: list[int] = []
    paginas_con_error = 0
    try:
        for numero, pagina in enumerate(lector.pages, start=1):
            try:
                texto = (pagina.extract_text() or "").strip()
            except Exception:
                paginas_con_error += 1
                continue
            if texto:
                bloques.append(texto)
                paginas.append(numero)
    except Exception as exc:
        raise DocumentoDanadoError(f"PDF dañado: no se pudieron recorrer sus páginas ({exc})")

    if not bloques:
        texto_ocr = _ocr(contenido)
        if texto_ocr:
            return texto_ocr, [1]
        if paginas_con_error:
            raise DocumentoDanadoError("PDF dañado: ninguna página se pudo leer.")
        raise DocumentoSinTextoError("PDF sin texto seleccionable y OCR sin resultado.")

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
