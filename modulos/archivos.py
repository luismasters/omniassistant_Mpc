import os
import shutil
import ctypes
import fitz  # PyMuPDF para leer PDFs

def obtener_ruta_real(ruta_texto):
    ruta = os.path.expandvars(os.path.expanduser(ruta_texto))
    if not os.path.isabs(ruta):
        ruta = os.path.join(os.path.expanduser("~"), ruta)
    return ruta.replace("/", "\\")

def crear_carpeta(ruta_texto):
    ruta_final = obtener_ruta_real(ruta_texto)
    try:
        os.makedirs(ruta_final, exist_ok=True)
        return f"Carpeta creada exitosamente en: {ruta_final}"
    except Exception as e:
        return f"Error al crear carpeta: {e}"

def crear_archivo(ruta_texto):
    ruta_final = obtener_ruta_real(ruta_texto)
    try:
        os.makedirs(os.path.dirname(ruta_final), exist_ok=True)
        with open(ruta_final, 'w') as f: pass
        return f"Archivo en blanco creado en: {ruta_final}"
    except Exception as e:
        return f"Error al crear archivo: {e}"

def eliminar_elemento(ruta_texto):
    try:
        ruta_final = obtener_ruta_real(ruta_texto)
        if not os.path.exists(ruta_final):
            return f"No se encontró nada para borrar en: {ruta_final}"
        
        mensaje = f"¿Estás seguro de que querés que Cortana ELIMINE esto para siempre?\n\n{ruta_final}"
        titulo = "⚠️ Alerta de Seguridad - Cortana"
        respuesta = ctypes.windll.user32.MessageBoxW(0, mensaje, titulo, 0x34)
        
        if respuesta == 6: 
            if os.path.isdir(ruta_final):
                shutil.rmtree(ruta_final)
                return f"Carpeta eliminada: {ruta_final}"
            else:
                os.remove(ruta_final)
                return f"Archivo eliminado: {ruta_final}"
        else:
            return f"Operación cancelada. El elemento '{ruta_final}' está a salvo."
    except Exception as e:
        return f"Error crítico al intentar borrar: {e}"

# =====================================================================
# EL OJO LECTOR DE CÓDIGO Y PDFs
# =====================================================================
def buscar_archivo_codigo(nombre_archivo):
    print(f"📄 [PYTHON REAL] Radar activado buscando el archivo: '{nombre_archivo}'")
    zonas_busqueda = [
        os.path.expanduser(r"~\Desktop"),
        os.path.expanduser(r"~\Documents"),
        os.path.expanduser(r"~\Downloads"), # Sumamos descargas al radar
        os.path.expanduser(r"~\OneDrive\Escritorio")
    ]
    nombre_limpio = nombre_archivo.lower().strip()
    
    for zona in zonas_busqueda:
        if not os.path.exists(zona): continue
        for raiz, directorios, archivos in os.walk(zona):
            directorios[:] = [d for d in directorios if d not in ['.git', 'node_modules', 'venv', '__pycache__', 'AppData', 'bin', 'obj']]
            for archivo in archivos:
                if nombre_limpio == archivo.lower(): 
                    ruta_encontrada = os.path.join(raiz, archivo)
                    print(f"✅ [PYTHON REAL] Archivo encontrado en: {ruta_encontrada}")
                    return ruta_encontrada
    return None

def leer_contenido_archivo(nombre_archivo):
    if ":" in nombre_archivo or "\\" in nombre_archivo:
        ruta = nombre_archivo
    else:
        ruta = buscar_archivo_codigo(nombre_archivo)
        
    if ruta and os.path.exists(ruta):
        try:
            # Si detectamos que es un PDF, usamos PyMuPDF
            if ruta.lower().endswith('.pdf'):
                doc = fitz.open(ruta)
                texto_pdf = ""
                for pagina in doc:
                    texto_pdf += pagina.get_text()
                doc.close()
                return f"Ruta: {ruta}\n\n[DOCUMENTO PDF]\n{texto_pdf[:15000]}"
            
            # Si es cualquier otra cosa (txt, py, json, cs), lo leemos normal
            else:
                with open(ruta, 'r', encoding='utf-8') as f:
                    contenido = f.read()
                return f"Ruta: {ruta}\n\n{contenido[:15000]}" 
        except Exception as e:
            # Usamos un código de error exacto para evitar la autoreferencia
            return f"CODIGO_ERROR_LECTURA: {e}"
            
    return "CODIGO_ERROR_NO_ENCONTRADO"