import sys
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Timeout en segundos para cada llamada al servidor MCP
MCP_TIMEOUT = 12

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
        except asyncio.TimeoutError:
            return f"TIMEOUT: El servidor MCP no respondió en {MCP_TIMEOUT}s"
        except Exception as e:
            return f"Error al conectar con el servidor MCP: {e}"

    def ejecutar(self, nombre_herramienta, argumentos=None):
        """
        Puente síncrono con timeout: permite que ia.py use MCP sin async.
        Si el servidor no responde en MCP_TIMEOUT segundos, retorna error
        en vez de bloquear indefinidamente.
        """
        if argumentos is None:
            argumentos = {}
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                resultado = loop.run_until_complete(
                    asyncio.wait_for(
                        self._solicitar_herramienta(nombre_herramienta, argumentos),
                        timeout=MCP_TIMEOUT
                    )
                )
                return resultado
            finally:
                loop.close()
        except asyncio.TimeoutError:
            return f"TIMEOUT: El servidor MCP no respondió en {MCP_TIMEOUT}s"
        except Exception as e:
            return f"Error MCP: {e}"

# Instancia global lista para ser usada por Argus
cliente_sistema = GestorMCP()