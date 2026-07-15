import os
import chromadb
import uuid
import datetime
import json
import threading
import time
import config
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from chromadb.utils import embedding_functions

# 1. Definimos dónde se va a guardar la bóveda físicamente
ruta_actual = os.path.dirname(os.path.abspath(__file__))
ruta_db = os.path.join(ruta_actual, "boveda_memoria")

print(f"🧠 [MEMORIA] Inicializando bóveda en: {ruta_db}")

cliente = chromadb.PersistentClient(path=ruta_db)
modelo_traductor = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

coleccion_principal = cliente.get_or_create_collection(
    name="contexto_general",
    embedding_function=modelo_traductor
)

print("✅ [MEMORIA] Base de datos vectorial lista y conectada.")

# =====================================================================
# CACHÉ DE EMBEDDINGS (evita recalcular embeddings repetidos)
# =====================================================================
_cache_embeddings = {}          # {texto: resultado}
_cache_lock = threading.Lock()
_CACHE_MAX_SIZE = 50            # máximo de entradas en caché
_CACHE_TTL_SEGUNDOS = 300       # 5 minutos de vida por entrada

def _cache_get(clave: str):
    """Obtiene un resultado cacheado si existe y no expiró."""
    with _cache_lock:
        entry = _cache_embeddings.get(clave)
        if entry:
            resultado, timestamp = entry
            if time.time() - timestamp < _CACHE_TTL_SEGUNDOS:
                return resultado
            else:
                del _cache_embeddings[clave]
    return None

def _cache_set(clave: str, valor):
    """Guarda un resultado en caché, limpiando entradas viejas si es necesario."""
    with _cache_lock:
        if len(_cache_embeddings) >= _CACHE_MAX_SIZE:
            # Eliminar la entrada más vieja
            clave_vieja = min(_cache_embeddings, key=lambda k: _cache_embeddings[k][1])
            del _cache_embeddings[clave_vieja]
        _cache_embeddings[clave] = (valor, time.time())

def limpiar_cache():
    """Limpia toda la caché de embeddings."""
    with _cache_lock:
        _cache_embeddings.clear()
    print("🧹 [MEMORIA] Caché de embeddings limpiada.")

# =====================================================================
# HERRAMIENTAS DE GUARDADO Y BÚSQUEDA (OPTIMIZADAS)
# =====================================================================
def guardar_recuerdo(texto_a_guardar, etiqueta_tema, metadatos_extra=None):
    """Guarda un recuerdo en la bóveda. Thread-safe."""
    id_recuerdo = str(uuid.uuid4())
    fecha_hoy = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    metadatos = {"etiqueta": etiqueta_tema, "fecha_guardado": fecha_hoy}
    if metadatos_extra:
        metadatos.update(metadatos_extra)

    try:
        coleccion_principal.add(
            documents=[texto_a_guardar],
            metadatas=[metadatos],
            ids=[id_recuerdo]
        )
        # Invalidar caché relacionada ya que hay nuevo contenido
        limpiar_cache()
        print(f"📥 [MEMORIA] Recuerdo guardado con éxito. (Tema: {etiqueta_tema})")
        return True
    except Exception as e:
        print(f"❌ [MEMORIA] Error al guardar recuerdo: {e}")
        return False


def buscar_contexto(pregunta_usuario, cantidad_resultados=3):
    """
    Busca en la bóveda DIRECTO sin pasar por MCP.
    Usa caché para consultas repetidas. Thread-safe.
    """
    clave_cache = f"{pregunta_usuario}:{cantidad_resultados}"
    resultado_cacheado = _cache_get(clave_cache)
    if resultado_cacheado is not None:
        print(f"⚡ [MEMORIA] Resultado desde caché para: '{pregunta_usuario[:40]}'")
        return resultado_cacheado

    print(f"🔍 [MEMORIA] Escaneando bóveda para: '{pregunta_usuario[:60]}'")
    try:
        resultados = coleccion_principal.query(
            query_texts=[pregunta_usuario],
            n_results=cantidad_resultados
        )
        documentos_encontrados = resultados['documents'][0]

        if documentos_encontrados:
            print(f"💡 [MEMORIA] {len(documentos_encontrados)} resultado(s) encontrado(s).")
            contexto_unido = " | ".join(documentos_encontrados)
            salida = [contexto_unido]
        else:
            print("🤷 [MEMORIA] No hay recuerdos relacionados con esto.")
            salida = []

        _cache_set(clave_cache, salida)
        return salida

    except Exception as e:
        print(f"❌ [MEMORIA] Error al buscar contexto: {e}")
        return []


# =====================================================================
# BÚSQUEDA ANTICIPADA (pre-fetch mientras la IA piensa)
# =====================================================================
_resultado_anticipado = None
_anticipado_lock = threading.Lock()
_anticipado_consulta = None


def iniciar_busqueda_anticipada(consulta: str):
    """
    Lanza la búsqueda en bóveda en un hilo paralelo mientras Gemini/DeepSeek
    procesa la consulta. El resultado queda disponible para cuando se necesite.
    """
    global _resultado_anticipado, _anticipado_consulta

    with _anticipado_lock:
        _resultado_anticipado = None
        _anticipado_consulta = consulta

    def _buscar():
        global _resultado_anticipado
        resultado = buscar_contexto(consulta)
        with _anticipado_lock:
            # Solo guardar si la consulta sigue siendo la misma
            if _anticipado_consulta == consulta:
                _resultado_anticipado = resultado
                print(f"⚡ [MEMORIA] Búsqueda anticipada lista para: '{consulta[:40]}'")

    hilo = threading.Thread(target=_buscar, daemon=True)
    hilo.start()


def obtener_resultado_anticipado(consulta: str):
    """
    Obtiene el resultado de la búsqueda anticipada si está disponible
    y corresponde a la misma consulta. Si no, hace la búsqueda normal.
    """
    with _anticipado_lock:
        if _anticipado_consulta == consulta and _resultado_anticipado is not None:
            print(f"⚡ [MEMORIA] Usando resultado anticipado para: '{consulta[:40]}'")
            return _resultado_anticipado

    # Si no hay resultado anticipado listo, buscar directo
    return buscar_contexto(consulta)


# =====================================================================
# SNAPSHOT
# =====================================================================
def guardar_snapshot(ruta_workspace, texto_estado):
    try:
        ruta_cortana = os.path.join(ruta_workspace, ".cortana")
        os.makedirs(ruta_cortana, exist_ok=True)
        ruta_archivo = os.path.join(ruta_cortana, "snapshot.json")

        with open(ruta_archivo, "w", encoding="utf-8") as f:
            json.dump({"estado": texto_estado}, f, ensure_ascii=False, indent=4)

        print(f"📸 [SNAPSHOT] Estado físico guardado en: {ruta_archivo}")
        return True
    except Exception as e:
        print(f"❌ Error al guardar snapshot local: {e}")
        return False


def cargar_snapshot(ruta_workspace):
    try:
        ruta_archivo = os.path.join(ruta_workspace, ".cortana", "snapshot.json")
        if os.path.exists(ruta_archivo):
            with open(ruta_archivo, "r", encoding="utf-8") as f:
                data = json.load(f)
            print(f"📂 [SNAPSHOT] Estado recuperado físicamente del proyecto.")
            return data.get("estado", "")
    except Exception as e:
        print(f"❌ Error al cargar snapshot local: {e}")
    return ""


# =====================================================================
# MOTOR WATCHDOG (Radar de Cambios con Debounce)
# =====================================================================
_observador_global = None


class ManejadorCambiosProyecto(FileSystemEventHandler):
    """Manejador que reacciona cuando modificas un archivo con debounce."""

    def __init__(self, ruta_workspace, ui_callback=None, debounce_ms=500):
        self.ruta_workspace = ruta_workspace
        self.ui_callback = ui_callback
        self.debounce_ms = debounce_ms
        self._timers = {}
        self._lock = threading.Lock()

    def on_modified(self, event):
        if event.is_directory or any(
            x in event.src_path
            for x in ['.git', '.cortana', '__pycache__', 'venv', 'chroma.sqlite3']
        ):
            return

        ruta_abs = os.path.abspath(event.src_path)
        nombre_archivo = os.path.basename(ruta_abs)

        with self._lock:
            if ruta_abs in self._timers:
                self._timers[ruta_abs].cancel()
                del self._timers[ruta_abs]

        timer = threading.Timer(
            self.debounce_ms / 1000.0,
            self._procesar_cambio,
            args=[ruta_abs, nombre_archivo]
        )
        timer.daemon = True
        with self._lock:
            self._timers[ruta_abs] = timer
        timer.start()

    def _procesar_cambio(self, ruta_abs, nombre_archivo):
        with self._lock:
            if ruta_abs in self._timers:
                del self._timers[ruta_abs]

        print(f"👁️ [RADAR] Cambio confirmado en: {nombre_archivo}")

        archivos_memoria = config.estado.obtener_archivos_copia()
        if ruta_abs in archivos_memoria:
            config.estado.eliminar_archivo_memoria(ruta_abs)

            contexto_actual = config.estado.obtener_contexto_copia()
            nuevo_contexto = [
                msg for msg in contexto_actual
                if not (
                    isinstance(msg.get('parts', [''])[0], str)
                    and f"[CONTENIDO DE '{ruta_abs}']:" in msg['parts'][0]
                )
            ]
            # FIX: antes era `config.estado.contexto_chat = nuevo_contexto`,
            # una asignación directa que se salta el lock de EstadoGlobal.
            # Esto corre dentro de un hilo de threading.Timer (debounce del
            # watchdog), así que si el hilo principal está en medio de un
            # agregar_mensaje_chat() (que sí usa el lock) al mismo tiempo,
            # hay una condición de carrera real sobre la misma lista.
            # Ahora se usa el método thread-safe centralizado.
            config.estado.reemplazar_contexto_chat(nuevo_contexto)

            msg_log = f"Caché limpia para: {nombre_archivo}. Argus leerá los cambios nuevos."
            print(f"💡 [RADAR] {msg_log}")
            if self.ui_callback:
                self.ui_callback(
                    "⚙️ Sistema",
                    f"🔄 Radar: Cambio detectado en '{nombre_archivo}'. Memoria sincronizada.",
                    "#80868B"
                )


def iniciar_radar_proyecto(ruta_workspace, ui_callback=None):
    """Arranca el hilo espía que vigila tu carpeta de desarrollo con debounce."""
    global _observador_global

    if _observador_global:
        _observador_global.stop()
        _observador_global.join()

    print(f"👁️ [RADAR] Activando vigilancia en tiempo real para: {ruta_workspace}")
    manejador = ManejadorCambiosProyecto(ruta_workspace, ui_callback, debounce_ms=500)
    _observador_global = Observer()
    _observador_global.schedule(manejador, path=ruta_workspace, recursive=True)
    _observador_global.start()