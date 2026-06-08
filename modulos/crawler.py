import os

def extraer_codigo_proyecto(ruta_base):
    """
    Recorre todo el árbol del proyecto, filtra carpetas innecesarias,
    y concatena el código de todos los archivos en un solo texto.
    """
    ignorar_carpetas = ['.git', '__pycache__', 'venv', 'env', 'node_modules', '.cortana', 'boveda_memoria']
    extensiones_validas = ['.py', '.md', '.json', '.txt']
    
    contenido_total = []
    
    for raiz, carpetas, archivos in os.walk(ruta_base):
        # Modificamos la lista in-place para que os.walk ignore las carpetas no deseadas
        carpetas[:] = [d for d in carpetas if d not in ignorar_carpetas]
        
        for archivo in archivos:
            _, ext = os.path.splitext(archivo)
            if ext.lower() in extensiones_validas:
                ruta_completa = os.path.join(raiz, archivo)
                ruta_relativa = os.path.relpath(ruta_completa, ruta_base)
                
                # Omitimos el .env por máxima seguridad (para que no mande tus contraseñas a la IA)
                if archivo == ".env": continue
                
                try:
                    with open(ruta_completa, 'r', encoding='utf-8') as f:
                        codigo = f.read()
                        
                    # Agregamos una cabecera para que la IA sepa qué archivo está leyendo
                    bloque_archivo = (
                        f"\n{'='*50}\n"
                        f"📁 ARCHIVO: {ruta_relativa}\n"
                        f"{'='*50}\n"
                        f"{codigo}\n"
                    )
                    contenido_total.append(bloque_archivo)
                    
                except Exception as e:
                    print(f"⚠️ No se pudo leer {ruta_relativa}: {e}")
                    
    # Retorna el mega-string con todo el código
    return "\n".join(contenido_total)