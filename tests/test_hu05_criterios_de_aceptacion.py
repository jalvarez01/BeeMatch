"""
HU-05 — una o más pruebas por cada criterio de aceptación.

Cada nombre empieza por `test_hu05_criterioN_` para que la trazabilidad
criterio → prueba se lea directo en la salida de pytest. Las pruebas que ya
existían (`test_hu05_credenciales_invalidas.py` y `test_hu05_secreto_enmascarado.py`)
siguen cubriendo el 4 y el 2 desde el servicio y no se repiten aquí.

Ninguna prueba sale a la red:

- Los criterios 1, 2, 3 y 5 usan `ClienteFalso` (ver `conftest.py`) en lugar de
  Google Drive.
- El criterio 4 usa el `GoogleDriveClient` real para que el motivo que se
  compruebe sea el que de verdad ve el administrador. Un JSON ilegible o
  incompleto falla al leerlo, antes de cualquier petición; el caso "bien
  formado pero rechazado por Google" sustituye solo el transporte HTTP por una
  respuesta `invalid_grant`, y `sin_red` garantiza que nada más salga.
"""

import json
from datetime import datetime

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import inspect

import backend.domain.services.repositorio_config_service as servicio_config
import backend.workers.scheduler as scheduler
from backend.domain.services.indexacion_service import IndexacionService
from backend.domain.services.repositorio_config_service import RepositorioConfigService
from backend.infrastructure.crypto import cifrar, descifrar
from backend.infrastructure.gdrive.drive_client import (
    GoogleDriveClient,
    _RespuestaTransporte,
    _TransporteHttpx,
)
from backend.infrastructure.persistence.database import get_db
from backend.infrastructure.persistence.models.configuracion import (
    ConfiguracionRepositorioModel,
)
from backend.infrastructure.persistence.models.hoja_vida import HojaDeVidaModel
from backend.infrastructure.persistence.models.usuario import UsuarioModel
from backend.infrastructure.persistence.repositories.configuracion_repo import (
    RepositorioConfigRepository,
)
from backend.infrastructure.repositorio.base import (
    TIPO_GDRIVE,
    TIPO_ONEDRIVE,
    DocumentoRepositorio,
    ResultadoPrueba,
)
from backend.infrastructure.repositorio.sync_service import SincronizacionService
from backend.main import app
from backend.security import ROL_COORDINADOR, get_current_user
from backend.workers.busqueda_worker import _sincronizar_repositorio
from tests.conftest import SECRETO_DE_PRUEBA, ClienteFalso

CARPETA_VIGENTE = "carpeta-en-uso"

ACEPTA_30 = ResultadoPrueba(
    exito=True, documentos_detectados=30, mensaje="Conexión exitosa. Se detectaron 30 hojas de vida."
)
RECHAZA = ResultadoPrueba(
    exito=False,
    mensaje="Credenciales inválidas.",
    detalle="La llave privada del JSON está corrupta o incompleta.",
)


# --- Andamiaje -----------------------------------------------------------------


@pytest.fixture
def cliente(db, administrador):
    """TestClient con la sesión de pruebas y el administrador ya autenticado."""
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: administrador
    # Sin gestor de contexto: no corre el startup (semilla del repositorio y planificador).
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def cliente_coordinador(db):
    coordinador = UsuarioModel(
        nombre="Coordinadora de prueba",
        correo="coordinadora@beematch.test",
        rol=ROL_COORDINADOR,
        activo=True,
    )
    db.add(coordinador)
    db.commit()
    db.refresh(coordinador)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: coordinador
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def sin_red(monkeypatch):
    """Cualquier petición HTTP directa de httpx rompe la prueba."""

    def prohibido(*args, **kwargs):
        raise AssertionError("La prueba intentó salir a la red.")

    monkeypatch.setattr(httpx, "request", prohibido)


@pytest.fixture
def configuracion_vigente(db, administrador):
    """Una conexión válida ya guardada, la que un intento fallido no puede tocar."""
    RepositorioConfigRepository(db).guardar(
        tipo=TIPO_GDRIVE,
        carpeta=CARPETA_VIGENTE,
        credenciales_cifradas=cifrar(json.dumps({"credenciales_json": SECRETO_DE_PRUEBA})),
        usuario_id=administrador.id,
        documentos_detectados=30,
    )


def _foto_de_la_configuracion(db) -> dict:
    """Todas las columnas de la fila activa, releída desde la base de datos."""
    db.expire_all()
    fila = RepositorioConfigRepository(db).get_activa()
    columnas = inspect(ConfiguracionRepositorioModel).column_attrs
    return {c.key: getattr(fila, c.key) for c in columnas}


def _cuerpo_gdrive(carpeta: str, credenciales_json: str) -> dict:
    return {
        "tipo": TIPO_GDRIVE,
        "carpeta": carpeta,
        "credenciales": {"credenciales_json": credenciales_json},
    }


# --- Criterio 1: el administrador registra credenciales y ruta ----------------------


def test_hu05_criterio1_el_administrador_registra_credenciales_y_carpeta(cliente, db, administrador, origen):
    origen(ACEPTA_30)

    respuesta = cliente.put(
        "/configuracion/repositorio", json=_cuerpo_gdrive("carpeta-de-hojas-de-vida", SECRETO_DE_PRUEBA)
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["guardado"] is True
    assert cuerpo["configuracion"]["carpeta"] == "carpeta-de-hojas-de-vida"

    # Quedó persistida, a nombre de quien la registró, y la consulta la devuelve.
    fila = RepositorioConfigRepository(db).get_activa()
    assert fila.tipo == TIPO_GDRIVE
    assert fila.carpeta == "carpeta-de-hojas-de-vida"
    assert fila.actualizado_por == administrador.id
    assert fila.documentos_detectados == 30

    consulta = cliente.get("/configuracion/repositorio").json()
    assert consulta["configurado"] is True
    assert consulta["carpeta"] == "carpeta-de-hojas-de-vida"


def test_hu05_criterio1_un_usuario_que_no_es_administrador_no_puede_registrar(
    cliente_coordinador, db, origen
):
    origen(ACEPTA_30)

    respuesta = cliente_coordinador.put(
        "/configuracion/repositorio", json=_cuerpo_gdrive("carpeta-de-hojas-de-vida", SECRETO_DE_PRUEBA)
    )

    assert respuesta.status_code == 403
    assert RepositorioConfigRepository(db).get_activa() is None


def test_hu05_criterio1_se_puede_cambiar_solo_la_carpeta_sin_reescribir_el_secreto(
    cliente, db, configuracion_vigente, origen
):
    origen(ACEPTA_30)
    antes = json.loads(descifrar(RepositorioConfigRepository(db).get_activa().credenciales_cifradas))

    # El formulario llega con la credencial vacía: solo cambió el ID de la carpeta.
    respuesta = cliente.put(
        "/configuracion/repositorio",
        json={"tipo": TIPO_GDRIVE, "carpeta": "carpeta-nueva", "credenciales": {"credenciales_json": ""}},
    )

    assert respuesta.json()["guardado"] is True
    fila = RepositorioConfigRepository(db).get_activa()
    assert fila.carpeta == "carpeta-nueva"
    assert json.loads(descifrar(fila.credenciales_cifradas)) == antes


# --- Criterio 2: las credenciales se almacenan cifradas ---------------------------


@pytest.mark.parametrize(
    ("tipo", "credenciales", "campo_secreto"),
    [
        pytest.param(
            TIPO_GDRIVE,
            {"credenciales_json": SECRETO_DE_PRUEBA},
            "credenciales_json",
            id="google_drive",
        ),
        pytest.param(
            TIPO_ONEDRIVE,
            {
                "tenant_id": "tenant-0001",
                "client_id": "cliente-0002",
                "client_secret": "S3cr3to-de-OneDrive-9f8e7d6c",
                "drive_id": "unidad-0003",
            },
            "client_secret",
            id="onedrive",
        ),
    ],
)
def test_hu05_criterio2_ninguna_credencial_queda_en_claro_ni_en_tabla_ni_en_api(
    cliente, db, origen, tipo, credenciales, campo_secreto
):
    origen(ACEPTA_30)
    secreto = credenciales[campo_secreto]

    guardado = cliente.put(
        "/configuracion/repositorio",
        json={"tipo": tipo, "carpeta": "carpeta-de-hojas-de-vida", "credenciales": credenciales},
    )
    assert guardado.json()["guardado"] is True
    consultado = cliente.get("/configuracion/repositorio")

    # En la tabla: ningún valor de la credencial aparece en claro, y aun así se
    # recupera íntegro al descifrar (es cifrado, no pérdida de datos).
    almacenado = db.query(ConfiguracionRepositorioModel).one().credenciales_cifradas
    for valor in credenciales.values():
        assert valor not in almacenado
    assert json.loads(descifrar(almacenado)) == credenciales

    # En la API: ni el guardado ni la consulta devuelven el secreto.
    for respuesta in (guardado, consultado):
        assert secreto not in respuesta.text
        assert secreto[:8] not in respuesta.text
    enmascarado = consultado.json()["credenciales"][campo_secreto]
    assert enmascarado != secreto
    assert enmascarado.startswith("•")


# --- Criterio 3: "Probar conexión" informa éxito y cantidad de documentos ------------


def test_hu05_criterio3_probar_conexion_informa_exito_y_cantidad_de_documentos(cliente, db, origen):
    origen(ACEPTA_30)

    respuesta = cliente.post(
        "/configuracion/repositorio/probar",
        json=_cuerpo_gdrive("carpeta-de-hojas-de-vida", SECRETO_DE_PRUEBA),
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["exito"] is True
    assert cuerpo["documentos_detectados"] == 30
    assert "30 hojas de vida" in cuerpo["mensaje"]
    # Probar no es guardar.
    assert RepositorioConfigRepository(db).get_activa() is None


def test_hu05_criterio3_probar_conexion_informa_el_fallo_con_su_motivo(cliente, origen):
    origen(RECHAZA)

    respuesta = cliente.post(
        "/configuracion/repositorio/probar",
        json=_cuerpo_gdrive("carpeta-de-hojas-de-vida", SECRETO_DE_PRUEBA),
    )

    cuerpo = respuesta.json()
    assert respuesta.status_code == 200
    assert cuerpo["exito"] is False
    assert cuerpo["mensaje"] == "Credenciales inválidas."
    assert "llave privada" in cuerpo["detalle"]


def test_hu05_criterio3_revalidar_la_conexion_guardada_actualiza_el_conteo(cliente, origen):
    origen(ACEPTA_30)
    cliente.put(
        "/configuracion/repositorio", json=_cuerpo_gdrive("carpeta-de-hojas-de-vida", SECRETO_DE_PRUEBA)
    )

    origen(ResultadoPrueba(exito=True, documentos_detectados=35, mensaje="Conexión exitosa."))
    revalidada = cliente.post("/configuracion/repositorio/probar-guardada").json()

    assert revalidada["exito"] is True
    assert revalidada["documentos_detectados"] == 35
    assert cliente.get("/configuracion/repositorio").json()["documentos_detectados"] == 35


@pytest.mark.parametrize(
    ("codigo_http", "mensaje_esperado", "pista_en_el_detalle"),
    [
        pytest.param(
            404, "Carpeta no encontrada.", "compartida con el correo", id="404_no_existe_o_no_compartida"
        ),
        pytest.param(
            403, "Sin permiso de lectura.", "Compártela con su correo", id="403_sin_permiso_de_lectura"
        ),
    ],
)
def test_hu05_criterio3_carpeta_inexistente_o_sin_permiso_informa_el_motivo_sin_guardar(
    cliente, db, configuracion_vigente, monkeypatch, codigo_http, mensaje_esperado, pista_en_el_detalle
):
    """
    Credenciales correctas, carpeta equivocada. El token se da por bueno y solo
    se simula lo que responde Drive; el mensaje lo arma el cliente real.
    """
    monkeypatch.setattr(GoogleDriveClient, "_obtener_token", lambda self: "token-de-prueba")
    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: httpx.Response(codigo_http, json={}))
    antes = _foto_de_la_configuracion(db)

    respuesta = cliente.post(
        "/configuracion/repositorio/probar",
        json=_cuerpo_gdrive("id-de-carpeta-equivocada", SECRETO_DE_PRUEBA),
    )

    prueba = respuesta.json()
    assert prueba["exito"] is False
    assert prueba["mensaje"] == mensaje_esperado
    assert pista_en_el_detalle in prueba["detalle"]
    assert _foto_de_la_configuracion(db) == antes


# --- Criterio 4: credencial inválida → motivo, guardado=false, config intacta -------


def _llave_privada_valida() -> str:
    """RSA de juguete generada al vuelo: tiene forma de llave real, no abre nada."""
    llave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return llave.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()


JSON_BIEN_FORMADO_PERO_REVOCADO = json.dumps(
    {
        "type": "service_account",
        "project_id": "proyecto-de-prueba",
        "private_key_id": "llave-revocada-de-prueba",
        "private_key": _llave_privada_valida(),
        "client_email": "lector@proyecto-de-prueba.iam.gserviceaccount.com",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
)


def _google_rechaza_la_llave(self, url, method="GET", body=None, headers=None, timeout=None, **kwargs):
    """Lo que responde oauth2.googleapis.com ante una llave revocada o alterada."""
    return _RespuestaTransporte(
        httpx.Response(400, json={"error": "invalid_grant", "error_description": "Invalid JWT Signature."})
    )


@pytest.mark.parametrize("endpoint", ["probar", "guardar"])
@pytest.mark.parametrize(
    ("credencial", "motivo_esperado", "google_rechaza"),
    [
        pytest.param("{esto no es json", "no es un JSON válido", False, id="json_ilegible"),
        pytest.param('{"type": "service_account"}', "faltan los campos", False, id="json_incompleto"),
        pytest.param(
            JSON_BIEN_FORMADO_PERO_REVOCADO,
            "Google rechazó la cuenta de servicio",
            True,
            id="bien_formado_rechazado_por_google",
        ),
    ],
)
def test_hu05_criterio4_credencial_invalida_informa_el_motivo_y_no_sobrescribe(
    cliente,
    db,
    configuracion_vigente,
    sin_red,
    monkeypatch,
    endpoint,
    credencial,
    motivo_esperado,
    google_rechaza,
):
    if google_rechaza:
        monkeypatch.setattr(_TransporteHttpx, "__call__", _google_rechaza_la_llave)
    antes = _foto_de_la_configuracion(db)
    cuerpo = _cuerpo_gdrive("carpeta-que-no-debe-guardarse", credencial)

    if endpoint == "probar":
        respuesta = cliente.post("/configuracion/repositorio/probar", json=cuerpo)
        prueba = respuesta.json()
    else:
        respuesta = cliente.put("/configuracion/repositorio", json=cuerpo)
        assert respuesta.json()["guardado"] is False
        assert respuesta.json()["configuracion"] is None
        prueba = respuesta.json()["prueba"]

    # El motivo llega hasta la pantalla y no es un mensaje genérico.
    assert respuesta.status_code == 200
    assert prueba["exito"] is False
    assert prueba["mensaje"] == "Credenciales inválidas."
    assert motivo_esperado in prueba["detalle"]

    # La fila anterior es idéntica en todas sus columnas: tipo, carpeta,
    # credenciales cifradas, fecha de validación, conteo y quién la registró.
    assert _foto_de_la_configuracion(db) == antes
    assert db.query(ConfiguracionRepositorioModel).count() == 1


# --- Criterio 5: las búsquedas usan la carpeta configurada ---------------------


class ClientePorCarpeta(ClienteFalso):
    """Origen falso cuyo único documento depende de la carpeta con la que se construyó."""

    def __init__(self, carpeta: str):
        super().__init__(ResultadoPrueba(exito=True, documentos_detectados=1, mensaje="ok"))
        self.carpeta = carpeta

    def listar_documentos(self, cursor=None):
        documento = DocumentoRepositorio(
            id_documento=f"doc-de-{self.carpeta}",
            nombre_archivo=f"cv-de-{self.carpeta}.pdf",
            ruta=f"/{self.carpeta}/cv.pdf",
            url_web=None,
            formato="PDF",
            hash_contenido=f"hash-{self.carpeta}",
            fecha_modificacion=datetime(2026, 9, 1),
            tamanio=10,
        )
        return [documento], None


@pytest.fixture
def clientes_construidos(monkeypatch):
    """
    Registra con qué (tipo, carpeta) se construye cada cliente del origen.

    Sustituye la fábrica en el servicio de configuración, que es por donde pasan
    la sincronización, la indexación y las búsquedas. Impide además que la
    sincronización mande a indexar: aquí solo importa qué carpeta se consulta.
    """
    construidos: list[tuple[str, str]] = []

    def crear_cliente_registrado(tipo, carpeta, credenciales):
        construidos.append((tipo, carpeta))
        return ClientePorCarpeta(carpeta)

    monkeypatch.setattr(servicio_config, "crear_cliente", crear_cliente_registrado)
    monkeypatch.setattr(scheduler, "encolar", lambda *args, **kwargs: None)
    return construidos


def _registrar_carpeta(db, administrador, carpeta: str) -> None:
    guardado, _ = RepositorioConfigService(db).guardar(
        TIPO_GDRIVE, carpeta, {"credenciales_json": SECRETO_DE_PRUEBA}, usuario_id=administrador.id
    )
    assert guardado


def _nombres_de_hojas(db) -> set[str]:
    db.expire_all()
    return {hoja.nombre_archivo for hoja in db.query(HojaDeVidaModel).all()}


def test_hu05_criterio5_la_sincronizacion_lee_la_carpeta_guardada(db, administrador, clientes_construidos):
    _registrar_carpeta(db, administrador, "carpeta-a")
    clientes_construidos.clear()  # se descarta el cliente de la prueba de guardado

    SincronizacionService(db).sincronizar()

    assert clientes_construidos == [(TIPO_GDRIVE, "carpeta-a")]
    assert _nombres_de_hojas(db) == {"cv-de-carpeta-a.pdf"}


def test_hu05_criterio5_la_indexacion_usa_el_cliente_de_la_carpeta_guardada(
    db, administrador, clientes_construidos
):
    _registrar_carpeta(db, administrador, "carpeta-a")
    clientes_construidos.clear()

    indexacion = IndexacionService(db, llm=object())

    assert clientes_construidos == [(TIPO_GDRIVE, "carpeta-a")]
    assert indexacion.repositorio.carpeta == "carpeta-a"


def test_hu05_criterio5_al_cambiar_la_carpeta_la_siguiente_sincronizacion_usa_la_nueva(
    db, administrador, clientes_construidos
):
    _registrar_carpeta(db, administrador, "carpeta-a")
    SincronizacionService(db).sincronizar()
    assert "cv-de-carpeta-a.pdf" in _nombres_de_hojas(db)

    _registrar_carpeta(db, administrador, "carpeta-b")
    clientes_construidos.clear()
    SincronizacionService(db).sincronizar()

    assert clientes_construidos == [(TIPO_GDRIVE, "carpeta-b")]
    assert "cv-de-carpeta-b.pdf" in _nombres_de_hojas(db)
    # Y la indexación posterior también arranca con la carpeta nueva.
    assert IndexacionService(db, llm=object()).repositorio.carpeta == "carpeta-b"


def test_hu05_criterio5_la_sincronizacion_previa_a_una_busqueda_usa_la_carpeta_vigente(
    db, administrador, clientes_construidos
):
    """
    Camino real de una búsqueda: el worker sincroniza el origen configurado
    antes de analizar (`busqueda_worker._sincronizar_repositorio`).
    """
    _registrar_carpeta(db, administrador, "carpeta-a")
    _registrar_carpeta(db, administrador, "carpeta-b")
    clientes_construidos.clear()

    _sincronizar_repositorio()

    assert clientes_construidos == [(TIPO_GDRIVE, "carpeta-b")]
    assert _nombres_de_hojas(db) == {"cv-de-carpeta-b.pdf"}


def _sin_conexion_con_google(self, url, method="GET", body=None, headers=None, timeout=None, **kwargs):
    raise httpx.ConnectError("All connection attempts failed")


@pytest.mark.parametrize("endpoint", ["probar", "guardar"])
def test_hu05_criterio4_sin_conexion_con_google_no_se_reporta_como_credencial_invalida(
    cliente, db, configuracion_vigente, sin_red, monkeypatch, endpoint
):
    """
    Si Google no responde, las credenciales no fueron juzgadas: decirle al
    administrador que son inválidas lo llevaría a rotar una llave que estaba bien.
    El motivo correcto es que no se pudo contactar a Google, y la configuración
    anterior sigue intacta igual que en cualquier otro fallo.
    """
    monkeypatch.setattr(_TransporteHttpx, "__call__", _sin_conexion_con_google)
    antes = _foto_de_la_configuracion(db)
    cuerpo = _cuerpo_gdrive("carpeta-que-no-debe-guardarse", JSON_BIEN_FORMADO_PERO_REVOCADO)

    if endpoint == "probar":
        prueba = cliente.post("/configuracion/repositorio/probar", json=cuerpo).json()
    else:
        respuesta = cliente.put("/configuracion/repositorio", json=cuerpo).json()
        assert respuesta["guardado"] is False
        prueba = respuesta["prueba"]

    assert prueba["exito"] is False
    assert prueba["mensaje"] == "No se pudo contactar a Google."
    assert "Credenciales inválidas" not in prueba["mensaje"]
    assert _foto_de_la_configuracion(db) == antes
