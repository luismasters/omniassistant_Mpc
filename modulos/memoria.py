import os
import chromadb
import uuid
import datetime
from chromadb.utils import embedding_functions

# 1. Definimos dónde se va a guardar la bóveda físicamente
ruta_actual = os.path.dirname(os.path.abspath(__file__))
ruta_db = os.path.join(ruta_actual, "boveda_memoria")

print(f"🧠 [MEMORIA] Inicializando bóveda en: {ruta_db}")

# 2. Arrancamos el cliente de ChromaDB
cliente = chromadb.PersistentClient(path=ruta_db)

# 3. Configuramos el Traductor
modelo_traductor = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

# 4. Creamos la Colección
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

# =====================================================================
# NUEVO: GESTIÓN DE SNAPSHOTS DE PROYECTOS (LIVE WORKSPACE)
# =====================================================================
def guardar_snapshot(nombre_proyecto, texto_estado):
    """Sobreescribe el estado actual de un proyecto para que siempre tenga el contexto fresco."""
    etiqueta = f"Snapshot_{nombre_proyecto}"
    try:
        # Borramos el snapshot anterior si existe (para no mezclar info vieja con nueva)
        coleccion_principal.delete(where={"etiqueta": etiqueta})
    except: pass
    
    guardar_recuerdo(texto_a_guardar=texto_estado, etiqueta_tema=etiqueta)
    print(f"📸 [SNAPSHOT] Estado del proyecto '{nombre_proyecto}' actualizado en la bóveda.")
    return True

def cargar_snapshot(nombre_proyecto):
    """Recupera la foto del estado del proyecto al anclarse."""
    etiqueta = f"Snapshot_{nombre_proyecto}"
    try:
        resultados = coleccion_principal.get(where={"etiqueta": etiqueta})
        if resultados and resultados['documents']:
            print(f"📂 [SNAPSHOT] Contexto de '{nombre_proyecto}' recuperado de la bóveda.")
            return " | ".join(resultados['documents'])
    except: pass
    return ""