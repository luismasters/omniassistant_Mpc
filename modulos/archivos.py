import os
import shutil
import PyPDF2

def obtener_ruta_real(ruta_base):
    """Resuelve la ruta para entender atajos como ~ (Directorio del usuario)."""
    ruta_expandida = os.path.expanduser(ruta_base.strip())
    return os.path.abspath(ruta_expandida)

def buscar_archivo_local(nombre_archivo):
    """Busca el archivo en el proyecto actual si la ruta directa falla."""
    nombre_limpio = os.path.basename(nombre_archivo).lower()
    # Buscamos desde la carpeta donde se ejecuta main.py
    for raiz, dirs, archivos in os.walk(os.getcwd()):
        # Ignoramos carpetas basura para no perder tiempo
        dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', 'venv', 'node_modules']]
        for archivo in archivos:
            if archivo.lower() == nombre_limpio:
                print(f"✅ [PYTHON REAL] Archivo encontrado con radar local: {os.path.join(raiz, archivo)}")
                return os.path.join(raiz, archivo)
    return None

def crear_carpeta(ruta):
    """Crea una nueva carpeta en la ruta especificada."""
    ruta_real = obtener_ruta_real(ruta)
    try:
        os.makedirs(ruta_real, exist_ok=True)
        return "Carpeta creada con éxito."
    except Exception as e:
        return f"Error al crear carpeta: {e}"

def crear_archivo(ruta):
    """Crea un archivo de texto vacío en la ruta especificada."""
    ruta_real = obtener_ruta_real(ruta)
    try:
        with open(ruta_real, 'w', encoding='utf-8') as f:
            f.write("")
        return "Archivo creado con éxito."
    except Exception as e:
        return f"Error al crear archivo: {e}"

def eliminar_elemento(ruta):
    """Elimina un archivo o una carpeta completa."""
    ruta_real = obtener_ruta_real(ruta)
    try:
        if not os.path.exists(ruta_real):
            return "El elemento no existe."
        if os.path.isdir(ruta_real):
            shutil.rmtree(ruta_real)
        else:
            os.remove(ruta_real)
        return "Elemento eliminado con éxito."
    except Exception as e:
        return f"Error al eliminar: {e}"
    
def escribir_archivo(ruta, contenido):
    """Crea o sobreescribe un archivo inyectándole el contenido directamente."""
    ruta_real = obtener_ruta_real(ruta)
    try:
        # Si la ruta no es absoluta, intentamos usar el radar local
        directorio_padre = os.path.dirname(ruta_real)
        if directorio_padre and not os.path.exists(directorio_padre):
            os.makedirs(directorio_padre, exist_ok=True)
            
        with open(ruta_real, 'w', encoding='utf-8') as f:
            f.write(contenido)
        return "Archivo guardado con su contenido con éxito."
    except Exception as e:
        return f"Error al escribir en el archivo: {e}"    

def leer_contenido_archivo(ruta):
    """Lee el texto de un archivo, protegiendo al sistema de archivos gigantes."""
    ruta_real = obtener_ruta_real(ruta)
    
    if not os.path.exists(ruta_real):
        # SI FALLA LA RUTA EXACTA, ACTIVAMOS EL RADAR
        ruta_alternativa = buscar_archivo_local(ruta)
        if ruta_alternativa:
            ruta_real = ruta_alternativa
        else:
            return "CODIGO_ERROR_NO_ENCONTRADO"
        
    try:
        # =====================================================================
        # 1. PARACAÍDAS DE PESO BRUTO
        # =====================================================================
        peso_bytes = os.path.getsize(ruta_real)
        peso_mb = peso_bytes / (1024 * 1024)
        
        # Límite de 2.5 MB para lectura rápida en memoria volátil
        if peso_mb > 2.5:
            return (
                f"ALERTA_SISTEMA: El archivo pesa {peso_mb:.2f} MB. Es demasiado grande "
                "para la memoria a corto plazo. Dile al usuario con naturalidad: 'Che Luis, este archivo es un "
                "monstruo muy pesado. Para no saturar el sistema, mejor pasámelo con el botón "
                "del clip (📎) así lo meto en la bóveda y lo leo tranquilo'."
            )

        extension = os.path.splitext(ruta_real)[1].lower()
        
        # =====================================================================
        # 2. LECTURA ESPECÍFICA PARA PDF
        # =====================================================================
        if extension == '.pdf':
            texto = ""
            with open(ruta_real, 'rb') as f:
                lector = PyPDF2.PdfReader(f)
                
                # PARACAÍDAS DE PÁGINAS 
                if len(lector.pages) > 30:
                    return (
                        f"ALERTA_SISTEMA: El PDF tiene {len(lector.pages)} páginas. Es un documento muy largo. "
                        "Dile al usuario: 'Che, el PDF es larguísimo. Usá el clip para adjuntarlo a la bóveda permanente'."
                    )
                
                for pagina in lector.pages:
                    extraido = pagina.extract_text()
                    if extraido:
                        texto += extraido + "\n"
            
            # PARACAÍDAS DE TOKENS 
            if len(texto) > 40000:
                return "ALERTA_SISTEMA: El texto extraído es demasiado denso (más de 40.000 caracteres). Dile al usuario que lo pase a la bóveda."
                
            if not texto.strip():
                return "ALERTA_SISTEMA: Pude abrir el PDF, pero parece ser solo un escaneo de imágenes sin texto que pueda leer."
                
            return texto.strip()
            
        # =====================================================================
        # 3. LECTURA DE CÓDIGO Y TEXTO PLANO
        # =====================================================================
        else:
            with open(ruta_real, 'r', encoding='utf-8', errors='ignore') as f:
                texto = f.read()
                
                # PARACAÍDAS DE TOKENS PARA CÓDIGO
                if len(texto) > 40000:
                    return (
                        "ALERTA_SISTEMA: El archivo tiene más de 40.000 caracteres. "
                        "Dile al usuario que es demasiado código para leer de golpe y que lo adjunte a la bóveda con el clip."
                    )
                return texto

    except Exception as e:
        return f"CODIGO_ERROR_LECTURA: {e}"