"""
División del CV en fragmentos con solapamiento.

El fragmento es la unidad de recuperación y también el ancla de evidencia: toda
explicación mostrada al usuario apunta a uno de estos fragmentos (RNF28).
"""

from backend.config import CHUNK_SOLAPAMIENTO, CHUNK_TAMANIO


def dividir_en_fragmentos(
    texto: str,
    tamanio: int = CHUNK_TAMANIO,
    solapamiento: int = CHUNK_SOLAPAMIENTO,
) -> list[dict]:
    """Retorna [{'orden': int, 'texto': str}] respetando límites de párrafo."""
    if not texto:
        return []

    parrafos = [p.strip() for p in texto.split("\n") if p.strip()]
    fragmentos: list[str] = []
    actual = ""

    for parrafo in parrafos:
        if len(actual) + len(parrafo) + 1 <= tamanio:
            actual = f"{actual}\n{parrafo}" if actual else parrafo
        else:
            if actual:
                fragmentos.append(actual)
            if len(parrafo) > tamanio:
                for i in range(0, len(parrafo), tamanio - solapamiento):
                    fragmentos.append(parrafo[i : i + tamanio])
                actual = ""
            else:
                cola = actual[-solapamiento:] if actual else ""
                actual = f"{cola}\n{parrafo}".strip() if cola else parrafo

    if actual:
        fragmentos.append(actual)

    return [{"orden": i, "texto": t} for i, t in enumerate(fragmentos)]
