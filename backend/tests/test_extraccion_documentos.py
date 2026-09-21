"""HU-17: extracción de texto de PDF, .docx y .doc; documentos dañados o protegidos."""

import pytest

from backend.infrastructure.loaders.errores import (
    DocumentoDanadoError,
    DocumentoProtegidoError,
    ExtraccionError,
)
from backend.infrastructure.loaders.extractor import extraer_texto
from backend.tests.conftest import (
    crear_docx,
    crear_pdf,
    cifrar_docx,
    cifrar_pdf,
    doc_ejemplo,
    marcar_doc_como_cifrado,
    requiere_antiword,
)

# --- Criterio 1: PDF ----------------------------------------------------------


def test_extrae_texto_de_pdf():
    assert "Java Spring Boot" in extraer_texto(crear_pdf())


def test_pdf_con_clave_de_apertura_vacia_se_lee():
    """Muchos PDF solo restringen copiar/imprimir: no exigen contraseña real."""
    assert "Java" in extraer_texto(cifrar_pdf(crear_pdf(), clave_usuario=""))


# --- Criterio 2: Word (.docx y .doc) -------------------------------------------


def test_extrae_texto_de_docx_incluyendo_tablas():
    texto = extraer_texto(crear_docx())
    assert "microservicios" in texto
    assert "Core bancario" in texto


@requiere_antiword
def test_extrae_texto_de_doc_clasico():
    texto = extraer_texto(doc_ejemplo())
    assert "microservicios" in texto
    assert "Core bancario" in texto  # tabla del .doc


# --- Criterio 3: dañados o protegidos se marcan, no revientan -------------------


@pytest.mark.parametrize("algoritmo", ["RC4-128", "AES-256"])
def test_pdf_con_contrasena_es_protegido(algoritmo):
    with pytest.raises(DocumentoProtegidoError, match="contraseña"):
        extraer_texto(cifrar_pdf(crear_pdf(), clave_usuario="secreto", algoritmo=algoritmo))


def test_docx_con_contrasena_es_protegido():
    with pytest.raises(DocumentoProtegidoError, match="contraseña"):
        extraer_texto(cifrar_docx(crear_docx()))


def test_doc_con_contrasena_es_protegido():
    with pytest.raises(DocumentoProtegidoError, match="contraseña"):
        extraer_texto(marcar_doc_como_cifrado(doc_ejemplo()))


@pytest.mark.parametrize(
    "contenido",
    [
        b"",
        b"esto no es un documento",
        crear_pdf()[:200],  # PDF truncado
        crear_docx()[:1500],  # DOCX truncado
        b"PK\x03\x04" + b"\x00" * 50,  # zip falso
        bytes.fromhex("D0CF11E0A1B11AE1") + b"\x00" * 100,  # OLE roto
    ],
    ids=["vacio", "texto_plano", "pdf_truncado", "docx_truncado", "zip_falso", "ole_roto"],
)
def test_documento_danado_lanza_error_de_extraccion(contenido):
    with pytest.raises(DocumentoDanadoError):
        extraer_texto(contenido)


def test_todo_fallo_es_un_extraccion_error():
    """El indexador solo necesita capturar ExtraccionError."""
    assert issubclass(DocumentoProtegidoError, ExtraccionError)
    assert issubclass(DocumentoDanadoError, ExtraccionError)
