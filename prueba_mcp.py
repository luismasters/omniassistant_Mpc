import sys
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def probar_conexion():
    print("🔌 Iniciando Cliente MCP...")
    print("Buscando el servidor 'servidor_sistema_mcp.py'...")

    # 1. Usamos sys.executable para blindar la ruta de Python de tu (venv)
    parametros_servidor = StdioServerParameters(
        command=sys.executable,  # <-- ESTE ES EL CAMBIO CLAVE
        args=["servidor_sistema_mcp.py"]
    )

    # 2. Abrimos la conexión estándar (STDIO)
    try:
        async with stdio_client(parametros_servidor) as (lectura, escritura):
            async with ClientSession(lectura, escritura) as sesion:
                # Inicializamos el protocolo
                await sesion.initialize()
                print("✅ ¡Conexión establecida con el Servidor MCP!")

                # 3. Le preguntamos al servidor qué herramientas sabe usar
                respuesta_herramientas = await sesion.list_tools()
                nombres_herramientas = [herramienta.name for herramienta in respuesta_herramientas.tools]
                print(f"🛠️ Herramientas descubiertas: {nombres_herramientas}")

                # 4. Simulamos ser Gemini y le pedimos al servidor que ejecute una herramienta
                print("\n🤖 Cliente: 'Servidor, ejecutá reporte_estado_pc por favor...'")
                
                # Ejecutamos la herramienta pasando su nombre exacto
                resultado = await sesion.call_tool("reporte_estado_pc", arguments={})
                
                # Extraemos el texto de la respuesta del servidor
                texto_resultado = resultado.content[0].text
                print(f"📊 Respuesta del Servidor:\n{texto_resultado}")
                
                print("\n✨ ¡Si ves los datos de tu PC arriba, la arquitectura MCP funciona a la perfección!")
    
    except Exception as e:
        print(f"\n❌ Error de conexión MCP: {e}")
        print("💡 Sugerencia: Asegurate de que 'servidor_sistema_mcp.py' esté guardado y NO tenga ningún print() global.")

if __name__ == "__main__":
    asyncio.run(probar_conexion())