"""Normalización del puntaje de afinidad y su nivel visual."""

from backend.config import UMBRAL_AFINIDAD_MINIMA

NIVEL_ALTA = "ALTA"
NIVEL_MEDIA = "MEDIA"
NIVEL_BAJA = "BAJA"

# HU-20: cortes de cada nivel. La leyenda del frontend (Badges.tsx) los repite.
PUNTAJE_MINIMO_ALTA = 85
PUNTAJE_MINIMO_MEDIA = 70


def normalizar_puntaje(valor: float) -> float:
    """RD6: el puntaje siempre vive entre 0 y 100."""
    return max(0.0, min(100.0, round(float(valor), 1)))


def nivel_de(puntaje: float) -> str:
    if puntaje >= PUNTAJE_MINIMO_ALTA:
        return NIVEL_ALTA
    if puntaje >= PUNTAJE_MINIMO_MEDIA:
        return NIVEL_MEDIA
    return NIVEL_BAJA


def supera_umbral(puntaje: float) -> bool:
    return puntaje >= UMBRAL_AFINIDAD_MINIMA
