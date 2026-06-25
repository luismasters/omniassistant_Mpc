import sys
import os
import logging

# Agregar la ruta del proyecto para importar módulos
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ─── CONFIGURAR LOGGER PARA USAR STDERR ──────────────────────────────
logger = logging.getLogger("servidor_mcp")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    console_handler = logging.StreamHandler(sys.stderr)  # <-- stderr, no stdout
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - MCP - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

# ─── REDIRIGIR STDOUT A DEVNULL (PARA NO CONTAMINAR JSON-RPC) ──────
# Guardamos referencia original por si acaso (no se usa)
sys.stdout = open(os.devnull, 'w', encoding='utf-8')
# sys.stderr se mantiene para logs (no se redirige)

# =====================================================================
# IMPORTACIONES (con captura de errores)
# =====================================================================
try:
    from modulos.sistema import obtener_estado_pc, escanear_hardware_completo, explorar_directorio
    from modulos.archivos import leer_contenido_archivo
    from modulos.memoria import buscar_contexto, guardar_recuerdo
    logger.info("Módulos importados correctamente")
except Exception as e:
    logger.exception("Error al importar módulos")
    sys.exit(1)

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Servidor_Sistema_Cortana")

@mcp.tool()
def reporte_estado_pc() -> str:
    try:
        resultado = obtener_estado_pc()
        logger.debug(f"reporte_estado_pc ejecutado: {resultado}")
        return f"Estado actual del sistema: {resultado}"
    except Exception as e:
        logger.exception("Error en reporte_estado_pc")
        return f"Error al obtener estado del sistema: {str(e)}"

@mcp.tool()
def reporte_hardware() -> str:
    try:
        hw = escanear_hardware_completo()
        resultado = f"Hardware detectado: CPU: {hw['cpu']}, GPU: {hw['gpu']}, Motherboard: {hw['motherboard']}"
        logger.debug(f"reporte_hardware ejecutado: {resultado}")
        return resultado
    except Exception as e:
        logger.exception("Error en reporte_hardware")
        return f"Error al obtener hardware: {str(e)}"

@mcp.tool()
def buscar_en_boveda(consulta: str) -> str:
    try:
        resultados = buscar_contexto(consulta)
        if resultados:
            logger.debug(f"buscar_en_boveda: {len(resultados)} resultados")
            return f"Recuerdos recuperados de la bóveda:\n{resultados[0]}"
        logger.debug("buscar_en_boveda: sin resultados")
        return "No encontré nada relacionado a ese tema en la bóveda de memoria."
    except Exception as e:
        logger.exception("Error en buscar_en_boveda")
        return f"Error al buscar en la bóveda: {str(e)}"

@mcp.tool()
def guardar_en_boveda(dato: str) -> str:
    try:
        guardar_recuerdo(texto_a_guardar=dato, etiqueta_tema="Memoria_MCP")
        logger.info(f"guardar_en_boveda: dato guardado ({len(dato)} caracteres)")
        return "¡Dato guardado exitosamente en la bóveda permanente!"
    except Exception as e:
        logger.exception("Error en guardar_en_boveda")
        return f"Error al guardar en la bóveda: {str(e)}"

@mcp.tool()
def explorar_ruta(ruta: str) -> str:
    try:
        resultado = explorar_directorio(ruta)
        logger.debug(f"explorar_ruta: {ruta} -> {len(resultado)} caracteres")
        return resultado
    except Exception as e:
        logger.exception(f"Error en explorar_ruta: {ruta}")
        return f"Error al explorar la ruta: {str(e)}"

@mcp.tool()
def leer_documento(ruta: str) -> str:
    try:
        contenido = leer_contenido_archivo(ruta)
        if contenido == "CODIGO_ERROR_NO_ENCONTRADO" or contenido.startswith("CODIGO_ERROR_LECTURA:"):
            logger.warning(f"leer_documento: archivo no encontrado o error: {ruta}")
            return "Error: No se pudo encontrar o abrir el archivo. Quizás la ruta es incorrecta."
        logger.debug(f"leer_documento: {ruta} leído ({len(contenido)} caracteres)")
        return f"Contenido del archivo:\n{contenido}"
    except Exception as e:
        logger.exception(f"Error en leer_documento: {ruta}")
        return f"Error al leer el documento: {str(e)}"

if __name__ == "__main__":
    logger.info("Iniciando servidor MCP...")
    try:
        mcp.run()
    except Exception as e:
        logger.exception("Error al ejecutar el servidor MCP")
        sys.exit(1)