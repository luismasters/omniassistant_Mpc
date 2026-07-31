"""
Gestor de Wake Word usando Vosk en modo continuo (sin gramática).
Detecta "ok argus" en resultados parciales en tiempo real.
CUALQUIER palabra, sin API key, gratis.
Corre en un hilo background escuchando el micrófono.
Thread-safe con toggle on/off.

PROTECCIÓN ANTI-BUCLE:
- Mientras el asistente está hablando (hablando_actualmente=True),
  se descarta el audio del micrófono para evitar que la propia
  respuesta de voz dispare una nueva detección.
- Cooldown post-respuesta para evitar falsos positivos justo
  después de terminar de hablar.
- Palabra de interrupción "corta" que detiene la voz del asistente.
"""

import os
import time
import json
import threading
from modulos.logger import logger
from modulos.audio_custom import detener_voz, esta_hablando

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
FRAME_LENGTH = 4096
SILENCIO_MAX_GRABACION = 8
PALABRA_CLAVE = "ok argus"

# Gramática de Vosk optimizada para reducir uso de CPU y maximizar detección fonética
GRAMATICA_WAKE_WORD = [
    "ok argos", "okey argos", "oquei argos", "o k argos", "okey argus",
    "oquei argus", "o k argos", "o cargos", "o cargo", "o cargus",
    "ocargos", "ocargo", "ocargus", "okargo", "okargos", "okargus",
    "ok algo", "ok arcos", "ok angus",
    "corta", "[unk]"
]


def _es_match_wake_word(texto: str) -> bool:
    """
    Comprueba si el texto reconocido coincide con 'ok argus' o sus variaciones
    fonéticas equivalentes en el vocabulario en español de Vosk.
    """
    texto = texto.lower().strip()
    if not texto:
        return False
        
    if "ok argus" in texto:
        return True
        
    variaciones_directas = [
        "ok argos", "okey argos", "oquei argos", "o k argos", "okey argus",
        "oquei argus", "o k argus", "o cargos", "o cargo", "o cargus",
        "ocargos", "ocargo", "ocargus", "okargo", "okargos", "okargus",
        "ok algo", "ok arcos", "ok angus"
    ]
    for var in variaciones_directas:
        if var in texto:
            return True
            
    palabras = texto.split()
    prefijos_ok = {"ok", "okey", "oquei", "o", "k"}
    sufijos_argus = {"argus", "argos", "argo", "algus", "angus", "arcos", "algo"}
    
    for i in range(len(palabras) - 1):
        if palabras[i] in prefijos_ok and palabras[i+1] in sufijos_argus:
            return True
            
    return False


def _descargar_modelo_vosk():
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
    Hilo background que escucha la frase "ok argus" vía Vosk en modo continuo.
    Detecta la frase completa en resultados parciales para minimizar falsos positivos.
    """

    def __init__(self, callback_grabar=None, palabra_clave=None):
        self._activo = False
        self._hilo = None
        self._modelo = None
        self._recognizer = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._callback_grabar = callback_grabar
        self._palabra_clave = (palabra_clave or PALABRA_CLAVE).lower()

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
                
                # Reconocimiento con gramática optimizada para variantes de "ok argus".
                gramatica = json.dumps(GRAMATICA_WAKE_WORD)
                self._recognizer = vosk.KaldiRecognizer(self._modelo, FS_AUDIO, gramatica)
                self._recognizer.SetWords(False)
                logger.info(f"🔊 Wake Word activado — escuchando frase '{self._palabra_clave}' con gramática optimizada")
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
        cooldown_hasta = 0.0
        try:
            with sd.InputStream(
                samplerate=FS_AUDIO,
                channels=1,
                dtype='int16',
                blocksize=FRAME_LENGTH,
            ) as stream:
                while self.esta_activo() and not self._stop_event.is_set():
                    try:
                        # ─── PROTECCIÓN ANTI-BUCLE ──────────────────────────
                        # 1. SI EL ASISTENTE ESTÁ HABLANDO: descartar audio
                        if esta_hablando():
                            time.sleep(0.05)
                            # Resetear recognizer para evitar falsos acumulados
                            # (Vosk puede falsear detecciones con silencios)
                            self._recognizer.Reset()
                            continue

                        # 2. COOLDOWN POST-RESPUESTA: evitar falsos positivos
                        #    justo después de que el asistente termina de hablar
                        ahora = time.time()
                        if ahora < cooldown_hasta:
                            time.sleep(0.05)
                            continue
                        # ─── FIN PROTECCIÓN ANTI-BUCLE ───────────────────────

                        bloque, _ = stream.read(FRAME_LENGTH)
                        datos_bytes = bloque.tobytes()
                        
                        # Alimentar al recognizer (devuelve True si cerró frase/silencio)
                        es_final = self._recognizer.AcceptWaveform(datos_bytes)
                        
                        if es_final:
                            res = json.loads(self._recognizer.Result())
                            texto = res.get("text", "").lower()
                        else:
                            partial = json.loads(self._recognizer.PartialResult())
                            texto = partial.get("partial", "").lower()
                        
                        if not texto:
                            continue

                        # ─── PALABRA DE INTERRUPCIÓN ──────────────────────
                        # Si el usuario dice "corta" mientras el asistente habla,
                        # detener la voz inmediatamente
                        if "corta" in texto.split():
                            logger.info("✋ Palabra de interrupción 'corta' detectada — deteniendo voz del asistente")
                            detener_voz()
                            # Cooldown breve para evitar que el eco del "corta"
                            # dispare otra detección de palabra clave
                            cooldown_hasta = time.time() + 0.5
                            continue

                        # ─── DETECCIÓN DE FRASE CLAVE ─────────────────────
                        # Coincidencia fonética flexible para "ok argus"
                        if _es_match_wake_word(texto):
                            logger.info(f"🔊 Frase clave '{self._palabra_clave}' detectada en: '{texto}'")
                            # Activar cooldown post-detección para evitar doble disparo
                            cooldown_hasta = ahora + 1.0
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