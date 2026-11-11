"""
Pruebas propias de PostgreSQL + pgvector (C19 a C21).

El resto de la suite corre sobre SQLite, donde la búsqueda vectorial es un
cálculo en memoria y la léxica un LIKE. Aquí se prueba lo que solo existe en
el motor de producción: los índices HNSW y GIN, la distancia coseno de
pgvector y el `tsvector` en español.

Se omiten solas si la base no es PostgreSQL. Para ejecutarlas:

    docker run -d -p 55432:5432 -e POSTGRES_USER=beematch -e POSTGRES_PASSWORD=beematch \
        -e POSTGRES_DB=beematch pgvector/pgvector:pg16
    PRUEBAS_DATABASE_URL=postgresql+psycopg://beematch:beematch@localhost:55432/beematch \
        python -m pytest tests/test_postgres_pgvector.py
"""

import pytest
from sqlalchemy import text

from backend.config import EMBEDDING_DIMENSIONES, USA_PGVECTOR
from backend.domain.matching.retriever import RecuperadorHibrido
from backend.infrastructure.persistence.database import (
    INDICES_DE_BUSQUEDA,
    crear_indices_de_busqueda,
)
from backend.infrastructure.persistence.models.hoja_vida import FragmentoCVModel, HojaDeVidaModel

pytestmark = pytest.mark.skipif(not USA_PGVECTOR, reason="Requiere PostgreSQL con pgvector")


def _vector(posicion: int) -> list[float]:
    """Vector unitario: un 1.0 en la posición dada. Dos distintos son ortogonales."""
    v = [0.0] * EMBEDDING_DIMENSIONES
    v[posicion] = 1.0
    return v


@pytest.fixture
def fragmentos(db):
    hoja = HojaDeVidaModel(id_documento="doc-pg", nombre_archivo="cv.pdf", formato="PDF")
    db.add(hoja)
    db.commit()
    textos = {
        "java": ("Desarrolladora Java con Spring Boot y microservicios", _vector(0)),
        "datos": ("Ingeniero de datos con Python, Spark y Airflow", _vector(1)),
        "contab": ("Contadora pública con experiencia en auditoría", _vector(2)),
    }
    ids = {}
    for orden, (clave, (texto, vector)) in enumerate(textos.items()):
        fragmento = FragmentoCVModel(
            hoja_de_vida_id=hoja.id, orden=orden, texto=texto, embedding=vector
        )
        db.add(fragmento)
        db.flush()
        ids[clave] = fragmento.id
    db.commit()
    return ids


def test_la_extension_vector_esta_habilitada(db):
    nombre = db.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector'")).scalar()
    assert nombre == "vector"


def test_el_embedding_es_una_columna_vector_de_las_dimensiones_configuradas(db):
    tipo = db.execute(
        text(
            "SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
            "WHERE attrelid = 'fragmentos_cv'::regclass AND attname = 'embedding'"
        )
    ).scalar()
    assert tipo == f"vector({EMBEDDING_DIMENSIONES})"


def test_los_indices_hnsw_y_gin_se_crean_y_la_creacion_es_idempotente(db):
    crear_indices_de_busqueda()
    crear_indices_de_busqueda()
    existentes = {
        fila[0]
        for fila in db.execute(
            text("SELECT indexname FROM pg_indexes WHERE tablename = 'fragmentos_cv'")
        )
    }
    assert set(INDICES_DE_BUSQUEDA) <= existentes


def test_la_busqueda_vectorial_usa_el_indice_hnsw(db, fragmentos):
    crear_indices_de_busqueda()
    db.execute(text("SET LOCAL enable_seqscan = off"))
    plan = "\n".join(
        fila[0]
        for fila in db.execute(
            text(
                "EXPLAIN SELECT id FROM fragmentos_cv WHERE embedding IS NOT NULL "
                "ORDER BY embedding <=> CAST(:v AS vector) LIMIT 5"
            ),
            {"v": str(_vector(0))},
        )
    )
    assert "ix_fragmentos_cv_embedding_hnsw" in plan


def test_la_busqueda_lexica_usa_el_indice_gin(db, fragmentos):
    crear_indices_de_busqueda()
    db.execute(text("SET LOCAL enable_seqscan = off"))
    plan = "\n".join(
        fila[0]
        for fila in db.execute(
            text(
                "EXPLAIN SELECT id FROM fragmentos_cv "
                "WHERE to_tsvector('spanish', texto) @@ plainto_tsquery('spanish', 'java')"
            )
        )
    )
    assert "ix_fragmentos_cv_texto_fts" in plan


def test_la_busqueda_vectorial_devuelve_primero_el_fragmento_mas_cercano(db, fragmentos):
    ids = RecuperadorHibrido(db)._buscar_vectorial(_vector(1), limite=3)
    assert ids[0] == fragmentos["datos"]
    assert set(ids) == set(fragmentos.values())


def test_la_busqueda_lexica_usa_el_diccionario_en_espanol(db, fragmentos):
    # "auditorías" y "auditoría" comparten raíz solo con el stemmer en español.
    ids = RecuperadorHibrido(db)._buscar_lexico("auditorías", limite=5)
    assert ids == [fragmentos["contab"]]


def test_la_recuperacion_hibrida_fusiona_ambas_listas(db, fragmentos):
    resultado = RecuperadorHibrido(db).recuperar("Java Spring", _vector(0), limite=3)
    assert resultado[0].fragmento_id == fragmentos["java"]
    # Aparece en las dos listas, así que su puntaje RRF supera al de los demás.
    assert resultado[0].puntaje > resultado[-1].puntaje


def test_un_vector_de_dimension_incorrecta_se_rechaza(db):
    hoja = HojaDeVidaModel(id_documento="doc-dim", nombre_archivo="x.pdf", formato="PDF")
    db.add(hoja)
    db.commit()
    db.add(FragmentoCVModel(hoja_de_vida_id=hoja.id, texto="x", embedding=[0.1, 0.2, 0.3]))
    with pytest.raises(Exception, match="dimensions"):
        db.commit()
    db.rollback()
