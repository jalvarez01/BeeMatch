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

# --- Microsoft Graph / OneDrive (RNF11: solo lectura) ------------------------
MS_TENANT_ID = os.getenv("MS_TENANT_ID", "")
MS_CLIENT_ID = os.getenv("MS_CLIENT_ID", "")
MS_CLIENT_SECRET = os.getenv("MS_CLIENT_SECRET", "")
ONEDRIVE_DRIVE_ID = os.getenv("ONEDRIVE_DRIVE_ID", "")
ONEDRIVE_CARPETA_CV = os.getenv("ONEDRIVE_CARPETA_CV", "/HojasDeVida")
GRAPH_SCOPES = ["https://graph.microsoft.com/.default"]
SYNC_INTERVALO_HORAS = int(os.getenv("SYNC_INTERVALO_HORAS", "6"))

# --- Servicio de IA (RNF33: configurable sin recompilar) ---------------------
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODELO = os.getenv("LLM_MODELO", "claude-sonnet-4-6")
EMBEDDING_MODELO = os.getenv("EMBEDDING_MODELO", "text-embedding-3-small")
EMBEDDING_DIMENSIONES = int(os.getenv("EMBEDDING_DIMENSIONES", "1536"))

# --- Parámetros del motor de matching (RNF02) --------------------------------
TOP_N_RESULTADOS = int(os.getenv("TOP_N_RESULTADOS", "5"))
FINALISTAS_RERANK = int(os.getenv("FINALISTAS_RERANK", "20"))
UMBRAL_AFINIDAD_MINIMA = float(os.getenv("UMBRAL_AFINIDAD_MINIMA", "60"))
CHUNK_TAMANIO = int(os.getenv("CHUNK_TAMANIO", "1200"))
CHUNK_SOLAPAMIENTO = int(os.getenv("CHUNK_SOLAPAMIENTO", "200"))

# --- Seguridad ---------------------------------------------------------------
JWT_SECRET = os.getenv("JWT_SECRET", "beematch-dev-secret-cambiar-en-produccion")
JWT_ALGORITHM = "HS256"
JWT_EXPIRACION_HORAS = int(os.getenv("JWT_EXPIRACION_HORAS", "8"))

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
