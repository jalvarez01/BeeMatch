"""
HU-05, cuarto criterio de aceptación:

    "Si las credenciales son inválidas se muestra el motivo del error sin
    sobrescribir la configuración anterior."

Lo que se verifica es la garantía completa: que `guardar` valide primero, que
informe el motivo, y que la configuración que ya estaba en uso siga íntegra
—tipo, carpeta, credenciales y fecha de validación— después del intento
fallido. Es el criterio que más duele si se rompe: un administrador que se
equivoca al escribir el secreto dejaría a BeeMatch sin origen de hojas de vida.
"""

import json

from backend.domain.services.repositorio_config_service import RepositorioConfigService
from backend.infrastructure.crypto import descifrar
from backend.infrastructure.persistence.repositories.configuracion_repo import (
    RepositorioConfigRepository,
)
from backend.infrastructure.repositorio.base import TIPO_GDRIVE, ResultadoPrueba
from tests.conftest import SECRETO_DE_PRUEBA

CARPETA_BUENA = "carpeta-en-uso"
CARPETA_NUEVA = "carpeta-con-credencial-mala"

ACEPTA = ResultadoPrueba(
    exito=True, documentos_detectados=30, mensaje="Conexión exitosa. Se detectaron 30 hojas de vida."
)
RECHAZA = ResultadoPrueba(
    exito=False,
    mensaje="Credenciales inválidas.",
    detalle="La llave privada del JSON está corrupta o incompleta.",
)


def _configuracion_valida(servicio: RepositorioConfigService) -> None:
    guardado, _ = servicio.guardar(
        TIPO_GDRIVE, CARPETA_BUENA, {"credenciales_json": SECRETO_DE_PRUEBA}
    )
    assert guardado, "la configuración de partida debía guardarse"


def test_credenciales_invalidas_no_sobrescriben_la_configuracion_anterior(db, origen):
    servicio = RepositorioConfigService(db)

    origen(ACEPTA)
    _configuracion_valida(servicio)

    anterior = RepositorioConfigRepository(db).get_activa()
    validacion_anterior = anterior.ultima_validacion
    documentos_anteriores = anterior.documentos_detectados

    # El administrador se equivoca: otra carpeta y una credencial que el
    # proveedor rechaza.
    origen(RECHAZA)
    guardado, resultado = servicio.guardar(
        TIPO_GDRIVE, CARPETA_NUEVA, {"credenciales_json": '{"type": "service_account"}'}
    )

    assert guardado is False
    assert resultado.exito is False

    # El motivo llega hasta quien llamó, no se traga ni se reemplaza por un
    # mensaje genérico: es lo que la interfaz muestra al administrador.
    assert resultado.mensaje == "Credenciales inválidas."
    assert "llave privada" in resultado.detalle

    vigente = RepositorioConfigRepository(db).get_activa()
    assert vigente.carpeta == CARPETA_BUENA
    assert vigente.tipo == TIPO_GDRIVE
    # Lo cifrado es el diccionario de credenciales completo, tal como lo
    # interpreta el cliente del proveedor.
    assert json.loads(descifrar(vigente.credenciales_cifradas)) == {
        "credenciales_json": SECRETO_DE_PRUEBA
    }

    # Tampoco se toca el rastro de la última validación buena: un intento
    # fallido no es una validación.
    assert vigente.ultima_validacion == validacion_anterior
    assert vigente.documentos_detectados == documentos_anteriores

    # Y solo sigue existiendo una configuración activa: el intento fallido no
    # dejó una fila huérfana.
    assert db.query(type(vigente)).count() == 1


def test_probar_no_persiste_nada(db, origen):
    """
    "Probar conexión" es una validación, no un guardado: con credenciales
    válidas y sin configuración previa, la tabla debe seguir vacía.
    """
    servicio = RepositorioConfigService(db)

    origen(ACEPTA)
    resultado = servicio.probar(TIPO_GDRIVE, CARPETA_BUENA, {"credenciales_json": SECRETO_DE_PRUEBA})

    assert resultado.exito is True
    assert resultado.documentos_detectados == 30
    assert RepositorioConfigRepository(db).get_activa() is None
