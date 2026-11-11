"""
Prueba del script de migración de SQLite a PostgreSQL.

Solo corre contra PostgreSQL (PRUEBAS_DATABASE_URL): el origen es un SQLite
mínimo armado aquí, con un embedding guardado como JSON, y el destino es la
base de pruebas.
"""

import json
import sqlite3

import pytest
from sqlalchemy import text

from backend.config import DATABASE_URL, EMBEDDING_DIMENSIONES, USA_PGVECTOR
from scripts import migrar_sqlite_a_postgres as migracion

pytestmark = pytest.mark.skipif(not USA_PGVECTOR, reason="Requiere PostgreSQL con pgvector")


@pytest.fixture
def origen(tmp_path):
    ruta = tmp_path / "origen.db"
    conexion = sqlite3.connect(ruta)
    conexion.executescript(
        """
        CREATE TABLE hojas_de_vida (
            id VARCHAR(36) PRIMARY KEY, id_documento VARCHAR(200), nombre_archivo VARCHAR(300),
            ruta VARCHAR(600), formato VARCHAR(20), estado_procesamiento VARCHAR(20),
            created_at DATETIME
        );
        CREATE TABLE fragmentos_cv (
            id VARCHAR(36) PRIMARY KEY, hoja_de_vida_id VARCHAR(36), orden INTEGER,
            pagina INTEGER, texto TEXT, embedding TEXT
        );
        """
    )
    vector = json.dumps([0.5] * EMBEDDING_DIMENSIONES)
    conexion.execute(
        "INSERT INTO hojas_de_vida VALUES ('h1', 'doc-1', 'cv.pdf', '/', 'PDF', 'INDEXADA', "
        "'2026-10-01 10:30:00.000000')"
    )
    conexion.executemany(
        "INSERT INTO fragmentos_cv VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("f1", "h1", 0, 1, "Java y Spring Boot", vector),
            ("f2", "h1", 1, 1, "Sin vector", None),
            # La hoja "borrada" no existe: SQLite lo permite, PostgreSQL no.
            ("huerfano", "h-borrada", 0, 1, "Fragmento sin hoja", vector),
        ],
    )
    conexion.commit()
    conexion.close()
    return ruta


def test_copia_las_filas_convierte_el_embedding_a_vector_y_descarta_los_huerfanos(db, origen):
    copiadas = migracion.migrar(origen, DATABASE_URL)

    assert copiadas["hojas_de_vida"] == 1
    assert copiadas["fragmentos_cv"] == 2

    db.expire_all()
    dimensiones = db.execute(
        text("SELECT vector_dims(embedding) FROM fragmentos_cv WHERE id = 'f1'")
    ).scalar()
    assert dimensiones == EMBEDDING_DIMENSIONES
    assert db.execute(text("SELECT embedding IS NULL FROM fragmentos_cv WHERE id = 'f2'")).scalar()
    assert not db.execute(text("SELECT 1 FROM fragmentos_cv WHERE id = 'huerfano'")).first()
    assert any("fragmento" in motivo and "descartada" in motivo for motivo in migracion.ajustes)


def test_las_fechas_sin_zona_de_sqlite_quedan_en_utc(db, origen):
    migracion.migrar(origen, DATABASE_URL)
    db.expire_all()
    fecha = db.execute(text("SELECT created_at FROM hojas_de_vida WHERE id = 'h1'")).scalar()
    assert fecha.utcoffset().total_seconds() == 0
    assert (fecha.year, fecha.month, fecha.day, fecha.hour, fecha.minute) == (2026, 10, 1, 10, 30)


def test_no_pisa_un_destino_con_datos_salvo_que_se_pida(db, origen):
    migracion.migrar(origen, DATABASE_URL)
    with pytest.raises(SystemExit, match="--vaciar"):
        migracion.migrar(origen, DATABASE_URL)
    # Con --vaciar reemplaza y deja el mismo resultado.
    copiadas = migracion.migrar(origen, DATABASE_URL, vaciar=True)
    assert copiadas["fragmentos_cv"] == 2


def test_simular_no_escribe_en_el_destino(db, origen):
    migracion.migrar(origen, DATABASE_URL, simular=True)
    assert db.execute(text("SELECT COUNT(*) FROM hojas_de_vida")).scalar() == 0


def test_no_modifica_el_archivo_de_origen(db, origen):
    antes = origen.read_bytes()
    migracion.migrar(origen, DATABASE_URL)
    assert origen.read_bytes() == antes
