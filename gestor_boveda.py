import os
import chromadb

# =====================================================================
# CONFIGURACIÓN DE LA BASE DE DATOS
# =====================================================================
# Apuntamos a la carpeta "boveda_memoria" que está dentro de "modulos"
RUTA_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modulos", "boveda_memoria")

print("🔌 Conectando con la Bóveda de Memoria de Cortana...")
try:
    cliente_chroma = chromadb.PersistentClient(path=RUTA_DB)
    # Usamos el nombre exacto que definiste en memoria.py
    coleccion = cliente_chroma.get_or_create_collection(name="contexto_general")
except Exception as e:
    print(f"❌ Error al conectar con ChromaDB: {e}")
    exit()

def obtener_etiquetas_unicas():
    """Extrae todas las etiquetas únicas de la bóveda usando la clave 'etiqueta'."""
    try:
        datos = coleccion.get()
        metadatas = datos.get("metadatas", [])
        
        etiquetas = set()
        for meta in metadatas:
            # En tu memoria.py, la clave de los metadatos se llama "etiqueta"
            if meta and "etiqueta" in meta:
                etiquetas.add(meta["etiqueta"])
                
        return sorted(list(etiquetas))
    except Exception as e:
        print(f"❌ Error al leer las metadatas: {e}")
        return []

def listar_documentos():
    """Muestra en pantalla todo lo que Cortana tiene memorizado."""
    etiquetas = obtener_etiquetas_unicas()
    
    print("\n" + "="*50)
    print("🧠 CONTENIDO DE LA BÓVEDA PERMANENTE")
    print("="*50)
    
    if not etiquetas:
        print("La bóveda está completamente vacía.")
    else:
        for i, etiqueta in enumerate(etiquetas):
            # Filtramos usando la clave "etiqueta"
            resultado = coleccion.get(where={"etiqueta": etiqueta})
            cantidad_chunks = len(resultado['ids']) if resultado and 'ids' in resultado else 0
            
            print(f"{i + 1}. {etiqueta} (Fragmentos: {cantidad_chunks})")
    print("="*50 + "\n")
    
    return etiquetas

def borrar_documento(etiqueta_a_borrar):
    """Elimina de la base de datos todos los fragmentos asociados a una etiqueta."""
    try:
        coleccion.delete(where={"etiqueta": etiqueta_a_borrar})
        print(f"\n✅ ¡Éxito! Se purgó de la memoria todo el contenido de: '{etiqueta_a_borrar}'")
    except Exception as e:
        print(f"\n❌ Hubo un error al intentar borrar: {e}")

def hard_reset():
    """Formatea la base de datos completa y la deja en blanco."""
    confirmacion = input("\n⚠️ PELIGRO: ¿Estás seguro de que quieres BORRAR TODA LA BÓVEDA? Esto es irreversible. (Escribe 'SI' para confirmar): ")
    if confirmacion == 'SI':
        try:
            cliente_chroma.delete_collection(name="contexto_general")
            # Volvemos a crear la colección limpia para que el sistema siga funcionando
            global coleccion
            coleccion = cliente_chroma.create_collection(name="contexto_general")
            print("\n✅ Bóveda formateada con éxito. Cortana tiene la mente en blanco.")
        except Exception as e:
            print(f"\n❌ Error al formatear la bóveda: {e}")
    else:
        print("\nOperación de formateo cancelada.")

def menu_principal():
    while True:
        print("\n🛠️  GESTOR DE BÓVEDA OMNIASSISTANT")
        print("1. 📋 Listar archivos y recuerdos guardados")
        print("2. 🗑️  Eliminar un archivo específico de la memoria")
        print("3. 💥 Formatear la bóveda completa (Hard Reset)")
        print("4. ❌ Salir")
        
        opcion = input("\nElige una opción (1/2/3/4): ").strip()
        
        if opcion == "1":
            listar_documentos()
            
        elif opcion == "2":
            etiquetas = listar_documentos()
            if etiquetas:
                print("Escribe el nombre EXACTO de la etiqueta que quieres borrar.")
                print("Ejemplo: Doc: buildMonje.pdf")
                seleccion = input("\nNombre de la etiqueta (o 'cancelar' para volver): ").strip()
                
                if seleccion.lower() == 'cancelar':
                    continue
                elif seleccion in etiquetas:
                    confirmacion = input(f"⚠️ ¿Estás seguro de borrar '{seleccion}' de forma irreversible? (s/n): ")
                    if confirmacion.lower() == 's':
                        borrar_documento(seleccion)
                    else:
                        print("Operación cancelada.")
                else:
                    print("\n❌ Error: La etiqueta ingresada no coincide con ninguna de la lista.")
                    
        elif opcion == "3":
            hard_reset()
            
        elif opcion == "4":
            print("\nCerrando gestor de bóveda. ¡Nos vemos!")
            break
            
        else:
            print("\n❌ Opción no válida. Intenta de nuevo.")

if __name__ == "__main__":
    menu_principal()