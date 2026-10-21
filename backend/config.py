"""Configuración central del backend. Todo valor sensible viene del entorno (RNF10)."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
STORAGE_DIR = BASE_DIR / "storage"

DATA_DIR.mkdir(parents=True, exist_ok=True)
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# --- Base de datos -----------------------------------------------------------
# Desarrollo: SQLite. Producción: PostgreSQL 16 + pgvector.
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'beematch.db'}")
USA_PGVECTOR = DATABASE_URL.startswith("postgresql")

# --- Cola de trabajos (RNF04) ------------------------------------------------
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# --- Repositorio de hojas de vida (RNF11: solo lectura) ----------------------
# El origen (OneDrive o Google Drive) y sus credenciales viven en base de datos
# y los administra el usuario desde la aplicación (HU-05). Los valores de abajo
# solo se usan como semilla inicial cuando la tabla está vacía, útil para
# levantar un entorno automatizado.
MS_TENANT_ID = os.getenv("MS_TENANT_ID", "")
MS_CLIENT_ID = os.getenv("MS_CLIENT_ID", "")
MS_CLIENT_SECRET = os.getenv("MS_CLIENT_SECRET", "")
ONEDRIVE_DRIVE_ID = os.getenv("ONEDRIVE_DRIVE_ID", "")
ONEDRIVE_CARPETA_CV = os.getenv("ONEDRIVE_CARPETA_CV", "/HojasDeVida")
GRAPH_SCOPES = ["https://graph.microsoft.com/.default"]
SYNC_INTERVALO_HORAS = int(os.getenv("SYNC_INTERVALO_HORAS", "6"))

# Semilla de Google Drive: archivo de la cuenta de servicio en la raíz del
# proyecto y carpeta de hojas de vida compartida con esa cuenta. Sirve para que
# el equipo no tenga que registrar la conexión a mano en cada máquina. El
# archivo está en .gitignore y nunca se versiona (RNF10).
GDRIVE_ARCHIVO_CREDENCIALES = Path(
    os.getenv("GDRIVE_ARCHIVO_CREDENCIALES", str(BASE_DIR / "beematch-credenciales.json"))
)
GDRIVE_CARPETA_ID = os.getenv("GDRIVE_CARPETA_ID", "1H7-p-d3auJOzrw660zGfmKa5drW0Hn_V")

# --- Servicio de IA (RNF33: configurable sin recompilar) ---------------------
# El proveedor es OpenAI para todo: el re-ranking y la explicación (etapa 3) y
# la vectorización de CV y consultas. Cada uso lleva su variable de clave para
# poder separar proyectos o cupos, pero puede ser la misma clave.
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODELO = os.getenv("LLM_MODELO", "gpt-4o-mini")

EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "")
EMBEDDING_MODELO = os.getenv("EMBEDDING_MODELO", "text-embedding-3-small")
EMBEDDING_DIMENSIONES = int(os.getenv("EMBEDDING_DIMENSIONES", "1536"))
EMBEDDING_URL = os.getenv("EMBEDDING_URL", "https://api.openai.com/v1/embeddings")
# Textos por petición. El endpoint acepta lotes; mandarlos de a uno multiplica
# las llamadas en la ingesta inicial.
EMBEDDING_LOTE = int(os.getenv("EMBEDDING_LOTE", "96"))

# --- Parámetros del motor de matching (RNF02) --------------------------------
TOP_N_RESULTADOS = int(os.getenv("TOP_N_RESULTADOS", "5"))
FINALISTAS_RERANK = int(os.getenv("FINALISTAS_RERANK", "20"))
UMBRAL_AFINIDAD_MINIMA = float(os.getenv("UMBRAL_AFINIDAD_MINIMA", "60"))
CHUNK_TAMANIO = int(os.getenv("CHUNK_TAMANIO", "1200"))
CHUNK_SOLAPAMIENTO = int(os.getenv("CHUNK_SOLAPAMIENTO", "200"))

# --- Seguridad ---------------------------------------------------------------
JWT_SECRET = os.getenv("JWT_SECRET", "beematch-dev-secret-cambiar-en-produccion")

# Clave de cifrado de secretos en base de datos (client secret de Graph).
# Debe ser una clave Fernet válida. Si se omite, se deriva del JWT_SECRET.
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")
JWT_ALGORITHM = "HS256"

# HU-02: la sesión se cierra tras 30 minutos sin actividad. El token dura lo
# mismo y el navegador lo renueva mientras el usuario trabaja, así el servidor
# también rechaza un token copiado que lleva media hora sin usarse.
JWT_EXPIRACION_MINUTOS = int(os.getenv("JWT_EXPIRACION_MINUTOS", "30"))

# HU-01: tras LOGIN_MAX_INTENTOS fallos seguidos el acceso se bloquea.
LOGIN_MAX_INTENTOS = int(os.getenv("LOGIN_MAX_INTENTOS", "5"))
LOGIN_BLOQUEO_MINUTOS = int(os.getenv("LOGIN_BLOQUEO_MINUTOS", "15"))

# HU-03: el autorregistro solo acepta correos corporativos de este dominio.
DOMINIO_CORREO = os.getenv("DOMINIO_CORREO", "bee.com.co").lower()

# HU-03: superusuaria (Diana). Si no existe ninguna al arrancar y el correo y la
# contraseña están definidos, se crea con el rol SUPERADMINISTRADOR.
SUPERUSUARIO_CORREO = os.getenv("SUPERUSUARIO_CORREO", "").strip().lower()
SUPERUSUARIO_NOMBRE = os.getenv("SUPERUSUARIO_NOMBRE", "Diana")
SUPERUSUARIO_PASSWORD = os.getenv("SUPERUSUARIO_PASSWORD", "")

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
