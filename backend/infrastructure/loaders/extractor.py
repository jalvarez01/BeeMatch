"""
Punto único de extracción de texto de una hoja de vida (HU-17).

El formato se decide por el CONTENIDO del archivo y no por su extensión ni por
lo que diga la base de datos: un .doc registrado como DOCX, o un PDF sin
extensión, se leen igual con el lector que les corresponde.
"""

import io
import struct

from backend.infrastructure.loaders.doc_loader import extraer_texto_doc
from backend.infrastructure.loaders.docx_loader import extraer_texto_docx
from backend.infrastructure.loaders.errores import (
    DocumentoDanadoError,
    DocumentoProtegidoError,
    ExtraccionNoDisponibleError,
)
from backend.infrastructure.loaders.pdf_loader import extraer_texto_pdf

# Firmas de archivo.
_FIRMA_PDF = b"%PDF-"
_FIRMA_ZIP = b"PK\x03\x04"  # .docx es un zip
_FIRMA_OLE = bytes.fromhex("D0CF11E0A1B11AE1")  # .doc y .docx con contraseña

# MS-DOC, cabecera FIB: la palabra de banderas está en el byte 0x0A y el bit
# 0x0100 indica que el documento está cifrado.
_OFFSET_BANDERAS_FIB = 0x0A
_BANDERA_CIFRADO = 0x0100


def extraer_texto(contenido: bytes) -> str:
    """
    Devuelve el texto del documento (PDF, .docx o .doc).

    Lanza un ExtraccionError si el documento no se puede leer:
    DocumentoProtegidoError, DocumentoDanadoError o DocumentoSinTextoError. Si lo
    que falta es una dependencia del servidor, lanza ExtraccionNoDisponibleError,
    que no es culpa del archivo. Nunca otra cosa.
    """
    if not contenido:
        raise DocumentoDanadoError("El archivo está vacío.")

    if _FIRMA_PDF in contenido[:1024]:
        texto, _paginas = extraer_texto_pdf(contenido)
        return texto
    if contenido.startswith(_FIRMA_ZIP):
        return extraer_texto_docx(contenido)
    if contenido.startswith(_FIRMA_OLE):
        return _extraer_ole(contenido)

    raise DocumentoDanadoError("El archivo no es un PDF ni un documento de Word reconocible.")


def _extraer_ole(contenido: bytes) -> str:
    """
    Los contenedores OLE cubren dos casos que se distinguen por sus flujos
    internos: el .doc clásico (WordDocument) y el .docx protegido con
    contraseña, que Word guarda cifrado dentro de un contenedor OLE
    (EncryptedPackage).
    """
    try:
        import olefile
    except ImportError as exc:  # pragma: no cover
        # Se importa aquí y no arriba para que un entorno sin olefile pueda
        # igual arrancar la aplicación y leer PDF y .docx.
        raise ExtraccionNoDisponibleError(
            f"El servidor no tiene la dependencia 'olefile', necesaria para los .doc: {exc}"
        ) from exc

    try:
        ole = olefile.OleFileIO(io.BytesIO(contenido))
    except Exception as exc:
        raise DocumentoDanadoError(f"Documento de Word dañado o ilegible: {exc}")

    try:
        if ole.exists("EncryptedPackage") or ole.exists("EncryptionInfo"):
            raise DocumentoProtegidoError("Documento de Word protegido con contraseña.")
        if not ole.exists("WordDocument"):
            raise DocumentoDanadoError("El archivo no es un documento de Word.")

        cabecera = ole.openstream("WordDocument").read(_OFFSET_BANDERAS_FIB + 2)
        if len(cabecera) < _OFFSET_BANDERAS_FIB + 2:
            raise DocumentoDanadoError("Documento .doc dañado: cabecera incompleta.")
        (banderas,) = struct.unpack_from("<H", cabecera, _OFFSET_BANDERAS_FIB)
        if banderas & _BANDERA_CIFRADO:
            raise DocumentoProtegidoError("Documento de Word protegido con contraseña.")
    except (DocumentoProtegidoError, DocumentoDanadoError):
        raise
    except Exception as exc:
        raise DocumentoDanadoError(f"Documento de Word dañado o ilegible: {exc}")
    finally:
        ole.close()

    return extraer_texto_doc(contenido)
