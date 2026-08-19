"""
Punto de Entrada Principal de Argus — Web HUD (PyWebView + Edge Chromium WebView2).

Inicia la interfaz web moderna con aceleración por GPU, rostros de EMO a 60 FPS,
temas neón dinámicos, escucha de micrófono por F8/L3+R3 y soporte completo para Modo Escritorio.
"""

import os
import sys
import traceback
import threading

# Forzar UTF-8 en consola para Windows (evita UnicodeEncodeError con emojis)
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ─── GLOBAL UNHANDLED EXCEPTION HOOK (captura crashes en cualquier hilo) ──
_original_excepthook = sys.excepthook
def _global_excepthook(exctype, value, tb):
    try:
        from modulos.logger import logger
        logger.critical(f"❌ EXCEPCIÓN NO CAPTURADA: {exctype.__name__}: {value}")
        logger.critical("".join(traceback.format_tb(tb)))
    except Exception:
        pass
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"❌ ERROR CRÍTICO NO CAPTURADO: {exctype.__name__}: {value}", file=sys.stderr)
    traceback.print_exception(exctype, value, tb, file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)
    if _original_excepthook:
        _original_excepthook(exctype, value, tb)
sys.excepthook = _global_excepthook

# También capturar excepciones en hilos (threading.Thread)
_threading_original_excepthook = None
def _thread_excepthook(args):
    try:
        from modulos.logger import logger
        logger.critical(f"❌ EXCEPCIÓN EN HILO: {args.exc_type.__name__}: {args.exc_value}")
        if args.exc_traceback:
            logger.critical("".join(traceback.format_tb(args.exc_traceback)))
    except Exception:
        pass
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"❌ ERROR EN HILO: {args.exc_type.__name__}: {args.exc_value}", file=sys.stderr)
    if args.exc_traceback:
        traceback.print_exception(args.exc_type, args.exc_value, args.exc_traceback, file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)
    if _threading_original_excepthook:
        _threading_original_excepthook(args)
try:
    _threading_original_excepthook = threading.excepthook
    threading.excepthook = _thread_excepthook
except AttributeError:
    pass

import json
import webview
from config import TECLA_HABLAR
from modulos.logger import logger
from modulos.web_bridge import ArgusWebBridge


def main():
    logger.info("==================================================")
    logger.info("🚀 Iniciando Argus Copilot — Web HUD (PyWebView)")
    logger.info("==================================================")

    # 0. Fase P — restaurar preferencias persistentes del usuario.
    #    (workspace/modelo/visualización). Best-effort: si falla, defaults.
    try:
        from config import estado as _estado
        from modulos.persistencia import (
            cargar_preferencias, cargar_estado_proyecto,
            iniciar_radar_persistente, marcar_sesiones_abiertas_como_aborted,
            sesion_abierta_en_disco, purgar_todos_los_contextos,
        )
        prefs = cargar_preferencias()
        if prefs.get("modelo_seleccionado"):
            _estado.cambiar_modelo_seleccionado(prefs["modelo_seleccionado"])
        if prefs.get("modo_visualizacion"):
            _estado.cambiar_modo_visualizacion(prefs["modo_visualizacion"])
        if prefs.get("modo_actual"):
            try:
                _estado.cambiar_modo(prefs["modo_actual"])
            except Exception:
                pass
        workspace = prefs.get("workspace_actual") or ""
        if workspace and os.path.isdir(workspace):
            _estado.cambiar_workspace(workspace)
            # Recargar el estado del proyecto desde lo que YA existe en disco.
            _estado.cambiar_snapshot(cargar_estado_proyecto(workspace))
            # Re-armar el radar de cambios de archivos (estaba solo en main_gui).
            try:
                iniciar_radar_persistente(workspace)
            except Exception as e:
                logger.warning(f"[RADAR] No se pudo re-armar el radar: {e}")
        # Marcar sesiones que quedaron abiertas por un cierre anormal previo.
        aborted = marcar_sesiones_abiertas_como_aborted()
        if aborted:
            logger.info(f"[FASE P] Sesiones recuperadas de cierre anormal: {aborted}")
        # Rotación global: purgar contextos que excedan MAX_SESIONES_POR_CONTEXTO.
        try:
            purgados = purgar_todos_los_contextos()
            if purgados:
                logger.info(f"[FASE P] Rotación aplicada a {purgados} contexto(s).")
        except Exception as e:
            logger.warning(f"[FASE P] No se pudo purgar historial: {e}")
        # Reabrir una sesión para el contexto activo si quedó historial en disco.
        sesion_abierta_en_disco()
    except Exception as e:
        logger.warning(f"[FASE P] No se pudieron restaurar preferencias/sesión: {e}")

    # 1. Instanciar Puente de Comunicación (API Bridge)
    bridge = ArgusWebBridge()

    # 2. Ruta al HTML del Frontend
    html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "gui", "index.html"))
    if not os.path.exists(html_path):
        logger.error(f"No se encontró el archivo de interfaz: {html_path}")
        sys.exit(1)

    url_target = f"file:///{html_path.replace(chr(92), '/')}"
    logger.info(f"Cargando frontend web desde: {url_target}")

    # 3. Hotkey F8 (teclado) — usa Win32 API GetAsyncKeyState para funcionar en juegos fullscreen
    def _iniciar_teclado_windows():
        """Hilo dedicado que lee F8 via GetAsyncKeyState (funciona incluso en juegos fullscreen)."""
        import ctypes
        import time
        user32 = ctypes.windll.user32
        VK_F8 = 0x77
        estado_anterior = False

        try:
            from modulos.audio_custom import esta_escuchando, esta_hablando, detener_voz
        except Exception:
            return

        while True:
            try:
                # GetAsyncKeyState devuelve el bit más significativo (presionado ahora)
                presionado = bool(user32.GetAsyncKeyState(VK_F8) & 0x8000)
                if presionado and not estado_anterior:
                    # Transición: no presionado → presionado (flanco de subida)
                    if not esta_escuchando():
                        if esta_hablando():
                            detener_voz()
                        else:
                            res = bridge.iniciar_escucha_voz()
                            win = bridge._window or (webview.windows[0] if webview.windows else None)
                            if res and res.get("exito") and win:
                                win.evaluate_js("if (window.iniciarEscuchaVozUI) window.iniciarEscuchaVozUI();")
                    estado_anterior = True
                elif not presionado and estado_anterior:
                    # Transición: presionado → no presionado (flanco de bajada)
                    estado_anterior = False
                    # Apagar micrófono inmediatamente al soltar F8 (sin esperar a Whisper)
                    win = bridge._window or (webview.windows[0] if webview.windows else None)
                    if win:
                        try:
                            win.evaluate_js("if (window.detenerEscuchaVozUI) window.detenerEscuchaVozUI();")
                        except Exception:
                            pass
                time.sleep(0.03)  # ~33 Hz — suficiente para capturar F8 sin saturar CPU
            except Exception as _e:
                logger.error(f"Error en hilo de detección F8 (se omite, loop continúa): {_e}")
                time.sleep(0.03)

    if sys.platform == "win32":
        # Usar GetAsyncKeyState (funciona en juegos fullscreen)
        logger.info(f"🎤 Iniciando detector F8 vía Win32 API GetAsyncKeyState (compatible con juegos fullscreen).")
        threading.Thread(target=_iniciar_teclado_windows, daemon=True).start()
    else:
        # Fallback al módulo keyboard para otros SO
        try:
            import keyboard
            def _on_f8():
                try:
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
            logger.info(f"🎤 Global hotkey '{TECLA_HABLAR}' registrado OK (fallback keyboard module).")
        except Exception as e:
            logger.warning(f"Error global hotkey: {e}")

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
                        try:
                            enviar_a_gemini(texto, modo_voz=True, ui_callback=bridge._ui_callback)
                        except Exception as e_inner:
                            logger.exception(f"[GAMEPAD] Error procesando mensaje en IA: {e_inner}")
                            from modulos.audio_custom import hablar_no_bloqueante
                            try:
                                hablar_no_bloqueante("Lo siento, hubo un error al procesar tu mensaje.")
                            except Exception:
                                pass
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

    # 5. Configurar carpeta de almacenamiento persistente (evita errores de borrado temporal en WebView2)
    user_data_dir = os.path.join(os.getenv("LOCALAPPDATA", os.path.expanduser("~")), "ArgusCopilot", "webview_data")
    os.makedirs(user_data_dir, exist_ok=True)

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
        webview.start(private_mode=False, storage_path=user_data_dir)
    except Exception as e:
        logger.exception(f"Error al iniciar ventana PyWebView: {e}")
    finally:
        if bridge._gestor_gamepad:
            try:
                bridge._gestor_gamepad.detener()
            except Exception:
                pass
        try:
            from config import estado
            # Fase P — flush del historial: cerrar la sesión del contexto activo
            # y purgar su historial (rotación a MAX_SESIONES_POR_CONTEXTO).
            try:
                from modulos.persistencia import cerrar_sesion, armar_context_id, purgar_historial
                context_id_saliente = armar_context_id(estado.modo_actual)
                cerrar_sesion(context_id_saliente)
                purgar_historial(context_id_saliente)
            except Exception:
                pass
            mensajes = estado.obtener_contexto_copia()
            if mensajes:
                if estado.modo_actual == "mentor":
                    from modulos.progreso_mentoria import sesion_ya_procesada
                    if sesion_ya_procesada(mensajes):
                        logger.info("Sesión de mentoría ya persistida (cambio de modo previo); se omite re-examen al cierre.")
                    else:
                        from modulos.perfil_mentor import extraer_y_procesar_sesion_mentor
                        extraer_y_procesar_sesion_mentor(mensajes, estado.workspace_actual)
                        from modulos.progreso_mentoria import procesar_sesion_progreso
                        procesar_sesion_progreso(mensajes)
                elif estado.modo_actual == "gamer":
                    from modulos.perfil_gamer import extraer_y_procesar_sesion_gamer
                    extraer_y_procesar_sesion_gamer(mensajes)
                else:
                    from modulos.perfil_usuario import extraer_y_procesar_sesion
                    extraer_y_procesar_sesion(mensajes)
                logger.info("✅ Sesión procesada y guardada al cerrar la aplicación.")
        except Exception as e_close:
            logger.warning(f"Error al guardar sesión al cerrar ventana: {e_close}")


if __name__ == "__main__":
    main()
