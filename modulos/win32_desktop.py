"""
Módulo de Integración Win32 para Modo Escritorio (Wallpaper Integration) en Argus.

Proporciona llamadas a Win32 API vía ctypes para:
- Desovar y ubicar la ventana WorkerW del escritorio (estándar Rainmeter / Wallpaper Engine).
- Realizar Reparenting (SetParent) para incrustar ventanas de Argus en el fondo del escritorio.
- Gestionar estilos de ventana (WS_EX_TOOLWINDOW) para ocultar de la barra de tareas y Alt+Tab.
- Detectar monitores, resoluciones y manejar DPI Awareness.
"""

import ctypes
import ctypes.wintypes as wintypes
from ctypes import byref, c_int, c_void_p, WINFUNCTYPE, Structure
from modulos.logger import logger

# ─── CONSTANTES WIN32 ─────────────────────────────────────────────────────────

GWL_STYLE    = -16
GWL_EXSTYLE  = -20

WS_CHILD        = 0x40000000
WS_POPUP        = 0x80000000
WS_VISIBLE      = 0x10000000
WS_CAPTION      = 0x00C00000
WS_THICKFRAME   = 0x00040000
WS_MINIMIZEBOX  = 0x00020000
WS_MAXIMIZEBOX  = 0x00010000
WS_SYSMENU      = 0x00080000

WS_EX_TOOLWINDOW  = 0x00000080
WS_EX_APPWINDOW   = 0x00040000
WS_EX_LAYERED     = 0x00080000

SWP_NOSIZE      = 0x0001
SWP_NOMOVE      = 0x0002
SWP_NOZORDER    = 0x0004
SWP_NOACTIVATE  = 0x0010
SWP_FRAMECHANGED = 0x0020
SWP_SHOWWINDOW  = 0x0040

SMTO_NORMAL = 0x0000

SM_XVIRTUALSCREEN  = 76
SM_YVIRTUALSCREEN  = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79
SM_CMONITORS       = 80

# ─── CARGA DE DLLS Y PROTOTIPOS 64-BIT EXPLÍCITOS ────────────────────────────

user32 = ctypes.windll.user32
shcore = getattr(ctypes.windll, 'shcore', None)

def _setup_prototypes():
    """Configura prototipos Win32 de 64-bit para evitar truncamiento en Python x64."""
    user32.FindWindowW.argtypes    = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.FindWindowW.restype     = wintypes.HWND

    user32.FindWindowExW.argtypes  = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.FindWindowExW.restype   = wintypes.HWND

    user32.GetShellWindow.argtypes = []
    user32.GetShellWindow.restype  = wintypes.HWND

    user32.GetDesktopWindow.argtypes = []
    user32.GetDesktopWindow.restype  = wintypes.HWND

    user32.GetAncestor.argtypes    = [wintypes.HWND, wintypes.UINT]
    user32.GetAncestor.restype     = wintypes.HWND

    user32.GetParent.argtypes      = [wintypes.HWND]
    user32.GetParent.restype       = wintypes.HWND

    user32.SetParent.argtypes      = [wintypes.HWND, wintypes.HWND]
    user32.SetParent.restype       = wintypes.HWND

    user32.SetWindowPos.argtypes   = [
        wintypes.HWND, wintypes.HWND,
        c_int, c_int, c_int, c_int,
        wintypes.UINT
    ]
    user32.SetWindowPos.restype    = wintypes.BOOL

    user32.SendMessageTimeoutW.argtypes = [
        wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
        wintypes.UINT, wintypes.UINT, ctypes.POINTER(c_void_p)
    ]
    user32.SendMessageTimeoutW.restype = c_void_p

    user32.GetClassNameW.argtypes  = [wintypes.HWND, wintypes.LPWSTR, c_int]
    user32.GetClassNameW.restype   = c_int

    global WNDENUMPROC
    WNDENUMPROC = WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes    = [WNDENUMPROC, wintypes.LPARAM]
    user32.EnumWindows.restype     = wintypes.BOOL

_setup_prototypes()

# GetWindowLongPtr / SetWindowLongPtr (64-bit aware)
_GetWLPtr = getattr(user32, 'GetWindowLongPtrW', user32.GetWindowLongW)
_SetWLPtr = getattr(user32, 'SetWindowLongPtrW', user32.SetWindowLongW)
_GetWLPtr.argtypes = [wintypes.HWND, c_int]
_GetWLPtr.restype  = c_void_p
_SetWLPtr.argtypes = [wintypes.HWND, c_int, c_void_p]
_SetWLPtr.restype  = c_void_p

def get_style(hwnd: int) -> int:
    return int(_GetWLPtr(hwnd, GWL_STYLE) or 0)

def set_style(hwnd: int, style: int):
    _SetWLPtr(hwnd, GWL_STYLE, c_void_p(style))

def get_ex_style(hwnd: int) -> int:
    return int(_GetWLPtr(hwnd, GWL_EXSTYLE) or 0)

def set_ex_style(hwnd: int, style: int):
    _SetWLPtr(hwnd, GWL_EXSTYLE, c_void_p(style))

# Structs de monitor
class RECT(Structure):
    _fields_ = [("left", c_int), ("top", c_int), ("right", c_int), ("bottom", c_int)]

class MONITORINFOEX(Structure):
    _fields_ = [
        ("cbSize",    wintypes.DWORD),
        ("rcMonitor", RECT),
        ("rcWork",    RECT),
        ("dwFlags",   wintypes.DWORD),
        ("szDevice",  wintypes.WCHAR * 32)
    ]

# ─── DPI Y HWND ───────────────────────────────────────────────────────────────

def habilitar_dpi_awareness():
    """Habilita DPI awareness Per-Monitor V2."""
    try:
        if shcore:
            shcore.SetProcessDpiAwareness(2)
        else:
            user32.SetProcessDPIAware()
    except Exception as e:
        logger.warning(f"DPI awareness: {e}")

def obtener_hwnd_top_level(app) -> int:
    """
    Retorna el HWND Win32 real del TkTopLevel (GA_ROOT).
    winfo_id() devuelve el canvas interno, NO el marco Win32 de nivel superior.
    """
    try:
        app.update_idletasks()
        inner = app.winfo_id()
        root  = user32.GetAncestor(inner, 2)  # GA_ROOT = 2
        if root:
            return root
        parent = user32.GetParent(inner)
        return parent if parent else inner
    except Exception as e:
        logger.error(f"Error obteniendo HWND: {e}")
        return app.winfo_id()

# ─── BÚSQUEDA DE WORKERW ──────────────────────────────────────────────────────

def obtener_workerw_escritorio() -> int:
    """
    Localiza la ventana WorkerW del fondo del escritorio.
    Envía 0x052C a Progman para desovar el WorkerW (técnica usada por Wallpaper Engine / Rainmeter).
    Retorna HWND de WorkerW, o Progman como fallback.
    """
    progman = user32.FindWindowW("Progman", None) or user32.GetShellWindow()
    logger.info(f"Progman HWND: {progman}")

    if progman:
        res = c_void_p(0)
        user32.SendMessageTimeoutW(progman, 0x052C, 0, 0, SMTO_NORMAL, 2000, byref(res))

    # Enumerar ventanas top-level buscando WorkerW que contenga SHELLDLL_DefView
    workerw_found = [0]
    ventanas_vistas = [0]

    def enum_cb(hwnd, lparam):
        ventanas_vistas[0] += 1
        shelldll = user32.FindWindowExW(hwnd, None, "SHELLDLL_DefView", None)
        if shelldll:
            ww = user32.FindWindowExW(0, hwnd, "WorkerW", None)
            workerw_found[0] = ww if ww else hwnd
            logger.info(f"WorkerW localizado: {workerw_found[0]} (SHELLDLL parent: {hwnd})")
        return True

    cb = WNDENUMPROC(enum_cb)
    user32.EnumWindows(cb, 0)
    logger.info(f"EnumWindows: {ventanas_vistas[0]} ventanas inspeccionadas, WorkerW={workerw_found[0]}")

    if workerw_found[0]:
        return workerw_found[0]
    if progman:
        logger.warning(f"Usando Progman ({progman}) como WorkerW fallback.")
        return progman

    desktop = user32.GetDesktopWindow()
    logger.warning(f"Usando GetDesktopWindow ({desktop}) como WorkerW LAST RESORT.")
    return desktop

# ─── ANCLAJE / DESANCLAJE ────────────────────────────────────────────────────

def anclar_a_escritorio(hwnd: int) -> bool:
    """
    Incrusta hwnd en WorkerW. Convierte WS_POPUP -> WS_CHILD, quita barra de título.
    Retorna True si SetParent devolvió un padre válido.
    """
    try:
        workerw = obtener_workerw_escritorio()
        if not workerw:
            logger.error("No se encontró WorkerW.")
            return False

        logger.info(f"Anclando HWND={hwnd} en WorkerW={workerw}")

        # 1. SetParent
        prev = user32.SetParent(hwnd, workerw)
        logger.info(f"SetParent anterior={prev}")

        # 2. WS_POPUP -> WS_CHILD (obligatorio para DWM)
        old_style = get_style(hwnd)
        new_style  = (old_style | WS_CHILD) & ~(WS_POPUP | WS_CAPTION | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU)
        set_style(hwnd, new_style)
        logger.info(f"GWL_STYLE: {hex(old_style)} -> {hex(new_style)}")

        # 3. Ex-style: quitar APPWINDOW, agregar TOOLWINDOW
        old_ex = get_ex_style(hwnd)
        new_ex = (old_ex | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
        set_ex_style(hwnd, new_ex)

        # 4. Aplicar posición/tamaño y forzar repaint de marco Win32
        if w > 0 and h > 0:
            # Posición y tamaño explícitos (las coords son relativas al WorkerW/Progman padre)
            flags = SWP_NOZORDER | SWP_FRAMECHANGED | SWP_SHOWWINDOW
            user32.SetWindowPos(hwnd, 0, x, y, w, h, flags)
            logger.info(f"SetWindowPos: pos=({x},{y}) size=({w}x{h})")
        else:
            # Solo actualizar el marco sin mover/redimensionar
            user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0,
                                SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED | SWP_SHOWWINDOW)

        # Verificar
        actual = user32.GetParent(hwnd)
        logger.info(f"Verificacion parent={actual} == workerw={workerw} -> {actual == workerw}")
        return actual == workerw or prev is not None
    except Exception as e:
        logger.exception(f"Error en anclar_a_escritorio: {e}")
        return False

def desanclar_de_escritorio(hwnd: int) -> bool:
    """Desincrustar hwnd del WorkerW y restaurar estilos de ventana normal."""
    try:
        user32.SetParent(hwnd, 0)

        old_style = get_style(hwnd)
        new_style  = (old_style & ~WS_CHILD) | WS_POPUP | WS_CAPTION | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU
        set_style(hwnd, new_style)

        old_ex = get_ex_style(hwnd)
        new_ex = (old_ex & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
        set_ex_style(hwnd, new_ex)

        user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED | SWP_SHOWWINDOW)
        logger.info(f"HWND {hwnd} desanclado del escritorio.")
        return True
    except Exception as e:
        logger.exception(f"Error en desanclar_de_escritorio: {e}")
        return False

# ─── MONITORES Y MÉTRICAS ─────────────────────────────────────────────────────

def obtener_monitores_disponibles() -> list:
    """Enumera todos los monitores conectados."""
    monitores = []

    def enum_monitor_cb(hmon, hdc, lprect, lparam):
        mi = MONITORINFOEX()
        mi.cbSize = ctypes.sizeof(MONITORINFOEX)
        if user32.GetMonitorInfoW(hmon, byref(mi)):
            r = mi.rcMonitor
            monitores.append({
                "index":      len(monitores),
                "hmonitor":   int(hmon),
                "device":     mi.szDevice,
                "x":          r.left,
                "y":          r.top,
                "width":      r.right - r.left,
                "height":     r.bottom - r.top,
                "is_primary": bool(mi.dwFlags & 1)
            })
        return True

    MONITORENUMPROC = WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
                                   ctypes.POINTER(RECT), wintypes.LPARAM)
    user32.EnumDisplayMonitors(0, 0, MONITORENUMPROC(enum_monitor_cb), 0)
    return monitores

def obtener_bounds_pantalla_virtual() -> dict:
    """Coordenadas y dimensiones de la pantalla virtual (todos los monitores)."""
    return {
        "x":      user32.GetSystemMetrics(SM_XVIRTUALSCREEN),
        "y":      user32.GetSystemMetrics(SM_YVIRTUALSCREEN),
        "width":  user32.GetSystemMetrics(SM_CXVIRTUALSCREEN),
        "height": user32.GetSystemMetrics(SM_CYVIRTUALSCREEN),
    }

def formatear_geometria(ancho: int, alto: int, x: int, y: int) -> str:
    """Genera string de geometría Tkinter tolerando coordenadas negativas (multi-monitor)."""
    sx = f"{x}" if x < 0 else f"+{x}"
    sy = f"{y}" if y < 0 else f"+{y}"
    return f"{ancho}x{alto}{sx}{sy}"
