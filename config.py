import os
from dotenv import load_dotenv

# Carga las variables ocultas del archivo .env a la memoria del sistema
load_dotenv()

# Rescatamos la llave
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# --- NUEVA CONFIGURACIÓN DE AUDIO DISTRIBUIBLE ---
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "medium")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cuda")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "float16")

# Pequeño fail-safe de seguridad por si el archivo .env se borra o está mal escrito
if not GEMINI_API_KEY:
    raise ValueError("⚠️ ALERTA: No se encontró la API Key. Revisá tu archivo .env")

# ---------------------------------------------------------
# CONSTANTES GLOBALES DEL ASISTENTE
# ---------------------------------------------------------
TECLA_HABLAR = 'f8'
FS_AUDIO = 16000