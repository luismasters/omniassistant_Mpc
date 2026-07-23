"""
Puente de Comunicación Python <-> JavaScript para Argus (PyWebView).

Proporciona métodos thread-safe llamados desde el Frontend Web (JS vía window.pywebview.api):
- enviar_mensaje(prompt)
- cambiar_modo_interfaz(modo)
- cambiar_modo_visualizacion(modo)
- iniciar_escucha_voz()
- obtener_estado_inicial()
- cambiar_modelo_seleccionado(modelo)
- anclar_proyecto()
- actualizar_memoria()
- limpiar_contexto()
- seleccionar_perfil_mentor(perfil)
- obtener_perfiles_mentor()
"""

import threading
import json
import webview
from config import estado, TECLA_HABLAR
from modulos.logger import logger
from modulos.ia import enviar_a_gemini
from modulos.audio_custom import capturar_voz_micro, hablar_no_bloqueante
from modulos.perfil_mentor import cargar_perfil_mentor, guardar_perfil_mentor


def resolver_modelo_actual(modelo_seleccionado: str, modo_actual: str) -> str:
    """
    Resuelve el nombre real del modelo activo cuando el usuario tiene 
    seleccionado 'Por Defecto'. Esto permite mostrar en la UI qué modelo
    se está usando realmente según el modo actual.
    """
    if modelo_seleccionado != "Por Defecto":
        return modelo_seleccionado
    # Modo mentor usa DeepSeek por defecto
    if modo_actual == "mentor":
        return "DeepSeek Reasoner"
    # Modo gamer usa Groq Llama 3.1 8B (más rápido para gaming)
    if modo_actual == "gamer":
        return "Groq Llama 3.1 8B"
    # General usa Gemini por defecto
    return "Gemini 3.1 Flash Lite"

class ArgusWebBridge:
    """Clase expuesta hacia JavaScript en window.pywebview.api."""

    def __init__(self, app_window=None):
        self._window = app_window
        self._gestor_gamepad = None  # instanciado en main_web.py
        # Cola de notificaciones de recordatorios que llegaron antes
        # de que la ventana PyWebView estuviera lista
        self._cola_recordatorios_pendientes: list = []
        self._suscribir_recordatorios()

    def _suscribir_recordatorios(self):
        try:
            from modulos.skills.recordatorios.gestor_recordatorios import gestor_recordatorios
            gestor_recordatorios.suscribir_callback_aviso(self._on_recordatorio_disparado)
            logger.info("[RECORDATORIOS] Callback de aviso suscrito correctamente en web_bridge.")
        except Exception as e:
            logger.warning(f"No se pudo suscribir callback de recordatorios: {e}")

    def _on_recordatorio_disparado(self, data: dict):
        """Llamado por el scheduler cuando un recordatorio expira.
        Si la ventana no está lista aún, encola la notificación para reenviarla.
        La síntesis de voz se ejecuta en un hilo separado para no bloquear el scheduler.
        """
        try:
            win = self._window or (webview.windows[0] if webview.windows else None)
            if win:
                js_cmd = f"if (window.mostrarNubeRecordatorioEmo) window.mostrarNubeRecordatorioEmo({json.dumps(data)});"
                try:
                    win.evaluate_js(js_cmd)
                    logger.info(f"[RECORDATORIOS] Nube EMO mostrada para: '{data.get('mensaje', '')}' ")
                except Exception as e_js:
                    logger.warning(f"[RECORDATORIOS] evaluate_js fallido, encolando: {e_js}")
                    self._cola_recordatorios_pendientes.append(data)
            else:
                # Ventana aún no disponible: encolar para reenviar en set_window
                logger.warning("[RECORDATORIOS] Ventana no disponible, encolando notificacion para reenvio.")
                self._cola_recordatorios_pendientes.append(data)

            # Síntesis de voz en hilo separado (no bloquear el scheduler)
            msg = data.get("mensaje", "")
            es_previo = data.get("es_aviso_previo", False)
            prefix = "Aviso para mañana: " if es_previo else "Recordatorio: "
            threading.Thread(
                target=hablar_no_bloqueante,
                args=(f"{prefix}{msg}",),
                daemon=True
            ).start()
        except Exception as e:
            logger.exception(f"Error procesando disparo de recordatorio en bridge: {e}")

    def _reenviar_recordatorios_encolados(self):
        """Reenvía al frontend todas las notificaciones que llegaron
        antes de que la ventana PyWebView estuviera lista.
        Se llama automáticamente desde set_window() con un delay
        para asegurar que el JS del frontend ya haya cargado.
        """
        if not self._cola_recordatorios_pendientes:
            return
        # Esperar 4 segundos para que el frontend JS termine de cargar
        import time
        time.sleep(4)
        win = self._window or (webview.windows[0] if webview.windows else None)
        if not win:
            return
        pendientes = list(self._cola_recordatorios_pendientes)
        self._cola_recordatorios_pendientes.clear()
        for data in pendientes:
            try:
                js_cmd = f"if (window.mostrarNubeRecordatorioEmo) window.mostrarNubeRecordatorioEmo({json.dumps(data)});"
                win.evaluate_js(js_cmd)
                logger.info(f"[RECORDATORIOS] Notificacion re-enviada (encolada): '{data.get('mensaje', '')}' ")
            except Exception as e:
                logger.warning(f"[RECORDATORIOS] Error re-enviando notificacion encolada: {e}")

    def set_window(self, window):
        self._window = window
        # Reenviar cualquier recordatorio que haya disparado antes de que la ventana existiera
        threading.Thread(target=self._reenviar_recordatorios_encolados, daemon=True).start()

    def set_gestor_gamepad(self, gestor):
        """Recibe el GestorGamepad ya iniciado desde main_web.py."""
        self._gestor_gamepad = gestor

    def _ui_callback(self, remitente, texto, color=None, nueva_linea=True):
        """Callback invocado por enviar_a_gemini para emitir respuestas hacia el chat web."""
        try:
            if not texto and nueva_linea:
                return
            win = self._window or (webview.windows[0] if webview.windows else None)
            if win:
                es_continuacion = not nueva_linea
                js_cmd = f"if (window.agregarRespuestaArgus) window.agregarRespuestaArgus({json.dumps(texto)}, {json.dumps(remitente or 'Argus Copilot')}, {json.dumps(es_continuacion)});"
                win.evaluate_js(js_cmd)
        except Exception as e:
            logger.exception(f"Error enviando callback_ia a web: {e}")

    def obtener_estado_inicial(self) -> dict:
        """Devuelve el estado global inicial al frontend al cargar la aplicación."""
        try:
            perfil_actual = cargar_perfil_mentor()
            modelo_real = resolver_modelo_actual(estado.modelo_seleccionado, estado.modo_actual)
            return {
                "modo_actual": estado.modo_actual,
                "modo_visualizacion": estado.modo_visualizacion,
                "gamer_mode_activo": getattr(estado, "gamer_mode_activo", False),
                "perfil_mentor": perfil_actual.get("stack_objetivo", {}).get("backend", "General"),
                "lista_perfiles": [perfil_actual],
                "modelo_seleccionado": estado.modelo_seleccionado,
                "modelo_real": modelo_real,
                "workspace_actual": estado.workspace_actual
            }
        except Exception as e:
            logger.exception(f"Error en obtener_estado_inicial: {e}")
            return {"error": str(e)}

    def enviar_mensaje(self, prompt: str) -> dict:
        """
        Procesa un prompt recibido desde el chat web usando el motor de IA de Argus.
        """
        if not prompt or not prompt.strip():
            return {"exito": False, "error": "Prompt vacío"}

        try:
            # Hook de primera interacción del día para recordatorios sin hora / cumpleaños
            try:
                from modulos.skills.recordatorios.gestor_recordatorios import gestor_recordatorios
                gestor_recordatorios.comprobar_primera_interaccion_dia()
            except Exception as e_rec:
                logger.warning(f"Error en comprobar_primera_interaccion_dia: {e_rec}")

            win = self._window or (webview.windows[0] if webview.windows else None)
            if win:
                win.evaluate_js("if (window.mostrarTypingIndicator) window.mostrarTypingIndicator();")

            def _hilo_procesar():
                enviar_a_gemini(prompt.strip(), modo_voz=False, ui_callback=self._ui_callback)

            threading.Thread(target=_hilo_procesar, daemon=True).start()
            return {"exito": True}
        except Exception as e:
            logger.exception(f"Error procesando mensaje en web bridge: {e}")
            return {"exito": False, "respuesta": f"❌ Error: {str(e)}"}

    def obtener_recordatorios(self) -> dict:
        """Devuelve la lista de recordatorios pendientes."""
        try:
            from modulos.skills.recordatorios.gestor_recordatorios import gestor_recordatorios
            recs = gestor_recordatorios.listar_recordatorios(incluir_completados=False)
            return {"exito": True, "recordatorios": recs}
        except Exception as e:
            logger.exception(f"Error obteniendo recordatorios: {e}")
            return {"exito": False, "error": str(e)}

    def crear_recordatorio_manual(self, mensaje: str, tiempo_str: str, opciones: str = "") -> dict:
        """Crea un recordatorio desde la GUI manual."""
        try:
            from modulos.skills.recordatorios.gestor_recordatorios import gestor_recordatorios
            rec = gestor_recordatorios.crear_recordatorio(mensaje, tiempo_str, opciones, origen="gui_manual")
            return {"exito": True, "recordatorio": rec}
        except Exception as e:
            logger.exception(f"Error creando recordatorio manual: {e}")
            return {"exito": False, "error": str(e)}

    def cancelar_recordatorio_manual(self, id_rec: str) -> dict:
        """Cancela un recordatorio desde la GUI manual."""
        try:
            from modulos.skills.recordatorios.gestor_recordatorios import gestor_recordatorios
            exito = gestor_recordatorios.cancelar_recordatorio(id_rec)
            return {"exito": exito}
        except Exception as e:
            logger.exception(f"Error cancelando recordatorio manual: {e}")
            return {"exito": False, "error": str(e)}

    def cambiar_modo_interfaz(self, modo: str) -> dict:
        """
        Cambia el modo de la interfaz (chat, mentor, gamer).
        """
        try:
            modo_lower = modo.lower()
            if modo_lower not in ["chat", "mentor", "gamer"]:
                return {"exito": False, "error": f"Modo inválido: {modo}"}

            estado.cambiar_modo(modo_lower)
            logger.info(f"Modo de interfaz cambiado a: {modo_lower.upper()}")

            # Si se activa el Modo Gamer, descargar Whisper de VRAM para liberar la GPU
            if modo_lower == "gamer":
                try:
                    import modulos.audio_custom as _audio
                    if getattr(_audio, "_modelo_whisper", None) is not None:
                        del _audio._modelo_whisper
                        _audio._modelo_whisper = None
                        logger.info("🎮 Modo Gaming ON — Modelo Whisper descargado de VRAM de GPU para maximizar rendimiento en juegos.")
                except Exception as e_vram:
                    logger.warning(f"[GAMEPAD] Error al liberar VRAM de Whisper: {e_vram}")

            return {"exito": True, "modo": modo_lower}
        except Exception as e:
            logger.exception(f"Error cambiando modo interfaz: {e}")
            return {"exito": False, "error": str(e)}

    def cambiar_modo_visualizacion(self, modo_vis: str) -> dict:
        """
        Cambia el modo de visualización de la ventana (traditional, floating, desktop_full, desktop_side).
        """
        try:
            opts = {}
            if modo_vis == "desktop_full":
                clave_host = "desktop"
                opts = {"full_span": True}
            elif modo_vis == "desktop_side":
                clave_host = "desktop"
                opts = {"full_span": False}
            elif modo_vis == "floating":
                clave_host = "floating"
            else:
                clave_host = "traditional"

            estado.cambiar_modo_visualizacion(clave_host)

            win = self._window or (webview.windows[0] if webview.windows else None)
            if win:
                if clave_host == "desktop":
                    from modulos.win32_desktop import obtener_bounds_pantalla_virtual
                    b = obtener_bounds_pantalla_virtual()
                    if opts.get("full_span", True):
                        win.move(b["x"], b["y"])
                        win.resize(b["width"], b["height"])
                elif clave_host == "floating":
                    win.resize(450, 700)

            return {"exito": True, "modo_visualizacion": modo_vis}
        except Exception as e:
            logger.exception(f"Error cambiando modo visualizacion: {e}")
            return {"exito": False, "error": str(e)}

    def obtener_modelo_real(self) -> dict:
        """Devuelve el nombre del modelo que realmente se está usando 
        (resolviendo 'Por Defecto' según el modo actual)."""
        try:
            modelo_real = resolver_modelo_actual(estado.modelo_seleccionado, estado.modo_actual)
            return {"exito": True, "modelo_real": modelo_real}
        except Exception as e:
            logger.exception(f"Error obteniendo modelo real: {e}")
            return {"exito": False, "error": str(e)}

    def cambiar_modelo_seleccionado(self, modelo: str) -> dict:
        """Cambia el modelo de IA seleccionado."""
        try:
            estado.cambiar_modelo_seleccionado(modelo)
            logger.info(f"Modelo cambiado a: {modelo}")
            return {"exito": True, "modelo": modelo}
        except Exception as e:
            logger.exception(f"Error cambiando modelo: {e}")
            return {"exito": False, "error": str(e)}

    def anclar_proyecto(self) -> dict:
        """Abre cuadro de diálogo para seleccionar carpeta de proyecto."""
        try:
            win = self._window or (webview.windows[0] if webview.windows else None)
            if win:
                res = win.create_file_dialog(webview.FOLDER_DIALOG)
                if res and len(res) > 0:
                    carpeta = res[0]
                    estado.cambiar_workspace(carpeta)
                    logger.info(f"Workspace anclado: {carpeta}")
                    return {"exito": True, "workspace": carpeta}
            return {"exito": False, "error": "No se seleccionó carpeta"}
        except Exception as e:
            logger.exception(f"Error anclando proyecto: {e}")
            return {"exito": False, "error": str(e)}

    def actualizar_memoria(self) -> dict:
        """Dispara la extracción y actualización manual de memoria de perfil (usuario o mentor)."""
        try:
            import threading
            import config as _cfg
            mensajes = _cfg.estado.obtener_contexto_copia()
            if not mensajes:
                return {"exito": False, "motivo": "sin_mensajes"}

            def _hilo_extraccion():
                try:
                    if _cfg.estado.modo_actual == "mentor":
                        from modulos.perfil_mentor import extraer_y_procesar_sesion_mentor
                        extraer_y_procesar_sesion_mentor(mensajes)
                    else:
                        from modulos.perfil_usuario import extraer_y_procesar_sesion
                        extraer_y_procesar_sesion(mensajes)
                    import webview
                    win = self._window or (webview.windows[0] if webview.windows else None)
                    if win:
                        win.evaluate_js("if (window.agregarMensajeSistema) window.agregarMensajeSistema('✅ Memoria de perfil actualizada.');")
                except Exception as ex:
                    logger.exception(f"Error extrayendo memoria de perfil: {ex}")

            threading.Thread(target=_hilo_extraccion, daemon=True).start()
            return {"exito": True}
        except Exception as e:
            logger.exception(f"Error actualizando memoria: {e}")
            return {"exito": False, "error": str(e)}

    def limpiar_contexto(self) -> dict:
        """Limpia el contexto de chat."""
        try:
            estado.limpiar_contexto()
            return {"exito": True}
        except Exception as e:
            logger.exception(f"Error limpiando contexto: {e}")
            return {"exito": False, "error": str(e)}

    def iniciar_escucha_voz(self) -> dict:
        """Activa el micrófono y procesa la entrada por voz."""
        try:
            from modulos.audio_custom import esta_escuchando
            if esta_escuchando():
                logger.info("🎤 Captura de voz ya en curso, ignorando nueva solicitud.")
                return {"exito": False, "motivo": "ya_escuchando"}

            def _hilo_escucha():
                texto = capturar_voz_micro()
                win = self._window or (webview.windows[0] if webview.windows else None)
                if win:
                    win.evaluate_js("if (window.detenerEscuchaVozUI) window.detenerEscuchaVozUI();")
                    if texto:
                        win.evaluate_js(f"if (window.agregarMensajeUsuario) window.agregarMensajeUsuario({json.dumps(texto)});")
                        enviar_a_gemini(texto, modo_voz=True, ui_callback=self._ui_callback)

            threading.Thread(target=_hilo_escucha, daemon=True).start()
            return {"exito": True}
        except Exception as e:
            logger.exception(f"Error en escucha de voz: {e}")
            return {"exito": False, "error": str(e)}

    def obtener_perfiles_mentor(self) -> list:
        """Devuelve la lista de perfiles de mentor disponibles."""
        try:
            perfil = cargar_perfil_mentor()
            return [perfil]
        except Exception as e:
            logger.exception(f"Error obteniendo perfiles de mentor: {e}")
            return []

    def seleccionar_perfil_mentor(self, nombre_perfil: str) -> dict:
        """Activa un perfil de mentor específico."""
        try:
            return {"exito": True, "perfil": nombre_perfil}
        except Exception as e:
            logger.exception(f"Error seleccionando perfil mentor: {e}")
            return {"exito": False, "error": str(e)}

    def obtener_clima(self) -> dict:
        """
        Obtiene el clima actual desde wttr.in (gratuito, sin API key).
        Retorna temperatura, descripción, humedad, viento, ícono y condición para EMO.
        Incluye reintento automático en caso de timeout (hasta 2 intentos).
        """
        import urllib.request, urllib.parse, json as _json
        import socket
        import time
        import config as _cfg

        ciudad = getattr(_cfg, 'CIUDAD_CLIMA', 'San Martin, Buenos Aires, Argentina')
        ciudad_enc = urllib.parse.quote(ciudad)
        url = f"https://wttr.in/{ciudad_enc}?format=j1"
        timeout_total = 4  # segundos por intento (más rápido que 8s)
        data = None

        for intento in range(1, 3):  # hasta 2 intentos
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'OmniAssistant/1.0'})
                # Socket-level timeout para cortar antes del timeout de urllib
                socket.setdefaulttimeout(timeout_total)
                with urllib.request.urlopen(req, timeout=timeout_total) as resp:
                    data = _json.loads(resp.read().decode('utf-8'))
                break  # éxito, salir del bucle de reintentos
            except (urllib.error.URLError, socket.timeout, OSError) as e:
                if intento < 2:
                    logger.warning(f"[Clima] Intento {intento} falló: {e}. Reintentando en 1s...")
                    time.sleep(1)
                else:
                    logger.warning(f"[Clima] Error obteniendo clima tras {intento} intentos: {e}")
                    return {'exito': False, 'error': f"Timeout conectando con wttr.in: {e}"}

        # Si llegamos acá sin data, algo raro pasó
        if data is None:
            logger.warning("[Clima] No se obtuvo data tras reintentos.")
            return {'exito': False, 'error': 'No se recibieron datos del clima'}

        try:
            cc = data['current_condition'][0]
            temp = int(cc['temp_C'])
            humedad = int(cc['humidity'])
            viento = int(cc['windspeedKmph'])
            descripcion_en = cc['weatherDesc'][0]['value']
            codigo = int(cc['weatherCode'])
        except (KeyError, IndexError, ValueError) as e:
            logger.warning(f"[Clima] Error parseando datos: {e}")
            return {'exito': False, 'error': f"Datos climáticos inválidos: {e}"}

        # Mapear código a condición climática para EMO
        _storm  = {200, 386, 389, 392, 395}
        _rain   = {176, 182, 185, 263, 266, 281, 284, 293, 296, 299,
                   302, 305, 308, 311, 314, 353, 356, 359}
        _snow   = {179, 227, 230, 317, 320, 323, 326, 329, 332, 335,
                   338, 362, 365, 368, 371}
        _fog    = {143, 248, 260}
        _cloudy = {119, 122}

        if codigo in _storm:
            condicion = 'stormy'
        elif codigo in _rain:
            condicion = 'rainy'
        elif codigo in _snow or temp <= 4:
            condicion = 'cold'
        elif temp >= 30:
            condicion = 'hot'
        elif viento >= 30:
            condicion = 'windy'
        elif codigo in _fog or codigo in _cloudy:
            condicion = 'cloudy'
        else:
            condicion = 'clear'

        # Descripción en español (mapeo parcial)
        _desc = {
            'Clear': 'Despejado', 'Sunny': 'Soleado',
            'Partly cloudy': 'Parcialmente nublado', 'Partly Cloudy': 'Parcialmente nublado',
            'Cloudy': 'Nublado', 'Overcast': 'Cubierto',
            'Mist': 'Neblina', 'Fog': 'Niebla', 'Freezing fog': 'Niebla helada',
            'Light rain': 'Lluvia leve', 'Moderate rain': 'Lluvia moderada',
            'Heavy rain': 'Lluvia intensa', 'Light drizzle': 'Llovizna',
            'Heavy drizzle': 'Llovizna intensa', 'Drizzle': 'Llovizna',
            'Freezing drizzle': 'Llovizna helada', 'Patchy rain possible': 'Posible lluvia',
            'Patchy light rain': 'Lluvia leve', 'Light snow': 'Nieve leve',
            'Moderate snow': 'Nieve moderada', 'Heavy snow': 'Nevada intensa',
            'Blizzard': 'Ventisca', 'Blowing snow': 'Nieve con viento',
            'Sleet': 'Aguanieve', 'Thunder': 'Tormenta',
            'Thundery outbreaks': 'Posible tormenta',
            'Patchy light rain with thunder': 'Lluvia con tormenta',
            'Moderate or heavy rain with thunder': 'Tormenta',
            'Patchy snow possible': 'Posible nieve', 'Ice pellets': 'Granizo',
        }
        descripcion = descripcion_en
        for en, es in _desc.items():
            if en.lower() in descripcion_en.lower():
                descripcion = es
                break

        # Ícono emoji
        if codigo == 113:
            icono = '☀️'
        elif codigo == 116:
            icono = '⛅'
        elif codigo in _cloudy:
            icono = '☁️'
        elif codigo in _fog:
            icono = '🌫'
        elif codigo in _rain:
            icono = '🌧'
        elif codigo in _storm:
            icono = '⛈'
        elif codigo in _snow:
            icono = '❄️'
        else:
            icono = '🌤'

        logger.info(f"☁️ Clima: {temp}°C, {descripcion}, {condicion}")
        return {
            'exito': True,
            'temp': temp,
            'humedad': humedad,
            'viento': viento,
            'descripcion': descripcion,
            'condicion': condicion,
            'icono': icono,
            'ciudad': ciudad,
        }



    def adjuntar_archivo(self) -> dict:
        """Abre cuadro de diálogo para seleccionar archivos a adjuntar al contexto."""
        try:
            win = self._window or (webview.windows[0] if webview.windows else None)
            if win:
                res = win.create_file_dialog(
                    webview.OPEN_DIALOG,
                    allow_multiple=True,
                    file_types=('Todos los archivos (*.*)',
                                'Texto y código (*.txt;*.py;*.js;*.ts;*.html;*.css;*.json;*.md;*.csv;*.xml)',
                                'Imágenes (*.png;*.jpg;*.jpeg;*.webp;*.gif)')
                )
                if res and len(res) > 0:
                    rutas = list(res)
                    logger.info(f"Archivos adjuntados: {rutas}")
                    return {"exito": True, "rutas": rutas}
            return {"exito": False, "error": "No se seleccionó archivo"}
        except Exception as e:
            logger.exception(f"Error adjuntando archivo: {e}")
            return {"exito": False, "error": str(e)}

    def actualizar_estado_gamepad_js(self, presionado: bool) -> dict:
        """Recibe el estado actual del combo L3+R3 desde la API HTML5 Gamepad de JS."""
        self._gamepad_combo_presionado_js = presionado
        return {"exito": True}

    def check_gamepad_combo_js(self) -> bool:
        """Condición de corte para capturar_voz_micro cuando se usa el mando en JS."""
        return getattr(self, "_gamepad_combo_presionado_js", False)

    def iniciar_escucha_voz_gamepad(self) -> dict:
        """Activa la escucha por voz desde la UI por combo L3+R3 del gamepad."""
        try:
            from modulos.audio_custom import esta_escuchando, capturar_voz_micro
            if esta_escuchando():
                return {"exito": False, "motivo": "ya_escuchando"}

            self._gamepad_combo_presionado_js = True

            def _hilo_escucha_gamepad():
                texto = capturar_voz_micro(condicion_seguir_grabando=self.check_gamepad_combo_js)
                win = self._window or (webview.windows[0] if webview.windows else None)
                if win:
                    win.evaluate_js("if (window.detenerEscuchaVozUI) window.detenerEscuchaVozUI();")
                    if texto:
                        win.evaluate_js(f"if (window.agregarMensajeUsuario) window.agregarMensajeUsuario({json.dumps(texto)});")
                        enviar_a_gemini(texto, modo_voz=True, ui_callback=self._ui_callback)

            threading.Thread(target=_hilo_escucha_gamepad, daemon=True).start()
            return {"exito": True}
        except Exception as e:
            logger.exception(f"Error en escucha de voz gamepad: {e}")
            return {"exito": False, "error": str(e)}

    def listar_mandos_gamepad(self) -> dict:
        """Lista los mandos detectados por GestorGamepad (subproceso aislado)."""
        try:
            from modulos.gamepad_control import GestorGamepad
            mandos = GestorGamepad.listar_mandos_disponibles()
            estado_mando = None
            if mandos:
                nombre = f"Todos ({len(mandos)} mando(s))" if len(mandos) > 1 else mandos[0]['nombre']
                estado_mando = {"conectado": True, "nombre": nombre, "indice": -1}
            else:
                estado_mando = {"conectado": False, "nombre": "No detectado", "indice": -1}
            return {"exito": True, "mandos": mandos, "estado": estado_mando}
        except Exception as e:
            logger.warning(f"Error listando mandos: {e}")
            return {"exito": True, "mandos": [], "estado": None}

    def seleccionar_mando_gamepad(self, indice: int) -> dict:
        """Cambia el mando activo en el GestorGamepad."""
        try:
            if self._gestor_gamepad:
                self._gestor_gamepad.iniciar_con_indice(indice)
            from modulos.gamepad_control import GestorGamepad
            mandos = GestorGamepad.listar_mandos_disponibles()
            if indice == -1:
                nombre = f"Todos ({len(mandos)} mando(s))"
            else:
                nombre = mandos[indice]['nombre'] if mandos and 0 <= indice < len(mandos) else 'Gamepad'
            return {"exito": True, "estado": {"conectado": True, "nombre": nombre, "indice": indice}}
        except Exception as e:
            logger.exception(f"Error seleccionando mando: {e}")
            return {"exito": False, "error": str(e)}

    def reintentar_escaneo_gamepad(self) -> dict:
        """Fuerza un re-escaneo completo de mandos desde la UI web."""
        try:
            if self._gestor_gamepad:
                self._gestor_gamepad.reintentar_escaneo()
            from modulos.gamepad_control import GestorGamepad
            mandos = GestorGamepad.listar_mandos_disponibles()
            return {"exito": True, "mandos": mandos}
        except Exception as e:
            logger.exception(f"Error re-escanenado mandos: {e}")
            return {"exito": False, "error": str(e)}

