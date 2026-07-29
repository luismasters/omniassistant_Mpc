"""
Gestor de Wake Word usando Vosk con keyphrase (CUALQUIER palabra, sin API key).
Corre en un hilo background escuchando el micrófono.
Thread-safe con toggle on/off.
La palabra clave es configurable. Por defecto: "argus"
"""

import os
import time
import json
import threading
from modulos.logger import logger

# Vosk
try:
    import vosk
    _HAY_VOSK = True
except ImportError:
    _HAY_VOSK = False
    logger.warning("⚠️ vosk no instalado. Wake Word no disponible. pip install vosk")

# sounddevice
import sounddevice as sd
import numpy as np

# Constantes
FS_AUDIO = 16000
FRAME_LENGTH = 4096  # Vosk funciona bien con frames de ~4000 samples
SILENCIO_MAX_GRABACION = 8
PALABRA_CLAVE = "argus"  # <<< CAMBIÁ ESTO por la palabra que quieras


def _descargar_modelo_vosk():
    """
    Descarga el modelo Vosk de español pequeño si no existe.
    ~42 MB, se descarga una sola vez a la carpeta modulos/skills/wake_word/
    """
    import urllib.request
    import zipfile
    
    directorio = os.path.dirname(os.path.abspath(__file__))
    ruta_modelo = os.path.join(directorio, "vosk-model")
    
    if os.path.exists(ruta_modelo) and os.path.isdir(ruta_modelo):
        if any(f.endswith('.conf') or f.endswith('.bin') for _, _, files in os.walk(ruta_modelo) for f in files):
            return ruta_modelo
    
    url = "https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip"
    zip_path = os.path.join(directorio, "vosk-model-small-es-0.42.zip")
    
    logger.info(f"📥 Descargando modelo Vosk español ({url})...")
    try:
        urllib.request.urlretrieve(url, zip_path)
        logger.info("📦 Extrayendo modelo Vosk...")
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(directorio)
        extracted = os.path.join(directorio, "vosk-model-small-es-0.42")
        if os.path.exists(extracted):
            if os.path.exists(ruta_modelo):
                import shutil
                shutil.rmtree(ruta_modelo)
            os.rename(extracted, ruta_modelo)
        os.remove(zip_path)
        logger.info("✅ Modelo Vosk descargado y extraído.")
        return ruta_modelo
    except Exception as e:
        logger.exception(f"Error descargando modelo Vosk: {e}")
        return None


class GestorWakeWord:
    """
    Hilo background que escucha la palabra clave "argus" vía Vosk.
    Al detectarla, inicia una captura de voz con Whisper.
    """

    def __init__(self, callback_grabar=None, palabra_clave=None):
        self._activo = False
        self._hilo = None
        self._modelo = None
        self._recognizer = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._callback_grabar = callback_grabar
        self._palabra_clave = palabra_clave or PALABRA_CLAVE

    # ─── API PÚBLICA ────────────────────────────────────────────────

    def activar(self):
        with self._lock:
            if self._activo:
                return {"exito": True, "estado": "already_active"}
            if not _HAY_VOSK:
                return {"exito": False, "error": "vosk no está instalado"}

            try:
                ruta_modelo = _descargar_modelo_vosk()
                if not ruta_modelo:
                    return {"exito": False, "error": "No se pudo obtener el modelo Vosk"}
                
                logger.info(f"🔊 Cargando modelo Vosk desde: {ruta_modelo}")
                self._modelo = vosk.Model(ruta_modelo)
                
                gramatica = json.dumps([self._palabra_clave])
                self._recognizer = vosk.KaldiRecognizer(self._modelo, FS_AUDIO, gramatica)
                logger.info(f"🔊 Wake Word activado con palabra: '{self._palabra_clave}'")
            except Exception as e:
                logger.exception(f"Error inicializando Vosk: {e}")
                return {"exito": False, "error": str(e)}

            self._activo = True
            self._stop_event.clear()

        self._hilo = threading.Thread(target=self._loop_escucha, daemon=True)
        self._hilo.start()
        logger.info("🔊 Hilo de Wake Word iniciado.")
        return {"exito": True, "estado": "activated"}

    def desactivar(self):
        with self._lock:
            if not self._activo:
                return {"exito": True, "estado": "already_inactive"}
            self._activo = False
            self._stop_event.set()
        self._modelo = None
        self._recognizer = None
        logger.info("🔇 Wake Word desactivado.")
        return {"exito": True, "estado": "deactivated"}

    def toggle(self, callback_grabar=None):
        if self.esta_activo():
            self.desactivar()
            return {"exito": True, "estado": "deactivated"}
        else:
            if callback_grabar:
                self._callback_grabar = callback_grabar
            return self.activar()

    def esta_activo(self) -> bool:
        with self._lock:
            return self._activo

    # ─── BUCLE PRINCIPAL ────────────────────────────────────────────

    def _loop_escucha(self):
        try:
            with sd.InputStream(
                samplerate=FS_AUDIO,
                channels=1,
                dtype='int16',
                blocksize=FRAME_LENGTH,
            ) as stream:
                while self.esta_activo() and not self._stop_event.is_set():
                    try:
                        bloque, _ = stream.read(FRAME_LENGTH)
                        # Convertir numpy array int16 a bytes
                        datos_bytes = bloque.tobytes()
                        
                        if self._recognizer.AcceptWaveform(datos_bytes):
                            resultado = json.loads(self._recognizer.Result())
                            texto = resultado.get("text", "").strip().lower()
                            
                            if self._palabra_clave in texto:
                                logger.info(f"🔊 Palabra clave '{self._palabra_clave}' detectada!")
                                self._on_wake_word_detectado()
                                return
                                
                    except Exception as e:
                        if self.esta_activo():
                            logger.warning(f"Error en loop de wake word: {e}")
                            time.sleep(0.1)
        except Exception as e:
            logger.exception(f"Error en stream de audio para wake word: {e}")
        finally:
            logger.info("🔇 Hilo de Wake Word terminado.")
            if self.esta_activo():
                logger.info("🔊 Reiniciando hilo de Wake Word...")
                self._hilo = threading.Thread(target=self._loop_escucha, daemon=True)
                self._hilo.start()

    def _on_wake_word_detectado(self):
        try:
            from modulos.audio_custom import capturar_voz_micro, _beep_inicio
            
            _beep_inicio()
            self._notificar_estado("listening")
            
            inicio = time.time()
            
            def condicion_grabar():
                if not self.esta_activo():
                    return False
                if time.time() - inicio > SILENCIO_MAX_GRABACION:
                    return False
                return True
            
            texto = capturar_voz_micro(condicion_seguir_grabando=condicion_grabar)
            
            self._notificar_estado("idle")
            
            if texto and self._callback_grabar:
                self._callback_grabar(texto)
                
        except Exception as e:
            logger.exception(f"Error procesando wake word detection: {e}")
            self._notificar_estado("idle")

    def _notificar_estado(self, estado: str):
        try:
            import webview
            win = webview.windows[0] if webview.windows else None
            if win:
                if estado == "listening":
                    win.evaluate_js("if (window.iniciarEscuchaVozUI) window.iniciarEscuchaVozUI();")
                else:
                    win.evaluate_js("if (window.detenerEscuchaVozUI) window.detenerEscuchaVozUI();")
        except Exception:
            pass


# Instancia global
gestor_wake_word = GestorWakeWord()