import os
import chromadb
import uuid
import datetime
import json 
import threading
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
# HERRAMIENTAS DE GUARDADO Y BÚSQUEDA
# =====================================================================
def guardar_recuerdo(texto_a_guardar, etiqueta_tema, metadatos_extra=None):
    id_recuerdo = str(uuid.uuid4())
    fecha_hoy = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    metadatos = {"etiqueta": etiqueta_tema, "fecha_guardado": fecha_hoy}
    if metadatos_extra: metadatos.update(metadatos_extra)

    coleccion_principal.add(documents=[texto_a_guardar], metadatas=[metadatos], ids=[id_recuerdo])
    print(f"📥 [MEMORIA] Recuerdo guardado con éxito. (Tema: {etiqueta_tema})")
    return True

def buscar_contexto(pregunta_usuario, cantidad_resultados=3):
    print(f"🔍 [MEMORIA] Escaneando recuerdos para: '{pregunta_usuario}'")
    resultados = coleccion_principal.query(query_texts=[pregunta_usuario], n_results=cantidad_resultados)
    documentos_encontrados = resultados['documents'][0]
    
    if documentos_encontrados:
        print("💡 [MEMORIA] ¡Contexto encontrado!")
        contexto_unido = " | ".join(documentos_encontrados) 
        return [contexto_unido] 
    else:
        print("🤷‍♂️ [MEMORIA] No hay recuerdos relacionados con esto.")
        return []

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
        self._timers = {}  # {ruta: timer}
        self._lock = threading.Lock()

    def on_modified(self, event):
        # Ignorar si es directorio o archivos del sistema
        if event.is_directory or any(x in event.src_path for x in ['.git', '.cortana', '__pycache__', 'venv', 'chroma.sqlite3']):
            return

        ruta_abs = os.path.abspath(event.src_path)
        nombre_archivo = os.path.basename(ruta_abs)

        # Cancelar cualquier timer pendiente para esta ruta
        with self._lock:
            if ruta_abs in self._timers:
                self._timers[ruta_abs].cancel()
                del self._timers[ruta_abs]

        # Crear un nuevo timer
        timer = threading.Timer(self.debounce_ms / 1000.0, self._procesar_cambio, args=[ruta_abs, nombre_archivo])
        timer.daemon = True
        with self._lock:
            self._timers[ruta_abs] = timer
        timer.start()

    def _procesar_cambio(self, ruta_abs, nombre_archivo):
        """Procesa el cambio después del debounce."""
        # Limpiar el timer
        with self._lock:
            if ruta_abs in self._timers:
                del self._timers[ruta_abs]

        print(f"👁️ [RADAR] Cambio confirmado en: {nombre_archivo}")

        # Usar los métodos thread-safe de config.estado
        archivos_memoria = config.estado.obtener_archivos_copia()
        if ruta_abs in archivos_memoria:
            # Eliminar de la caché
            config.estado.eliminar_archivo_memoria(ruta_abs)
            
            # Eliminar del contexto del chat
            contexto_actual = config.estado.obtener_contexto_copia()
            nuevo_contexto = []
            for msg in contexto_actual:
                if isinstance(msg.get('parts', [''])[0], str) and f"[CONTENIDO DE '{ruta_abs}']:" in msg['parts'][0]:
                    continue
                nuevo_contexto.append(msg)
            
            # Actualizar el contexto de forma segura
            config.estado.contexto_chat = nuevo_contexto

            msg_log = f"Caché desactualizada limpia para: {nombre_archivo}. Argus leerá los cambios nuevos."
            print(f"💡 [RADAR] {msg_log}")
            if self.ui_callback:
                self.ui_callback("⚙️ Sistema", f"🔄 Radar: Detectado cambio manual en '{nombre_archivo}'. Memoria sincronizada.", "#80868B")

def iniciar_radar_proyecto(ruta_workspace, ui_callback=None):
    """Arranca el hilo espía que vigila tu carpeta de desarrollo con debounce."""
    global _observador_global
    
    # Si ya había un radar corriendo para otro proyecto, lo apagamos primero
    if _observador_global:
        _observador_global.stop()
        _observador_global.join()
        
    print(f"👁️ [RADAR] Activando vigilancia en tiempo real para: {ruta_workspace}")
    manejador = ManejadorCambiosProyecto(ruta_workspace, ui_callback, debounce_ms=500)
    _observador_global = Observer()
    _observador_global.schedule(manejador, path=ruta_workspace, recursive=True)
    _observador_global.start()