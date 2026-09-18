"""
Cliente de Google Drive.

Origen alternativo a OneDrive cuando el tenant del cliente no está disponible.
Cumple el mismo contrato (RepositorioDocumentos) y la misma regla de acceso de
SOLO LECTURA (RNF11): el scope solicitado es drive.readonly, que no permite
escribir aunque el código lo intentara.

La autenticación es por service account: el administrador pega el JSON de la
cuenta de servicio en Configuración y comparte la carpeta de hojas de vida con
el correo de esa cuenta. No hay consentimiento interactivo, igual que el flujo
client-credentials de Graph.
"""

import json
from datetime import datetime
from typing import Optional

import httpx

from backend.infrastructure.repositorio.base import (
    CredencialesInvalidasError,
    DocumentoRepositorio,
    RepositorioDocumentos,
    RepositorioError,
    RepositorioNoEncontradoError,
    ResultadoPrueba,
    SinPermisoLecturaError,
)

DRIVE_BASE = "https://www.googleapis.com/drive/v3"
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

MIME_PDF = "application/pdf"
MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MIME_DOC = "application/msword"
MIME_GOOGLE_DOC = "application/vnd.google-apps.document"

# Solo hojas de vida: PDF, Word y documentos nativos de Google.
MIMES_VALIDOS = (MIME_PDF, MIME_DOCX, MIME_DOC, MIME_GOOGLE_DOC)

# Formato con el que se registra la hoja de vida. Determina qué loader usa la
# indexación, por eso los Google Docs figuran como PDF: es el formato al que se
# exportan al descargarlos.
FORMATO_POR_MIME = {
    MIME_PDF: "PDF",
    MIME_DOCX: "DOCX",
    MIME_DOC: "DOCX",
    MIME_GOOGLE_DOC: "PDF",
}

CAMPOS_ARCHIVO = "id,name,mimeType,md5Checksum,modifiedTime,size,webViewLink"


class _RespuestaTransporte:
    """Adapta una respuesta de httpx a lo que espera google-auth."""

    def __init__(self, respuesta: httpx.Response):
        self.status = respuesta.status_code
        self.headers = respuesta.headers
        self.data = respuesta.content


class _TransporteHttpx:
    """
    Transporte HTTP para google-auth sobre httpx.

    google-auth trae transportes para `requests` y `urllib3`; usar cualquiera
    de los dos obligaría a sumar un segundo cliente HTTP al proyecto, que ya
    habla con Microsoft Graph por httpx. La interfaz que google-auth espera es
    solo este callable.
    """

    def __call__(self, url, method="GET", body=None, headers=None, timeout=None, **kwargs):
        respuesta = httpx.request(
            method,
            url,
            content=body,
            headers=headers,
            timeout=timeout or 30,
            follow_redirects=True,
        )
        return _RespuestaTransporte(respuesta)


class GoogleDriveClient(RepositorioDocumentos):
    def __init__(self, credenciales_json: str, folder_id: str):
        self.credenciales_json = credenciales_json
        self.folder_id = (folder_id or "").strip()
        self._token: Optional[str] = None

    @classmethod
    def desde_credenciales(cls, credenciales: dict, carpeta: str) -> "GoogleDriveClient":
        """Construye el cliente desde el JSON de credenciales descifrado."""
        return cls(
            credenciales_json=credenciales.get("credenciales_json", ""),
            folder_id=carpeta,
        )

    # --- Autenticación -------------------------------------------------------

    def _obtener_token(self) -> str:
        """
        Token OAuth2 firmado con la llave privada de la cuenta de servicio.

        google-auth hace el intercambio JWT -> access token contra
        oauth2.googleapis.com. Cualquier fallo aquí es un problema de
        credenciales, no de red del repositorio.
        """
        if self._token:
            return self._token

        info = self._leer_credenciales()

        try:
            from google.oauth2 import service_account
        except ImportError as exc:  # pragma: no cover
            raise RepositorioError(
                "Falta la dependencia google-auth para conectar con Google Drive. "
                "Instálala con: pip install google-auth"
            ) from exc

        try:
            credenciales = service_account.Credentials.from_service_account_info(
                info, scopes=DRIVE_SCOPES
            )
            credenciales.refresh(_TransporteHttpx())
        except Exception as exc:  # google-auth agrupa todo en excepciones propias
            raise CredencialesInvalidasError(self._describir_error_token(exc)) from exc

        self._token = credenciales.token
        return self._token

    def _leer_credenciales(self) -> dict:
        """Valida que el JSON pegado sea el de una cuenta de servicio."""
        try:
            info = json.loads(self.credenciales_json)
        except (ValueError, TypeError) as exc:
            raise CredencialesInvalidasError(
                "El contenido pegado no es un JSON válido. Debe ser el archivo de "
                "credenciales que Google Cloud descarga para la cuenta de servicio."
            ) from exc

        if not isinstance(info, dict):
            raise CredencialesInvalidasError(
                "El JSON de credenciales debe ser un objeto, no una lista."
            )

        faltantes = [c for c in ("client_email", "private_key", "token_uri") if not info.get(c)]
        if faltantes:
            raise CredencialesInvalidasError(
                "El JSON no corresponde a una cuenta de servicio: faltan los campos "
                f"{', '.join(faltantes)}. Verifica que no sea un JSON de cliente OAuth."
            )

        return info

    @staticmethod
    def _describir_error_token(exc: Exception) -> str:
        """Traduce el fallo de Google a un motivo legible (HU-05)."""
        detalle = str(exc)

        if "invalid_grant" in detalle:
            return (
                "Google rechazó la cuenta de servicio. La llave puede estar revocada "
                "o el reloj del servidor desincronizado."
            )
        if "invalid_client" in detalle or "unauthorized_client" in detalle:
            return "La cuenta de servicio no existe o fue deshabilitada en Google Cloud."
        if (
            "Could not deserialize key" in detalle
            or "Unable to load PEM" in detalle
            or "private_key" in detalle
        ):
            return "La llave privada del JSON está corrupta o incompleta."
        if "accessNotConfigured" in detalle or "has not been used" in detalle:
            return (
                "La API de Google Drive no está habilitada en el proyecto de Google Cloud "
                "de la cuenta de servicio."
            )
        return f"Google rechazó las credenciales: {detalle}"

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._obtener_token()}"}

    # --- Prueba de conexión (HU-05) ------------------------------------------

    def probar_conexion(self) -> ResultadoPrueba:
        """
        Valida credenciales y carpeta, y cuenta los documentos.
        Nunca lanza excepción: devuelve el motivo del fallo para mostrarlo.
        """
        try:
            self._obtener_token()
        except CredencialesInvalidasError as exc:
            return ResultadoPrueba(False, mensaje="Credenciales inválidas.", detalle=str(exc))
        except RepositorioError as exc:
            return ResultadoPrueba(False, mensaje="No se pudo contactar a Google.", detalle=str(exc))

        try:
            self._verificar_carpeta()
            documentos = self.contar_documentos()
        except RepositorioNoEncontradoError as exc:
            return ResultadoPrueba(False, mensaje="Carpeta no encontrada.", detalle=str(exc))
        except SinPermisoLecturaError as exc:
            return ResultadoPrueba(False, mensaje="Sin permiso de lectura.", detalle=str(exc))
        except RepositorioError as exc:
            return ResultadoPrueba(False, mensaje="Error consultando el repositorio.", detalle=str(exc))

        return ResultadoPrueba(
            exito=True,
            documentos_detectados=documentos,
            mensaje=f"Conexión exitosa. Se detectaron {documentos} hojas de vida en la carpeta indicada.",
        )

    def _verificar_carpeta(self) -> None:
        """
        Confirma que la carpeta existe y es visible para la cuenta de servicio.

        Es un paso aparte porque el listado por `q` no falla con un folder id
        inexistente: simplemente devuelve cero resultados, que el administrador
        leería como "carpeta vacía" en lugar de "carpeta equivocada".
        """
        if not self.folder_id:
            raise RepositorioNoEncontradoError(
                "No se indicó el ID de la carpeta de hojas de vida."
            )

        cuerpo = self._get(
            f"{DRIVE_BASE}/files/{self.folder_id}",
            {"fields": "id,mimeType", "supportsAllDrives": "true"},
        )

        if cuerpo.get("mimeType") != "application/vnd.google-apps.folder":
            raise RepositorioNoEncontradoError(
                "El ID indicado corresponde a un archivo, no a una carpeta."
            )

    def contar_documentos(self) -> int:
        """Cuenta los documentos válidos de la carpeta, recorriendo páginas."""
        return sum(1 for _ in self._recorrer_archivos())

    # --- Sincronización ------------------------------------------------------

    def listar_documentos(
        self, cursor: Optional[str] = None
    ) -> tuple[list[DocumentoRepositorio], Optional[str]]:
        """
        Lista completa de la carpeta configurada.

        A diferencia de Graph, la API de Drive no ofrece un delta por carpeta:
        el pageToken sirve para paginar dentro de una corrida, no para retomar
        entre corridas. Por eso siempre se recorre todo y se devuelve None como
        cursor; quien detecta los cambios es el hash del documento (RD5), no el
        cursor. El parámetro se acepta para cumplir el contrato y se ignora.
        """
        self._verificar_carpeta()
        documentos = [self._mapear(archivo) for archivo in self._recorrer_archivos()]
        return documentos, None

    def _recorrer_archivos(self):
        """Itera los archivos válidos de la carpeta paginando con pageToken."""
        consulta = f"'{self.folder_id}' in parents and trashed=false"
        page_token: Optional[str] = None

        while True:
            parametros = {
                "q": consulta,
                "fields": f"nextPageToken,files({CAMPOS_ARCHIVO})",
                "pageSize": "100",
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true",
            }
            if page_token:
                parametros["pageToken"] = page_token

            cuerpo = self._get(f"{DRIVE_BASE}/files", parametros)

            for archivo in cuerpo.get("files", []): # devuelve tmb archivos no soportados
                if archivo.get("mimeType") == "application/vnd.google-apps.folder":
                    continue
                yield archivo

            page_token = cuerpo.get("nextPageToken")
            if not page_token:
                return

    def descargar(self, id_documento: str) -> bytes:
        """
        Contenido en memoria (RNF14).

        Los documentos nativos de Google no tienen bytes propios: se exportan a
        PDF, que es el formato con el que quedaron registrados.
        """
        mime = self._mime_de(id_documento)

        if mime == MIME_GOOGLE_DOC:
            url = f"{DRIVE_BASE}/files/{id_documento}/export"
            parametros = {"mimeType": MIME_PDF}
        else:
            url = f"{DRIVE_BASE}/files/{id_documento}"
            parametros = {"alt": "media", "supportsAllDrives": "true"}

        try:
            respuesta = httpx.get(
                url,
                params=parametros,
                headers=self._headers(),
                timeout=120,
                follow_redirects=True,
            )
            respuesta.raise_for_status()
        except httpx.HTTPError as exc:
            raise RepositorioError(f"No fue posible descargar el documento: {exc}")

        return respuesta.content

    def _mime_de(self, id_documento: str) -> str:
        cuerpo = self._get(
            f"{DRIVE_BASE}/files/{id_documento}",
            {"fields": "mimeType", "supportsAllDrives": "true"},
        )
        return cuerpo.get("mimeType", "")

    # --- HTTP ----------------------------------------------------------------

    def _get(self, url: str, parametros: dict) -> dict:
        try:
            respuesta = httpx.get(url, params=parametros, headers=self._headers(), timeout=60)
        except httpx.HTTPError as exc:
            raise RepositorioError(f"Error de red consultando Google Drive: {exc}")

        if respuesta.status_code == 401:
            raise CredencialesInvalidasError(
                "Google rechazó el token de la cuenta de servicio."
            )
        if respuesta.status_code == 403:
            raise SinPermisoLecturaError(self._describir_error_403(respuesta))
        if respuesta.status_code == 404:
            # Drive responde 404 tanto si la carpeta no existe como si existe
            # pero no fue compartida: desde fuera son indistinguibles.
            raise RepositorioNoEncontradoError(
                f"No se encontró la carpeta '{self.folder_id}'. Verifica el ID y que la "
                "carpeta esté compartida con el correo de la cuenta de servicio."
            )
        if respuesta.status_code >= 400:
            raise RepositorioError(f"Google Drive respondió HTTP {respuesta.status_code}.")

        return respuesta.json()

    @staticmethod
    def _describir_error_403(respuesta: httpx.Response) -> str:
        try:
            errores = respuesta.json().get("error", {}).get("errors", [])
            razon = errores[0].get("reason", "") if errores else ""
        except (ValueError, AttributeError, IndexError):
            razon = ""

        if razon in ("rateLimitExceeded", "userRateLimitExceeded"):
            return "Google está limitando las consultas. Intenta de nuevo en unos minutos."
        if razon == "accessNotConfigured":
            return "La API de Google Drive no está habilitada en el proyecto de Google Cloud."
        return (
            "La cuenta de servicio no tiene permiso de lectura sobre esta carpeta. "
            "Compártela con su correo, con rol de Lector."
        )

    # --- Mapeo ---------------------------------------------------------------

    def _mapear(self, archivo: dict) -> DocumentoRepositorio:
        mime = archivo.get("mimeType", "")
        modificado = archivo.get("modifiedTime")

        return DocumentoRepositorio(
            id_documento=archivo["id"],
            nombre_archivo=archivo.get("name", ""),
            ruta=self.folder_id,
            url_web=archivo.get("webViewLink"),
            formato=FORMATO_POR_MIME.get(mime, "NO_SOPORTADO"),
            # Los documentos nativos de Google no exponen md5Checksum: para
            # ellos el cambio se detecta por modifiedTime (RD5).
            hash_contenido=archivo.get("md5Checksum"),
            fecha_modificacion=(
                datetime.fromisoformat(modificado.replace("Z", "+00:00")) if modificado else None
            ),
            tamanio=int(archivo.get("size") or 0),
        )
