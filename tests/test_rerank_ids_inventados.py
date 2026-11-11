"""
El modelo de lenguaje puede devolver identificadores que no le dimos: un
fragmento inventado, uno mal copiado o un candidato que no era finalista.

En SQLite eso se guardaba sin quejarse. En PostgreSQL, un `fragmento_id` de más
de 36 caracteres rompe el INSERT ("value too long for type character varying(36)")
y toda la búsqueda termina en "error inesperado". Pasó en producción el
11/11/2026. El re-ranking debe aceptar solo lo que pueda anclarse a un fragmento
real (RD3, RNF28) y descartar el resto.
"""

from backend.domain.matching.reranker import REQUISITO_MAX_CARACTERES, Reranker
from backend.infrastructure.llm.llm_provider import RespuestaIA
from backend.infrastructure.persistence.models.hoja_vida import (
    CandidatoModel,
    FragmentoCVModel,
    HojaDeVidaModel,
)
from backend.infrastructure.persistence.models.solicitud import SolicitudModel
from backend.infrastructure.persistence.repositories.busqueda_repo import BusquedaRepository

FINALISTAS = [
    {
        "candidato_id": "c-1",
        "nombre": "Ana",
        "fragmentos": [
            {"id": "f-1", "texto": "Desarrolladora Java con Spring Boot."},
            {"id": "f-2", "texto": "Despliegues en AWS."},
        ],
    },
    {
        "candidato_id": "c-2",
        "nombre": "Luis",
        "fragmentos": [{"id": "f-9", "texto": "Analista de datos."}],
    },
]

FRAGMENTO_INVENTADO = "fragmento-que-el-modelo-invento-" + "x" * 40  # 71 caracteres


class ProveedorQueDevuelve:
    def __init__(self, candidatos: list[dict]):
        self.candidatos = candidatos

    def completar_json(self, system, prompt, max_reintentos=3):
        return RespuestaIA(datos={"candidatos": self.candidatos})


def _coincidencia(requisito="Java", estado="ENCONTRADO", fragmento_id="f-1"):
    return {
        "requisito": requisito,
        "estado": estado,
        "evidencia_texto": "texto citado",
        "fragmento_id": fragmento_id,
    }


def _ordenar(candidatos: list[dict], requisitos=("Java",)):
    resultados, _ = Reranker(ProveedorQueDevuelve(candidatos)).ordenar_y_explicar(
        "perfil", list(requisitos), FINALISTAS
    )
    return resultados


def _candidato(candidato_id="c-1", coincidencias=None, puntaje=80):
    return {
        "candidato_id": candidato_id,
        "puntaje_afinidad": puntaje,
        "resumen": "resumen",
        "coincidencias": coincidencias if coincidencias is not None else [_coincidencia()],
    }


# --- Fragmentos --------------------------------------------------------------


def test_un_fragmento_valido_del_candidato_se_conserva():
    [resultado] = _ordenar([_candidato()])

    [coincidencia] = resultado["coincidencias"]
    assert (coincidencia["estado"], coincidencia["fragmento_id"]) == ("ENCONTRADO", "f-1")


def test_un_fragmento_inventado_degrada_la_coincidencia_a_no_evidenciado():
    [resultado] = _ordenar([_candidato(coincidencias=[_coincidencia(fragmento_id=FRAGMENTO_INVENTADO)])])

    [coincidencia] = resultado["coincidencias"]
    assert coincidencia["estado"] == "NO_EVIDENCIADO"
    assert coincidencia["fragmento_id"] is None
    assert coincidencia["evidencia_texto"] is None


def test_un_fragmento_real_pero_de_otro_candidato_tambien_se_rechaza():
    """f-9 existe, pero es de Luis: no puede sustentar lo que se afirma de Ana."""
    [resultado] = _ordenar([_candidato("c-1", [_coincidencia(fragmento_id="f-9")])])

    assert resultado["coincidencias"][0]["estado"] == "NO_EVIDENCIADO"


def test_un_fragmento_que_no_es_texto_no_rompe_nada():
    [resultado] = _ordenar([_candidato(coincidencias=[_coincidencia(fragmento_id=12345)])])

    assert resultado["coincidencias"][0]["estado"] == "NO_EVIDENCIADO"


def test_un_fragmento_dado_como_numero_que_coincide_con_uno_real_se_acepta():
    finalistas = [{"candidato_id": "c-1", "nombre": "Ana", "fragmentos": [{"id": "7", "texto": "x"}]}]
    proveedor = ProveedorQueDevuelve([_candidato(coincidencias=[_coincidencia(fragmento_id=7)])])

    [resultado], _ = Reranker(proveedor).ordenar_y_explicar("perfil", ["Java"], finalistas)

    assert resultado["coincidencias"][0]["fragmento_id"] == "7"


# --- Candidatos --------------------------------------------------------------


def test_un_candidato_que_no_era_finalista_se_descarta():
    resultados = _ordenar([_candidato("c-1"), _candidato("candidato-inventado-" + "y" * 40)])

    assert [r["candidato_id"] for r in resultados] == ["c-1"]


# --- Requisitos --------------------------------------------------------------


def test_un_requisito_demasiado_largo_se_recorta_al_tamano_de_la_columna():
    largo = "Experiencia en " + "algo muy específico " * 20
    [resultado] = _ordenar([_candidato(coincidencias=[_coincidencia(requisito=largo)])])

    requisito = resultado["coincidencias"][0]["requisito"]
    assert len(requisito) <= REQUISITO_MAX_CARACTERES
    assert largo.startswith(requisito.rstrip())


# --- De punta a punta contra la base ------------------------------------------


def test_una_respuesta_con_ids_inventados_se_guarda_sin_romper_la_base(db):
    """
    Con PostgreSQL (PRUEBAS_DATABASE_URL) esta prueba falla si algún id inventado
    llega a la tabla. Con SQLite verifica al menos que nada inventado se guarda.
    """
    hoja = HojaDeVidaModel(id_documento="doc-1", nombre_archivo="cv.pdf", formato="PDF")
    db.add(hoja)
    db.commit()
    real = FragmentoCVModel(hoja_de_vida_id=hoja.id, texto="Desarrolladora Java con Spring Boot.")
    candidato = CandidatoModel(hoja_de_vida_id=hoja.id, nombre="Ana")
    db.add_all([real, candidato])
    db.commit()
    solicitud = SolicitudModel(
        descripcion_libre="Backend Java", rol_buscado="Backend", usuario_id=_usuario(db)
    )
    db.add(solicitud)
    db.commit()

    finalistas = [
        {
            "candidato_id": candidato.id,
            "nombre": "Ana",
            "fragmentos": [{"id": real.id, "texto": real.texto}],
        }
    ]
    proveedor = ProveedorQueDevuelve(
        [
            _candidato(
                candidato.id,
                [
                    _coincidencia("Java", "ENCONTRADO", real.id),
                    _coincidencia("AWS", "ENCONTRADO", FRAGMENTO_INVENTADO),
                ],
            ),
            _candidato("candidato-inventado-" + "y" * 40),
        ]
    )
    resultados, _ = Reranker(proveedor).ordenar_y_explicar("perfil", ["Java", "AWS"], finalistas)

    repo = BusquedaRepository(db)
    busqueda = repo.crear(solicitud.id)
    [recomendacion] = repo.guardar_recomendaciones(busqueda.id, resultados)

    guardadas = {c.requisito: c for c in repo.listar_coincidencias(recomendacion.id)}
    assert guardadas["Java"].fragmento_id == real.id
    assert guardadas["AWS"].estado == "NO_EVIDENCIADO"
    assert guardadas["AWS"].fragmento_id is None


def _usuario(db) -> str:
    from backend.infrastructure.persistence.models.usuario import UsuarioModel
    from backend.security import ROL_COORDINADOR, hashear_password

    usuario = UsuarioModel(
        nombre="Prueba",
        correo="prueba@bee.com.co",
        password_hash=hashear_password("x" * 12),
        rol=ROL_COORDINADOR,
    )
    db.add(usuario)
    db.commit()
    return usuario.id


# --- Que el error real no se pierda --------------------------------------------


def test_un_error_inesperado_deja_su_detalle_en_la_bitacora_aunque_la_transaccion_este_rota(db):
    """Antes, si el error venía de la base, el registro fallaba en silencio y se perdía."""
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    from backend.domain.services.busqueda_service import BusquedaService
    from backend.infrastructure.persistence.models.configuracion import RegistroBitacoraModel

    solicitud = SolicitudModel(
        descripcion_libre="Backend Java", rol_buscado="Backend", usuario_id=_usuario(db)
    )
    db.add(solicitud)
    db.commit()

    # Deja la transacción rota, como un error de PostgreSQL a mitad de una escritura.
    try:
        db.execute(text("SELECT * FROM tabla_que_no_existe"))
    except SQLAlchemyError:
        pass

    BusquedaService(db)._registrar_error(solicitud, "ERROR_INESPERADO", "value too long (36)")

    detalle = (
        db.query(RegistroBitacoraModel)
        .filter(RegistroBitacoraModel.detalle.like("%ERROR_INESPERADO%"))
        .one()
        .detalle
    )
    assert "value too long (36)" in detalle


def test_un_error_inesperado_en_la_busqueda_se_escribe_en_el_log_con_su_traza(db, caplog):
    import logging

    from backend.domain.services.busqueda_service import BusquedaService

    class MotorQueFalla:
        def recuperar(self, *args, **kwargs):
            raise RuntimeError("fallo de prueba en el motor")

    solicitud = SolicitudModel(
        descripcion_libre="Backend Java", rol_buscado="Backend", usuario_id=_usuario(db)
    )
    db.add(solicitud)
    db.commit()
    busqueda = BusquedaRepository(db).crear(solicitud.id)

    servicio = BusquedaService(db)
    servicio.recuperador = MotorQueFalla()
    servicio.embeddings = type("E", (), {"generar_uno": lambda self, texto: [0.1]})()
    with caplog.at_level(logging.ERROR):
        servicio.ejecutar(busqueda.id)

    assert "fallo de prueba en el motor" in caplog.text
    assert "Traceback" in caplog.text or "RuntimeError" in caplog.text
