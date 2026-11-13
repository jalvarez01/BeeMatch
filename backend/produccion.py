"""
Validaciones de arranque para producción.

Con ENTORNO=produccion la API se niega a iniciar si quedó algún valor de
desarrollo: es mejor un contenedor que no sube y dice por qué, que un servidor
público firmando sesiones con el secreto de ejemplo que está en el repositorio.
En desarrollo no hace nada.
"""

import logging

from backend import config

logger = logging.getLogger(__name__)

SECRETO_DE_EJEMPLO = "beematch-dev-secret-cambiar-en-produccion"
LARGO_MINIMO_JWT = 32
LARGO_MINIMO_CLAVE_SUPERUSUARIA = 12


class ConfiguracionDeProduccionInvalida(RuntimeError):
    pass


def _es_clave_fernet(valor: str) -> bool:
    from cryptography.fernet import Fernet

    try:
        Fernet(valor.encode("utf-8"))
        return True
    except (ValueError, TypeError):
        return False


def problemas_de_configuracion() -> list[str]:
    """Lista de lo que está mal. Vacía si la configuración sirve para producción."""
    problemas = []

    if config.JWT_SECRET == SECRETO_DE_EJEMPLO or config.JWT_SECRET.startswith("cambiar"):
        problemas.append("JWT_SECRET sigue siendo el valor de ejemplo.")
    elif len(config.JWT_SECRET) < LARGO_MINIMO_JWT:
        problemas.append(f"JWT_SECRET debe tener al menos {LARGO_MINIMO_JWT} caracteres.")

    if not config.ENCRYPTION_KEY:
        problemas.append(
            "ENCRYPTION_KEY está vacía: la clave que cifra las credenciales del repositorio "
            "debe ser propia, no derivada de JWT_SECRET (rotar uno dejaría ilegible el otro)."
        )
    elif not _es_clave_fernet(config.ENCRYPTION_KEY):
        problemas.append(
            "ENCRYPTION_KEY no es una clave Fernet válida. Genera una con: "
            'python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )

    if not config.USA_PGVECTOR:
        problemas.append(
            "DATABASE_URL no es de PostgreSQL: producción usa PostgreSQL con pgvector, no SQLite."
        )

    if config.SUPERUSUARIO_CORREO and config.SUPERUSUARIO_PASSWORD:
        if len(config.SUPERUSUARIO_PASSWORD) < LARGO_MINIMO_CLAVE_SUPERUSUARIA:
            problemas.append(
                "SUPERUSUARIO_PASSWORD debe tener al menos "
                f"{LARGO_MINIMO_CLAVE_SUPERUSUARIA} caracteres."
            )

    return problemas


def advertencias_de_configuracion() -> list[str]:
    """Cosas que no impiden arrancar pero que conviene saber."""
    avisos = []
    if not config.EMBEDDING_API_KEY or not config.LLM_API_KEY:
        avisos.append(
            "Faltan EMBEDDING_API_KEY o LLM_API_KEY: la aplicación arranca, pero las "
            "búsquedas e indexaciones fallarán hasta que se configuren."
        )
    if all("localhost" in origen or "127.0.0.1" in origen for origen in config.ALLOWED_ORIGINS):
        avisos.append(
            "ALLOWED_ORIGINS solo permite localhost. Si el frontend se sirve desde el mismo "
            "dominio que la API no hace falta; si no, indica la URL pública."
        )
    return avisos


def validar_configuracion_de_produccion() -> None:
    if not config.ES_PRODUCCION:
        return
    for aviso in advertencias_de_configuracion():
        logger.warning(aviso)
    problemas = problemas_de_configuracion()
    if problemas:
        raise ConfiguracionDeProduccionInvalida(
            "Configuración de producción inválida:\n  - " + "\n  - ".join(problemas)
        )
