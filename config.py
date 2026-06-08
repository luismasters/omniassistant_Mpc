import os
from dotenv import load_dotenv

# Carga las variables ocultas del archivo .env a la memoria del sistema
load_dotenv()

# =========================================================
# CONFIGURACIÓN DE SEGURIDAD (SANDBOX)
# =========================================================
# Define la carpeta raíz de OmniAssistant como zona segura
SANDBOX_BASE = os.path.abspath(os.path.dirname(__file__))

# =========================================================
# LÍMITES CONFIGURABLES (Seguridad Fase 1)
# =========================================================
MAX_FILE_SIZE_MB = 10
MAX_CONTENT_SIZE_MB = 10
MAX_PDF_PAGES = 100
MAX_CHARACTERS = 100_000
MIN_FREE_SPACE_MB = 100

# =========================================================
# API KEYS
# =========================================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# Pequeño fail-safe de seguridad por si el archivo .env se borra
if not GEMINI_API_KEY:
    raise ValueError("⚠️ ALERTA: No se encontró la API Key. Revisá tu archivo .env")

# =========================================================
# CONFIGURACIÓN DE AUDIO DISTRIBUIBLE
# =========================================================
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "medium")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cuda")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "float16")

TECLA_HABLAR = 'f8'
FS_AUDIO = 16000

# =========================================================
# ESTADOS DEL SISTEMA
# =========================================================
MODO_PROGRAMADOR = True # Cambiar a False en entorno de producción