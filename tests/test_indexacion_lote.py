"""HU-17, criterio 3 de punta a punta: una hoja mala no detiene a las demás."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.domain.services import indexacion_service
from backend.domain.services.indexacion_service import IndexacionService
from backend.infrastructure.llm.llm_provider import RespuestaIA
from backend.infrastructure.persistence import models  # noqa: F401
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models.hoja_vida import (
    ESTADO_INDEXADA,
    ESTADO_NO_PROCESABLE,
    HojaDeVidaModel,
)
from backend.infrastructure.persistence.repositories.candidato_repo import CandidatoRepository
from backend.infrastructure.persistence.repositories.hoja_vida_repo import HojaDeVidaRepository
from tests.documentos_hu17 import (
    crear_docx,
    crear_pdf,
    cifrar_pdf,
    doc_ejemplo,
    requiere_antiword,
)


class RepositorioFalso:
    def __init__(self, documentos: dict[str, bytes]):
        self.documentos = documentos

    def descargar(self, id_documento: str) -> bytes:
        return self.documentos[id_documento]


class EmbeddingsFalso:
    def generar(self, textos):
        return [[0.1, 0.2, 0.3] for _ in textos]


class LLMFalso:
    """Responde el perfil estructurado sin salir a la red (HU-18)."""

    def __init__(self, datos: dict | None = None):
        self.datos = datos if datos is not None else {
            "nombre": "Ana Perez",
            "rol_principal": "Desarrolladora Backend",
            "anios_experiencia": 6,
            "ubicacion": "Medellin",
            "resumen": "Perfil de prueba.",
            "tecnologias": [{"nombre": "Java", "categoria": "TECNOLOGIA"}],
        }
        self.llamadas = 0

    def completar_json(self, system, prompt, max_reintentos=3):
        self.llamadas += 1
        return RespuestaIA(datos=self.datos)


@pytest.fixture()
def db():
    motor = create_engine("sqlite://")
    Base.metadata.create_all(bind=motor)
    sesion = sessionmaker(bind=motor)()
    yield sesion
    sesion.close()


def _servicio(db, documentos: dict[str, bytes]) -> IndexacionService:
    servicio = IndexacionService.__new__(IndexacionService)  # sin tocar OneDrive ni OpenAI
    servicio.db = db
    servicio.hojas = HojaDeVidaRepository(db)
    servicio.candidatos = CandidatoRepository(db)
    servicio.embeddings = EmbeddingsFalso()
    servicio.llm = LLMFalso()
    servicio.repositorio = RepositorioFalso(documentos)
    return servicio


def _registrar(db, documentos: dict[str, bytes]) -> list[str]:
    ids = []
    for nombre in documentos:
        hoja = HojaDeVidaModel(id_documento=nombre, nombre_archivo=nombre, formato="PDF")
        db.add(hoja)
        db.commit()
        ids.append(hoja.id)
    return ids


def test_lote_mixto_indexa_las_buenas_y_marca_las_malas(db):
    documentos = {
        "ana.pdf": crear_pdf(),
        "beto_con_clave.pdf": cifrar_pdf(crear_pdf(), clave_usuario="secreto"),
        "carla_danada.docx": crear_docx()[:1500],
        "diego.docx": crear_docx(),
    }
    ids = _registrar(db, documentos)
    servicio = _servicio(db, documentos)

    resultados = [servicio.indexar_hoja(hoja_id) for hoja_id in ids]

    assert resultados == [True, False, False, True]  # la corrida llegó hasta el final
    hojas = HojaDeVidaRepository(db)
    assert hojas.contar_por_estado(ESTADO_INDEXADA) == 2
    assert hojas.contar_por_estado(ESTADO_NO_PROCESABLE) == 2
    assert "contraseña" in hojas.get_by_id(ids[1]).motivo_error
    assert "dañado" in hojas.get_by_id(ids[2]).motivo_error


@requiere_antiword
def test_hoja_en_formato_doc_queda_indexada_aunque_este_rotulada_como_docx(db):
    documentos = {"eva.doc": doc_ejemplo()}
    ids = _registrar(db, documentos)
    db.get(HojaDeVidaModel, ids[0]).formato = "DOCX"  # así la registran los clientes de OneDrive/Drive
    db.commit()

    assert _servicio(db, documentos).indexar_hoja(ids[0]) is True


def test_un_error_inesperado_al_leer_no_escapa_ni_deja_la_hoja_pendiente(db, monkeypatch):
    documentos = {"raro.pdf": crear_pdf()}
    ids = _registrar(db, documentos)

    def explota(_contenido):
        raise RuntimeError("fallo imprevisto de la librería")

    monkeypatch.setattr(indexacion_service, "extraer_texto", explota)

    assert _servicio(db, documentos).indexar_hoja(ids[0]) is False
    hoja = HojaDeVidaRepository(db).get_by_id(ids[0])
    assert hoja.estado_procesamiento == ESTADO_NO_PROCESABLE
    assert "fallo imprevisto" in hoja.motivo_error
