"""
gamepad_control.py
===================
Lectura de gamepad (Xbox / DualSense) via pygame.joystick.

NO usa la libreria 'keyboard' ni hooks globales de Windows.
pygame.joystick lee el dispositivo via XInput/DirectInput directamente,
evitando el conflicto que causaba el deadlock con PoE2.

Combo de activacion: L3 + R3 mantenidos (push-to-talk).
Compatible con Xbox One y DualSense simultaneamente.
"""

import threading
import time

try:
    import pygame
    _PYGAME_DISPONIBLE = True
except ImportError:
    _PYGAME_DISPONIBLE = False

from modulos.logger import logger

# =====================================================================
# MAPEO DE BOTONES — deteccion automatica por tipo de mando
# =====================================================================
# Confirmado en pruebas reales del usuario:
#   DualSense (PS5): L3=7, R3=8
#   Xbox One:        L3=8, R3=9

MAPEO_POR_TIPO = {
    "dualsense":           (7, 8),
    "ps5":                 (7, 8),
    "wireless controller": (7, 8),
    "xbox":                (8, 9),
    "xinput":              (8, 9),
}
MAPEO_DEFECTO = (8, 9)
MAPEOS_ALTERNATIVOS = [(7, 8), (8, 9), (9, 10)]

BOTON_L3 = 8
BOTON_R3 = 9


class GestorGamepad:
    """
    Gestiona la deteccion de mando y el combo L3+R3 push-to-talk.
    Corre en su propio hilo, aislado del hilo de teclado.
    """

    def __init__(self, callback_activar_voz, callback_pausa_activa=None):
        self._callback_activar_voz = callback_activar_voz
        self._callback_pausa_activa = callback_pausa_activa
        self._stop_event = threading.Event()
        self._hilo = None
        self._joystick = None
        self._combo_l3 = BOTON_L3
        self._combo_r3 = BOTON_R3
        self._combo_presionado = False
        self._disponible = False
        self._indice_preferido = 0  # Se sobreescribe con iniciar_con_indice()

    # ------------------------------------------------------------------
    # API publica
    # ------------------------------------------------------------------

    @staticmethod
    def listar_mandos_disponibles() -> list:
        """
        Escanea y retorna los mandos conectados.
        NUNCA lanza excepción — siempre retorna lista (vacía si no hay mandos
        o si pygame falla). El llamador debe manejar la lista vacía.
        """
        try:
            if not pygame.get_init():
                pygame.init()
        except Exception as e:
            logger.error(f"[GAMEPAD] No se pudo inicializar pygame: {e}")
            return []

        try:
            pygame.joystick.init()
        except Exception as e:
            logger.error(f"[GAMEPAD] No se pudo inicializar joystick: {e}")
            return []

        mandos = []
        try:
            cantidad = pygame.joystick.get_count()
            for i in range(cantidad):
                try:
                    joy = pygame.joystick.Joystick(i)
                    joy.init()
                    mandos.append({"indice": i, "nombre": joy.get_name()})
                    joy.quit()
                except Exception as e:
                    logger.warning(f"[GAMEPAD] Error leyendo mando {i}: {e}")
        except Exception as e:
            logger.error(f"[GAMEPAD] Error listando mandos: {e}")

        logger.info(f"[GAMEPAD] Mandos encontrados: {[m['nombre'] for m in mandos]}")
        return mandos

    def iniciar_con_indice(self, indice: int):
        """
        Inicia el hilo usando el mando del indice elegido por el usuario.
        Detiene cualquier hilo anterior antes de arrancar uno nuevo.
        """
        logger.info(f"[GAMEPAD] Iniciando con indice preferido: {indice}")
        self._indice_preferido = indice
        # Resetear estado por si habia un hilo anterior
        self._stop_event.clear()
        self._disponible = False
        self._joystick = None
        self.iniciar()

    def iniciar(self):
        """Arranca el hilo de escucha. Seguro de llamar sin mando conectado."""
        if not _PYGAME_DISPONIBLE:
            logger.warning("[GAMEPAD] pygame no disponible.")
            return
        if self._hilo and self._hilo.is_alive():
            logger.debug("[GAMEPAD] Hilo ya corriendo, ignorando iniciar().")
            return
        self._stop_event.clear()
        self._hilo = threading.Thread(target=self._loop_escucha, daemon=True)
        self._hilo.start()
        logger.info(f"[GAMEPAD] Hilo iniciado (indice preferido: {self._indice_preferido})")

    def detener(self):
        """Detiene el hilo de escucha de forma limpia."""
        self._stop_event.set()
        if self._hilo:
            self._hilo.join(timeout=2.0)
        self._disponible = False
        self._joystick = None
        logger.info("[GAMEPAD] Hilo detenido.")

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _inicializar_pygame_joystick(self):
        try:
            if not pygame.get_init():
                pygame.init()
            pygame.joystick.init()
            return True
        except Exception as e:
            logger.error(f"[GAMEPAD] Error inicializando pygame: {e}")
            return False

    def _conectar_mando(self):
        """
        Conecta el mando segun _indice_preferido.
        CRITICO: no reinicializa pygame.joystick aqui para evitar que los
        indices se reordenen despues de que el usuario eligio uno especifico.
        """
        try:
            cantidad = pygame.joystick.get_count()
            logger.info(f"[GAMEPAD] Mandos disponibles: {cantidad}, indice preferido: {self._indice_preferido}")
            if cantidad == 0:
                return False

            # Usar el indice elegido; si ya no existe usar el primero
            indice = self._indice_preferido if self._indice_preferido < cantidad else 0

            self._joystick = pygame.joystick.Joystick(indice)
            self._joystick.init()
            nombre = self._joystick.get_name()
            logger.info(f"[GAMEPAD] Conectado indice {indice}: '{nombre}'")
            self._detectar_mapeo_l3_r3()
            self._disponible = True
            return True
        except Exception as e:
            logger.error(f"[GAMEPAD] Error conectando mando: {e}")
            self._disponible = False
            return False

    def _detectar_mapeo_l3_r3(self):
        """Elige el mapeo L3/R3 segun el nombre del mando."""
        if not self._joystick:
            return
        nombre = self._joystick.get_name().lower()
        total_botones = self._joystick.get_numbuttons()

        for clave, mapeo in MAPEO_POR_TIPO.items():
            if clave in nombre:
                l3, r3 = mapeo
                if l3 < total_botones and r3 < total_botones:
                    self._combo_l3 = l3
                    self._combo_r3 = r3
                    logger.info(f"[GAMEPAD] Mapeo por nombre '{clave}': L3={l3}, R3={r3}")
                    return
                else:
                    logger.warning(f"[GAMEPAD] Mapeo ({l3},{r3}) supera {total_botones} botones.")

        # Fallback por alternativas
        for l3, r3 in MAPEOS_ALTERNATIVOS:
            if l3 < total_botones and r3 < total_botones:
                self._combo_l3 = l3
                self._combo_r3 = r3
                logger.warning(f"[GAMEPAD] Mapeo alternativo: L3={l3}, R3={r3}")
                return

        self._combo_l3, self._combo_r3 = MAPEO_DEFECTO
        logger.error(f"[GAMEPAD] Usando mapeo default para '{nombre}'")

    def _loop_escucha(self):
        """Loop principal en hilo propio."""
        if not self._inicializar_pygame_joystick():
            return

        # Conectar inmediatamente al indice elegido, sin esperar
        if not self._conectar_mando():
            logger.warning("[GAMEPAD] No se pudo conectar al inicio, reintentando cada 3s...")

        while not self._stop_event.is_set():
            try:
                if not self._disponible or not self._joystick:
                    if not self._conectar_mando():
                        time.sleep(3.0)
                        continue

                pygame.event.pump()

                total_botones = self._joystick.get_numbuttons()
                if self._combo_l3 >= total_botones or self._combo_r3 >= total_botones:
                    logger.warning(f"[GAMEPAD] Indice de boton invalido, reconectando...")
                    self._disponible = False
                    self._joystick = None
                    time.sleep(1.0)
                    continue

                l3 = self._joystick.get_button(self._combo_l3)
                r3 = self._joystick.get_button(self._combo_r3)
                combo_activo = bool(l3 and r3)

                if combo_activo and not self._combo_presionado:
                    self._combo_presionado = True
                    logger.debug(f"[GAMEPAD] Combo L3+R3 detectado, iniciando captura...")
                    if self._callback_activar_voz:
                        threading.Thread(
                            target=self._callback_activar_voz,
                            args=(self._combo_sigue_presionado,),
                            daemon=True
                        ).start()
                elif not combo_activo:
                    self._combo_presionado = False

                time.sleep(0.03)

            except pygame.error as e:
                logger.warning(f"[GAMEPAD] Error pygame: {e}")
                self._disponible = False
                self._joystick = None
                time.sleep(1.0)
            except Exception as e:
                logger.exception("[GAMEPAD] Error inesperado en loop")
                time.sleep(1.0)

    def _combo_sigue_presionado(self) -> bool:
        """Condicion de corte para capturar_voz_micro: True mientras L3+R3 sigan presionados."""
        try:
            if not self._joystick:
                return False
            pygame.event.pump()
            l3 = self._joystick.get_button(self._combo_l3)
            r3 = self._joystick.get_button(self._combo_r3)
            return bool(l3 and r3)
        except Exception:
            return False