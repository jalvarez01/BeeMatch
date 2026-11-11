"""
Criterios estructurados de la solicitud agrupados por tipo (HU-09).

La coordinadora registra rol, tecnologías, frameworks, años de experiencia y
otros conocimientos en campos separados. Para que el análisis combine todo lo
diligenciado sin perder esa distinción, la consulta del motor nombra cada grupo
("Frameworks: Spring Boot") en lugar de mezclar los valores en una sola lista:
así el embedding y el re-ranking saben qué es una tecnología, qué un framework
y qué un conocimiento de negocio.

Es lógica pura, sin base de datos ni IA, para poder probarla de forma aislada.
"""

from collections.abc import Iterable
from typing import Protocol


class CriterioConTipo(Protocol):
    """Lo único que se necesita de un criterio: su tipo y su valor."""

    tipo: str
    valor: str


# Orden en que los grupos aparecen en la consulta: el mismo del formulario.
ETIQUETAS_POR_TIPO: dict[str, str] = {
    "TECNOLOGIA": "Tecnologías",
    "FRAMEWORK": "Frameworks",
    "OTRO": "Otros conocimientos",
    "DOMINIO": "Dominio",
    "CERTIFICACION": "Certificaciones",
    "IDIOMA": "Idiomas",
}


def agrupar_por_tipo(criterios: Iterable[CriterioConTipo]) -> list[tuple[str, list[str]]]:
    """
    Grupos (etiqueta, valores) en el orden del formulario, sin grupos vacíos ni
    valores repetidos. Un tipo desconocido no se pierde: va al final con su
    propio nombre, para que ningún criterio diligenciado quede fuera del análisis.
    """
    grupos: dict[str, list[str]] = {}
    for criterio in criterios:
        valor = (criterio.valor or "").strip()
        if not valor:
            continue
        valores = grupos.setdefault(criterio.tipo, [])
        if valor not in valores:
            valores.append(valor)

    conocidos = [tipo for tipo in ETIQUETAS_POR_TIPO if tipo in grupos]
    desconocidos = [tipo for tipo in grupos if tipo not in ETIQUETAS_POR_TIPO]
    return [
        (ETIQUETAS_POR_TIPO.get(tipo, tipo.capitalize()), grupos[tipo])
        for tipo in conocidos + desconocidos
    ]


def lineas_de_criterios(criterios: Iterable[CriterioConTipo]) -> list[str]:
    """Una línea por grupo, lista para sumarse a la consulta: "Frameworks: Spring Boot, Django"."""
    return [f"{etiqueta}: {', '.join(valores)}" for etiqueta, valores in agrupar_por_tipo(criterios)]
