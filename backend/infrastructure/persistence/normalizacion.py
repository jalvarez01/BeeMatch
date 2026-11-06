"""Normalización de nombres para comparar sin que importen mayúsculas ni espacios (HU-12)."""

import unicodedata
from typing import Optional

LONGITUD_MAXIMA_NOMBRE = 160


def limpiar_nombre(nombre: Optional[str]) -> str:
    """Recorta los extremos y deja un solo espacio entre palabras: ``"  Banco   X "`` -> ``"Banco X"``."""
    return " ".join(unicodedata.normalize("NFC", nombre or "").split())


def normalizar_nombre(nombre: Optional[str]) -> str:
    """Forma comparable del nombre: limpio y sin distinguir mayúsculas de minúsculas."""
    return limpiar_nombre(nombre).casefold()
