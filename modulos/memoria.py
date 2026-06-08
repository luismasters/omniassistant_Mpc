import os
import chromadb
import uuid
import datetime
import json 

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

def guardar_snapshot(ruta_workspace, texto_estado):
    """Guarda el estado del proyecto en un archivo JSON dentro del propio proyecto."""
    try:
        # Creamos una carpeta oculta .cortana dentro del proyecto del usuario
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
    """Recupera la foto del estado del proyecto desde el archivo físico."""
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