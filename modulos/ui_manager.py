"""
Gestor de Modos de Interfaz y Hosts para Argus.

Implementa la arquitectura orientada a objetos (Strategy Pattern) para gestionar
los diferentes modos de visualización de la GUI:
- Ventana Tradicional (TraditionalWindowHost)
- Widget Flotante (FloatingWidgetHost)
- Modo Escritorio / Wallpaper (DesktopModeHost)
"""

from abc import ABC, abstractmethod
from modulos.logger import logger
from modulos.win32_desktop import (
    anclar_a_escritorio,
    desanclar_de_escritorio,
    obtener_monitores_disponibles,
    obtener_bounds_pantalla_virtual,
    habilitar_dpi_awareness,
    obtener_hwnd_top_level,
    formatear_geometria,
)

# ─── INTERFAZ ABSTRACTA DE HOST ──────────────────────────────────────────────

class IWindowHost(ABC):
    @abstractmethod
    def apply_mode(self, app, config_opts: dict = None) -> bool: ...
    @abstractmethod
    def remove_mode(self, app) -> bool: ...

# ─── HOST TRADICIONAL ─────────────────────────────────────────────────────────

class TraditionalWindowHost(IWindowHost):
    def apply_mode(self, app, config_opts: dict = None) -> bool:
        try:
            app.withdraw()
            app.overrideredirect(False)
            app.attributes("-topmost", False)
            app.deiconify()
            app.update()
            hwnd = obtener_hwnd_top_level(app)
            desanclar_de_escritorio(hwnd)
            logger.info("Modo Tradicional aplicado.")
            return True
        except Exception as e:
            logger.exception(f"Error Modo Tradicional: {e}")
            return False

    def remove_mode(self, app) -> bool:
        return True

# ─── HOST WIDGET FLOTANTE ─────────────────────────────────────────────────────

class FloatingWidgetHost(IWindowHost):
    def apply_mode(self, app, config_opts: dict = None) -> bool:
        try:
            topmost = (config_opts or {}).get("topmost", True)
            app.withdraw()
            app.overrideredirect(True)
            app.attributes("-topmost", topmost)
            app.deiconify()
            app.update()
            hwnd = obtener_hwnd_top_level(app)
            desanclar_de_escritorio(hwnd)
            logger.info(f"Modo Widget Flotante aplicado (topmost={topmost}).")
            return True
        except Exception as e:
            logger.exception(f"Error Modo Widget Flotante: {e}")
            return False

    def remove_mode(self, app) -> bool:
        try:
            app.withdraw()
            app.overrideredirect(False)
            app.attributes("-topmost", False)
            app.deiconify()
            return True
        except Exception:
            return False

# ─── HOST MODO ESCRITORIO (WALLPAPER INTEGRATION) ─────────────────────────────

class DesktopModeHost(IWindowHost):
    """
    Incrusta Argus nativamente en la capa WorkerW del escritorio de Windows.
    La ventana queda detrás de todas las apps, visible con Win+D.

    Secuencia crítica de embedding:
    1. withdraw -> overrideredirect(True) -> deiconify -> update  (re-crea HWND sin borde DWM)
    2. Calcular bounds de pantalla virtual
    3. app.after(50ms) -> realizar embedding Win32 (SetParent + GWL_STYLE)
    4. SetWindowPos con coordenadas exactas en sistema de coordenadas del WorkerW padre
    """

    def apply_mode(self, app, config_opts: dict = None) -> bool:
        try:
            habilitar_dpi_awareness()
            opts = config_opts or {}

            # ── Calcular bounds antes de modificar la ventana ────────────────
            full_span = opts.get("full_span", True)

            if full_span:
                b = obtener_bounds_pantalla_virtual()
                vx, vy, vw, vh = b["x"], b["y"], b["width"], b["height"]
            else:
                monitores = obtener_monitores_disponibles()
                idx = opts.get("monitor_target", 0)
                m = monitores[idx] if monitores and idx < len(monitores) else None
                if m:
                    ancho = opts.get("width", 450)
                    vx = m["x"] + m["width"] - ancho
                    vy = m["y"]
                    vw = ancho
                    vh = m["height"]
                else:
                    b = obtener_bounds_pantalla_virtual()
                    ancho = 450
                    vx = b["x"] + b["width"] - ancho
                    vy = b["y"]
                    vw = ancho
                    vh = b["height"]

            logger.info(f"DesktopMode: bounds=({vx},{vy},{vw}x{vh}) full_span={full_span}")

            # ── Paso 1: quitar marco DWM con withdraw/deiconify ──────────────
            app.withdraw()
            app.overrideredirect(True)
            app.attributes("-topmost", False)
            app.deiconify()
            app.update()

            # ── Paso 2: diferir el embed Win32 50ms para que Tkinter termine ─
            # Usar app.after() garantiza que el HWND ya está estable antes del embed
            def _do_embed():
                try:
                    hwnd = obtener_hwnd_top_level(app)
                    logger.info(f"DesktopMode embed: HWND={hwnd}")

                    # Pasar coordenadas absolutas — WorkerW/Progman usan el mismo
                    # sistema de coordenadas de pantalla que Windows normalmente
                    exito = anclar_a_escritorio(hwnd, x=vx, y=vy, w=vw, h=vh)
                    if not exito:
                        logger.error("anclar_a_escritorio falló.")
                        return

                    # Aplicar geometría Tkinter también (por si Tkinter la resetea)
                    geom = formatear_geometria(vw, vh, vx, vy)
                    app.geometry(geom)
                    app.update()
                    logger.info(f"DesktopMode activo. geom={geom}")
                except Exception as e:
                    logger.exception(f"Error en _do_embed: {e}")

            app.after(50, _do_embed)
            return True

        except Exception as e:
            logger.exception(f"Error DesktopModeHost.apply_mode: {e}")
            return False

    def remove_mode(self, app) -> bool:
        try:
            hwnd = obtener_hwnd_top_level(app)
            desanclar_de_escritorio(hwnd)
            app.withdraw()
            app.overrideredirect(False)
            app.deiconify()
            app.update()
            return True
        except Exception as e:
            logger.exception(f"Error DesktopModeHost.remove_mode: {e}")
            return False

# ─── GESTOR PRINCIPAL ────────────────────────────────────────────────────────

class UIManager:
    def __init__(self):
        self._hosts = {
            "traditional": TraditionalWindowHost(),
            "floating":    FloatingWidgetHost(),
            "desktop":     DesktopModeHost(),
        }
        self.modo_actual = "traditional"

    def cambiar_modo(self, app, nuevo_modo: str, config_opts: dict = None) -> bool:
        if nuevo_modo not in self._hosts:
            logger.error(f"Modo desconocido: {nuevo_modo}")
            return False

        # Remover modo actual
        if self.modo_actual in self._hosts:
            self._hosts[self.modo_actual].remove_mode(app)

        exito = self._hosts[nuevo_modo].apply_mode(app, config_opts or {})
        if exito:
            self.modo_actual = nuevo_modo
            logger.info(f"Visualización -> {nuevo_modo.upper()}")
        return exito

# Singleton global
ui_manager = UIManager()
