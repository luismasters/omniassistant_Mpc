import os
import time
import threading
import keyboard
import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wav
import asyncio
import edge_tts
import tempfile

# Ocultar el mensaje de bienvenida de pygame en la consola
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame

# Importamos la configuración limpia y desacoplada
from config import WHISPER_MODEL_SIZE, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE
from config import TECLA_HABLAR, FS_AUDIO

hablando_actualmente = False

# Inicializamos el reproductor de audio de pygame
try:
    pygame.mixer.init()
except Exception as e:
    print(f"⚠️ Error al inicializar reproductor de audio: {e}")

# =====================================================================
# FASE 2.2: LAZY LOADING DE WHISPER
# =====================================================================
_modelo_whisper = None  # Variable oculta que inicia vacía

def _cargar_whisper_si_necesario():
    global _modelo_whisper
    if _modelo_whisper is None:
        print(f"\n⚙️ [AUDIO REAL] Cargando Whisper '{WHISPER_MODEL_SIZE}' en {WHISPER_DEVICE.upper()} ({WHISPER_COMPUTE_TYPE})... Esto solo pasa una vez.")
        from faster_whisper import WhisperModel
        _modelo_whisper = WhisperModel(
            WHISPER_MODEL_SIZE, 
            device=WHISPER_DEVICE, 
            compute_type=WHISPER_COMPUTE_TYPE
        )
        print("✅ Modelo de voz cargado en memoria (Listo para escuchar).")
    return _modelo_whisper
# =====================================================================

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
    global hablando_actualmente
    
    detener_voz()
    texto_limpio = limpiar_texto_para_voz(texto)
    
    if not texto_limpio:
        return

    print(f"🔊 Hablando (Voz: es-MX-JorgeNeural)...")
    
    def _hilo_voz():
        global hablando_actualmente
        try:
            hablando_actualmente = True
            archivo_salida = os.path.join(tempfile.gettempdir(), "cortana_voz_temp.mp3")
            
            # --- TAREA ASÍNCRONA PARA DESCARGAR LA VOZ ---
            async def generar_audio():
                comunicacion = edge_tts.Communicate(texto_limpio, "es-MX-JorgeNeural", rate="+0%")
                await comunicacion.save(archivo_salida)

            # Creamos un nuevo bucle de eventos asíncrono para este hilo
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(generar_audio())
            
            # --- REPRODUCCIÓN DEL AUDIO ---
            if os.path.exists(archivo_salida):
                pygame.mixer.music.load(archivo_salida)
                pygame.mixer.music.play()
                
                # Mantener el hilo vivo mientras habla o hasta que lo interrumpamos
                while pygame.mixer.music.get_busy() and hablando_actualmente:
                    time.sleep(0.05)
                    
                # Limpiar recursos para poder borrar el archivo
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
                
                try:
                    os.remove(archivo_salida)
                except Exception:
                    pass

        except Exception as e:
            print(f"⚠️ Error en el hilo de voz (Edge-TTS): {e}")
        finally:
            hablando_actualmente = False

    # Ejecutamos todo el proceso de voz en un hilo secundario
    threading.Thread(target=_hilo_voz, daemon=True).start()

def detener_voz():
    global hablando_actualmente
    if hablando_actualmente:
        try:
            print("🛑 [INTERRUPCIÓN] Callando a Cortana...")
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
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
        time.sleep(0.2) 
        while keyboard.is_pressed(TECLA_HABLAR):
            time.sleep(0.02)
            
    print("--- ✅ PROCESANDO VOZ ---")
    
    if not audio_data:
        print("⚠️ [AUDIO] Grabación demasiado corta o vacía. Ignorando...")
        return ""

    archivo_temporal = 'output.wav'
    grabacion = np.concatenate(audio_data, axis=0)
    wav.write(archivo_temporal, FS_AUDIO, grabacion)
    
    modelo_activo = _cargar_whisper_si_necesario() 
    segmentos, info = modelo_activo.transcribe(archivo_temporal, beam_size=5, language="es")
    
    texto_completo = ""
    for segmento in segmentos:
        texto_completo += segmento.text
        
    texto = texto_completo.strip()
    
    if os.path.exists(archivo_temporal):
        os.remove(archivo_temporal)
        
    return texto