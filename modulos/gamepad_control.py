"""
gamepad_control.py
===================
Controlador de gamepad via subproceso aislado (gamepad_service.py).
Conecta la lectura de mandos (Xbox / DualSense) sin interferencias con PyWebView.
"""

import os
import sys
import subprocess
import threading
import time
from modulos.logger import logger


class GestorGamepad:
    """
    Gestiona el subproceso independiente gamepad_service.py y expone
    el callback de voz push-to-talk (L3+R3) de forma segura.
    """
    _instancia = None

    def __init__(self, callback_activar_voz=None, callback_pausa_activa=None, callback_mandos_changed=None):
        self._callback_activar_voz = callback_activar_voz
        self._callback_pausa_activa = callback_pausa_activa
        self._callback_mandos_changed = callback_mandos_changed
        self._proc = None
        self._thread = None
        self._stop_event = threading.Event()
        self._combo_activo = False
        self._mandos = []
        self._indice_preferido = -1
        GestorGamepad._instancia = self

    def iniciar_con_indice(self, indice: int):
        self._indice_preferido = indice
        self.iniciar()

    def iniciar(self):
        if self._proc and self._proc.poll() is None:
            return

        GestorGamepad._instancia = self
        script_path = os.path.join(os.path.dirname(__file__), "gamepad_service.py")
        cmd = [sys.executable, script_path]

        try:
            creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                creationflags=creationflags
            )
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._read_stdout, daemon=True)
            self._thread.start()
            logger.info("🎮 Subproceso gamepad_service.py iniciado exitosamente.")
        except Exception as e:
            logger.error(f"[GAMEPAD] Error iniciando subproceso de gamepad: {e}")

    def detener(self):
        self._stop_event.set()
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=1.0)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None
        logger.info("[GAMEPAD] Subproceso de gamepad detenido.")

    def _read_stdout(self):
        if not self._proc or not self._proc.stdout:
            return

        for line in iter(self._proc.stdout.readline, ''):
            if self._stop_event.is_set():
                break
            line = line.strip()
            if not line:
                continue

            if line.startswith("COMBO_START"):
                if not self._combo_activo:
                    self._combo_activo = True
                    partes = line.split(":", 1)
                    nombre_mando = partes[1] if len(partes) > 1 else "Gamepad"
                    logger.info(f"[GAMEPAD] Combo L3+R3 activado en '{nombre_mando}'")
                    if self._callback_activar_voz:
                        threading.Thread(
                            target=self._callback_activar_voz,
                            args=(self._combo_sigue_presionado,),
                            daemon=True
                        ).start()
            elif line == "COMBO_STOP":
                self._combo_activo = False
            elif line.startswith("MANDO_ADDED:"):
                partes = line.split(":", 2)
                if len(partes) == 3:
                    try:
                        idx = int(partes[1])
                        nombre = partes[2]
                        if not any(m["indice"] == idx for m in self._mandos):
                            self._mandos.append({"indice": idx, "nombre": nombre})
                            logger.info(f"[GAMEPAD] Mando detectado: '{nombre}' (idx {idx})")
                            if self._callback_mandos_changed:
                                try:
                                    self._callback_mandos_changed(self._mandos)
                                except Exception:
                                    pass
                    except ValueError:
                        pass
            elif line.startswith("MANDO_REMOVED:"):
                partes = line.split(":", 1)
                if len(partes) == 2:
                    try:
                        idx = int(partes[1])
                        self._mandos = [m for m in self._mandos if m["indice"] != idx]
                        if self._callback_mandos_changed:
                            try:
                                self._callback_mandos_changed(self._mandos)
                            except Exception:
                                pass
                    except ValueError:
                        pass

    def _combo_sigue_presionado(self) -> bool:
        return self._combo_activo

    def reintentar_escaneo(self):
        """Detiene y reinicia el subproceso para forzar un re-escaneo de mandos."""
        self._mandos = []
        self.detener()
        self._stop_event.clear()
        self.iniciar()
        logger.info("[GAMEPAD] Re-escaneo forzado de mandos.")

    @staticmethod
    def listar_mandos_disponibles() -> list:
        instancia = getattr(GestorGamepad, '_instancia', None)
        if instancia:
            return instancia._mandos
        return []
