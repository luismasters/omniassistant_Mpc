"""
Gestor de Wake Word usando OpenWakeWord (gratuito, open source, sin API key).
Corre en un hilo background escuchando el micrófono con un modelo ONNX local.
Thread-safe con toggle on/off.
"""

import os
import time
import queue
import threading
from modulos.logger import logger

# OpenWakeWord
try:
    from openwakeword import Model as OWWModel
    _HAY_OPENWAKEWORD = True
except ImportError:
    _HAY_OPENWAKEWORD = False
    logger.warning("⚠️ openwakeword no instalado. Wake Word no disponible. pip install openwakeword")

# sounddevice para capturar audio del micrófono
import sounddevice as sd
import numpy as np

# Constantes
FS_AUDIO = 16000
FRAME_LENGTH = 1280  # OpenWakeWord funciona bien con ~1280 samples (80ms a 16kHz)
SILENCIO_MAX_GRABACION = 8  # segundos máximos de grabación tras detectar wake word
UMBRAL_DETECCION = 0.5      # threshold de confianza para considerar detectado


class GestorWakeWord:
    """
    Hilo background que escucha la palabra "computer" vía OpenWakeWord.
    Al detectarla, inicia una captura de voz con Whisper.
    """

    def __init__(self, callback_grabar=None):
        self._activo = False
        self._hilo = None
        self._modelo = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._callback_grabar = callback_grabar  # función a llamar al detectar wake word

    # ─── API PÚBLICA ────────────────────────────────────────────────

    def activar(self):
        """Activa la escucha de wake word en un hilo background."""
        with self._lock:
            if self._activo:
                return {"exito": True, "estado": "already_active"}
            if not _HAY_OPENWAKEWORD:
                return {"exito": False, "error": "openwakeword no está instalado"}

            try:
                # Cargar modelo "computer" (se descarga automáticamente la primera vez ~30MB)
                logger.info("🔊 Cargando modelo OpenWakeWord 'computer'...")
                self._modelo = OWWModel(wakeword_models=["computer"])
                logger.info(f"🔊 Wake Word activado: 'computer'")
            except Exception as e:
                logger.exception(f"Error inicializando OpenWakeWord: {e}")
                return {"exito": False, "error": str(e)}

            self._activo = True
            self._stop_event.clear()

        # Iniciar hilo de escucha
        self._hilo = threading.Thread(target=self._loop_escucha, daemon=True)
        self._hilo.start()
        logger.info("🔊 Hilo de Wake Word iniciado.")
        return {"exito": True, "estado": "activated"}

    def desactivar(self):
        """Desactiva la escucha de wake word y libera recursos."""
        with self._lock:
            if not self._activo:
                return {"exito": True, "estado": "already_inactive"}
            self._activo = False
            self._stop_event.set()

        # Liberar modelo
        self._modelo = None

        logger.info("🔇 Wake Word desactivado.")
        return {"exito": True, "estado": "deactivated"}

    def toggle(self, callback_grabar=None):
        """Alterna entre activado/desactivado."""
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
        """
        Lee continuamente del micrófono en bloques a 16kHz.
        Por cada bloque, llama al modelo para detectar la palabra clave.
        """
        try:
            with sd.InputStream(
                samplerate=FS_AUDIO,
                channels=1,
                dtype='float32',
                blocksize=FRAME_LENGTH,
            ) as stream:
                while self.esta_activo() and not self._stop_event.is_set():
                    try:
                        bloque, _ = stream.read(FRAME_LENGTH)
                        pcm = bloque.flatten()
                        
                        # OpenWakeWord predice sobre el frame
                        resultado = self._modelo.predict(pcm)
                        
                        # Revisar si la palabra "computer" fue detectada
                        confianza = resultado.get("computer", 0.0)
                        if confianza > UMBRAL_DETECCION:
                            logger.info(f"🔊 Wake word 'computer' detectado! (confianza: {confianza:.2f})")
                            self._on_wake_word_detectado()
                            
                    except Exception as e:
                        logger.warning(f"Error en loop de wake word: {e}")
                        time.sleep(0.1)
        except Exception as e:
            logger.exception(f"Error en stream de audio para wake word: {e}")
        finally:
            logger.info("🔇 Hilo de Wake Word terminado.")

    def _on_wake_word_detectado(self):
        """
        Se llama cuando se detecta la palabra clave.
        Inicia una captura de voz y la envía al callback.
        """
        try:
            from modulos.audio_custom import capturar_voz_micro, _beep_inicio
            
            # Beep de confirmación
            _beep_inicio()
            
            # Notificar a la UI
            self._notificar_estado("listening")
            
            # Definir condición de corte: grabar hasta timeout
            inicio = time.time()
            
            def condicion_grabar():
                if not self.esta_activo():
                    return False
                if time.time() - inicio > SILENCIO_MAX_GRABACION:
                    return False
                return True
            
            # Grabar audio
            texto = capturar_voz_micro(condicion_seguir_grabando=condicion_grabar)
            
            self._notificar_estado("idle")
            
            if texto and self._callback_grabar:
                self._callback_grabar(texto)
                
        except Exception as e:
            logger.exception(f"Error procesando wake word detection: {e}")
            self._notificar_estado("idle")

    def _notificar_estado(self, estado: str):
        """Notifica al frontend via evaluate_js si hay ventana disponible."""
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