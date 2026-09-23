"""
Andamiaje de las pruebas.

Dos reglas que valen para todo el paquete:

- La base de datos es un SQLite temporal, nunca `data/beematch.db`. Se fija
  DATABASE_URL antes de importar `backend`, porque el engine se construye al
  importar el módulo de persistencia.
- Ninguna prueba sale a la red. El origen de hojas de vida se sustituye por un
  cliente falso que devuelve el ResultadoPrueba que cada caso necesita, así que
  no hacen falta credenciales de Google ni de Microsoft para ejecutarlas.
"""

import os
import tempfile

os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(
    tempfile.mkdtemp(prefix="beematch-pruebas-"), "pruebas.db"
)

import pytest  # noqa: E402

from backend.infrastructure.persistence import models  # noqa: E402,F401  (registra las tablas)
from backend.infrastructure.persistence.database import Base, SessionLocal, engine  # noqa: E402
from backend.infrastructure.persistence.models.usuario import UsuarioModel  # noqa: E402
from backend.infrastructure.repositorio.base import (  # noqa: E402
    DocumentoRepositorio,
    RepositorioDocumentos,
    ResultadoPrueba,
)
from backend.security import ROL_ADMINISTRADOR  # noqa: E402

# Credencial de juguete con la forma de un JSON de cuenta de servicio. No es
# una llave real: lo único que importa es poder buscarla en claro después.
SECRETO_DE_PRUEBA = (
    '{"type": "service_account", "client_email": "lector@ejemplo.iam.gserviceaccount.com", '
    '"private_key": "-----BEGIN PRIVATE KEY-----AQUI-VA-LA-LLAVE-----END PRIVATE KEY-----", '
    '"token_uri": "https://oauth2.googleapis.com/token"}'
)


class ClienteFalso(RepositorioDocumentos):
    """
    Origen de hojas de vida de mentira.

    Cumple el contrato completo para poder pasar por el mismo camino que el
    cliente real, y se construye con el resultado que debe devolver la prueba
    de conexión: así un caso simula credenciales válidas y otro el rechazo del
    proveedor, sin depender de Google.
    """

    def __init__(self, resultado: ResultadoPrueba):
        self.resultado = resultado

    def probar_conexion(self) -> ResultadoPrueba:
        return self.resultado

    def listar_documentos(self, cursor=None) -> tuple[list[DocumentoRepositorio], None]:
        return [], None

    def descargar(self, id_documento: str) -> bytes:
        return b""


@pytest.fixture(autouse=True)
def base_limpia():
    """Cada prueba arranca con las tablas vacías."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    sesion = SessionLocal()
    try:
        yield sesion
    finally:
        sesion.close()


@pytest.fixture
def administrador(db):
    usuario = UsuarioModel(
        nombre="Administradora de prueba",
        correo="admin@beematch.test",
        rol=ROL_ADMINISTRADOR,
        activo=True,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


@pytest.fixture
def origen(monkeypatch):
    """
    Sustituye la fábrica de clientes por el cliente falso.

    Devuelve una función que fija el resultado de la próxima prueba de
    conexión, de modo que el caso decida si el proveedor acepta o rechaza las
    credenciales.
    """
    import backend.domain.services.repositorio_config_service as servicio

    estado = {"resultado": ResultadoPrueba(exito=True, documentos_detectados=0, mensaje="")}

    def crear_cliente_falso(tipo, carpeta, credenciales):
        return ClienteFalso(estado["resultado"])

    monkeypatch.setattr(servicio, "crear_cliente", crear_cliente_falso)

    def configurar(resultado: ResultadoPrueba):
        estado["resultado"] = resultado

    return configurar
