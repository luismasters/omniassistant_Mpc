"""
Punto de Entrada Principal de Argus — Web HUD (PyWebView + Edge Chromium WebView2).

Inicia la interfaz web moderna con aceleración por GPU, rostros de EMO a 60 FPS,
temas neón dinámicos, escucha de micrófono por F8/L3+R3 y soporte completo para Modo Escritorio.
"""

import os
import sys

# Forzar UTF-8 en consola para Windows (evita UnicodeEncodeError con emojis)
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import threading
import json
import webview
from config import TECLA_HABLAR
from modulos.logger import logger
from modulos.web_bridge import ArgusWebBridge


def main():
    logger.info("==================================================")
    logger.info("🚀 Iniciando Argus Copilot — Web HUD (PyWebView)")
    logger.info("==================================================")

    # 1. Instanciar Puente de Comunicación (API Bridge)
    bridge = ArgusWebBridge()

    # 2. Ruta al HTML del Frontend
    html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "gui", "index.html"))
    if not os.path.exists(html_path):
        logger.error(f"No se encontró el archivo de interfaz: {html_path}")
        sys.exit(1)

    url_target = f"file:///{html_path.replace(chr(92), '/')}"
    logger.info(f"Cargando frontend web desde: {url_target}")

    # 3. Hotkey F8 (teclado)
    def _iniciar_teclado():
        try:
            import keyboard
            def _on_f8():
                try:
                    from config import estado
                    if getattr(estado, "gamer_mode_activo", False):
                        logger.debug("🎮 Modo Gamer activo: ignorando hotkey F8 del teclado.")
                        return

                    from modulos.audio_custom import esta_escuchando, esta_hablando, detener_voz
                    if esta_escuchando():
                        return
                    if esta_hablando():
                        detener_voz()
                    res = bridge.iniciar_escucha_voz()
                    win = bridge._window or (webview.windows[0] if webview.windows else None)
                    if res and res.get("exito") and win:
                        win.evaluate_js("if (window.iniciarEscuchaVozUI) window.iniciarEscuchaVozUI();")
                except Exception as e:
                    logger.exception(f"Error F8: {e}")
            keyboard.add_hotkey(TECLA_HABLAR, _on_f8)
            logger.info(f"🎤 Global hotkey '{TECLA_HABLAR}' registrado OK.")
        except Exception as e:
            logger.warning(f"Error global hotkey: {e}")

    _iniciar_teclado()

    # 4. Gamepad — L3+R3 push-to-talk (GestorGamepad via subproceso aislado gamepad_service.py)
    def _iniciar_gamepad():
        try:
            from modulos.gamepad_control import GestorGamepad
            from modulos.audio_custom import capturar_voz_micro

            def _callback_voz_gamepad(combo_sigue_presionado):
                try:
                    win = bridge._window or (webview.windows[0] if webview.windows else None)
                    if not win:
                        return
                    win.evaluate_js("if (window.iniciarEscuchaVozUI) window.iniciarEscuchaVozUI();")
                    texto = capturar_voz_micro(condicion_seguir_grabando=combo_sigue_presionado)
                    win.evaluate_js("if (window.detenerEscuchaVozUI) window.detenerEscuchaVozUI();")
                    if texto:
                        win.evaluate_js(
                            f"if (window.agregarMensajeUsuario) "
                            f"window.agregarMensajeUsuario({json.dumps(texto)});"
                        )
                        from modulos.ia import enviar_a_gemini
                        enviar_a_gemini(texto, modo_voz=True, ui_callback=bridge._ui_callback)
                except Exception as e:
                    logger.exception(f"[GAMEPAD] Error en callback de voz: {e}")

            def _callback_mandos_changed(mandos):
                try:
                    win = bridge._window or (webview.windows[0] if webview.windows else None)
                    if win:
                        win.evaluate_js("if (window.actualizarMandosGamepad) window.actualizarMandosGamepad();")
                except Exception as e:
                    logger.debug(f"[GAMEPAD] Error notificando cambio de mandos a la UI: {e}")

            gestor = GestorGamepad(
                callback_activar_voz=_callback_voz_gamepad,
                callback_mandos_changed=_callback_mandos_changed
            )
            gestor.iniciar()
            bridge.set_gestor_gamepad(gestor)
            logger.info("🎮 GestorGamepad iniciado (L3+R3 push-to-talk activo para DualSense y Xbox).")
        except Exception as e:
            logger.warning(f"[GAMEPAD] No se pudo iniciar el gamepad: {e}")

    threading.Thread(target=_iniciar_gamepad, daemon=True).start()

    # 5. Crear ventana PyWebView (Edge Chromium WebView2)
    window = webview.create_window(
        title="Argus — OmniAssistant HUD",
        url=url_target,
        js_api=bridge,
        width=1220,
        height=820,
        min_size=(900, 600),
        resizable=True,
    )

    # Conectar la ventana al bridge
    bridge.set_window(window)

    # 6. Iniciar bucle de eventos de PyWebView (bloquea hasta cerrar la ventana)
    try:
        webview.start()
    except Exception as e:
        logger.exception(f"Error al iniciar ventana PyWebView: {e}")
    finally:
        if bridge._gestor_gamepad:
            try:
                bridge._gestor_gamepad.detener()
            except Exception:
                pass


if __name__ == "__main__":
    main()
