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
# audio_custom se importa de forma perezosa para evitar dependencias pesadas

# Vosk y sounddevice se importan de forma perezosa dentro de los métodos
# que los usan, para no arrastrar dependencias pesadas al importar el módulo.
_HAY_VOSK = False
_HERRAMIENTAS_AUDIO_OK = False

try:
    import vosk
    _HAY_VOSK = True
except ImportError:
    logger.warning("⚠️ vosk no instalado. Wake Word no disponible. pip install vosk")

try:
    import sounddevice as sd
    import numpy as np
    _HERRAMIENTAS_AUDIO_OK = True
except ImportError:
    logger.warning("⚠️ sounddevice/numpy no instalados. Wake Word no disponible.")

# Constantes
FS_AUDIO = 16000
FRAME_LENGTH = 4096
SILENCIO_MAX_GRABACION = 8
PALABRA_CLAVE = "ok argus"

# Gramática de Vosk optimizada para reducir uso de CPU y maximizar detección fonética.
# Solo variantes reales de "ok argus" — sin sufijos lejanos como "algo", "arcos",
# "angus" que generan falsos positivos con frases coloquiales comunes.
GRAMATICA_WAKE_WORD = [
    "ok argos", "okey argos", "oquei argos", "okey argus",
    "oquei argus", "o cargos", "o cargo", "o cargus",
    "ocargos", "ocargo", "ocargus", "okargo", "okargos", "okargus",
    "corta", "[unk]"
]

# Prefijos FUERTES: solo variantes claras de "ok". Se eliminan "o" y "k" sueltos
# porque "o algo", "o cargos" en medio de frases coloquiales causan falsos positivos.
PREFIJOS_OK = {"ok", "okey", "oquei"}

# Sufijos realmente cercanos fonéticamente a "argus". Se eliminan
# "algo", "arcos", "angus", "algus" por ser demasiado lejanos y coloquiales.
SUFIJOS_ARGUS = {"argus", "argos", "argo", "cargus", "cargos", "cargo"}

# Variantes de frase completa que se permiten en resultados parciales.
# Solo la literal "ok argus" dispara con parciales; el resto requiere frase cerrada.
VARIANTES_DIRECTAS = [
    "ok argus", "ok argos", "okey argos", "oquei argos", "okey argus",
    "oquei argus", "o cargos", "o cargo", "o cargus",
    "ocargos", "ocargo", "ocargus", "okargo", "okargos", "okargus"
]


def _es_match_wake_word(texto: str, permitir_parcial: bool = True) -> bool:
    """
    Comprueba si el texto reconocido coincide con 'ok argus' o sus variaciones
    fonéticas equivales en el vocabulario en español de Vosk.

    Args:
        texto: texto reconocido por Vosk (lowercase)
        permitir_parcial: si False, solo detecta la frase literal "ok argus"
            (para resultados parciales ambiguos)
    """
    texto = texto.lower().strip()
    if not texto:
        return False

    palabras = texto.split()
    if not palabras:
        return False

    # La coincidencia debe estar al INICIO del texto (o tras silencio).
    # "quiero que ok argus abra chrome" NO debe disparar.
    primera_palabra = palabras[0]

    # La frase literal "ok argus" SIEMPRE es aceptada si va al inicio
    if primera_palabra == "ok" and len(palabras) >= 2 and palabras[1] == "argus":
        return True

    # Para variantes fonéticas se requiere frase cerrada
    if not permitir_parcial:
        return False

    # Caso 1: Prefijo fuerte + sufijo válido al inicio
    if len(palabras) >= 2 and primera_palabra in PREFIJOS_OK and palabras[1] in SUFIJOS_ARGUS:
        return True

    # Caso 2: Variantes fonéticas de una sola palabra
    if primera_palabra in {"ocargos", "ocargo", "ocargus", "okargo", "okargos", "okargus"}:
        return True

    # Caso 3: Variantes fonéticas de dos palabras ("o cargos", etc.)
    if len(palabras) >= 2:
        par_inicial = f"{palabras[0]} {palabras[1]}"
        if par_inicial in ("o cargos", "o cargo", "o cargus"):
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
        from modulos.audio_custom import detener_voz, esta_hablando
        cooldown_hasta = 0.0
        # Ventana de confirmación para reducir falsos positivos:
        # un candidato debe confirmarse en frames consecutivos antes de disparar.
        candidato_pendiente = None
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

                        # ─── VALIDACIÓN DE ENERGÍA (RMS) ────────────────────
                        # Evita que ruido ambiental, música de fondo o sonidos
                        # del juego disparen detecciones espurias.
                        from config import RMS_UMBRAL_VOZ
                        bloque_float = bloque.astype(np.float32)
                        rms = float(np.sqrt(np.mean(bloque_float**2))) if bloque_float.size else 0.0
                        hay_voz = rms >= RMS_UMBRAL_VOZ

                        # Si hay silencio, resetear candidato pendiente
                        if not hay_voz:
                            candidato_pendiente = None

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

                        # ─── VALIDAR QUE HAY VOZ REAL ANTES DE DETECTAR ─────
                        # Sin voz real no hay detección, aunque Vosk reconozca texto
                        if not hay_voz:
                            candidato_pendiente = None
                            continue

                        # ─── DETECCIÓN DE FRASE CLAVE ─────────────────────
                        # En frases finales (es_final=True) se permiten todas las
                        # variantes fonéticas. En parciales solo la literal "ok argus".
                        # Esto evita falsos positivos con audio ambiguo.
                        if es_final:
                            permitir_parcial = True
                        else:
                            permitir_parcial = False

                        if _es_match_wake_word(texto, permitir_parcial=permitir_parcial):
                            # ─── VENTANA DE CONFIRMACIÓN ──────────────────
                            # Si ya hay un candidato pendiente y el texto coincide,
                            # confirmar la detección. Si no, marcar como candidato.
                            if candidato_pendiente is not None and candidato_pendiente == texto:
                                logger.info(f"🔊 Frase clave '{self._palabra_clave}' detectada en: '{texto}'")
                                # Activar cooldown post-detección para evitar doble disparo
                                cooldown_hasta = ahora + 1.0
                                self._on_wake_word_detectado()
                                return
                            else:
                                candidato_pendiente = texto
                        else:
                            # El texto no coincide; si no es "ok argus" literal
                            # en parcial, descartar candidato (podría ser otra frase)
                            if not permitir_parcial:
                                candidato_pendiente = None
                                
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