"""
HU-09: el filtro de rol se arma con lo que hay en el repositorio.

La lista no puede ser fija. Bee carga hojas de vida de áreas nuevas y el
reclutador tiene que poder filtrar por ellas sin que nadie toque el código.
Los roles salen de lo que la IA extrajo durante la indexación.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.domain.services.candidato_service import CandidatoService
from backend.infrastructure.persistence import models  # noqa: F401
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models.hoja_vida import CandidatoModel, HojaDeVidaModel


@pytest.fixture()
def db():
    motor = create_engine("sqlite://")
    Base.metadata.create_all(bind=motor)
    sesion = sessionmaker(bind=motor)()
    yield sesion
    sesion.close()


def _candidato(db, rol: str | None, indice: int) -> None:
    hoja = HojaDeVidaModel(
        id_documento=f"doc-{indice}", nombre_archivo=f"cv{indice}.pdf", formato="PDF"
    )
    db.add(hoja)
    db.commit()
    db.add(CandidatoModel(hoja_de_vida_id=hoja.id, nombre=f"Candidato {indice}", rol_principal=rol))
    db.commit()


def _roles(db) -> list[tuple[str, int]]:
    return [(r.nombre, r.candidatos) for r in CandidatoService(db).roles_disponibles()]


def test_sin_candidatos_la_lista_viene_vacia(db):
    assert _roles(db) == []


def test_los_roles_salen_de_los_candidatos_indexados(db):
    for i, rol in enumerate(["Gerente de proyectos", "Analista QA"]):
        _candidato(db, rol, i)

    assert sorted(n for n, _ in _roles(db)) == ["Analista QA", "Gerente de proyectos"]


def test_un_rol_nuevo_aparece_solo_al_cargar_su_hoja_de_vida(db):
    """El caso que motivó el cambio: cargar un perfil de un área no prevista."""
    _candidato(db, "Backend Developer", 0)
    assert [n for n, _ in _roles(db)] == ["Backend Developer"]

    _candidato(db, "Arquitecto Cloud", 1)

    assert sorted(n for n, _ in _roles(db)) == ["Arquitecto Cloud", "Backend Developer"]


def test_las_variantes_de_mayusculas_se_agrupan(db):
    for i, rol in enumerate(["FullStack Developer", "Fullstack Developer", "fullstack developer"]):
        _candidato(db, rol, i)

    roles = _roles(db)
    assert len(roles) == 1
    assert roles[0][1] == 3


def test_las_variantes_con_tilde_se_agrupan(db):
    for i, rol in enumerate(["Líder Técnico de Datos", "Lider Tecnico de Datos"]):
        _candidato(db, rol, i)

    assert len(_roles(db)) == 1


def test_gana_la_forma_mas_escrita(db):
    for i, rol in enumerate(["fullstack developer", "FullStack Developer", "FullStack Developer"]):
        _candidato(db, rol, i)

    assert _roles(db)[0][0] == "FullStack Developer"


def test_el_mas_frecuente_va_primero(db):
    for i, rol in enumerate(["Analista QA", "Ingeniero de Datos", "Ingeniero de Datos"]):
        _candidato(db, rol, i)

    assert [n for n, _ in _roles(db)] == ["Ingeniero de Datos", "Analista QA"]


def test_un_candidato_sin_rol_no_ensucia_la_lista(db):
    """Pasa cuando la IA no estaba disponible y el perfil quedó incompleto."""
    _candidato(db, None, 0)
    _candidato(db, "   ", 1)
    _candidato(db, "Analista QA", 2)

    assert _roles(db) == [("Analista QA", 1)]
