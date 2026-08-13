"""
Cliente de Microsoft Graph. Acceso de SOLO LECTURA a la carpeta de hojas de
vida (RNF11). BeeMatch nunca escribe, edita ni borra en OneDrive.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import httpx

from backend.config import (
    GRAPH_SCOPES,
    MS_CLIENT_ID,
    MS_CLIENT_SECRET,
    MS_TENANT_ID,
    ONEDRIVE_CARPETA_CV,
    ONEDRIVE_DRIVE_ID,
)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class OneDriveError(Exception):
    """Fallo de conexión con el repositorio (HU-26, RNF18)."""


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


class GraphClient:
    def __init__(self):
        self._token: Optional[str] = None

    def _obtener_token(self) -> str:
        """Client credentials contra Entra ID. La clave vive en el gestor de secretos."""
        if self._token:
            return self._token

        url = f"https://login.microsoftonline.com/{MS_TENANT_ID}/oauth2/v2.0/token"
        try:
            respuesta = httpx.post(
                url,
                data={
                    "client_id": MS_CLIENT_ID,
                    "client_secret": MS_CLIENT_SECRET,
                    "scope": " ".join(GRAPH_SCOPES),
                    "grant_type": "client_credentials",
                },
                timeout=30,
            )
            respuesta.raise_for_status()
        except httpx.HTTPError as exc:
            raise OneDriveError(f"No fue posible autenticar contra Microsoft Graph: {exc}")

        self._token = respuesta.json()["access_token"]
        return self._token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._obtener_token()}"}

    def listar_documentos(self, delta_link: Optional[str] = None) -> tuple[list[DocumentoOneDrive], Optional[str]]:
        """
        Delta query: en la primera corrida trae todo, después solo lo que cambió.
        Retorna (documentos, nuevo_delta_link).
        """
        if delta_link:
            url = delta_link
        else:
            url = f"{GRAPH_BASE}/drives/{ONEDRIVE_DRIVE_ID}/root:{ONEDRIVE_CARPETA_CV}:/delta"

        documentos: list[DocumentoOneDrive] = []
        siguiente_delta: Optional[str] = None

        while url:
            try:
                respuesta = httpx.get(url, headers=self._headers(), timeout=60)
                respuesta.raise_for_status()
            except httpx.HTTPError as exc:
                raise OneDriveError(f"Error consultando OneDrive: {exc}")

            cuerpo = respuesta.json()
            for item in cuerpo.get("value", []):
                documento = self._mapear(item)
                if documento:
                    documentos.append(documento)

            url = cuerpo.get("@odata.nextLink")
            siguiente_delta = cuerpo.get("@odata.deltaLink", siguiente_delta)

        return documentos, siguiente_delta

    def descargar(self, id_onedrive: str) -> bytes:
        """Descarga el contenido en memoria. No se persiste el archivo (RNF14)."""
        url = f"{GRAPH_BASE}/drives/{ONEDRIVE_DRIVE_ID}/items/{id_onedrive}/content"
        try:
            respuesta = httpx.get(url, headers=self._headers(), timeout=120, follow_redirects=True)
            respuesta.raise_for_status()
        except httpx.HTTPError as exc:
            raise OneDriveError(f"No fue posible descargar el documento: {exc}")
        return respuesta.content

    @staticmethod
    def _mapear(item: dict) -> Optional[DocumentoOneDrive]:
        nombre = item.get("name", "")
        if "folder" in item or not nombre.lower().endswith((".pdf", ".docx", ".doc")):
            return None

        modificado = item.get("lastModifiedDateTime")
        return DocumentoOneDrive(
            id_onedrive=item["id"],
            nombre_archivo=nombre,
            ruta=item.get("parentReference", {}).get("path", ""),
            url_web=item.get("webUrl"),
            formato="PDF" if nombre.lower().endswith(".pdf") else "DOCX",
            hash_contenido=item.get("file", {}).get("hashes", {}).get("quickXorHash"),
            fecha_modificacion=datetime.fromisoformat(modificado.replace("Z", "+00:00")) if modificado else None,
            tamanio=item.get("size", 0),
        )
