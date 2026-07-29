"""
Gestor de Wake Word "Computer" usando Porcupine (Picovoice).
Corre en un hilo background escuchando el micrófono.
Thread-safe con toggle on/off.
"""

import os
import time
import queue
import threading
import struct
from modulos.logger import logger

# Porcupine
try:
    import pvporcupine
    _HAY_PORCUPINE = True
except ImportError:
    _HAY_PORCUPINE = False
    logger.warning("⚠️ pvporcupine no instalado. Wake Word no disponible. pip install pvporcupine")

# sounddevice para capturar audio del micrófono
import sounddevice as sd
import numpy as np

# Constantes
FS_AUDIO = 16000
FRAME_LENGTH = 512  # Porcupine espera 512 samples por frame
SILENCIO_MAX_GRABACION = 8  # segundos máximos de grabación tras detectar wake word
VAD_SILENCE_TIMEOUT = 2.0   # segundos de silencio para cortar grabación


class GestorWakeWord:
    """
    Hilo background que escucha la palabra "Computer" vía Porcupine.
    Al detectarla, inicia una captura de voz con Whisper.
    """

    def __init__(self, callback_grabar=None):
        self._activo = False
        self._hilo = None
        self._porcupine = None
        self._lock = threading.Lock()
        self._audio_queue = queue.Queue()
        self._stop_event = threading.Event()
        self._callback_grabar = callback_grabar  # función a llamar al detectar wake word

    # ─── API PÚBLICA ────────────────────────────────────────────────

    def activar(self):
        """Activa la escucha de wake word en un hilo background."""
        with self._lock:
            if self._activo:
                return {"exito": True, "estado": "already_active"}
            if not _HAY_PORCUPINE:
                return {"exito": False, "error": "pvporcupine no está instalado"}

            try:
                # Inicializar Porcupine con la palabra "Computer" (gratuita, sin API key)
                self._porcupine = pvporcupine.create(keywords=["computer"])
                logger.info(f"🔊 Wake Word activado: 'Computer' (tasa de muestreo: {self._porcupine.sample_rate})")
            except Exception as e:
                logger.exception(f"Error inicializando Porcupine: {e}")
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

        # Liberar Porcupine
        try:
            if self._porcupine:
                self._porcupine.delete()
                self._porcupine = None
        except Exception as e:
            logger.warning(f"Error liberando Porcupine: {e}")

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
        Lee continuamente del micrófono en bloques de 512 samples a 16kHz.
        Por cada bloque, llama a porcupine.process() para detectar la palabra clave.
        """
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
                        # Aplanar el array 2D a 1D
                        pcm = bloque.flatten()
                        
                        # Porcupine espera una lista de enteros int16
                        resultado = self._porcupine.process(pcm.tolist())
                        
                        if resultado >= 0:
                            logger.info("🔊 Wake word 'Computer' detectado!")
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
            
            # Callback de estado para la UI
            self._notificar_estado("listening")
            
            # Definir condición de corte: grabar hasta que se cumpla el timeout o silencio
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