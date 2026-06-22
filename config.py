import os
import sys
import threading
from dotenv import load_dotenv

# 1. Parche para la memoria (ChromaDB)
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

# 2. Parche definitivo para la Tarjeta Gráfica (Whisper/CTranslate2)
rutas_nvidia = [
    os.path.join(sys.prefix, "Lib", "site-packages", "torch", "lib"),
    os.path.join(sys.prefix, "Lib", "site-packages", "nvidia", "cublas", "bin"),
    os.path.join(sys.prefix, "Lib", "site-packages", "nvidia", "cudnn", "bin")
]
for ruta in rutas_nvidia:
    if os.path.exists(ruta):
        os.environ["PATH"] = ruta + os.pathsep + os.environ.get("PATH", "")

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
# ESTADOS DEL SISTEMA GLOBAL (CENTRALIZADO CON THREAD SAFETY)
# =========================================================
class EstadoGlobal:
    def __init__(self):
        self._lock = threading.Lock()
        self.modo_actual = "general"
        self.workspace_actual = None
        self.snapshot_actual = ""
        self.contexto_chat = []
        self.archivos_en_memoria = set()
        self.documento_volatil = ""
        self.pendiente_de_borrado = ""
        self.pendiente_de_git = None
        self.archivo_pendiente_inyeccion = None

    # ─── MÉTODOS SEGUROS PARA MODIFICAR EL ESTADO ──────────────────────

    def agregar_mensaje_chat(self, mensaje):
        """Añade un mensaje al contexto del chat de forma thread-safe."""
        with self._lock:
            self.contexto_chat.append(mensaje)
            if len(self.contexto_chat) > 100:
                self.contexto_chat = self.contexto_chat[-100:]

    def agregar_archivo_memoria(self, ruta):
        """Añade un archivo a la caché de memoria de forma thread-safe."""
        with self._lock:
            self.archivos_en_memoria.add(ruta)

    def eliminar_archivo_memoria(self, ruta):
        """Elimina un archivo de la caché de memoria de forma thread-safe."""
        with self._lock:
            self.archivos_en_memoria.discard(ruta)

    def limpiar_memoria(self):
        """Limpia el contexto y la caché de archivos de forma thread-safe."""
        with self._lock:
            self.contexto_chat.clear()
            self.archivos_en_memoria.clear()
            self.documento_volatil = ""

    def obtener_contexto_copia(self):
        """Devuelve una copia del contexto del chat para lectura thread-safe."""
        with self._lock:
            return list(self.contexto_chat)

    def obtener_archivos_copia(self):
        """Devuelve una copia del set de archivos en memoria para lectura thread-safe."""
        with self._lock:
            return set(self.archivos_en_memoria)

    def cambiar_modo(self, nuevo_modo):
        """Cambia el modo actual de forma thread-safe."""
        with self._lock:
            self.modo_actual = nuevo_modo

    def cambiar_workspace(self, ruta):
        """Cambia el workspace actual de forma thread-safe."""
        with self._lock:
            self.workspace_actual = ruta

    # ─── PROPIEDADES CON ACCESO SEGURO (PERO MANTENEMOS COMPATIBILIDAD) ──

    @property
    def contexto_chat(self):
        """Acceso de solo lectura al contexto (con copia)."""
        with self._lock:
            return self._contexto_chat

    @contexto_chat.setter
    def contexto_chat(self, value):
        """Asignación del contexto de forma thread-safe."""
        with self._lock:
            self._contexto_chat = value

    @property
    def archivos_en_memoria(self):
        """Acceso de solo lectura a archivos en memoria (con copia)."""
        with self._lock:
            return self._archivos_en_memoria

    @archivos_en_memoria.setter
    def archivos_en_memoria(self, value):
        """Asignación de archivos en memoria de forma thread-safe."""
        with self._lock:
            self._archivos_en_memoria = value

    # ─── INICIALIZACIÓN DE ATRIBUTOS INTERNOS ───────────────────────────

    def __getattribute__(self, name):
        """Intercepta el acceso a atributos que tienen backing store."""
        if name in ['_contexto_chat', '_archivos_en_memoria']:
            return super().__getattribute__(name)
        # Para los atributos normales, acceso directo
        return super().__getattribute__(name)

    def __setattr__(self, name, value):
        """Intercepta la asignación para sincronizar backing stores."""
        if name == 'contexto_chat':
            with self._lock:
                self._contexto_chat = value
        elif name == 'archivos_en_memoria':
            with self._lock:
                self._archivos_en_memoria = value
        else:
            super().__setattr__(name, value)

# ─── INSTANCIA GLOBAL (SINGLETON) ──────────────────────────────────────────
estado = EstadoGlobal()

# Inicializar los backing stores después de la creación
with estado._lock:
    estado._contexto_chat = []
    estado._archivos_en_memoria = set()