import sys
import os
import contextlib
import logging

# Agregar la ruta del proyecto para importar módulos
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configurar un logger específico para el servidor MCP
logger = logging.getLogger("servidor_mcp")
logger.setLevel(logging.DEBUG)

# Asegurar que los logs se muestren en consola
if not logger.handlers:
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - MCP - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

# =====================================================================
# 1. FORZAMOS UTF-8 EN LA CONSOLA PRINCIPAL
# =====================================================================
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# =====================================================================
# 2. REDIRIGIMOS STDOUT/STDERR A LOGGER (para no silenciar errores)
# =====================================================================
class LoggerRedirector:
    def __init__(self, logger, level=logging.INFO):
        self.logger = logger
        self.level = level
        self.buffer = ""

    def write(self, message):
        if message and message.strip():
            self.buffer += message
            if "\n" in self.buffer:
                lines = self.buffer.split("\n")
                for line in lines[:-1]:
                    if line.strip():
                        self.logger.log(self.level, line.strip())
                self.buffer = lines[-1]

    def flush(self):
        if self.buffer.strip():
            self.logger.log(self.level, self.buffer.strip())
            self.buffer = ""

# Guardar los originales
original_stdout = sys.stdout
original_stderr = sys.stderr

# Redirigir a logger
sys.stdout = LoggerRedirector(logger, logging.INFO)
sys.stderr = LoggerRedirector(logger, logging.ERROR)

# =====================================================================
# 3. IMPORTACIONES (con captura de errores)
# =====================================================================
try:
    from modulos.sistema import obtener_estado_pc, escanear_hardware_completo, explorar_directorio
    from modulos.archivos import leer_contenido_archivo
    from modulos.memoria import buscar_contexto, guardar_recuerdo
    logger.info("Módulos importados correctamente")
except Exception as e:
    logger.exception("Error al importar módulos")
    sys.exit(1)

# Restaurar stdout/stderr para que FastMCP pueda funcionar
sys.stdout = original_stdout
sys.stderr = original_stderr

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Servidor_Sistema_Cortana")

@mcp.tool()
def reporte_estado_pc() -> str:
    """Herramienta OBLIGATORIA para conocer el uso de CPU, RAM, temperatura de GPU y VRAM actual."""
    try:
        resultado = obtener_estado_pc()
        logger.debug(f"reporte_estado_pc ejecutado: {resultado}")
        return f"Estado actual del sistema: {resultado}"
    except Exception as e:
        logger.exception("Error en reporte_estado_pc")
        return f"Error al obtener estado del sistema: {str(e)}"

@mcp.tool()
def reporte_hardware() -> str:
    """Obtiene los componentes físicos de la PC."""
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
    """Busca en la bóveda de memoria a largo plazo."""
    try:
        # No silenciamos la salida, solo capturamos errores
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
    """Guarda información importante en la memoria a largo plazo."""
    try:
        guardar_recuerdo(texto_a_guardar=dato, etiqueta_tema="Memoria_MCP")
        logger.info(f"guardar_en_boveda: dato guardado ({len(dato)} caracteres)")
        return "¡Dato guardado exitosamente en la bóveda permanente!"
    except Exception as e:
        logger.exception("Error en guardar_en_boveda")
        return f"Error al guardar en la bóveda: {str(e)}"

@mcp.tool()
def explorar_ruta(ruta: str) -> str:
    """Explora una carpeta en la PC del usuario para listar su contenido."""
    try:
        resultado = explorar_directorio(ruta)
        logger.debug(f"explorar_ruta: {ruta} -> {len(resultado)} caracteres")
        return resultado
    except Exception as e:
        logger.exception(f"Error en explorar_ruta: {ruta}")
        return f"Error al explorar la ruta: {str(e)}"

@mcp.tool()
def leer_documento(ruta: str) -> str:
    """Lee el contenido de un archivo de texto o código local en la PC."""
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