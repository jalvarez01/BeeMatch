"""
Contrato común de los orígenes de hojas de vida.

BeeMatch leía únicamente de OneDrive. Este módulo extrae la interfaz que ese
cliente ya cumplía de facto, para que el origen sea intercambiable (OneDrive,
Google Drive) sin tocar la sincronización, la indexación ni el motor de
matching.

RNF11 sigue vigente para toda implementación: acceso de SOLO LECTURA. Ninguna
implementación puede escribir, editar ni borrar en el repositorio del cliente.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

# Tipos de origen soportados. Se guardan en `configuracion_repositorio.tipo`.
TIPO_ONEDRIVE = "ONEDRIVE"
TIPO_GDRIVE = "GDRIVE"
TIPOS_VALIDOS = (TIPO_ONEDRIVE, TIPO_GDRIVE)


class RepositorioError(Exception):
    """Fallo de conexión con el repositorio de documentos (HU-26, RNF18)."""


class CredencialesInvalidasError(RepositorioError):
    """El proveedor rechazó las credenciales registradas."""


class RepositorioNoEncontradoError(RepositorioError):
    """El repositorio existe pero la carpeta configurada no."""


class SinPermisoLecturaError(RepositorioError):
    """Las credenciales son válidas pero no tienen lectura sobre la carpeta."""


@dataclass
class DocumentoRepositorio:
    """
    Referencia a un documento del origen configurado (RNF14: no se copia el
    archivo, solo su referencia).

    `hash_contenido` es el discriminador de cambios (RD5): cada proveedor
    aporta el suyo (quickXorHash en OneDrive, md5Checksum en Google Drive). Si
    el proveedor no entrega checksum, queda en None y la detección de cambios
    recae en `fecha_modificacion`.
    """

    id_documento: str
    nombre_archivo: str
    ruta: str
    url_web: Optional[str]
    formato: str
    hash_contenido: Optional[str]
    fecha_modificacion: Optional[datetime]
    tamanio: int


@dataclass
class ResultadoPrueba:
    """Respuesta de "Probar conexión" (HU-05)."""

    exito: bool
    documentos_detectados: int = 0
    mensaje: str = ""
    detalle: Optional[str] = None


class RepositorioDocumentos(ABC):
    """
    Origen de hojas de vida. Toda implementación traduce los errores del
    proveedor a mensajes en español, porque llegan directo a la pantalla de
    Configuración del administrador (HU-05).
    """

    @abstractmethod
    def probar_conexion(self) -> ResultadoPrueba:
        """
        Valida credenciales y carpeta, y cuenta los documentos detectados.

        Nunca lanza excepción: el fallo viaja dentro del ResultadoPrueba para
        poder mostrarse sin guardar nada.
        """

    @abstractmethod
    def listar_documentos(
        self, cursor: Optional[str] = None
    ) -> tuple[list[DocumentoRepositorio], Optional[str]]:
        """
        Documentos del origen y el cursor para la siguiente corrida.

        El cursor es opaco y propio de cada proveedor: delta link en Microsoft
        Graph, pageToken en Google Drive. Quien lo persiste no lo interpreta.
        """

    @abstractmethod
    def descargar(self, id_documento: str) -> bytes:
        """Contenido del documento en memoria. No se persiste en disco (RNF14)."""
