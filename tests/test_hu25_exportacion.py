"""
HU-25: exportación de la preselección para el cliente.

Criterio 1 — "Exportar" genera el listado en PDF o en Excel.
Criterio 2 — el archivo trae el perfil solicitado, el cliente, la fecha y los
             datos de cada candidato con su nivel de afinidad.
Criterio 3 — sin candidatos preseleccionados se indica que hay que elegir al menos uno.

Se exporta por la API real y se leen los archivos descargados.
"""

import io
from datetime import datetime

import pytest
from openpyxl import load_workbook
from pypdf import PdfReader

from backend.domain.services import export_service
from backend.domain.services.bitacora_service import ACCION_EXPORTACION, BitacoraService
from backend.domain.services.export_service import MENSAJE_SIN_PRESELECCION
from backend.infrastructure.persistence.models.cliente import ClienteModel
from backend.infrastructure.persistence.models.solicitud import SolicitudModel
from tests.test_hu24_preseleccion import _marcar
from tests.test_hu24_preseleccion import busqueda as busqueda  # noqa: F401  (fixture)
from tests.test_hu24_preseleccion import cabeceras as cabeceras  # noqa: F401  (fixture)

ROL = "Desarrolladora Backend"
CLIENTE = "Bancolombia"


@pytest.fixture(autouse=True)
def _archivos_en_temporal(tmp_path, monkeypatch):
    """Los archivos de prueba no se quedan en storage/."""
    monkeypatch.setattr(export_service, "STORAGE_DIR", tmp_path)


@pytest.fixture
def con_cliente(db, busqueda):
    """La solicitud de la búsqueda con rol y cliente, como llega de una solicitud real."""
    cliente = ClienteModel(nombre=CLIENTE)
    db.add(cliente)
    db.flush()
    solicitud = db.get(SolicitudModel, busqueda["solicitud_id"])
    solicitud.rol_buscado = ROL
    solicitud.cliente_id = cliente.id
    db.commit()
    return busqueda


def _exportar(cliente, cabeceras, busqueda_id: str, formato: str):
    return cliente.post(f"/preseleccion/{busqueda_id}/exportar", json={"formato": formato}, headers=cabeceras)


def _texto_excel(contenido: bytes) -> str:
    hoja = load_workbook(io.BytesIO(contenido)).active
    return " | ".join(str(c) for fila in hoja.iter_rows(values_only=True) for c in fila if c is not None)


def _texto_pdf(contenido: bytes) -> str:
    return " ".join(pagina.extract_text() for pagina in PdfReader(io.BytesIO(contenido)).pages)


def _marcar_dos(cliente, cabeceras, busqueda):
    primero, segundo, _ = busqueda["recomendaciones"]
    _marcar(cliente, cabeceras, primero, True)
    _marcar(cliente, cabeceras, segundo, True)


# --- Criterio 1: PDF o Excel --------------------------------------------------


def test_exportar_en_excel_descarga_un_xlsx(cliente, cabeceras, busqueda):
    _marcar_dos(cliente, cabeceras, busqueda)

    respuesta = _exportar(cliente, cabeceras, busqueda["busqueda_id"], "XLSX")

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.content[:2] == b"PK"  # un .xlsx es un zip
    assert ".xlsx" in respuesta.headers["content-disposition"]


def test_exportar_en_pdf_descarga_un_pdf(cliente, cabeceras, busqueda):
    _marcar_dos(cliente, cabeceras, busqueda)

    respuesta = _exportar(cliente, cabeceras, busqueda["busqueda_id"], "PDF")

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.content.startswith(b"%PDF")
    assert ".pdf" in respuesta.headers["content-disposition"]


def test_un_formato_distinto_se_rechaza(cliente, cabeceras, busqueda):
    _marcar_dos(cliente, cabeceras, busqueda)

    assert _exportar(cliente, cabeceras, busqueda["busqueda_id"], "CSV").status_code == 422


# --- Criterio 2: contenido del archivo ---------------------------------------


@pytest.mark.parametrize("formato, leer", [("XLSX", _texto_excel), ("PDF", _texto_pdf)])
def test_el_archivo_trae_perfil_cliente_fecha_y_candidatos_con_nivel(
    cliente, cabeceras, con_cliente, formato, leer
):
    _marcar_dos(cliente, cabeceras, con_cliente)

    texto = leer(_exportar(cliente, cabeceras, con_cliente["busqueda_id"], formato).content)

    assert ROL in texto
    assert CLIENTE in texto
    assert datetime.now().strftime("%d/%m/%Y") in texto
    # Los dos marcados (92 % alta, 81 % media) con su afinidad y su nivel.
    assert "92%" in texto and "Alta" in texto
    assert "81%" in texto and "Media" in texto


@pytest.mark.parametrize("formato, leer", [("XLSX", _texto_excel), ("PDF", _texto_pdf)])
def test_el_archivo_solo_trae_los_preseleccionados(cliente, cabeceras, busqueda, formato, leer):
    _marcar_dos(cliente, cabeceras, busqueda)

    texto = leer(_exportar(cliente, cabeceras, busqueda["busqueda_id"], formato).content)

    assert "74%" not in texto


def test_sin_cliente_el_archivo_lo_indica(cliente, cabeceras, busqueda):
    _marcar_dos(cliente, cabeceras, busqueda)

    texto = _texto_excel(_exportar(cliente, cabeceras, busqueda["busqueda_id"], "XLSX").content)

    assert "Sin cliente asignado" in texto


# --- Criterio 3: sin preseleccionados -----------------------------------------


@pytest.mark.parametrize("formato", ["XLSX", "PDF"])
def test_sin_preseleccionados_pide_seleccionar_al_menos_uno(cliente, cabeceras, busqueda, formato):
    respuesta = _exportar(cliente, cabeceras, busqueda["busqueda_id"], formato)

    assert respuesta.status_code == 400
    assert respuesta.json()["detail"] == MENSAJE_SIN_PRESELECCION


def test_al_retirar_todas_las_marcas_vuelve_a_pedir_al_menos_uno(cliente, cabeceras, busqueda):
    primero = busqueda["recomendaciones"][0]
    _marcar(cliente, cabeceras, primero, True)
    _marcar(cliente, cabeceras, primero, False)

    respuesta = _exportar(cliente, cabeceras, busqueda["busqueda_id"], "XLSX")

    assert respuesta.status_code == 400
    assert respuesta.json()["detail"] == MENSAJE_SIN_PRESELECCION


def test_la_exportacion_queda_en_la_bitacora(db, cliente, cabeceras, busqueda):
    _marcar_dos(cliente, cabeceras, busqueda)
    _exportar(cliente, cabeceras, busqueda["busqueda_id"], "PDF")

    _, eventos = BitacoraService(db).listar()

    assert any(e["accion"] == ACCION_EXPORTACION and e["detalle"] == "PDF" for e in eventos), eventos
