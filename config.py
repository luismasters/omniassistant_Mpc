import os
import sys
import threading
from dotenv import load_dotenv

# Helper puro para persistir evidencia web entre turnos (rotación acotada).
from modulos.mensajes_web import agregar_evidencia

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
# RECUPERACIÓN AUTOMÁTICA DE MEMORIA (Fase 4)
# =========================================================
# La bóveda de ChromaDB usa el espacio por defecto de HNSW (l2).
# ChromaDB devuelve `distances` = distancia euclídea (menor = más similar).
# El recuperador la transforma a similitud como `sim = 1 - distancia`
# (monotónica y simple, sin fórmula compleja innecesaria).
#
# MEMORIA_SCORE_MIN es un UMBRAL CONSERVADOR, NO un valor calibrado:
# con la bóveda real (18 recuerdos, origen_fuente=perfil_proyecto) se
# observó:
#   - consulta RELEVANTE  → distancia ~0.47 (similitud ~0.53)
#   - consulta IRRELEVANTE → distancia ~0.57+ (similitud ~0.43 o menos)
#   - sin metadata custom → ChromaDB usa l2 por defecto.
# Queda PENDIENTE de recalibrar con más datos reales si el comportamiento
# en producción así lo requiere.
MEMORIA_TOP_K = 3
MEMORIA_SCORE_MIN = 0.45
MEMORIA_MAX_CARACTERES = 800
MEMORIA_DECAY_RECENCIA = 0.02

# =========================================================
# API KEYS
# =========================================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# =========================================================
# MAQUINA (rutas por equipo) — personalizables vía .env
# =========================================================
# Rutas personales que antes estaban hardcodeadas en modulos/sistema.py.
# Se configuran por equipo en el .env local (que NO se commitea).
#
# ARGUS_RUTA_JUEGOS: carpeta extra que el radar de juegos escanea para
# lanzar juegos "portables" que no instalan acceso directo en el menú
# Inicio. Vacío ("") = no se escanea nada extra.
RUTA_JUEGOS = os.getenv("ARGUS_RUTA_JUEGOS", "")

# ALIASES_USUARIO: {nombre_usuario_viejo: ruta_destino}. Con destino ""
# se reemplaza por el home real (os.path.expanduser("~")). Sirve cuando el
# LLM/usuario escribe una ruta con un nombre de usuario anterior al actual.
ALIASES_USUARIO = {"luis": ""}

# =========================================================
# MODELO POR DEFECTO GLOBAL (Fase D, Punto 2)
# =========================================================
# "Por Defecto"/"Auto" ya NO depende del modo: es UNA preferencia global.
# Si el usuario no elige un modelo específico, se usa este (único) para
# TODOS los contextos. Elegimos Gemini por defecto porque es el único con
# tool-calling MCP disponible (mata el "parpadeo MCP" al cambiar de modo).
# Configurable por env: ARGUS_MODELO_DEFECTO.
MODELO_DEFECTO_GLOBAL = os.getenv("ARGUS_MODELO_DEFECTO", "Gemini 3.5 Flash Lite")

# Activación de capacidad por embeddings (Fase D, Punto 3, refinamiento):
# similitud semántica contra prototipos cuando las keywords no detectan señal.
# Kill-switch por env: ARGUS_ACTIVACION_CAPACIDAD_EMBEDDINGS=0 lo desactiva.
ACTIVACION_CAPACIDAD_EMBEDDINGS = os.getenv("ARGUS_ACTIVACION_CAPACIDAD_EMBEDDINGS", "1") != "0"

# Ciudad para el widget de clima (configurable desde .env)
CIUDAD_CLIMA = os.getenv("CIUDAD_CLIMA", "San Martin, Buenos Aires, Argentina")

# Sin GEMINI_API_KEY la app NO crashea al importar: queda "" y cada llamada
# de IA responde con un mensaje amigable pidiendo configurarla (ver
# modulos.ia.enviar_a_gemini). Se imprime una advertencia única al arrancar.
TIENE_API_GEMINI = bool(GEMINI_API_KEY)
if not TIENE_API_GEMINI:
    print("⚠️ [CONFIG] GEMINI_API_KEY no configurada en .env. Las llamadas de IA responderán con un aviso.")

# =========================================================
# CONFIGURACIÓN DE AUDIO
# =========================================================
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "medium")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cuda")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "float16")

TECLA_HABLAR = 'f8'
FS_AUDIO = 16000

# Palabra clave de corte para finalizar la captura de voz por wake word.
# Se usa en audio_custom.py para el recognizer de corte en tiempo real.
PALABRA_CORTE_VOZ = os.getenv("PALABRA_CORTE_VOZ", "procede")

# Tiempo de silencio (en segundos) tras hablar que finaliza la grabación.
# Ampliado a 2.5s para permitir pausas naturales al dar instrucciones largas.
SILENCIO_CORTE_GRABACION = 2.5

# Umbral mínimo de RMS para considerar que hay voz activa en el micrófono.
# Sensibilidad optimizada (150) para captar adecuadamente la voz normal en micrófonos estándar.
RMS_UMBRAL_VOZ = int(os.getenv("RMS_UMBRAL_VOZ", "150"))

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
# Lock canónico de serialización del contexto de chat (C1). Lo usa
# modulos.ia (alias `_RLOCK_PROC`, cada turno) y las mutaciones que rebinden
# o limpian el contexto desde otros hilos (cambio de modo, limpieza): así un
# cambio de modo / limpiado NUNCA se intercala con un turno en curso.
RLOCK_CONTEXTO = threading.RLock()


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
        self.evidencia_web = []
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
        # Capacidad fijada por el usuario (pin): "general" | "mentor" | "gamer"
        # | None = automática (detección por modo/tema, Fase D).
        self.capacidad_fijada = None
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

        # Fase P: persistencia durable (best-effort, nunca bloquea el turno).
        # Se persiste DENTRO del lock canónico para no intercalarse con un
        # cambio de modo ni con otro turno (misma garantía de H.2).
        try:
            from modulos.persistencia import registrar_mensaje
            with RLOCK_CONTEXTO:
                registrar_mensaje(
                    self.modo_actual,
                    mensaje.get("role", "user"),
                    mensaje.get("parts", []),
                )
        except Exception:
            pass

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
        with RLOCK_CONTEXTO:
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
        with RLOCK_CONTEXTO:
            with self._lock:
                self.contexto_chat.clear()
                self.archivos_en_memoria.clear()
                self.documento_volatil = ""
                self.evidencia_web = []

    def obtener_contexto_copia(self):
        """Devuelve una copia del contexto del chat para lectura thread-safe."""
        with self._lock:
            return list(self.contexto_chat)

    def agregar_evidencia_web(self, texto_evidencia):
        """
        Persiste la evidencia web de un turno (resultados de la búsqueda) de
        forma thread-safe. La evidencia vive SEPARADA del contexto
        conversacional y se recorta a los últimos `MAX_EVIDENCIA_GUARDADA`.
        """
        with self._lock:
            self.evidencia_web = agregar_evidencia(self.evidencia_web, texto_evidencia)

    def obtener_evidencia_web(self):
        """Devuelve una copia de la evidencia web persistida (turnos previos)."""
        with self._lock:
            return list(self.evidencia_web)

    def limpiar_evidencia_web(self):
        """Descarta toda la evidencia web persistida (thread-safe)."""
        with self._lock:
            self.evidencia_web = []

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
        y restaura el del nuevo modo.         Cada modo (general, mentor, gamer) mantiene
        su propio histórico de conversación.
        """
        with RLOCK_CONTEXTO:
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
                # La evidencia web queda asociada a la conversación del modo anterior
                self.evidencia_web = []

            # Fase P: cerrar la sesión persistida del contexto saliente.
            # (Fuera del lock anidado pero dentro de RLOCK_CONTEXTO: no
            # interfiere con turnos en curso ni con el cambio de contexto.)
            try:
                from modulos.persistencia import cerrar_sesion, armar_context_id
                cerrar_sesion(armar_context_id(modo_anterior))
            except Exception:
                pass

    def cambiar_modo_visualizacion(self, nuevo_modo_vis):
        """Cambia el modo de visualización (tradicional, flotante, escritorio) de forma thread-safe."""
        with self._lock:
            self.modo_visualizacion = nuevo_modo_vis

    def cambiar_modelo_seleccionado(self, nuevo_modelo):
        """Cambia el modelo seleccionado de forma thread-safe."""
        with self._lock:
            self.modelo_seleccionado = nuevo_modelo

    def fijar_capacidad(self, capacidad):
        """Fija la capacidad activa (pin). None = automática. Thread-safe."""
        with self._lock:
            self.capacidad_fijada = capacidad

    def obtener_capacidad_fijada(self):
        """Devuelve la capacidad fijada (None = automática). Thread-safe."""
        with self._lock:
            return self.capacidad_fijada

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
        with RLOCK_CONTEXTO:
            with self._lock:
                self.contexto_chat.clear()
                self.evidencia_web = []

    def restaurar_historial_persistido(self, mensajes_historial):
        """
        Hidrata el contexto con el historial recuperado de disco (Fase P).

        Regla de retomar (decisión del 12/08/2026):
        - Si el contexto actual está vacío → lo reemplaza por el historial.
        - Si ya hay conversación en curso → ANEXA el historial al final
          (no pierde lo que se está escribiendo), recortando a
          MAX_MENSAJES_CONTEXTO si hace falta.

        NO persiste el historial recuperado (no debe re-grabarse): solo toca
        la RAM. Thread-safe (mismo RLOCK_CONTEXTO canónico, respeta H.2).
        """
        historial = [dict(m) for m in (mensajes_historial or [])]
        if not historial:
            return
        with RLOCK_CONTEXTO:
            with self._lock:
                if not self.contexto_chat:
                    self.contexto_chat = historial
                else:
                    self.contexto_chat.extend(historial)
                    if len(self.contexto_chat) > MAX_MENSAJES_CONTEXTO:
                        self.contexto_chat = self.contexto_chat[-MAX_MENSAJES_CONTEXTO:]

    def limpiar_archivos_memoria(self):
        """Limpia la caché de archivos (thread-safe)."""
        with self._lock:
            self.archivos_en_memoria.clear()

# Instancia global única
estado = EstadoGlobal()