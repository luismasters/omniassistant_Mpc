import os
from dotenv import load_dotenv

load_dotenv()

# =========================================================
# CONFIGURACIÓN DE SEGURIDAD (SANDBOX)
# =========================================================
SANDBOX_BASE = os.path.abspath(os.path.dirname(__file__))
RUTAS_SEGURAS = [SANDBOX_BASE]
RUTA_WORKSPACE_ACTUAL = None

# =========================================================
# LÍMITES CONFIGURABLES
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

if not GEMINI_API_KEY:
    raise ValueError("⚠️ No se encontró la API Key")

# =========================================================
# CONFIGURACIÓN DE AUDIO
# =========================================================
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "medium")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cuda")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "float16")

TECLA_HABLAR = 'f8'
FS_AUDIO = 16000

# =========================================================
# ESTADOS DEL SISTEMA GLOBAL (CENTRALIZADO)
# =========================================================
class EstadoGlobal:
    def __init__(self):
        self.modo_actual = "general"
        self.workspace_actual = None
        self.snapshot_actual = ""
        self.contexto_chat = []
        self.archivos_en_memoria = set()
        self.documento_volatil = ""
        self.pendiente_de_borrado = ""
        self.pendiente_de_git = None
        self.archivo_pendiente_inyeccion = None

    def limpiar_memoria(self):
        self.contexto_chat.clear()
        self.archivos_en_memoria.clear()
        self.documento_volatil = ""

estado = EstadoGlobal()