import asyncio
import edge_tts
import os

# Lista de voces en español de alta calidad
voces = [
    "es-ES-ElviraNeural",
    "es-ES-AlvaroNeural",
    "es-MX-DaliaNeural",
    "es-MX-JorgeNeural",
    "es-AR-ElenaNeural",
    "es-AR-TomasNeural"
]

async def probar_voces():
    texto = "Hola Luis, esta es una prueba de voz para tu asistente. ¿Qué te parece mi tono?"
    
    for voz in voces:
        print(f"Probando voz: {voz}...")
        archivo = f"{voz}.mp3"
        comunicador = edge_tts.Communicate(texto, voz)
        await comunicador.save(archivo)
        # Reproduce el archivo (en Windows)
        os.system(f"start {archivo}")
        await asyncio.sleep(5) # Espera a que termine de hablar antes de la siguiente

if __name__ == "__main__":
    asyncio.run(probar_voces())
