"""
Indexación de hojas de vida (componentes C8 + C9).

Se ejecuta una sola vez por versión de documento (RNF03). El worker de ingesta
llama a `indexar_hoja` por cada documento encolado.
"""

import logging

from sqlalchemy.orm import Session

from backend.infrastructure.llm.embeddings import ProveedorEmbeddings, serializar
from backend.infrastructure.llm.llm_provider import ProveedorLLM, ServicioIAError
from backend.infrastructure.llm.prompts import SYSTEM_EXTRACCION, construir_prompt_extraccion
from backend.infrastructure.loaders.chunker import dividir_en_fragmentos
from backend.infrastructure.loaders.errores import (
    ExtraccionError,
    ExtraccionNoDisponibleError,
)
from backend.infrastructure.loaders.extractor import extraer_texto
from backend.domain.services.repositorio_config_service import RepositorioConfigService
from backend.infrastructure.persistence.models.hoja_vida import ESTADO_INDEXADA
from backend.infrastructure.repositorio.base import RepositorioError
from backend.infrastructure.persistence.repositories.candidato_repo import CandidatoRepository
from backend.infrastructure.persistence.repositories.hoja_vida_repo import HojaDeVidaRepository

logger = logging.getLogger(__name__)

# Topes alineados con el ancho de las columnas de CandidatoModel. El modelo
# puede devolver un rol de tres renglones; SQLite lo aceptaría y PostgreSQL
# rechazaría la fila entera en producción.
MAX_NOMBRE = 160
MAX_ROL = 120
MAX_UBICACION = 120
MAX_RESUMEN = 1000
MAX_TECNOLOGIAS = 40
MAX_EVIDENCIA = 400

# Una vida laboral no llega a esto. Sirve para descartar un año mal leído
# (un "2015" tomado como años de experiencia) sin inventar nada.
MAX_ANIOS_EXPERIENCIA = 60

CATEGORIAS_VALIDAS = {
    "TECNOLOGIA",
    "FRAMEWORK",
    "BASE_DATOS",
    "HERRAMIENTA",
    "CERTIFICACION",
    "DOMINIO",
}

# El modelo a veces escribe la palabra en vez de dejar el campo nulo.
TEXTOS_NULOS = {"null", "none", "n/a", "na", "no especificado", "no especifica"}

# Largo mínimo de una cita para darla por encontrada. Solo descarta lo
# degenerado (una letra suelta coincide con cualquier texto); una cita corta
# pero real como "AWS" sí demuestra que la tecnología aparece en el documento.
MIN_CARACTERES_CITA = 3


class IndexacionService:
    def __init__(self, db: Session, llm: ProveedorLLM | None = None):
        self.db = db
        self.hojas = HojaDeVidaRepository(db)
        self.candidatos = CandidatoRepository(db)
        self.embeddings = ProveedorEmbeddings()
        self.llm = llm or ProveedorLLM()
        # Cliente del origen registrado por el administrador (HU-05): OneDrive
        # o Google Drive, indistinto para esta clase.
        self.repositorio = RepositorioConfigService(db).cliente_activo()

    def indexar_hoja(self, hoja_id: str) -> bool:
        """
        Descarga, extrae, fragmenta e indexa. Retorna True si quedó indexada.
        RNF19: un documento que falla se marca y no interrumpe la corrida.
        """
        hoja = self.hojas.get_by_id(hoja_id)
        if not hoja:
            return False
        if hoja.estado_procesamiento == ESTADO_INDEXADA:
            # Un cambio en el documento la devuelve a PENDIENTE, así que si
            # llega aquí ya indexada es un trabajo repetido en la cola.
            return True

        try:
            contenido = self.repositorio.descargar(hoja.id_documento)
        except RepositorioError as exc:
            self.hojas.marcar_no_procesable(hoja_id, f"No se pudo descargar: {exc}")
            return False

        # HU-17: el formato real sale del contenido (PDF, .docx o .doc), no de
        # la extensión. Un documento dañado o con contraseña se marca y la
        # corrida sigue con el siguiente.
        try:
            texto = extraer_texto(contenido)
        except ExtraccionError as exc:
            self.hojas.marcar_no_procesable(hoja_id, str(exc))
            return False
        except ExtraccionNoDisponibleError as exc:
            # Le falta al servidor, no al documento: marcarlo NO_PROCESABLE le
            # pondría un motivo falso y no se volvería a intentar. Queda
            # PENDIENTE y la próxima sincronización lo reintenta.
            logger.warning(
                "Falta una dependencia para leer %s, queda pendiente: %s",
                hoja.nombre_archivo,
                exc,
            )
            return False
        except Exception as exc:  # noqa: BLE001
            # Un fallo inesperado al leer un documento lo marca a él; no debe
            # tumbar la sincronización ni dejarlo PENDIENTE para siempre.
            logger.exception("Error inesperado extrayendo el texto de %s", hoja.nombre_archivo)
            self.hojas.marcar_no_procesable(hoja_id, f"Error inesperado al leer el documento: {exc}")
            return False

        fragmentos = dividir_en_fragmentos(texto)
        if not fragmentos:
            self.hojas.marcar_no_procesable(hoja_id, "El documento no produjo fragmentos de texto.")
            return False

        vectores = self.embeddings.generar([f["texto"] for f in fragmentos])
        for fragmento, vector in zip(fragmentos, vectores):
            fragmento["embedding"] = serializar(vector)

        guardados = self.candidatos.reemplazar_fragmentos(hoja_id, fragmentos)

        perfil, tecnologias = self._extraer_perfil(texto, hoja.nombre_archivo)
        candidato = self.candidatos.crear_o_reemplazar(hoja_id, perfil)
        # `None` significa que la extracción con IA no se pudo hacer: se dejan
        # las habilidades que hubiera de una corrida anterior en vez de
        # borrarlas. Una lista vacía sí es una respuesta: el documento no
        # declara ninguna tecnología y las viejas dejan de valer.
        if tecnologias is not None:
            self.candidatos.reemplazar_habilidades(
                candidato.id, self._anclar_evidencias(tecnologias, guardados)
            )

        self.hojas.marcar_indexada(hoja_id)
        return True

    # --- Extracción del perfil (RF02, HU-18) ---------------------------------

    def _extraer_perfil(self, texto: str, nombre_archivo: str) -> tuple[dict, list[dict] | None]:
        """
        Perfil estructurado del CV: lo que la tarjeta de resultados muestra.

        Si el servicio de IA no está disponible o falla, se cae a la heurística
        del nombre de archivo. Un documento vale más indexado con el perfil
        incompleto que no indexado: los fragmentos y sus embeddings ya están y
        la búsqueda sigue funcionando con ellos (RNF19).
        """
        try:
            respuesta = self.llm.completar_json(
                SYSTEM_EXTRACCION, construir_prompt_extraccion(texto)
            )
        except ServicioIAError as exc:
            logger.warning(
                "Sin perfil estructurado para %s, se usa el nombre del archivo: %s",
                nombre_archivo,
                exc,
            )
            return self._perfil_desde_nombre(texto, nombre_archivo), None

        datos = respuesta.datos
        perfil = {
            "nombre": self._texto(datos.get("nombre"), MAX_NOMBRE)
            or self._nombre_desde_archivo(nombre_archivo),
            "rol_principal": self._texto(datos.get("rol_principal"), MAX_ROL),
            "anios_experiencia": self._entero(datos.get("anios_experiencia")),
            "ubicacion": self._texto(datos.get("ubicacion"), MAX_UBICACION),
            "resumen": self._texto(datos.get("resumen"), MAX_RESUMEN) or texto[:MAX_RESUMEN],
        }
        return perfil, self._tecnologias(datos.get("tecnologias"))

    @staticmethod
    def _perfil_desde_nombre(texto: str, nombre_archivo: str) -> dict:
        """
        Respaldo sin IA: el nombre sale del archivo, que es como está
        organizado el repositorio de Bee. El resto queda sin determinar.
        """
        # Todas las claves, incluida `ubicacion`: `crear_o_reemplazar` solo
        # asigna lo que viene en el diccionario, así que omitir una dejaría el
        # valor de una corrida anterior mezclado con este perfil.
        return {
            "nombre": IndexacionService._nombre_desde_archivo(nombre_archivo),
            "rol_principal": None,
            "anios_experiencia": None,
            "ubicacion": None,
            "resumen": texto[:MAX_RESUMEN],
        }

    @staticmethod
    def _nombre_desde_archivo(nombre_archivo: str) -> str:
        nombre = nombre_archivo.rsplit(".", 1)[0].replace("_", " ").strip()
        return nombre[:MAX_NOMBRE] or "Sin nombre"

    @staticmethod
    def _texto(valor: object, tope: int) -> str | None:
        """Normaliza a texto recortado, o None si el modelo no lo encontró."""
        if valor is None:
            return None
        limpio = str(valor).strip()
        if not limpio or limpio.lower() in TEXTOS_NULOS:
            return None
        return limpio[:tope]

    @staticmethod
    def _entero(valor: object) -> int | None:
        """
        Años de experiencia como entero. El modelo puede devolverlos como
        texto, como decimal o fuera de todo rango razonable.
        """
        if valor is None or isinstance(valor, bool):
            return None
        try:
            numero = int(float(valor))
        except (TypeError, ValueError):
            return None
        if numero < 0 or numero > MAX_ANIOS_EXPERIENCIA:
            return None
        return numero

    @classmethod
    def _tecnologias(cls, valor: object) -> list[dict] | None:
        """
        Normaliza la lista de tecnologías y descarta duplicados conservando el
        orden en que el modelo las nombró, que sigue al del documento.

        Una lista vacía significa que el documento no declara ninguna. `None`
        significa que el modelo no devolvió la lista —falta la clave o vino con
        otra forma—, que no es lo mismo: ahí se conservan las que hubiera.
        """
        if valor is None or not isinstance(valor, list):
            return None

        vistas: set[str] = set()
        tecnologias: list[dict] = []
        for item in valor:
            if not isinstance(item, dict):
                continue
            nombre = cls._texto(item.get("nombre"), 120)
            if not nombre or nombre.casefold() in vistas:
                continue
            vistas.add(nombre.casefold())

            categoria = (cls._texto(item.get("categoria"), 30) or "TECNOLOGIA").upper()
            if categoria not in CATEGORIAS_VALIDAS:
                categoria = "TECNOLOGIA"

            tecnologias.append(
                {
                    "nombre": nombre,
                    "categoria": categoria,
                    "anios_experiencia": cls._entero(item.get("anios_experiencia")),
                    "evidencia_texto": cls._texto(item.get("evidencia_texto"), MAX_EVIDENCIA),
                }
            )
            if len(tecnologias) >= MAX_TECNOLOGIAS:
                break

        return tecnologias

    # --- Anclaje de la evidencia (RNF28) -------------------------------------

    @classmethod
    def _anclar_evidencias(cls, tecnologias: list[dict], fragmentos: list) -> list[dict]:
        """
        Ata cada cita al fragmento del CV que la contiene.

        RNF28: la evidencia que ve el reclutador tiene que poder rastrearse hasta
        el documento. La cita la escribe el modelo, así que se busca entre los
        fragmentos recién guardados y se le pega el id del que la contiene. Si no
        aparece en ninguno se descarta: una cita que no está en la hoja de vida no
        es evidencia, por verosímil que suene. La tecnología se conserva —el
        modelo pudo leerla bien y redactar mal la cita—, pero sin respaldo que
        mostrar, igual que el re-ranking degrada una coincidencia sin fragmento.
        """
        indice = [(cls._normalizar_cita(f.texto), f.id) for f in fragmentos]

        ancladas = []
        for tecnologia in tecnologias:
            cita = tecnologia.get("evidencia_texto")
            fragmento_id = cls._fragmento_que_contiene(cita, indice) if cita else None
            ancladas.append(
                {
                    **tecnologia,
                    "evidencia_texto": cita if fragmento_id else None,
                    "fragmento_id": fragmento_id,
                }
            )
        return ancladas

    @classmethod
    def _fragmento_que_contiene(cls, cita: str, indice: list[tuple[str, str]]) -> str | None:
        aguja = cls._normalizar_cita(cita)
        if len(aguja) < MIN_CARACTERES_CITA:
            return None
        for texto, fragmento_id in indice:
            if aguja in texto:
                return fragmento_id
        return None

    @staticmethod
    def _normalizar_cita(texto: str) -> str:
        """Un salto de línea del PDF no debe impedir reconocer la misma frase."""
        return " ".join(texto.split()).casefold()
