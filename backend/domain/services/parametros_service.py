"""Parámetros de recomendación que el administrador puede ajustar (HU-07)."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.config import TOP_N_RESULTADOS, UMBRAL_AFINIDAD_MINIMA
from backend.infrastructure.persistence.repositories.configuracion_repo import ParametroRepository

CLAVE_NUM_CANDIDATOS = "top_n_resultados"
CLAVE_UMBRAL_AFINIDAD = "umbral_afinidad_minima"

MINIMO_CANDIDATOS = 3
MAXIMO_CANDIDATOS = 10
MINIMO_UMBRAL = 0
MAXIMO_UMBRAL = 100

MENSAJE_NUM_CANDIDATOS = (
    f"El número de candidatos sugeridos debe ser un entero entre {MINIMO_CANDIDATOS} y {MAXIMO_CANDIDATOS}."
)
MENSAJE_UMBRAL = (
    f"El porcentaje mínimo de afinidad debe ser un entero entre {MINIMO_UMBRAL} y {MAXIMO_UMBRAL}."
)


class ParametrosInvalidosError(ValueError):
    """Algún valor está fuera de rango. El mensaje está listo para mostrarse."""


@dataclass(frozen=True)
class ParametrosRecomendacion:
    num_candidatos: int
    umbral_afinidad: int


def _por_defecto() -> ParametrosRecomendacion:
    return ParametrosRecomendacion(
        num_candidatos=TOP_N_RESULTADOS, umbral_afinidad=int(UMBRAL_AFINIDAD_MINIMA)
    )


def _entero(valor: str, minimo: int, maximo: int, defecto: int) -> int:
    """Lee un valor guardado; si está corrupto o fuera de rango usa el defecto."""
    try:
        numero = int(float(valor))
    except (TypeError, ValueError):
        return defecto
    return numero if minimo <= numero <= maximo else defecto


def validar(num_candidatos: int, umbral_afinidad: int) -> None:
    """Rechaza el conjunto completo si alguno de los dos valores no es válido."""
    errores = []
    if not MINIMO_CANDIDATOS <= num_candidatos <= MAXIMO_CANDIDATOS:
        errores.append(MENSAJE_NUM_CANDIDATOS)
    if not MINIMO_UMBRAL <= umbral_afinidad <= MAXIMO_UMBRAL:
        errores.append(MENSAJE_UMBRAL)
    if errores:
        raise ParametrosInvalidosError(" ".join(errores))


def validar_clave(clave: str, valor: str) -> None:
    """Para el endpoint genérico de parámetros: aplica los mismos límites a estas dos claves."""
    if clave not in (CLAVE_NUM_CANDIDATOS, CLAVE_UMBRAL_AFINIDAD):
        return
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        raise ParametrosInvalidosError(
            MENSAJE_NUM_CANDIDATOS if clave == CLAVE_NUM_CANDIDATOS else MENSAJE_UMBRAL
        ) from None
    if clave == CLAVE_NUM_CANDIDATOS:
        validar(numero, MINIMO_UMBRAL)
    else:
        validar(MINIMO_CANDIDATOS, numero)


class ParametrosRecomendacionService:
    def __init__(self, db: Session):
        self.repo = ParametroRepository(db)

    def obtener(self) -> ParametrosRecomendacion:
        """
        Valores vigentes. Se leen en cada búsqueda, así que un cambio aplica a
        las que se lancen después; sin fila guardada rigen los de config.py.
        """
        defecto = _por_defecto()
        num = self.repo.get(CLAVE_NUM_CANDIDATOS)
        umbral = self.repo.get(CLAVE_UMBRAL_AFINIDAD)
        return ParametrosRecomendacion(
            num_candidatos=(
                _entero(num.valor, MINIMO_CANDIDATOS, MAXIMO_CANDIDATOS, defecto.num_candidatos)
                if num
                else defecto.num_candidatos
            ),
            umbral_afinidad=(
                _entero(umbral.valor, MINIMO_UMBRAL, MAXIMO_UMBRAL, defecto.umbral_afinidad)
                if umbral
                else defecto.umbral_afinidad
            ),
        )

    def por_defecto(self) -> ParametrosRecomendacion:
        return _por_defecto()

    def actualizar(
        self, num_candidatos: int, umbral_afinidad: int, usuario_id: str | None = None
    ) -> ParametrosRecomendacion:
        """Guarda los dos valores o ninguno: si hay un error no se escribe nada."""
        validar(num_candidatos, umbral_afinidad)
        self.repo.establecer_varios(
            {
                CLAVE_NUM_CANDIDATOS: str(num_candidatos),
                CLAVE_UMBRAL_AFINIDAD: str(umbral_afinidad),
            },
            usuario_id,
        )
        return self.obtener()
