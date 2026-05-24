import os
from dotenv import load_dotenv

# Carga las variables ocultas del archivo .env a la memoria del sistema
load_dotenv()

# Rescatamos la llave
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# Pequeño fail-safe de seguridad por si el archivo .env se borra o está mal escrito
if not GEMINI_API_KEY:
    raise ValueError("⚠️ ALERTA: No se encontró la API Key. Revisá tu archivo .env")

# ---------------------------------------------------------
# CONSTANTES GLOBALES DEL ASISTENTE
# ---------------------------------------------------------
TECLA_HABLAR = 'f8'
FS_AUDIO = 16000