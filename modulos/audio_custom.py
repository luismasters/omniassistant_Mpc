import os
import time
import threading
import keyboard
import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wav
import queue
import re
import asyncio
import uuid
import tempfile

import pygame
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"

from config import WHISPER_MODEL_SIZE, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE
from config import TECLA_HABLAR, FS_AUDIO

hablando_actualmente = False

# ==============================================================
# CONFIGURACION DE VOZ — Edge TTS
# ==============================================================
VOZ_ACTIVA = "es-MX-JorgeNeural"   # colombiano, grave y serio
TONO       = "-3Hz"                   
VELOCIDAD  = "+0%"                    

try:
    pygame.mixer.init()
except Exception as e:
    print(f"Error al inicializar pygame: {e}")

# =====================================================================
# LAZY LOADING DE WHISPER
# =====================================================================
_modelo_whisper = None

def _cargar_whisper_si_necesario():
    global _modelo_whisper
    if _modelo_whisper is None:
        print(f"\n[AUDIO] Cargando Whisper '{WHISPER_MODEL_SIZE}'... Solo pasa una vez.")
        from faster_whisper import WhisperModel
        _modelo_whisper = WhisperModel(WHISPER_MODEL_SIZE, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE_TYPE)
    return _modelo_whisper

# =====================================================================
# UTILIDADES DE TEXTO
# =====================================================================
def limpiar_texto_para_voz(texto):
    lineas = texto.split('\n')
    texto_hablado = []
    for linea in lineas:
        linea_baja = linea.lower().strip()
        if linea_baja.startswith(("abrir:", "cerrar:", "navegar:", "buscar:", "*(accion")):
            continue
        texto_hablado.append(linea)
    texto_final = " ".join(texto_hablado).strip()
    reemplazos = {"🤖": "", "🧠": "", "🎙️": "", "`": "", "*": ""}
    for viejo, nuevo in reemplazos.items():
        texto_final = texto_final.replace(viejo, nuevo)
    return texto_final

def _agrupar_oraciones(oraciones, min_chars=80):
    grupos = []
    buffer = ""
    for o in oraciones:
        buffer += (" " if buffer else "") + o
        if len(buffer) >= min_chars:
            grupos.append(buffer.strip())
            buffer = ""
    if buffer.strip():
        grupos.append(buffer.strip())
    return grupos

# =====================================================================
# GENERACION DE AUDIO CON EDGE TTS (Directo a MP3)
# =====================================================================
async def _sintetizar_edge_async(texto, ruta_salida):
    import edge_tts
    tts = edge_tts.Communicate(texto, voice=VOZ_ACTIVA, pitch=TONO, rate=VELOCIDAD)
    await tts.save(ruta_salida)

def _sintetizar_sincrono(texto):
    """Genera el audio usando Edge TTS y lo guarda en un MP3 temporal seguro."""
    try:
        # Usamos UUID para que los archivos no se pisen entre hilos
        nombre_temp = f"edge_temp_{uuid.uuid4().hex[:8]}.mp3"
        ruta_salida = os.path.join(tempfile.gettempdir(), nombre_temp)
        
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_sintetizar_edge_async(texto, ruta_salida))
        loop.close()
        
        if os.path.exists(ruta_salida) and os.path.getsize(ruta_salida) > 0:
            return ruta_salida
        return None
    except Exception as e:
        print(f"[EDGE] Error en síntesis: {e}")
        return None

# =====================================================================
# COLA GLOBAL DE REPRODUCCION (Stream Continuo con Pygame)
# =====================================================================
_cola_reproduccion = queue.Queue()
_hilo_reproductor_activo = False

def _hilo_reproductor_global():
    global _hilo_reproductor_activo, hablando_actualmente

    while True:
        try:
            archivo_mp3 = _cola_reproduccion.get(timeout=0.5)
        except queue.Empty:
            if not hablando_actualmente:
                break
            continue

        if archivo_mp3 is None:
            break

        if not hablando_actualmente:
            _vaciar_cola()
            break

        try:
            # Reproducción nativa sin necesidad de FFmpeg
            pygame.mixer.music.load(archivo_mp3)
            pygame.mixer.music.play()
            
            while pygame.mixer.music.get_busy() and hablando_actualmente:
                if keyboard.is_pressed('esc') or not hablando_actualmente:
                    hablando_actualmente = False
                    pygame.mixer.music.stop()
                    _vaciar_cola()
                    break
                time.sleep(0.02)
                
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
            
            # Limpieza del archivo temporal
            try:
                os.remove(archivo_mp3)
            except:
                pass
        except Exception as e:
            print(f"Error reproduciendo con Pygame: {e}")

    _hilo_reproductor_activo = False

def _vaciar_cola():
    while not _cola_reproduccion.empty():
        try: 
            archivo = _cola_reproduccion.get_nowait()
            if archivo and isinstance(archivo, str) and os.path.exists(archivo):
                try:
                    os.remove(archivo)
                except:
                    pass
        except: 
            pass

def _asegurar_reproductor_activo():
    global _hilo_reproductor_activo
    if not _hilo_reproductor_activo:
        _hilo_reproductor_activo = True
        threading.Thread(target=_hilo_reproductor_global, daemon=True).start()

# =====================================================================
# FUNCIONES PUBLICAS
# =====================================================================
def encolar_texto_para_hablar(texto):
    global hablando_actualmente
    texto_limpio = limpiar_texto_para_voz(texto)
    if not texto_limpio:
        return

    hablando_actualmente = True
    _asegurar_reproductor_activo()

    def _generar_y_encolar():
        inicio = time.time()
        archivo = _sintetizar_sincrono(texto_limpio)
        if archivo is not None:
            _cola_reproduccion.put(archivo)
            print(f"[EDGE] '{texto_limpio[:45]}' → {time.time() - inicio:.2f}s")

    threading.Thread(target=_generar_y_encolar, daemon=True).start()

def hablar_no_bloqueante(texto):
    global hablando_actualmente
    detener_voz()
    texto_limpio = limpiar_texto_para_voz(texto)
    if not texto_limpio:
        return

    def _hilo_maestro():
        global hablando_actualmente
        try:
            hablando_actualmente = True
            oraciones_raw = [o.strip() for o in re.split(r'(?<=[.!?\n])', texto_limpio) if len(o.strip()) > 1]
            oraciones = _agrupar_oraciones(oraciones_raw, min_chars=80)
            cola_local = queue.Queue()

            def productor():
                for i, oracion in enumerate(oraciones):
                    if not hablando_actualmente:
                        break
                    inicio = time.time()
                    archivo = _sintetizar_sincrono(oracion)
                    if archivo is not None:
                        cola_local.put(archivo)
                        if i == 0:
                            print(f"[EDGE] Primer chunk listo en {time.time() - inicio:.2f}s")
                cola_local.put(None)

            threading.Thread(target=productor, daemon=True).start()

            while hablando_actualmente:
                archivo = cola_local.get()
                if archivo is None:
                    break
                if not hablando_actualmente:
                    break

                try:
                    pygame.mixer.music.load(archivo)
                    pygame.mixer.music.play()
                    
                    while pygame.mixer.music.get_busy() and hablando_actualmente:
                        if keyboard.is_pressed('esc') or not hablando_actualmente:
                            hablando_actualmente = False
                            pygame.mixer.music.stop()
                            break
                        time.sleep(0.02)
                        
                    pygame.mixer.music.stop()
                    pygame.mixer.music.unload()
                    
                    try:
                        os.remove(archivo)
                    except:
                        pass
                except Exception as e:
                    print(f"Error en reproducción local: {e}")

        except Exception as e:
            print(f"Error en hablar_no_bloqueante: {e}")
        finally:
            hablando_actualmente = False

    threading.Thread(target=_hilo_maestro, daemon=True).start()

def detener_voz():
    global hablando_actualmente
    hablando_actualmente = False
    try:
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
    except:
        pass
    _vaciar_cola()

# =====================================================================
# CAPTURA DE VOZ (Whisper)
# =====================================================================
def capturar_voz_micro():
    print(f"\n[GRABANDO] Habla ahora... (Solta {TECLA_HABLAR.upper()} para terminar)")
    audio_data = []

    def callback(indata, frames, time, status):
        audio_data.append(indata.copy())

    with sd.InputStream(samplerate=FS_AUDIO, channels=1, callback=callback):
        time.sleep(0.2)
        while keyboard.is_pressed(TECLA_HABLAR):
            time.sleep(0.02)

    print("--- PROCESANDO VOZ ---")
    if not audio_data:
        return ""

    archivo_temporal = 'output.wav'
    wav.write(archivo_temporal, FS_AUDIO, np.concatenate(audio_data, axis=0))
    modelo_activo = _cargar_whisper_si_necesario()

    segmentos, _ = modelo_activo.transcribe(
        archivo_temporal,
        beam_size=1,
        language="es",
        vad_filter=True
    )

    texto = "".join([s.text for s in segmentos]).strip()
    if os.path.exists(archivo_temporal):
        os.remove(archivo_temporal)
    return texto