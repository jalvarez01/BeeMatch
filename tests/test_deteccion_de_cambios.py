"""
RD5: solo se reindexa el documento que cambió.

La detección compara hash y fecha de modificación. El proveedor entrega la
fecha con zona horaria y SQLite la devuelve sin ella, así que la comparación
tiene que normalizar antes: si no, todo documento parece modificado y cada
sincronización reindexa el repositorio entero, con su costo en llamadas al
modelo. Eso además hace imposible el criterio 4 de HU-18 (menos de dos
minutos), porque la búsqueda sincroniza antes de ejecutarse.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.infrastructure.persistence import models  # noqa: F401
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models.hoja_vida import (
    ESTADO_INDEXADA,
    ESTADO_PENDIENTE,
)
from backend.infrastructure.persistence.repositories.hoja_vida_repo import HojaDeVidaRepository

FECHA = datetime(2026, 9, 18, 18, 36, 16, tzinfo=timezone.utc)


@pytest.fixture()
def db():
    motor = create_engine("sqlite://")
    Base.metadata.create_all(bind=motor)
    sesion = sessionmaker(bind=motor)()
    yield sesion
    sesion.close()


def _datos(hash_contenido: str = "abc123", fecha: datetime | None = FECHA) -> dict:
    return {
        "id_documento": "drive-1",
        "nombre_archivo": "cv.pdf",
        "ruta": "/HojasDeVida",
        "url_web": None,
        "formato": "PDF",
        "hash_contenido": hash_contenido,
        "fecha_modificacion": fecha,
    }


def test_un_documento_nuevo_se_indexa(db):
    _, necesita_reindexar = HojaDeVidaRepository(db).registrar_o_actualizar(_datos())
    assert necesita_reindexar is True


def test_el_mismo_documento_sin_cambios_no_se_reindexa(db):
    """
    El caso que estaba roto: SQLite devuelve la fecha sin zona horaria, el
    proveedor la manda con zona, y comparadas crudas nunca son iguales.
    """
    repo = HojaDeVidaRepository(db)
    hoja, _ = repo.registrar_o_actualizar(_datos())
    repo.marcar_indexada(hoja.id)

    # Tal como vuelve de una sesión nueva: la fecha ya viene sin zona.
    db.expire_all()
    guardada = repo.get_by_id_documento("drive-1").fecha_modificacion
    assert guardada.tzinfo is None, "SQLite debería devolverla sin zona"

    _, necesita_reindexar = repo.registrar_o_actualizar(_datos())

    assert necesita_reindexar is False
    assert repo.get_by_id_documento("drive-1").estado_procesamiento == ESTADO_INDEXADA


def test_un_documento_con_contenido_distinto_si_se_reindexa(db):
    repo = HojaDeVidaRepository(db)
    hoja, _ = repo.registrar_o_actualizar(_datos())
    repo.marcar_indexada(hoja.id)

    _, necesita_reindexar = repo.registrar_o_actualizar(_datos(hash_contenido="otro-hash"))

    assert necesita_reindexar is True
    assert repo.get_by_id_documento("drive-1").estado_procesamiento == ESTADO_PENDIENTE


def test_un_documento_editado_despues_si_se_reindexa(db):
    repo = HojaDeVidaRepository(db)
    hoja, _ = repo.registrar_o_actualizar(_datos())
    repo.marcar_indexada(hoja.id)

    _, necesita_reindexar = repo.registrar_o_actualizar(_datos(fecha=FECHA + timedelta(hours=2)))

    assert necesita_reindexar is True


def test_un_documento_sin_fecha_en_ambos_lados_no_se_reindexa(db):
    """Un origen que no informa la fecha no debe forzar reindexado perpetuo."""
    repo = HojaDeVidaRepository(db)
    hoja, _ = repo.registrar_o_actualizar(_datos(fecha=None))
    repo.marcar_indexada(hoja.id)

    _, necesita_reindexar = repo.registrar_o_actualizar(_datos(fecha=None))

    assert necesita_reindexar is False


def test_estrenar_fecha_donde_no_habia_cuenta_como_cambio(db):
    repo = HojaDeVidaRepository(db)
    hoja, _ = repo.registrar_o_actualizar(_datos(fecha=None))
    repo.marcar_indexada(hoja.id)

    _, necesita_reindexar = repo.registrar_o_actualizar(_datos(fecha=FECHA))

    assert necesita_reindexar is True
