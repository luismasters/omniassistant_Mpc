import os
import shutil
import logging
import tempfile
import subprocess
import base64
from pathlib import Path
from typing import Optional, List, Tuple

import config

# Iniciamos el logger que creamos en la Fase 1
logger = logging.getLogger(__name__)

# ==========================================================
# FUNCIONES DE SEGURIDAD (Fase 1)
# ==========================================================

def es_ruta_segura(ruta: str) -> bool:
    """Verifica que la ruta esté dentro del sandbox (config.SANDBOX_BASE) y no contenga '..' malicioso."""
    try:
        abs_ruta = os.path.abspath(ruta)
        sandbox = os.path.abspath(config.SANDBOX_BASE)
        
        # Normalizar con Path para eliminar posibles dobles barras
        abs_ruta = str(Path(abs_ruta).resolve())
        sandbox = str(Path(sandbox).resolve())
        
        # Verificar que la ruta normalizada comience con el sandbox
        if not abs_ruta.startswith(sandbox):
            logger.error(f"Ruta insegura: {ruta} -> {abs_ruta} (fuera de sandbox: {sandbox})")
            return False
            
        # Verificar enlaces simbólicos (opcional, pero recomendado)
        if os.path.islink(ruta):
            destino = os.path.realpath(ruta)
            if not destino.startswith(sandbox):
                logger.error(f"Enlace simbólico apunta fuera del sandbox: {ruta} -> {destino}")
                return False
                
        return True
    except Exception as e:
        logger.error(f"Error validando ruta {ruta}: {e}")
        return False

def verificar_espacio_suficiente(ruta: str, bytes_necesarios: int = config.MIN_FREE_SPACE_MB * 1024 * 1024) -> bool:
    """Verifica que haya al menos MIN_FREE_SPACE_MB libres en el disco de ruta."""
    try:
        dir_path = os.path.dirname(ruta) if os.path.isfile(ruta) else ruta
        if not os.path.exists(dir_path):
            dir_path = os.path.dirname(dir_path)
        if not os.path.isdir(dir_path):
            dir_path = os.path.dirname(dir_path) # Fallback simple
            
        uso = shutil.disk_usage(dir_path)
        return uso.free >= bytes_necesarios
    except Exception as e:
        logger.error(f"Error verificando espacio en disco: {e}")
        return False

def validar_tamano_contenido(contenido: str) -> bool:
    """Verifica que el contenido no exceda MAX_CONTENT_SIZE_MB."""
    max_bytes = config.MAX_CONTENT_SIZE_MB * 1024 * 1024
    if len(contenido.encode('utf-8')) > max_bytes:
        logger.error(f"Contenido excede el límite de {config.MAX_CONTENT_SIZE_MB} MB")
        return False
    return True


# ==========================================================
# FUNCIONES PRINCIPALES
# ==========================================================

def leer_contenido_archivo(ruta: str) -> str:
    """Lee el contenido de un archivo si la ruta es segura."""
    if not es_ruta_segura(ruta):
        return "ERROR: Ruta no permitida (fuera del sandbox)"
    try:
        # Verificar tamaño antes de leer
        tamano = os.path.getsize(ruta)
        if tamano > config.MAX_FILE_SIZE_MB * 1024 * 1024:
            return f"ERROR: El archivo excede el límite de {config.MAX_FILE_SIZE_MB} MB"
            
        with open(ruta, 'r', encoding='utf-8') as f:
            return f.read()
            
    except FileNotFoundError:
        logger.error(f"Archivo no encontrado: {ruta}")
        return "ERROR: Archivo no encontrado"
    except PermissionError:
        logger.error(f"Permiso denegado al leer: {ruta}")
        return "ERROR: Permiso denegado"
    except IsADirectoryError:
        logger.error(f"Se esperaba un archivo, pero es un directorio: {ruta}")
        return "ERROR: Es un directorio, no un archivo"
    except MemoryError:
        logger.error(f"Memoria insuficiente para leer: {ruta}")
        return "ERROR: Memoria insuficiente para leer el archivo"
    except OSError as e:
        logger.error(f"Error de sistema al leer {ruta}: {e}")
        return f"ERROR: Error de sistema: {e}"
    except Exception as e:
        logger.error(f"Error inesperado al leer {ruta}: {e}")
        return f"ERROR: Error inesperado: {e}"


def escribir_archivo(ruta: str, contenido: str) -> str:
    """Escribe contenido en un archivo si la ruta es segura y hay espacio."""
    if not es_ruta_segura(ruta):
        return "ERROR: Ruta no permitida (fuera del sandbox)"
        
    if not validar_tamano_contenido(contenido):
        return f"ERROR: Contenido excede el límite de {config.MAX_CONTENT_SIZE_MB} MB"
        
    if not verificar_espacio_suficiente(ruta):
        return f"ERROR: No hay suficiente espacio en disco (mínimo {config.MIN_FREE_SPACE_MB} MB libres)"
        
    try:
        # Crear directorio padre si no existe
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        logger.info(f"Archivo escrito correctamente: {ruta}")
        return f"Archivo guardado correctamente en: {ruta}"
        
    except PermissionError:
        logger.error(f"Permiso denegado al escribir: {ruta}")
        return "ERROR: Permiso denegado"
    except IsADirectoryError:
        logger.error(f"La ruta es un directorio, no se puede escribir: {ruta}")
        return "ERROR: La ruta especificada es un directorio"
    except OSError as e:
        logger.error(f"Error de sistema al escribir {ruta}: {e}")
        return f"ERROR: Error de sistema: {e}"
    except Exception as e:
        logger.error(f"Error inesperado al escribir {ruta}: {e}")
        return f"ERROR: Error inesperado: {e}"


def crear_carpeta(ruta: str) -> str:
    """Crea una carpeta (y padres) si la ruta es segura."""
    if not es_ruta_segura(ruta):
        return "ERROR: Ruta no permitida (fuera del sandbox)"
    try:
        os.makedirs(ruta, exist_ok=True)
        logger.info(f"Carpeta creada: {ruta}")
        return f"Carpeta creada correctamente: {ruta}"
    except PermissionError:
        logger.error(f"Permiso denegado al crear carpeta: {ruta}")
        return "ERROR: Permiso denegado"
    except OSError as e:
        logger.error(f"Error de sistema al crear carpeta {ruta}: {e}")
        return f"ERROR: Error de sistema: {e}"
    except Exception as e:
        logger.error(f"Error inesperado al crear carpeta {ruta}: {e}")
        return f"ERROR: Error inesperado: {e}"


def eliminar_elemento(ruta: str, confirmacion: bool = False) -> str:
    """Elimina un archivo o carpeta. Si confirmacion=False, devuelve código pidiendo confirmación."""
    if not es_ruta_segura(ruta):
        return "ERROR: Ruta no permitida (fuera del sandbox)"
        
    if not confirmacion:
        return f"SOLICITUD_DE_CONFIRMACION: ¿Estás seguro de eliminar '{ruta}'? Responde con confirmacion=True para proceder."
        
    try:
        if not os.path.exists(ruta):
            return "ERROR: La ruta no existe"
            
        if os.path.isfile(ruta):
            os.remove(ruta)
            logger.info(f"Archivo eliminado: {ruta}")
            return f"Archivo eliminado: {ruta}"
        elif os.path.isdir(ruta):
            shutil.rmtree(ruta)
            logger.info(f"Carpeta eliminada: {ruta}")
            return f"Carpeta eliminada: {ruta}"
        else:
            return "ERROR: Tipo de elemento no soportado"
            
    except PermissionError:
        logger.error(f"Permiso denegado al eliminar: {ruta}")
        return "ERROR: Permiso denegado"
    except FileNotFoundError:
        logger.error(f"Elemento no encontrado: {ruta}")
        return "ERROR: Elemento no encontrado"
    except OSError as e:
        logger.error(f"Error de sistema al eliminar {ruta}: {e}")
        return f"ERROR: Error de sistema: {e}"
    except Exception as e:
        logger.error(f"Error inesperado al eliminar {ruta}: {e}")
        return f"ERROR: Error inesperado: {e}"


def listar_contenido(ruta: str) -> str:
    """Lista el contenido de un directorio."""
    if not es_ruta_segura(ruta):
        return "ERROR: Ruta no permitida (fuera del sandbox)"
    try:
        if not os.path.isdir(ruta):
            return "ERROR: La ruta no es un directorio"
            
        items = os.listdir(ruta)
        resultado = []
        for item in items:
            ruta_completa = os.path.join(ruta, item)
            if os.path.isdir(ruta_completa):
                resultado.append(f"📁 {item}/")
            else:
                resultado.append(f"📄 {item}")
        return "\n".join(resultado)
        
    except PermissionError:
        logger.error(f"Permiso denegado al listar: {ruta}")
        return "ERROR: Permiso denegado"
    except FileNotFoundError:
        logger.error(f"Directorio no encontrado: {ruta}")
        return "ERROR: Directorio no encontrado"
    except OSError as e:
        logger.error(f"Error de sistema al listar {ruta}: {e}")
        return f"ERROR: Error de sistema: {e}"
    except Exception as e:
        logger.error(f"Error inesperado al listar {ruta}: {e}")
        return f"ERROR: Error inesperado: {e}"


def buscar_archivo_local(nombre: str) -> Optional[str]:
    """Busca un archivo dentro del sandbox. Usar SOLO como fallback de lectura y bajo confirmación explícita."""
    try:
        for root, dirs, files in os.walk(config.SANDBOX_BASE):
            if nombre in files:
                ruta_completa = os.path.join(root, nombre)
                if es_ruta_segura(ruta_completa):
                    return ruta_completa
        return None
    except Exception as e:
        logger.error(f"Error buscando archivo {nombre}: {e}")
        return None