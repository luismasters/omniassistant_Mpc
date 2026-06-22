import logging
from faster_whisper import WhisperModel

# Forzamos a que Python nos muestre TODO lo que está haciendo internamente
logging.basicConfig(level=logging.INFO)

print("🌐 Conectando con los servidores de HuggingFace...")
print("⬇️ Iniciando descarga forzada del modelo 'medium' (1.5 GB).")
print("⚠️ Verás el progreso real aquí abajo. Si se traba, tirará un error.\n")

try:
    # Usamos CPU e int8 solo para descargar el archivo sin tocar la tarjeta gráfica
    modelo = WhisperModel("medium", device="cpu", compute_type="int8")
    print("\n✅ ¡ÉXITO TOTAL! El modelo se descargó y guardó en la caché de tu PC.")
    print("Ya puedes borrar este archivo y abrir Argus normalmente.")
except Exception as e:
    print(f"\n❌ ERROR CRÍTICO DE RED O DESCARGA: {e}")