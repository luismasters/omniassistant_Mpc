import os
import time
import threading
import keyboard
import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wav
import soundfile as sf
import tempfile

# Importamos la configuración limpia y desacoplada
from config import WHISPER_MODEL_SIZE, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE
from config import TECLA_HABLAR, FS_AUDIO

hablando_actualmente = False

# =====================================================================
# LAZY LOADING DE WHISPER (Escucha)
# =====================================================================
_modelo_whisper = None  

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
        print("✅ Modelo de escucha (Whisper) cargado en memoria.")
    return _modelo_whisper

# =====================================================================
# LAZY LOADING DE XTTSv2 (Habla) + PARCHE PYTORCH 2.6
# =====================================================================
_modelo_xtts = None

def _cargar_xtts_si_necesario():
    global _modelo_xtts
    if _modelo_xtts is None:
        print("\n⚙️ [AUDIO REAL] Cargando motor premium XTTSv2 en la RTX 3060... Esto solo pasa una vez.")
        
        import torch
        # --- PARCHE DE COMPATIBILIDAD PARA PYTORCH 2.6+ ---
        # Obligamos a PyTorch a confiar en los archivos locales de XTTSv2
        _carga_original = torch.load
        def _carga_parcheada(*args, **kwargs):
            kwargs['weights_only'] = False
            return _carga_original(*args, **kwargs)
        torch.load = _carga_parcheada
        # --------------------------------------------------
        
        from TTS.api import TTS
        # Cargamos el modelo localmente en la GPU
        _modelo_xtts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=True)
        print("✅ Motor de voz (XTTSv2) cargado en memoria.")
    return _modelo_xtts

# =====================================================================
# UTILIDADES DE TEXTO
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

# =====================================================================
# FUNCIONES PRINCIPALES DE AUDIO
# =====================================================================
def hablar_no_bloqueante(texto):
    global hablando_actualmente
    
    detener_voz()
    texto_limpio = limpiar_texto_para_voz(texto)
    
    if not texto_limpio:
        return

    print(f"🔊 Hablando (Voz: XTTSv2 Premium Local)...")
    
    def _hilo_voz():
        global hablando_actualmente
        try:
            hablando_actualmente = True
            archivo_salida = os.path.join(tempfile.gettempdir(), "cortana_voz_temp.wav")
            # Ruta relativa a la raíz del proyecto donde se ejecuta main_gui.py
            ruta_referencia = "referencia.wav" 
            
            # 1. Asegurarnos de que el modelo está cargado (con el parche)
            tts = _cargar_xtts_si_necesario()

            if not os.path.exists(ruta_referencia):
                print(f"⚠️ [Error de Voz] No se encontró el archivo molde '{ruta_referencia}' en la raíz del proyecto.")
                return

            # 2. Generar el audio neuronal
            tts.tts_to_file(
                text=texto_limpio,
                file_path=archivo_salida,
                speaker_wav=ruta_referencia,
                language="es"
            )
            
            # 3. Reproducción del audio
            if os.path.exists(archivo_salida):
                data, fs = sf.read(archivo_salida)
                sd.play(data, fs)
                
                # Calcular la duración del audio para saber cuánto esperar
                duracion_segundos = len(data) / fs
                tiempo_inicio = time.time()
                
                # Mantener el hilo vivo mientras habla o hasta que lo interrumpamos
                while (time.time() - tiempo_inicio < duracion_segundos) and hablando_actualmente:
                    # Detectar si el usuario presiona la tecla Escape (Interrupción directa)
                    if keyboard.is_pressed('esc'):
                        print("\n🛑 [TECLADO] Tecla ESC presionada. Cortando audio...")
                        hablando_actualmente = False
                        break
                        
                    time.sleep(0.05)
                    
                # Limpiar la reproducción al terminar
                sd.stop()
                
                try:
                    os.remove(archivo_salida)
                except Exception:
                    pass

        except Exception as e:
            print(f"⚠️ Error en el hilo de voz (XTTSv2): {e}")
        finally:
            hablando_actualmente = False

    # Ejecutamos todo el proceso de voz en un hilo secundario
    threading.Thread(target=_hilo_voz, daemon=True).start()

def detener_voz():
    global hablando_actualmente
    if hablando_actualmente:
        try:
            print("🛑 [INTERRUPCIÓN] Callando a Argus...")
            sd.stop() # Corta de raíz cualquier sonido en sounddevice
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