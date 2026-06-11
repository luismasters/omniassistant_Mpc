import sys
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class GestorMCP:
    def __init__(self, ruta_servidor="modulos/servidor_sistema_mcp.py"):

        self.ruta_servidor = ruta_servidor

    async def _solicitar_herramienta(self, nombre_herramienta, argumentos):
        """Conecta con el servidor en segundo plano, ejecuta y cierra."""
        parametros = StdioServerParameters(command=sys.executable, args=[self.ruta_servidor])
        try:
            async with stdio_client(parametros) as (lectura, escritura):
                async with ClientSession(lectura, escritura) as sesion:
                    await sesion.initialize()
                    resultado = await sesion.call_tool(nombre_herramienta, arguments=argumentos)
                    return resultado.content[0].text
        except Exception as e:
            return f"Error al conectar con el servidor MCP: {e}"

    def ejecutar(self, nombre_herramienta, argumentos=None):
        """Puente síncrono: permite que IA.py use MCP sin complicarse con 'async'."""
        if argumentos is None: argumentos = {}
        return asyncio.run(self._solicitar_herramienta(nombre_herramienta, argumentos))

# Instancia global lista para ser usada por Cortana
cliente_sistema = GestorMCP()