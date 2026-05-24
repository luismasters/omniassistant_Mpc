import os
import time
import threading
import keyboard
import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wav
import pyttsx3
import whisper

# Importamos las variables de configuración global
from config import TECLA_HABLAR, FS_AUDIO

engine_voceando = None
hablando_actualmente = False

print("Cargando modelo Whisper 'Medium' en GPU (CUDA)... Esperá un momento.")
model = whisper.load_model("medium", device="cuda")
print("✅ Modelo de voz cargado.")

def limpiar_texto_para_voz(texto):
    lineas = texto.split('\n')
    texto_hablado = []
    
    for linea in lineas:
        linea_baja = linea.lower().strip()
        if linea_baja.startswith(("abrir:", "cerrar:", "navegar:", "buscar:")):
            continue
        if linea_baja.startswith("*(acción"):
            continue
            
        texto_hablado.append(linea)
        
    texto_final = " ".join(texto_hablado).strip()
    texto_final = texto_final.replace("🤖", "").replace("🧠", "").replace("🎙️", "").replace("`", "").replace("*", "")
    return texto_final

def hablar_no_bloqueante(texto):
    global hablando_actualmente, engine_voceando
    
    detener_voz()
    texto_limpio = limpiar_texto_para_voz(texto)
    
    if not texto_limpio:
        return

    print(f"🔊 Hablando...")
    
    def _hilo_voz():
        global hablando_actualmente, engine_voceando
        try:
            engine_voceando = pyttsx3.init()
            engine_voceando.setProperty('rate', 180)
            voices = engine_voceando.getProperty('voices')
            for voice in voices:
                if "spanish" in voice.name.lower() or "microsoft" in voice.id.lower():
                    engine_voceando.setProperty('voice', voice.id)
                    break
            
            hablando_actualmente = True
            engine_voceando.say(texto_limpio)
            engine_voceando.runAndWait()
        except Exception as e:
            print(f"⚠️ Error en el hilo de voz: {e}")
        finally:
            hablando_actualmente = False
            engine_voceando = None

    threading.Thread(target=_hilo_voz, daemon=True).start()

def detener_voz():
    global hablando_actualmente, engine_voceando
    if hablando_actualmente and engine_voceando:
        try:
            print("🛑 [INTERRUPCIÓN] Callando a Cortana...")
            engine_voceando.stop()
            time.sleep(0.1)
        except Exception:
            pass
        hablando_actualmente = False

def capturar_voz_micro():
    print(f"\n🎙️ [GRABANDO] Hablá ahora... (Soltá {TECLA_HABLAR.upper()} para terminar)")
    audio_data = []
    
    def callback(indata, frames, time, status):
        if status:
            print(f"⚠️ [AUDIO] {status}")
        audio_data.append(indata.copy())

    with sd.InputStream(samplerate=FS_AUDIO, channels=1, callback=callback):
        time.sleep(0.2) # <-- ¡Esta es la pausa que faltaba para darle respiro al mic!
        while keyboard.is_pressed(TECLA_HABLAR):
            time.sleep(0.02)
            
    print("--- ✅ PROCESANDO VOZ ---")
    
    # --- ACÁ ESTÁ EL PARCHE ---
    # Verificamos si realmente se grabó algo antes de intentar procesarlo
    if not audio_data:
        print("⚠️ [AUDIO] Grabación demasiado corta o vacía. Ignorando...")
        return ""
    # --------------------------

    archivo_temporal = 'output.wav'
    grabacion = np.concatenate(audio_data, axis=0)
    wav.write(archivo_temporal, FS_AUDIO, grabacion)
    
    # Le pasamos el archivo a Whisper
    result = model.transcribe(archivo_temporal, language="es")
    texto = result['text'].strip()
    
    # Limpiamos la basura temporal
    if os.path.exists(archivo_temporal):
        os.remove(archivo_temporal)
        
    return texto