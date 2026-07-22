"""
Manejo de Gamepad vía `inputs` (XInput/DirectInput) para evitar colisiones 
con el message loop de Windows y PyWebView.
"""
import threading
import time
from modulos.logger import logger

try:
    from inputs import devices, get_gamepad
    _INPUTS_DISPONIBLE = True
except ImportError:
    _INPUTS_DISPONIBLE = False

class GestorGamepadInputs:
    def __init__(self, callback_activar_voz=None):
        self._callback_activar_voz = callback_activar_voz
        self._hilo = None
        self._stop_event = threading.Event()
        self._combo_presionado = False
        self._indice_preferido = 0

    @classmethod
    def listar_mandos_disponibles(cls):
        if not _INPUTS_DISPONIBLE:
            return []
        try:
            mandos = []
            for idx, dev in enumerate(devices.gamepads):
                mandos.append({"indice": idx, "nombre": dev.name})
            return mandos
        except Exception as e:
            logger.warning(f"Error listando gamepads (inputs): {e}")
            return []

    def obtener_estado(self):
        try:
            mandos = self.listar_mandos_disponibles()
            nombre = mandos[self._indice_preferido]["nombre"] if mandos and self._indice_preferido < len(mandos) else "No conectado"
            return {
                "disponible": len(mandos) > 0,
                "nombre": nombre,
                "combo_l3": "L3",
                "combo_r3": "R3"
            }
        except Exception:
            return {"disponible": False, "nombre": "No conectado", "combo_l3": "N/A", "combo_r3": "N/A"}

    def iniciar_con_indice(self, indice: int):
        self._indice_preferido = indice
        self.detener()
        self.iniciar()

    def iniciar(self):
        if not _INPUTS_DISPONIBLE:
            logger.warning("[GAMEPAD] Librería 'inputs' no disponible. Gamepad deshabilitado.")
            return
        
        if self._hilo and self._hilo.is_alive():
            return
            
        self._stop_event.clear()
        self._hilo = threading.Thread(target=self._loop_escucha, daemon=True)
        self._hilo.start()
        logger.info("[GAMEPAD] GestorGamepadInputs (XInput) iniciado.")

    def detener(self):
        self._stop_event.set()
        if self._hilo:
            self._hilo.join(timeout=1.0)
        logger.info("[GAMEPAD] Detenido.")

    def _loop_escucha(self):
        # inputs.get_gamepad() es bloqueante, pero solo lanza eventos cuando ocurren.
        # Esto es mucho mejor que el polling de pygame.
        logger.info("[GAMEPAD] Esperando eventos de mando...")
        
        l3_pressed = False
        r3_pressed = False
        
        while not self._stop_event.is_set():
            try:
                events = get_gamepad()
                for event in events:
                    # 'BTN_THUMBL' es L3, 'BTN_THUMBR' es R3
                    if event.code == 'BTN_THUMBL':
                        l3_pressed = (event.state == 1)
                    elif event.code == 'BTN_THUMBR':
                        r3_pressed = (event.state == 1)
                        
                    # Comprobar el combo
                    combo_activo = l3_pressed and r3_pressed
                    
                    if combo_activo and not self._combo_presionado:
                        self._combo_presionado = True
                        logger.debug("[GAMEPAD] Combo L3+R3 (XInput) presionado.")
                        if self._callback_activar_voz:
                            # Lanzar en hilo para no bloquear lectura
                            def check_combo():
                                # Como no podemos leer el estado sincrónico fácil con inputs, 
                                # confiamos en el evento de soltar. Pero para ser seguros:
                                return self._combo_presionado
                            
                            threading.Thread(
                                target=self._callback_activar_voz, 
                                args=(check_combo,), 
                                daemon=True
                            ).start()
                            
                    elif not combo_activo and self._combo_presionado:
                        self._combo_presionado = False
                        logger.debug("[GAMEPAD] Combo L3+R3 soltado.")
                        
            except Exception as e:
                # Si se desconecta el mando, `get_gamepad` lanza excepción
                if "No gamepad found" not in str(e):
                    logger.warning(f"[GAMEPAD] Error leyendo: {e}")
                time.sleep(2.0)
