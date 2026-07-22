"""
xinput_reader.py
================
Lector nativo de XInput (API oficial de Microsoft para Xbox controllers)
vía ctypes. Lee el estado del mando directamente del driver, sin importar
si un juego lo tiene capturado en primer plano.
"""

import ctypes
import ctypes.wintypes
import time
from enum import IntFlag

# Constantes XInput
XINPUT_BATTERY_DEVTYPE_GAMEPAD = 0x00
XINPUT_BATTERY_DEVTYPE_HEADSET = 0x01
XINPUT_BATTERY_TYPE_DISCONNECTED = 0xFF

# Botones XInput
class XInputButtons(IntFlag):
    DPAD_UP = 0x0001
    DPAD_DOWN = 0x0002
    DPAD_LEFT = 0x0004
    DPAD_RIGHT = 0x0008
    START = 0x0010
    BACK = 0x0020
    LEFT_THUMB = 0x0040  # L3
    RIGHT_THUMB = 0x0080  # R3
    LEFT_SHOULDER = 0x0100
    RIGHT_SHOULDER = 0x0200
    A = 0x1000
    B = 0x2000
    X = 0x4000
    Y = 0x8000


class XINPUT_STATE(ctypes.Structure):
    _fields_ = [
        ("dwPacketNumber", ctypes.wintypes.DWORD),
        ("wButtons", ctypes.wintypes.WORD),
        ("bLeftTrigger", ctypes.c_byte),
        ("bRightTrigger", ctypes.c_byte),
        ("sThumbLX", ctypes.c_short),
        ("sThumbLY", ctypes.c_short),
        ("sThumbRX", ctypes.c_short),
        ("sThumbRY", ctypes.c_short)
    ]


class XINPUT_VIBRATION(ctypes.Structure):
    _fields_ = [
        ("wLeftMotorSpeed", ctypes.wintypes.WORD),
        ("wRightMotorSpeed", ctypes.wintypes.WORD)
    ]


# Cargar XInput (versión 1.4 o 9.1.0)
_xinput_dll = None
for _dll_name in ["xinput1_4.dll", "xinput9_1_0.dll", "xinput1_3.dll"]:
    try:
        _xinput_dll = ctypes.windll.LoadLibrary(_dll_name)
        break
    except Exception:
        continue

# Funciones tipadas
if _xinput_dll:
    _XInputGetState = _xinput_dll.XInputGetState
    _XInputGetState.argtypes = [ctypes.wintypes.DWORD, ctypes.POINTER(XINPUT_STATE)]
    _XInputGetState.restype = ctypes.wintypes.DWORD

    _XInputSetState = _xinput_dll.XInputSetState
    _XInputSetState.argtypes = [ctypes.wintypes.DWORD, ctypes.POINTER(XINPUT_VIBRATION)]
    _XInputSetState.restype = ctypes.wintypes.DWORD
else:
    _XInputGetState = None
    _XInputSetState = None

# Códigos de error XInput
ERROR_SUCCESS = 0
ERROR_DEVICE_NOT_CONNECTED = 1167


class MandoXInput:
    """Representa un mando Xbox leído vía XInput."""
    def __init__(self, indice: int):
        self.indice = indice
        self._state = XINPUT_STATE()
        self._conectado = False
        self._ultimo_packet = 0
        self.nombre = f"Xbox Controller ({indice})"

    @property
    def conectado(self) -> bool:
        return self._conectado

    def actualizar(self) -> bool:
        """
        Actualiza el estado del mando. Retorna True si hay datos nuevos.
        """
        if not _XInputGetState:
            return False
        try:
            res = _XInputGetState(self.indice, ctypes.byref(self._state))
            if res == ERROR_SUCCESS:
                if not self._conectado:
                    self._conectado = True
                    self._ultimo_packet = self._state.dwPacketNumber
                    return True  # recién conectado
                if self._state.dwPacketNumber != self._ultimo_packet:
                    self._ultimo_packet = self._state.dwPacketNumber
                    return True  # nuevo estado
                return True  # conectado pero sin cambios
            elif res == ERROR_DEVICE_NOT_CONNECTED:
                if self._conectado:
                    self._conectado = False
                    return True  # se desconectó
                return False
            return False
        except Exception:
            if self._conectado:
                self._conectado = False
                return True
            return False

    def get_button(self, boton: int) -> bool:
        """
        Verifica si un botón está presionado.
        Usar las constantes XInputButtons: LEFT_THUMB, RIGHT_THUMB, etc.
        """
        return bool(self._state.wButtons & boton)

    def esta_presionado_l3_r3(self) -> bool:
        """Verifica si L3 y R3 están presionados simultáneamente."""
        l3 = bool(self._state.wButtons & XInputButtons.LEFT_THUMB)
        r3 = bool(self._state.wButtons & XInputButtons.RIGHT_THUMB)
        return l3 and r3


def escanear_mandos_xinput() -> list:
    """
    Escanea los 4 posibles puertos XInput (0-3) y retorna
    una lista de MandoXInput conectados.
    """
    mandos = []
    for i in range(4):
        m = MandoXInput(i)
        m.actualizar()
        if m.conectado:
            mandos.append(m)
    return mandos