"""
Extracción de texto de Word 97-2003 (.doc), el formato binario anterior al .docx.

python-docx no lo lee, así que se delega en `antiword`, un programa externo
liviano que se instala en la imagen de Docker (ver backend/dockerfile). Se le
pasa un archivo temporal que se borra apenas termina, de modo que el documento
tampoco queda en disco (RNF14).
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

from backend.infrastructure.loaders.errores import (
    DocumentoDanadoError,
    DocumentoSinTextoError,
    ExtraccionNoDisponibleError,
)

TIMEOUT_SEGUNDOS = 60


def extraer_texto_doc(contenido: bytes) -> str:
    if shutil.which("antiword") is None:
        raise ExtraccionNoDisponibleError(
            "El servidor no tiene 'antiword' instalado, por lo que no puede leer archivos .doc."
        )

    with tempfile.TemporaryDirectory() as carpeta:
        ruta = Path(carpeta) / "documento.doc"
        ruta.write_bytes(contenido)
        try:
            resultado = subprocess.run(
                ["antiword", "-m", "UTF-8.txt", str(ruta)],
                capture_output=True,
                timeout=TIMEOUT_SEGUNDOS,
            )
        except subprocess.TimeoutExpired:
            raise DocumentoDanadoError("El documento .doc tardó demasiado en leerse.")

    if resultado.returncode != 0:
        detalle = resultado.stderr.decode("utf-8", errors="replace").strip()[:200]
        raise DocumentoDanadoError(f".doc dañado o ilegible: {detalle or 'sin detalle'}")

    texto = resultado.stdout.decode("utf-8", errors="replace").strip()
    if not texto:
        raise DocumentoSinTextoError("El documento no contiene texto.")
    return texto
