"""
Cliente de Microsoft Graph.

Acceso de SOLO LECTURA a la carpeta de hojas de vida (RNF11): BeeMatch nunca
escribe, edita ni borra en OneDrive.

Las credenciales se reciben por constructor y provienen de la configuración que
el administrador registró en la aplicación (HU-05), no de variables de entorno.
Eso permite validar una configuración nueva sin tocar la que está en uso.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import httpx

from backend.config import GRAPH_SCOPES

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
EXTENSIONES_VALIDAS = (".pdf", ".docx", ".doc")


class OneDriveError(Exception):
    """Fallo de conexión con el repositorio (HU-26, RNF18)."""


class CredencialesInvalidasError(OneDriveError):
    """El tenant, el client id o el secret fueron rechazados por Entra ID."""


class RepositorioNoEncontradoError(OneDriveError):
    """El drive existe pero la carpeta configurada no."""


@dataclass
class DocumentoOneDrive:
    id_onedrive: str
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


class GraphClient:
    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        drive_id: str,
        carpeta_cv: str,
    ):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.drive_id = drive_id
        self.carpeta_cv = self._normalizar_carpeta(carpeta_cv)
        self._token: Optional[str] = None

    @classmethod
    def desde_configuracion(cls, config, client_secret: str) -> "GraphClient":
        """Construye el cliente a partir del registro de configuración activo."""
        return cls(
            tenant_id=config.tenant_id,
            client_id=config.client_id,
            client_secret=client_secret,
            drive_id=config.drive_id,
            carpeta_cv=config.carpeta_cv,
        )

    @staticmethod
    def _normalizar_carpeta(carpeta: str) -> str:
        limpia = (carpeta or "").strip().rstrip("/")
        if not limpia:
            return ""
        return limpia if limpia.startswith("/") else f"/{limpia}"

    # --- Autenticación -------------------------------------------------------

    def _obtener_token(self) -> str:
        """Client credentials contra Entra ID."""
        if self._token:
            return self._token

        url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        try:
            respuesta = httpx.post(
                url,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": " ".join(GRAPH_SCOPES),
                    "grant_type": "client_credentials",
                },
                timeout=30,
            )
        except httpx.HTTPError as exc:
            raise OneDriveError(f"No se pudo contactar a Microsoft: {exc}")

        if respuesta.status_code != 200:
            raise CredencialesInvalidasError(self._describir_error_token(respuesta))

        self._token = respuesta.json()["access_token"]
        return self._token

    @staticmethod
    def _describir_error_token(respuesta: httpx.Response) -> str:
        """Traduce el error de Entra ID a un motivo legible (HU-05)."""
        try:
            cuerpo = respuesta.json()
        except ValueError:
            return f"Microsoft rechazó las credenciales (HTTP {respuesta.status_code})."

        codigo = cuerpo.get("error", "")
        descripcion = cuerpo.get("error_description", "")

        if "AADSTS700016" in descripcion:
            return "El Client ID no existe en el tenant indicado."
        if "AADSTS7000215" in descripcion:
            return "El Client Secret es incorrecto o está vencido."
        if "AADSTS90002" in descripcion:
            return "El Tenant ID no existe."
        if codigo == "invalid_client":
            return "Client ID o Client Secret inválidos."
        if codigo == "unauthorized_client":
            return "La aplicación registrada no tiene permiso para este flujo de autenticación."

        return descripcion.split("\r")[0] if descripcion else "Credenciales rechazadas por Entra ID."

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._obtener_token()}"}

    # --- Prueba de conexión (HU-05) ------------------------------------------

    def probar_conexion(self) -> ResultadoPrueba:
        """
        Valida credenciales y ruta, y cuenta los documentos de la carpeta.
        Nunca lanza excepción: devuelve el motivo del fallo para mostrarlo.
        """
        try:
            self._obtener_token()
        except CredencialesInvalidasError as exc:
            return ResultadoPrueba(False, mensaje="Credenciales inválidas.", detalle=str(exc))
        except OneDriveError as exc:
            return ResultadoPrueba(False, mensaje="No se pudo contactar a Microsoft.", detalle=str(exc))

        try:
            documentos = self.contar_documentos()
        except RepositorioNoEncontradoError as exc:
            return ResultadoPrueba(False, mensaje="Carpeta no encontrada.", detalle=str(exc))
        except OneDriveError as exc:
            return ResultadoPrueba(False, mensaje="Error consultando el repositorio.", detalle=str(exc))

        return ResultadoPrueba(
            exito=True,
            documentos_detectados=documentos,
            mensaje=(
                f"Conexión exitosa. Se detectaron {documentos} hojas de vida "
                f"en {self.carpeta_cv or 'la raíz del repositorio'}."
            ),
        )

    def contar_documentos(self) -> int:
        """Cuenta los PDF y Word de la carpeta configurada, recorriendo páginas."""
        url = self._url_listado()
        total = 0

        while url:
            cuerpo = self._get(url)
            for item in cuerpo.get("value", []):
                nombre = item.get("name", "")
                if "folder" not in item and nombre.lower().endswith(EXTENSIONES_VALIDAS):
                    total += 1
            url = cuerpo.get("@odata.nextLink")

        return total

    def _url_listado(self) -> str:
        if self.carpeta_cv:
            return f"{GRAPH_BASE}/drives/{self.drive_id}/root:{self.carpeta_cv}:/children"
        return f"{GRAPH_BASE}/drives/{self.drive_id}/root/children"

    def _get(self, url: str) -> dict:
        try:
            respuesta = httpx.get(url, headers=self._headers(), timeout=60)
        except httpx.HTTPError as exc:
            raise OneDriveError(f"Error de red consultando OneDrive: {exc}")

        if respuesta.status_code == 404:
            raise RepositorioNoEncontradoError(
                f"No existe la carpeta '{self.carpeta_cv}' en el repositorio indicado. "
                "Verifica el Drive ID y la ruta."
            )
        if respuesta.status_code == 403:
            raise OneDriveError(
                "La aplicación no tiene permiso de lectura sobre este repositorio. "
                "Revisa los permisos concedidos en Entra ID."
            )
        if respuesta.status_code >= 400:
            raise OneDriveError(f"OneDrive respondió HTTP {respuesta.status_code}.")

        return respuesta.json()

    # --- Sincronización ------------------------------------------------------

    def listar_documentos(
        self, delta_link: Optional[str] = None
    ) -> tuple[list[DocumentoOneDrive], Optional[str]]:
        """
        Delta query: la primera corrida trae todo, las siguientes solo lo que
        cambió. Retorna (documentos, nuevo_delta_link).
        """
        if delta_link:
            url = delta_link
        elif self.carpeta_cv:
            url = f"{GRAPH_BASE}/drives/{self.drive_id}/root:{self.carpeta_cv}:/delta"
        else:
            url = f"{GRAPH_BASE}/drives/{self.drive_id}/root/delta"

        documentos: list[DocumentoOneDrive] = []
        siguiente_delta: Optional[str] = None

        while url:
            cuerpo = self._get(url)
            for item in cuerpo.get("value", []):
                documento = self._mapear(item)
                if documento:
                    documentos.append(documento)

            url = cuerpo.get("@odata.nextLink")
            siguiente_delta = cuerpo.get("@odata.deltaLink", siguiente_delta)

        return documentos, siguiente_delta

    def descargar(self, id_onedrive: str) -> bytes:
        """Descarga el contenido en memoria. El archivo no se persiste (RNF14)."""
        url = f"{GRAPH_BASE}/drives/{self.drive_id}/items/{id_onedrive}/content"
        try:
            respuesta = httpx.get(url, headers=self._headers(), timeout=120, follow_redirects=True)
            respuesta.raise_for_status()
        except httpx.HTTPError as exc:
            raise OneDriveError(f"No fue posible descargar el documento: {exc}")
        return respuesta.content

    @staticmethod
    def _mapear(item: dict) -> Optional[DocumentoOneDrive]:
        nombre = item.get("name", "")
        if "folder" in item or not nombre.lower().endswith(EXTENSIONES_VALIDAS):
            return None

        modificado = item.get("lastModifiedDateTime")
        return DocumentoOneDrive(
            id_onedrive=item["id"],
            nombre_archivo=nombre,
            ruta=item.get("parentReference", {}).get("path", ""),
            url_web=item.get("webUrl"),
            formato="PDF" if nombre.lower().endswith(".pdf") else "DOCX",
            hash_contenido=item.get("file", {}).get("hashes", {}).get("quickXorHash"),
            fecha_modificacion=(
                datetime.fromisoformat(modificado.replace("Z", "+00:00")) if modificado else None
            ),
            tamanio=item.get("size", 0),
        )
