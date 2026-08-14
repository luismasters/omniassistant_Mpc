"""
Ingesta de archivos (PDF y texto) hacia la bóveda (Fase pendiente §7 de
GUIA_MEMORIA).

Objetivo: indexar archivos GRANDES en la memoria a largo plazo SIN gastar
tokens de contexto. El archivo se extrae a texto, se divide en fragmentos
(chunks) y cada uno se guarda con `guardar_recuerdo` bajo la etiqueta
`Doc: <nombre>`.

Garantías:
- NUNCA escribe `documento_volatil` ni el contexto conversacional.
- Respeta `MAX_PDF_PAGES` (config.py) para no procesar PDFs gigantes.
- El embedding es local (all-MiniLM-L6-v2): guardar no consume tokens de LLM.
- Thread-safe (delega en guardar_recuerdo, que ya lo es).

Tamaño de chunk: por defecto 1200 caracteres (decisión del 13/08/2026).
"""

import os

from modulos.logger import logger

# Tamaño de fragmento para dividir el contenido (decisión 13/08/2026).
TAMANO_CHUNK = 1200

# Extensiones tratadas como texto plano (sin pypdf).
_EXT_TEXT = {".txt", ".md", ".py", ".js", ".ts", ".html", ".css", ".json", ".csv", ".xml", ".log"}


def _leer_texto(ruta: str) -> str:
    """Lee un archivo de texto plano como UTF-8."""
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        # Reintento con latin-1 (pierde acentos pero no rompe).
        with open(ruta, "r", encoding="latin-1") as f:
            return f.read()


def extraer_texto_archivo(ruta: str) -> str:
    """
    Extrae el texto de un archivo:
    - PDF → pypdf (respeta MAX_PDF_PAGES).
    - Texto plano (.txt/.md/.py/...) → lectura directa.
    Devuelve "" si no se pudo extraer o el formato no es soportado.
    """
    if not ruta or not os.path.exists(ruta):
        return ""
    ext = os.path.splitext(ruta)[1].lower()

    if ext == ".pdf":
        try:
            import config
            import pypdf
            max_paginas = getattr(config, "MAX_PDF_PAGES", 100)
            texto = []
            with open(ruta, "rb") as f:
                lector = pypdf.PdfReader(f)
                paginas = min(len(lector.pages), max_paginas)
                for i in range(paginas):
                    try:
                        page_texto = lector.pages[i].extract_text() or ""
                        texto.append(page_texto)
                    except Exception:
                        continue
            return "\n".join(texto)
        except Exception as e:
            logger.exception(f"Error extrayendo PDF {ruta}: {e}")
            return ""

    if ext in _EXT_TEXT:
        try:
            return _leer_texto(ruta)
        except Exception as e:
            logger.exception(f"Error leyendo texto {ruta}: {e}")
            return ""

    logger.warning(f"⚠️ Formato no soportado para bóveda: {ext}")
    return ""


def dividir_en_fragmentos(texto: str, tamano: int = TAMANO_CHUNK) -> list:
    """
    Divide el texto en fragmentos de ~`tamano` caracteres, sin cortar en
    medio de una palabra cuando es posible (usa párrafos/oraciones como guía).
    """
    if not texto or not texto.strip():
        return []
    texto = texto.strip()
    if len(texto) <= tamano:
        return [texto]

    fragmentos = []
    resto = texto
    while len(resto) > tamano:
        # Buscar el último espacio antes del límite para no cortar palabras.
        corte = resto.rfind(" ", 0, tamano)
        if corte < tamano * 0.5:
            corte = tamano
        fragmentos.append(resto[:corte].strip())
        resto = resto[corte:].strip()
    if resto:
        fragmentos.append(resto)
    return [f for f in fragmentos if f]


def ingestar_archivo_a_boveda(ruta: str, etiqueta=None) -> dict:
    """
    Indexa un archivo (PDF o texto) en la bóveda por fragmentos.

    Returns:
        {"exito": bool, "mensaje": str, "fragmentos": int, "etiqueta": str}
    """
    texto = extraer_texto_archivo(ruta)
    if not texto or not texto.strip():
        return {"exito": False, "mensaje": "No se pudo extraer texto del archivo.", "fragmentos": 0, "etiqueta": ""}

    nombre = os.path.basename(ruta) or "archivo"
    etiqueta_final = etiqueta or f"Doc: {nombre}"

    fragmentos = dividir_en_fragmentos(texto)
    if not fragmentos:
        return {"exito": False, "mensaje": "El archivo no tiene contenido para guardar.", "fragmentos": 0, "etiqueta": etiqueta_final}

    from modulos.memoria import guardar_recuerdo

    guardados = 0
    for chunk in fragmentos:
        try:
            if guardar_recuerdo(
                texto_a_guardar=chunk,
                etiqueta_tema=etiqueta_final,
                origen_fuente="ingesta_archivo",
            ):
                guardados += 1
        except Exception as e:
            logger.exception(f"Error guardando fragmento de {nombre}: {e}")

    if guardados == 0:
        return {"exito": False, "mensaje": "No se pudo guardar ningún fragmento.", "fragmentos": 0, "etiqueta": etiqueta_final}

    return {
        "exito": True,
        "mensaje": f"Archivo guardado en la bóveda: '{nombre}' ({guardados} fragmento(s)).",
        "fragmentos": guardados,
        "etiqueta": etiqueta_final,
    }


def guardar_nota_a_boveda(texto: str, etiqueta: str = "") -> dict:
    """
    Guarda una nota (texto no muy extenso) en la bóveda con la etiqueta dada.
    Si la nota supera TAMANO_CHUNK se fragmenta.

    Returns:
        {"exito": bool, "mensaje": str, "fragmentos": int, "etiqueta": str}
    """
    if not texto or not texto.strip():
        return {"exito": False, "mensaje": "La nota está vacía.", "fragmentos": 0, "etiqueta": ""}

    etiqueta_final = (etiqueta or "Nota").strip() or "Nota"
    fragmentos = dividir_en_fragmentos(texto)
    if not fragmentos:
        return {"exito": False, "mensaje": "La nota no tiene contenido.", "fragmentos": 0, "etiqueta": etiqueta_final}

    from modulos.memoria import guardar_recuerdo

    guardados = 0
    for chunk in fragmentos:
        try:
            if guardar_recuerdo(
                texto_a_guardar=chunk,
                etiqueta_tema=etiqueta_final,
                origen_fuente="nota_manual",
            ):
                guardados += 1
        except Exception as e:
            logger.exception(f"Error guardando nota: {e}")

    if guardados == 0:
        return {"exito": False, "mensaje": "No se pudo guardar la nota.", "fragmentos": 0, "etiqueta": etiqueta_final}

    return {
        "exito": True,
        "mensaje": f"Nota guardada en la bóveda bajo '{etiqueta_final}' ({guardados} fragmento(s)).",
        "fragmentos": guardados,
        "etiqueta": etiqueta_final,
    }
