"""
gamepad_control.py
===================
Lectura de gamepad (Xbox / DualSense) vía pygame.joystick.

DISEÑO CRÍTICO: este módulo NO usa la librería 'keyboard' ni ningún hook
global de Windows. pygame.joystick lee el estado del dispositivo via
XInput/DirectInput de forma directa, sin instalar hooks de bajo nivel
que puedan competir con el input thread de juegos como PoE2 (Unreal Engine).

Esto es justamente lo que evita el "Deadlock detected" que se daba con
el polling de teclado.is_pressed() compitiendo con el hook del juego.

Combo de activación: L3 + R3 mantenidos (push-to-talk, igual que F8).
Funciona indistintamente con mando Xbox One y DualSense (PS5), ya que
Windows expone ambos de forma unificada vía XInput.
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
# MAPEO DE BOTONES — detección automática por tipo de mando
# =====================================================================
# Confirmado en pruebas reales:
#   - DualSense (PS5):    L3=7, R3=8
#   - Xbox One:            L3=8, R3=9
# pygame no reporta el mismo índice para ambos porque cada uno usa un
# driver distinto en Windows (DualSense suele ir por DirectInput,
# Xbox por XInput nativo). Por eso identificamos el mando por su NOMBRE
# y elegimos el mapeo correcto automáticamente, sin prueba y error.

MAPEO_POR_TIPO = {
    "dualsense": (7, 8),
    "ps5":       (7, 8),
    "wireless controller": (7, 8),  # nombre genérico que reporta DualSense en algunos drivers
    "xbox":      (8, 9),
    "xinput":    (8, 9),
}

# Fallback si el nombre no matchea ninguno de los anteriores
MAPEO_DEFECTO = (8, 9)

# Se mantienen como alternativas por si en el futuro aparece un mando
# con nombre no reconocido y hay que probar a ciegas.
MAPEOS_ALTERNATIVOS = [
    (7, 8),
    (8, 9),
    (9, 10),
]

BOTON_L3 = 8   # Se sobreescribe dinámicamente en _detectar_mapeo_l3_r3()
BOTON_R3 = 9   # Se sobreescribe dinámicamente en _detectar_mapeo_l3_r3()


class GestorGamepad:
    """
    Gestiona la detección de mando y el combo L3+R3 push-to-talk.
    Corre en su propio hilo, completamente aislado del hilo de teclado.
    """

    def __init__(self, callback_activar_voz, callback_pausa_activa=None):
        """
        callback_activar_voz: función a llamar cuando se suelta el combo
                               (igual que se llama al soltar F8).
        callback_pausa_activa: función que retorna True si el modo gaming
                                pausa también debe pausar el gamepad
                                (por defecto, el gamepad sigue activo
                                incluso en modo gaming, ya que es seguro).
        """
        self._callback_activar_voz = callback_activar_voz
        self._callback_pausa_activa = callback_pausa_activa
        self._stop_event = threading.Event()
        self._hilo = None
        self._joystick = None
        self._combo_l3 = BOTON_L3
        self._combo_r3 = BOTON_R3
        self._combo_presionado = False
        self._disponible = False

    def iniciar(self):
        """Arranca el hilo de escucha del gamepad. Seguro de llamar aunque no haya mando conectado."""
        if not _PYGAME_DISPONIBLE:
            logger.warning("[GAMEPAD] pygame no disponible, control por mando deshabilitado.")
            return

        if self._hilo and self._hilo.is_alive():
            return

        self._stop_event.clear()
        self._hilo = threading.Thread(target=self._loop_escucha, daemon=True)
        self._hilo.start()

    def detener(self):
        """Detiene el hilo de escucha de forma limpia."""
        self._stop_event.set()
        if self._hilo:
            self._hilo.join(timeout=1.0)

    def _inicializar_pygame_joystick(self):
        """Inicializa el subsistema de joystick de pygame de forma aislada."""
        try:
            if not pygame.get_init():
                pygame.init()
            pygame.joystick.init()
            return True
        except Exception as e:
            logger.error(f"[GAMEPAD] Error inicializando pygame.joystick: {e}")
            return False

    def _conectar_mando(self):
        """Intenta conectar el primer mando disponible. Retorna True si lo logra."""
        try:
            pygame.joystick.quit()
            pygame.joystick.init()
            cantidad = pygame.joystick.get_count()
            if cantidad == 0:
                return False

            self._joystick = pygame.joystick.Joystick(0)
            self._joystick.init()
            nombre = self._joystick.get_name()
            logger.info(f"[GAMEPAD] Mando detectado: {nombre}")
            self._detectar_mapeo_l3_r3()
            self._disponible = True
            return True
        except Exception as e:
            logger.error(f"[GAMEPAD] Error conectando mando: {e}")
            self._disponible = False
            return False

    def _detectar_mapeo_l3_r3(self):
        """
        Identifica el mapeo correcto de L3/R3 según el TIPO de mando,
        no a ciegas. Esto resuelve el problema de que DualSense reporta
        L3/R3 en índices distintos a Xbox One en el mismo sistema.
        """
        if not self._joystick:
            return

        nombre = self._joystick.get_name().lower()
        total_botones = self._joystick.get_numbuttons()

        # 1. Intentar matchear por nombre del dispositivo (método preferido)
        mapeo_encontrado = None
        for clave, mapeo in MAPEO_POR_TIPO.items():
            if clave in nombre:
                mapeo_encontrado = mapeo
                logger.info(f"[GAMEPAD] Tipo detectado por nombre ('{clave}' en '{nombre}') → mapeo {mapeo}")
                break

        if mapeo_encontrado:
            l3, r3 = mapeo_encontrado
            if l3 < total_botones and r3 < total_botones:
                self._combo_l3 = l3
                self._combo_r3 = r3
                logger.info(f"[GAMEPAD] Mapeo L3/R3 confirmado por tipo de mando: ({l3}, {r3})")
                return
            else:
                logger.warning(
                    f"[GAMEPAD] Mapeo esperado ({l3},{r3}) excede los {total_botones} "
                    f"botones reportados. Probando alternativas."
                )

        # 2. Fallback: el nombre no matcheó nada conocido, probar alternativas
        logger.warning(f"[GAMEPAD] Mando no reconocido por nombre ('{nombre}'). Probando mapeos alternativos.")
        for l3, r3 in MAPEOS_ALTERNATIVOS:
            if l3 < total_botones and r3 < total_botones:
                self._combo_l3 = l3
                self._combo_r3 = r3
                logger.warning(f"[GAMEPAD] Mapeo alternativo asignado: ({l3}, {r3}) de {total_botones} botones")
                return

        # 3. Último recurso: mapeo por defecto sin garantías
        self._combo_l3, self._combo_r3 = MAPEO_DEFECTO
        logger.error(
            f"[GAMEPAD] No se pudo determinar mapeo confiable para '{nombre}'. "
            f"Usando default {MAPEO_DEFECTO} — puede no funcionar correctamente."
        )

    def _loop_escucha(self):
        """
        Loop principal — corre en hilo propio, separado del de teclado.
        Reintenta conexión de mando periódicamente si no hay ninguno.
        """
        if not self._inicializar_pygame_joystick():
            return

        intentos_reconexion = 0

        while not self._stop_event.is_set():
            try:
                if not self._disponible or not self._joystick:
                    if not self._conectar_mando():
                        intentos_reconexion += 1
                        time.sleep(3.0)
                        continue

                pygame.event.pump()

                total_botones = self._joystick.get_numbuttons()
                if self._combo_l3 >= total_botones or self._combo_r3 >= total_botones:
                    self._disponible = False
                    self._joystick = None
                    time.sleep(1.0)
                    continue

                l3_estado = self._joystick.get_button(self._combo_l3)
                r3_estado = self._joystick.get_button(self._combo_r3)
                combo_activo = bool(l3_estado and r3_estado)

                # ── CORREGIDO: disparar AL PRESIONAR, no al soltar ──────────
                # Antes esperaba a que se soltara el combo para recién ahí
                # llamar a capturar_voz_micro(), lo cual era demasiado tarde:
                # la grabación arrancaba cuando ya no había nada que grabar.
                # Ahora se dispara la captura EN PARALELO al presionar, y la
                # condición de corte (_combo_sigue_presionado) se consulta
                # en tiempo real mientras se graba, deteniéndose al soltar.
                if combo_activo and not self._combo_presionado:
                    self._combo_presionado = True
                    if self._callback_activar_voz:
                        # Se dispara en un hilo nuevo para no bloquear este
                        # loop de lectura del gamepad mientras se graba.
                        threading.Thread(
                            target=self._callback_activar_voz,
                            args=(self._combo_sigue_presionado,),
                            daemon=True
                        ).start()
                elif not combo_activo:
                    self._combo_presionado = False

                time.sleep(0.03)  # ~33hz para detectar la suelta con precisión

            except pygame.error as e:
                logger.warning(f"[GAMEPAD] Mando desconectado: {e}")
                self._disponible = False
                self._joystick = None
                time.sleep(1.0)
            except Exception as e:
                logger.exception(f"[GAMEPAD] Error inesperado en loop de escucha")
                time.sleep(1.0)

    def _combo_sigue_presionado(self) -> bool:
        """
        Condición de corte que consulta capturar_voz_micro() en tiempo real
        para saber si debe seguir grabando. Retorna True mientras L3+R3
        sigan ambos presionados.
        """
        try:
            if not self._joystick:
                return False
            pygame.event.pump()
            l3 = self._joystick.get_button(self._combo_l3)
            r3 = self._joystick.get_button(self._combo_r3)
            return bool(l3 and r3)
        except Exception:
            # Si el mando se desconecta a mitad de grabación, cortar grabación
            return False