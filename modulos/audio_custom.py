import os
import time
import threading
import keyboard
import numpy as np

try:
    import sounddevice as sd
    HAY_SOUNDDEVICE = True
except Exception as e:
    sd = None
    HAY_SOUNDDEVICE = False
    print(f"[AUDIO] ⚠️ Advertencia: No se pudo inicializar sounddevice/PortAudio: {e}")

import scipy.io.wavfile as wav
import queue
import re
import asyncio
import uuid
import tempfile

import pygame
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"

from config import WHISPER_MODEL_SIZE, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE
from config import TECLA_HABLAR, FS_AUDIO, MAX_GRABACION_SEGUNDOS

hablando_actualmente = False
escuchando_actualmente = False

def esta_escuchando():
    global escuchando_actualmente
    return escuchando_actualmente

def esta_hablando():
    global hablando_actualmente
    return hablando_actualmente

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
            archivo_mp3 = _cola_reproduccion.get(timeout=0.2)
        except queue.Empty:
            with _secuencia_lock:
                sigue_sintetizando = (_siguiente_a_reproducir < _contador_secuencia)
            if not sigue_sintetizando and not pygame.mixer.music.get_busy() and _cola_reproduccion.empty():
                hablando_actualmente = False
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
    """
    Arranca el hilo reproductor si no está activo, y reinicia el
    contador de secuencia usado para garantizar el orden de lectura
    (ver bloque CONTROL DE ORDEN más abajo). Se resetea acá porque
    este es el punto de entrada de una nueva "sesión de habla":
    si no reseteáramos, una respuesta nueva podría arrastrar índices
    de la anterior y quedar esperando fragmentos que ya no van a llegar.
    """
    global _hilo_reproductor_activo, _contador_secuencia, _siguiente_a_reproducir, _buffer_pendientes
    if not _hilo_reproductor_activo:
        with _secuencia_lock:
            _contador_secuencia = 0
            _siguiente_a_reproducir = 0
            _buffer_pendientes = {}
        _hilo_reproductor_activo = True
        threading.Thread(target=_hilo_reproductor_global, daemon=True).start()

# =====================================================================
# CONTROL DE ORDEN PARA REPRODUCCIÓN EN STREAMING
# =====================================================================
# BUG ORIGINAL: encolar_texto_para_hablar() lanzaba un hilo por cada
# fragmento de texto que llegaba durante el streaming de la IA. Cada
# hilo hacía su propia llamada de red a Edge TTS, y la latencia de esa
# llamada varía por fragmento. Como el reproductor consume la cola en
# el orden en que los archivos llegan a ella (no en el orden en que
# fueron generados), un fragmento posterior podía terminar de
# sintetizarse antes que uno anterior y colarse primero — produciendo
# lectura fuera de orden en textos largos.
#
# FIX: cada fragmento recibe un número de secuencia al momento de ser
# encolado para síntesis. Cuando termina de sintetizarse, se guarda en
# un buffer temporal (_buffer_pendientes) en vez de ir directo a la
# cola de reproducción. Solo se despachan a la cola los fragmentos que
# están en orden estricto empezando por _siguiente_a_reproducir. Esto
# preserva el paralelismo de síntesis (todo se sigue generando en
# paralelo) pero serializa la salida para respetar el orden original.
_secuencia_lock = threading.Lock()
_contador_secuencia = 0
_siguiente_a_reproducir = 0
_buffer_pendientes = {}  # {indice: ruta_archivo_o_None}

def _despachar_en_orden():
    """Empuja a la cola de reproducción los fragmentos ya listos,
    respetando estrictamente el orden original del texto."""
    global _siguiente_a_reproducir
    with _secuencia_lock:
        while _siguiente_a_reproducir in _buffer_pendientes:
            archivo = _buffer_pendientes.pop(_siguiente_a_reproducir)
            if archivo is not None:
                _cola_reproduccion.put(archivo)
            _siguiente_a_reproducir += 1

# =====================================================================
# FUNCIONES PUBLICAS
# =====================================================================
def encolar_texto_para_hablar(texto):
    """
    Usada durante el streaming de la respuesta de la IA (ver
    _procesar_buffer_voz en ia.py). Genera el audio de cada fragmento
    en un hilo separado (para no bloquear el streaming), pero garantiza
    que la reproducción respete el orden original del texto mediante
    un número de secuencia (ver bloque CONTROL DE ORDEN arriba).
    """
    global hablando_actualmente, _contador_secuencia
    texto_limpio = limpiar_texto_para_voz(texto)
    if not texto_limpio:
        return

    hablando_actualmente = True
    _asegurar_reproductor_activo()

    with _secuencia_lock:
        indice_propio = _contador_secuencia
        _contador_secuencia += 1

    def _generar_y_encolar(indice=indice_propio, texto_local=texto_limpio):
        inicio = time.time()
        archivo = _sintetizar_sincrono(texto_local)
        with _secuencia_lock:
            _buffer_pendientes[indice] = archivo
        _despachar_en_orden()
        if archivo is not None:
            print(f"[EDGE] '{texto_local[:45]}' → {time.time() - inicio:.2f}s (orden {indice})")

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
def capturar_voz_micro(condicion_seguir_grabando=None):
    """
    Graba del micrófono mientras la condición de corte siga siendo True.
    """
    global escuchando_actualmente, sd, HAY_SOUNDDEVICE
    if not HAY_SOUNDDEVICE or sd is None:
        try:
            import sounddevice as _sd
            sd = _sd
            HAY_SOUNDDEVICE = True
        except Exception as e:
            print(f"[AUDIO] ❌ No se puede grabar audio del micrófono. PortAudio no está disponible: {e}")
            return ""

    escuchando_actualmente = True
    try:
        if condicion_seguir_grabando is None:
            condicion_seguir_grabando = lambda: keyboard.is_pressed(TECLA_HABLAR)
            print(f"\n[GRABANDO] Habla ahora... (Soltá {TECLA_HABLAR.upper()} para terminar)")
        else:
            print(f"\n[GRABANDO] Habla ahora... (Soltá el control para terminar)")

        audio_data = []

        def callback(indata, frames, time, status):
            audio_data.append(indata.copy())

        try:
            with sd.InputStream(samplerate=FS_AUDIO, channels=1, callback=callback):
                time.sleep(0.2)
                inicio = time.time()
                while condicion_seguir_grabando():
                    if time.time() - inicio > MAX_GRABACION_SEGUNDOS:
                        print(f"[GRABANDO] ⚠️ Límite de {MAX_GRABACION_SEGUNDOS}s alcanzado, cortando grabación por seguridad.")
                        break
                    time.sleep(0.02)
        except Exception as e:
            print(f"[AUDIO] ❌ Error al acceder al dispositivo de captura de audio: {e}")
            return ""

        print("--- PROCESANDO VOZ ---")
        if not audio_data:
            return ""

        archivo_temporal = 'output.wav'
        wav.write(archivo_temporal, FS_AUDIO, np.concatenate(audio_data, axis=0))
        modelo_activo = _cargar_whisper_si_necesario()

        segmentos, _ = modelo_activo.transcribe(
            archivo_temporal,
            beam_size=4,
            language="es",
            vad_filter=True
        )

        texto = "".join([s.text for s in segmentos]).strip()
        if os.path.exists(archivo_temporal):
            os.remove(archivo_temporal)
        return texto
    finally:
        escuchando_actualmente = False