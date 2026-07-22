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
MAX_MENSAJES_CONTEXTO = 25

# =========================================================
# API KEYS
# =========================================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Ciudad para el widget de clima (configurable desde .env)
CIUDAD_CLIMA = os.getenv("CIUDAD_CLIMA", "San Martin, Buenos Aires, Argentina")

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

# Límite de seguridad para grabación continua de voz (en segundos).
# Es solo una red de seguridad ante un fallo en la condición de corte
# (ej. el callback del gamepad o del teclado deja de reportar el estado
# real del botón). NO debería alcanzarse en uso normal: el corte real
# ocurre al soltar la tecla/stick. Antes estaba hardcodeado a 30s dentro
# de audio_custom.py, lo cual cortaba explicaciones largas de forma
# prematura aunque el botón siguiera presionado.
MAX_GRABACION_SEGUNDOS = 180

# =========================================================
# ESTADO GLOBAL CON THREAD SAFETY (VERSIÓN SIMPLIFICADA)
# =========================================================
class EstadoGlobal:
    def __init__(self):
        self._lock = threading.Lock()
        # Contextos de chat aislados por modo (general, mentor, gamer)
        self._contextos_por_modo = {"general": [], "mentor": [], "gamer": []}
        # Atributos públicos (acceso directo pero con locks en los métodos)
        self.modo_actual = "general"
        self.modelo_seleccionado = "Por Defecto"
        self.workspace_actual = None
        self.snapshot_actual = ""
        self.contexto_chat = []
        self.archivos_en_memoria = set()
        self.documento_volatil = ""
        self.pendiente_de_borrado = ""
        self.pendiente_de_boveda = ""
        self.pendiente_de_git = None
        self.archivo_pendiente_inyeccion = None
        # Contador para perfil de usuario: mensajes nuevos desde la última
        # extracción de hechos. Se incrementa en agregar_mensaje_chat y se
        # resetea vía obtener_y_reiniciar_mensajes_pendientes().
        self.mensajes_desde_ultima_extraccion = 0
        self.modo_visualizacion = "traditional" # "traditional" | "floating" | "desktop"

    # ─── MÉTODOS SEGUROS PARA MODIFICAR EL ESTADO ──────────────────────

    def agregar_mensaje_chat(self, mensaje, contar_para_perfil=True):
        """Añade un mensaje al contexto del chat de forma thread-safe."""
        with self._lock:
            self.contexto_chat.append(mensaje)
            if contar_para_perfil:
                self.mensajes_desde_ultima_extraccion += 1
            if len(self.contexto_chat) > MAX_MENSAJES_CONTEXTO:
                self.contexto_chat = self.contexto_chat[-MAX_MENSAJES_CONTEXTO:]

    def obtener_y_reiniciar_mensajes_pendientes(self):
        """
        Devuelve la cantidad de mensajes acumulados desde la última extracción
        de perfil y resetea el contador a 0. Thread-safe.
        """
        with self._lock:
            count = self.mensajes_desde_ultima_extraccion
            self.mensajes_desde_ultima_extraccion = 0
            return count

    def reemplazar_contexto_chat(self, nuevo_contexto):
        """
        Reemplaza la lista completa de contexto_chat de forma thread-safe.
        FIX: antes, tanto memoria.py (radar de cambios, corre en hilo de
        watchdog) como main_gui.py (_StateProxy.contexto_chat setter, usado
        en _cambiar_modo) asignaban directamente `config.estado.contexto_chat = X`,
        saltándose por completo el lock. Esto es una condición de carrera real:
        si el radar de cambios dispara justo cuando el hilo principal está
        agregando un mensaje (agregar_mensaje_chat, que sí usa el lock), la
        lista puede quedar en un estado inconsistente. Usar este método
        centraliza la escritura y la protege con el mismo lock.
        NOTA: Al reemplazar el contexto también reseteamos el contador de
        mensajes del perfil, ya que estos mensajes no representan conversación
        continua (ej. cambio de modo).
        """
        with self._lock:
            self.contexto_chat = nuevo_contexto
            self.mensajes_desde_ultima_extraccion = 0

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

    @property
    def gamer_mode_activo(self) -> bool:
        """Devuelve True si el Modo Gamer está activo."""
        with self._lock:
            return self.modo_actual == "gamer"

    def cambiar_modo(self, nuevo_modo):
        """Cambia el modo actual de forma thread-safe.
        
        Aísla el contexto de chat por modo: guarda el contexto del modo anterior
        y restaura el del nuevo modo. Cada modo (general, mentor, gamer) mantiene
        su propio histórico de conversación.
        """
        with self._lock:
            # Guardar contexto actual en el modo que estamos dejando
            modo_anterior = self.modo_actual
            self._contextos_por_modo[modo_anterior] = list(self.contexto_chat)
            
            # Cambiar al nuevo modo
            self.modo_actual = nuevo_modo
            
            # Restaurar contexto del nuevo modo (o vacío si nunca se usó)
            self.contexto_chat = list(self._contextos_por_modo.get(nuevo_modo, []))
            
            # Resetear contador de perfil al cambiar de modo
            self.mensajes_desde_ultima_extraccion = 0

    def cambiar_modo_visualizacion(self, nuevo_modo_vis):
        """Cambia el modo de visualización (tradicional, flotante, escritorio) de forma thread-safe."""
        with self._lock:
            self.modo_visualizacion = nuevo_modo_vis

    def cambiar_modelo_seleccionado(self, nuevo_modelo):
        """Cambia el modelo seleccionado de forma thread-safe."""
        with self._lock:
            self.modelo_seleccionado = nuevo_modelo

    def cambiar_workspace(self, ruta):
        """Cambia el workspace actual de forma thread-safe."""
        with self._lock:
            self.workspace_actual = ruta

    def cambiar_snapshot(self, texto):
        """Cambia el snapshot actual de forma thread-safe."""
        with self._lock:
            self.snapshot_actual = texto

    def cambiar_documento_volatil(self, texto):
        """Cambia el documento volátil de forma thread-safe."""
        with self._lock:
            self.documento_volatil = texto

    def limpiar_contexto(self):
        """Limpia el contexto del chat (thread-safe)."""
        with self._lock:
            self.contexto_chat.clear()

    def limpiar_archivos_memoria(self):
        """Limpia la caché de archivos (thread-safe)."""
        with self._lock:
            self.archivos_en_memoria.clear()

# Instancia global única
estado = EstadoGlobal()