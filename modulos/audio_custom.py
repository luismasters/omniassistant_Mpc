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
from config import PALABRA_CORTE_VOZ, SILENCIO_CORTE_GRABACION

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

def _agrupar_oraciones(oraciones, min_chars=30):
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
def _notificar_gui_hablando(hablando: bool):
    try:
        import webview
        if webview.windows and len(webview.windows) > 0:
            win = webview.windows[0]
            estado = "talking" if hablando else "idle"
            win.evaluate_js(f"if (window.notificarEstadoAvatar) window.notificarEstadoAvatar('{estado}');")
    except Exception:
        pass

# COLA GLOBAL DE REPRODUCCION (Stream Continuo con Pygame)
# =====================================================================
_cola_reproduccion = queue.Queue()
_hilo_reproductor_activo = False

def _hilo_reproductor_global():
    global _hilo_reproductor_activo, hablando_actualmente

    reproduciendo_voz_gui = False
    try:
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
                if not reproduciendo_voz_gui:
                    reproduciendo_voz_gui = True
                    _notificar_gui_hablando(True)

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
    finally:
        if reproduciendo_voz_gui:
            _notificar_gui_hablando(False)

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
        reproduciendo_voz_gui = False
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
                    if not reproduciendo_voz_gui:
                        reproduciendo_voz_gui = True
                        _notificar_gui_hablando(True)

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
            if reproduciendo_voz_gui:
                _notificar_gui_hablando(False)

    threading.Thread(target=_hilo_maestro, daemon=True).start()

def detener_voz():
    global hablando_actualmente
    hablando_actualmente = False
    _notificar_gui_hablando(False)
    try:
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
    except:
        pass
    _vaciar_cola()

# ─── Función helper para leer F8 vía Win32 API (funciona en juegos fullscreen) ──
def _f8_esta_presionado() -> bool:
    """
    Lee el estado de la tecla F8 usando GetAsyncKeyState de Win32 API.
    Funciona incluso cuando un juego en fullscreen captura la entrada del teclado.
    Si no está en Windows, usa keyboard.is_pressed como fallback.
    """
    import sys as _sys
    if _sys.platform == "win32":
        try:
            import ctypes
            return bool(ctypes.windll.user32.GetAsyncKeyState(0x77) & 0x8000)
        except Exception:
            pass
    try:
        return keyboard.is_pressed('f8')
    except Exception:
        return False

# =====================================================================
# CAPTURA DE VOZ (Whisper)
# =====================================================================
def _beep_inicio():
    """Emite un pitido corto (880 Hz, 200 ms) para confirmar que la captura de voz comenzó.
    Especialmente útil en modo gamer, donde la interfaz suele estar minimizada o fuera del
    campo visual y el usuario necesita una confirmación auditiva de que el mando L3+R3
    disparó correctamente la detección de audio."""
    try:
        import winsound
        winsound.Beep(880, 200)
    except Exception:
        pass  # Si falla el beep, no interrumpir la grabación

def capturar_voz_micro(condicion_seguir_grabando=None):
    """
    Graba del micrófono mientras la condición de corte siga siendo True.
    Al iniciar emite un pitido de confirmación (880 Hz, 200 ms).
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
        # Pitido de confirmación auditiva: la captura comenzó
        _beep_inicio()

        if condicion_seguir_grabando is None:
            condicion_seguir_grabando = _f8_esta_presionado
            print(f"\n[GRABANDO] Habla ahora... (Soltá {TECLA_HABLAR.upper()} para terminar)")
        else:
            print(f"\n[GRABANDO] Habla ahora... (Soltá el control para terminar)")

        audio_data = []
        ultimo_sonido = [time.time()]
        hablo_algo = [False]
        palabra_corte_detectada = [False]

        # Reconocedor de palabras clave de corte en tiempo real vía Vosk.
        # Soporta 'procede', 'corta', 'listo', 'proceda', 'cortar', etc.
        recognizer_corte = None
        palabras_corte_list = list(set([PALABRA_CORTE_VOZ.lower(), "corta", "cortar", "proceda", "proceder", "listo", "terminar"]))
        try:
            from modulos.skills.wake_word.gestor_wake_word import gestor_wake_word
            if gestor_wake_word._modelo is not None:
                import vosk, json
                gramatica_corte = json.dumps(palabras_corte_list + ["[unk]"])
                recognizer_corte = vosk.KaldiRecognizer(gestor_wake_word._modelo, FS_AUDIO, gramatica_corte)
                recognizer_corte.SetWords(False)
        except Exception:
            pass

        def callback(indata, frames, time_info, status):
            audio_data.append(indata.copy())
            bytes_audio = indata.tobytes()
            try:
                from config import RMS_UMBRAL_VOZ
                # indata es int16
                indata_float = indata.astype(np.float32)
                rms = float(np.sqrt(np.mean(indata_float**2))) if indata_float.size else 0.0
                if rms >= RMS_UMBRAL_VOZ:  # Umbral de voz activa
                    hablo_algo[0] = True
                    ultimo_sonido[0] = time.time()
                
                if recognizer_corte is not None:
                    if recognizer_corte.AcceptWaveform(bytes_audio):
                        res = json.loads(recognizer_corte.Result())
                        txt = res.get("text", "").lower()
                    else:
                        part = json.loads(recognizer_corte.PartialResult())
                        txt = part.get("partial", "").lower()
                    
                    # La palabra de corte debe ser la ÚLTIMA palabra reconocida
                    palabras_txt = txt.split()
                    if palabras_txt and palabras_txt[-1] in palabras_corte_list:
                        palabra_corte_detectada[0] = True
            except Exception:
                pass

        try:
            with sd.InputStream(samplerate=FS_AUDIO, channels=1, dtype='int16', callback=callback):
                time.sleep(0.2)
                inicio = time.time()
                while condicion_seguir_grabando():
                    ahora = time.time()
                    # 1. Corte instantáneo si pronunció la palabra clave de fin
                    if palabra_corte_detectada[0]:
                        print(f"[GRABANDO] ⚡ Palabra clave '{PALABRA_CORTE_VOZ}' detectada — procesando grabación al instante...")
                        break
                    # 2. Si el usuario comenzó a hablar y luego hace pausa/silencio,
                    #    finalizar automáticamente (umbral ampliado para instrucciones largas)
                    if hablo_algo[0] and (ahora - ultimo_sonido[0] > SILENCIO_CORTE_GRABACION):
                        print("[GRABANDO] 🤫 Silencio detectado post-habla, finalizando grabación...")
                        break
                    if ahora - inicio > MAX_GRABACION_SEGUNDOS:
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

        # Despojar palabras de corte al final del texto transcrito si estuvieran presentes
        if texto:
            patron_corte = r'|'.join([re.escape(w) for w in palabras_corte_list])
            texto = re.sub(
                rf'\s*\b({patron_corte})\b[\s\.\,\!\?]*$',
                '', texto, flags=re.IGNORECASE
            ).strip()

        return texto
    finally:
        escuchando_actualmente = False