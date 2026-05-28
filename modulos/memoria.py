import os
import chromadb
import uuid
import datetime
from chromadb.utils import embedding_functions

# 1. Definimos dónde se va a guardar la bóveda físicamente en tu PC
# Esto creará una carpeta llamada "boveda_memoria" justo al lado de este archivo
ruta_actual = os.path.dirname(os.path.abspath(__file__))
ruta_db = os.path.join(ruta_actual, "boveda_memoria")

print(f"🧠 [MEMORIA] Inicializando bóveda en: {ruta_db}")

# 2. Arrancamos el cliente de ChromaDB (PersistentClient hace que los datos no se borren al apagar la PC)
cliente = chromadb.PersistentClient(path=ruta_db)

# 3. Configuramos el "Traductor" (Embedding)
# all-MiniLM-L6-v2 es un modelo ultra rápido, gratuito y pesa solo ~80MB. Corre 100% en CPU.
modelo_traductor = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

# 4. Creamos las "Cajas" (Colecciones) donde irán los recuerdos
# get_or_create significa que si la caja no existe, la crea. Si ya existe, simplemente la abre.
coleccion_principal = cliente.get_or_create_collection(
    name="contexto_general",
    embedding_function=modelo_traductor
)

print("✅ [MEMORIA] Base de datos vectorial lista y conectada.")

# =====================================================================
# HERRAMIENTAS DE GUARDADO Y BÚSQUEDA
# =====================================================================

def guardar_recuerdo(texto_a_guardar, etiqueta_tema, metadatos_extra=None):
    """
    Toma un texto, le pega una etiqueta (ej: 'ProyectoSubli', 'Juegos') y lo guarda.
    """
    # 1. Generamos un DNI único e irrepetible para este recuerdo
    id_recuerdo = str(uuid.uuid4())
    
    # 2. Preparamos el sello de metadatos (el Log)
    fecha_hoy = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    metadatos = {
        "etiqueta": etiqueta_tema,
        "fecha_guardado": fecha_hoy
    }
    
    # Si le pasamos datos extra (ej: nombre del PDF), los suma al sello
    if metadatos_extra:
        metadatos.update(metadatos_extra)

    # 3. Lo inyectamos en la base de datos
    coleccion_principal.add(
        documents=[texto_a_guardar],
        metadatas=[metadatos],
        ids=[id_recuerdo]
    )
    
    print(f"📥 [MEMORIA] Recuerdo guardado con éxito. (Tema: {etiqueta_tema})")
    return True


def buscar_contexto(pregunta_usuario, cantidad_resultados=3): # <--- CAMBIO 1: Pedimos 3 en vez de 1
    """
    Traduce la pregunta a números y busca el recuerdo más parecido en la bóveda.
    """
    print(f"🔍 [MEMORIA] Escaneando recuerdos para: '{pregunta_usuario}'")
    
    resultados = coleccion_principal.query(
        query_texts=[pregunta_usuario],
        n_results=cantidad_resultados
    )
    
    # Extraemos la lista de recuerdos encontrados
    documentos_encontrados = resultados['documents'][0]
    
    if documentos_encontrados:
        print("💡 [MEMORIA] ¡Contexto encontrado!")
        # CAMBIO 2: Unimos los 3 recuerdos con un separador para que Gemini los lea TODOS
        contexto_unido = " | ".join(documentos_encontrados) 
        return [contexto_unido] # Lo devolvemos como lista para que ia.py no se rompa
    else:
        print("🤷‍♂️ [MEMORIA] No hay recuerdos relacionados con esto.")
        return []
   