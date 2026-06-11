import sys
import os
import contextlib

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =====================================================================
# 1. FORZAMOS UTF-8 EN LA CONSOLA PRINCIPAL
# =====================================================================
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# =====================================================================
# 2. SILENCIADOR ABSOLUTO
# =====================================================================
original_stdout = sys.stdout
sys.stdout = open(os.devnull, 'w', encoding='utf-8')
original_stderr = sys.stderr
sys.stderr = open(os.devnull, 'w', encoding='utf-8')

try:
    from modulos.sistema import obtener_estado_pc, escanear_hardware_completo, explorar_directorio
    from modulos.archivos import leer_contenido_archivo
    from modulos.memoria import buscar_contexto, guardar_recuerdo
finally:
    sys.stdout = original_stdout
    sys.stderr = original_stderr

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Servidor_Sistema_Cortana")

@mcp.tool()
def reporte_estado_pc() -> str:
    """Herramienta OBLIGATORIA para conocer el uso de CPU, RAM, temperatura de GPU y VRAM actual."""
    return f"Estado actual del sistema: {obtener_estado_pc()}"

@mcp.tool()
def reporte_hardware() -> str:
    """Obtiene los componentes físicos de la PC."""
    hw = escanear_hardware_completo()
    return f"Hardware detectado: CPU: {hw['cpu']}, GPU: {hw['gpu']}, Motherboard: {hw['motherboard']}"

@mcp.tool()
def buscar_en_boveda(consulta: str) -> str:
    """Busca en la bóveda de memoria a largo plazo."""
    with open(os.devnull, 'w', encoding='utf-8') as f, contextlib.redirect_stdout(f), contextlib.redirect_stderr(f):
        resultados = buscar_contexto(consulta)
    if resultados: return f"Recuerdos recuperados de la bóveda:\n{resultados[0]}"
    return "No encontré nada relacionado a ese tema en la bóveda de memoria."

@mcp.tool()
def guardar_en_boveda(dato: str) -> str:
    """Guarda información importante en la memoria a largo plazo."""
    with open(os.devnull, 'w', encoding='utf-8') as f, contextlib.redirect_stdout(f), contextlib.redirect_stderr(f):
        guardar_recuerdo(texto_a_guardar=dato, etiqueta_tema="Memoria_MCP")
    return "¡Dato guardado exitosamente en la bóveda permanente!"

@mcp.tool()
def explorar_ruta(ruta: str) -> str:
    """Explora una carpeta en la PC del usuario para listar su contenido."""
    return explorar_directorio(ruta)

@mcp.tool()
def leer_documento(ruta: str) -> str:
    """Lee el contenido de un archivo de texto o código local en la PC."""
    contenido = leer_contenido_archivo(ruta)
    if contenido == "CODIGO_ERROR_NO_ENCONTRADO" or contenido.startswith("CODIGO_ERROR_LECTURA:"):
        return "Error: No se pudo encontrar o abrir el archivo. Quizás la ruta es incorrecta."
    return f"Contenido del archivo:\n{contenido}"

if __name__ == "__main__":
    mcp.run()