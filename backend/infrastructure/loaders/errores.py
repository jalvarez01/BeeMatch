"""
Errores de extracción de texto.

Todos heredan de ExtraccionError: el indexador captura esa base, marca el
documento como NO_PROCESABLE con el mensaje del error y sigue con el siguiente
(HU-17, RNF19). El mensaje llega tal cual a la pantalla del coordinador, por eso
está en español y dice qué le pasa al archivo.
"""


class ExtraccionError(Exception):
    """El documento no pudo procesarse. El motivo se registra, no se aborta todo."""


class DocumentoProtegidoError(ExtraccionError):
    """El documento está cifrado o protegido con contraseña de apertura."""


class DocumentoDanadoError(ExtraccionError):
    """El archivo está corrupto, truncado o no es del formato que dice ser."""


class DocumentoSinTextoError(ExtraccionError):
    """El documento se abre bien pero no contiene texto extraíble."""


class ExtraccionNoDisponibleError(Exception):
    """
    Al servidor le falta algo para leer este formato: una dependencia de Python
    o un programa externo.

    No hereda de ExtraccionError a propósito. El problema es del entorno, no del
    archivo, así que el documento no se marca como NO_PROCESABLE —quedaría con un
    motivo falso y no se reintentaría nunca—: se queda PENDIENTE y la siguiente
    sincronización lo vuelve a intentar. Es el mismo criterio que
    `ProveedorEmbeddingsNoDisponibleError`.
    """
