import os
import threading
import time
import webview
import markdown 
import json 

import config

# =====================================================================
# ⚠️ CARGA DIFERIDA DE LA IA (fix del freeze de 10-15s al arrancar)
# =====================================================================
# `from modulos.ia import enviar_a_gemini` dispara, en cadena,
# `modulos.memoria` -> ChromaDB + sentence-transformers + torch. Esa carga
# tarda ~10-15s y, si se hace en el tope del archivo (como antes), ocupa el
# hilo principal ANTES de que webview.create_window()/webview.start() puedan
# terminar de inicializar el control nativo (WinForms + WebView2). Eso es lo
# que generaba la ventana congelada y la cascada de errores
# "AccessibilityObject.Bounds.Empty..." / "CoreWebView2Controller members
# can only be accessed from the UI thread" en consola.
#
# Solución: mostramos la ventana primero, y cargamos modulos.ia en un hilo
# en background. Mientras carga, el chat queda deshabilitado en el frontend
# con un aviso; apenas termina, se habilita solo.
enviar_a_gemini = None          # se asigna cuando termine la carga
motor_ia = None                 # referencia al módulo modulos.ia ya cargado
IA_LISTA = threading.Event()
VOZ_DISPONIBLE = False
capturar_voz_micro = None
detener_voz = None


def _cargar_motor_ia_en_background(api_ref):
    """Corre en un hilo aparte: importa modulos.ia (pesado) y modulos.audio_custom,
    y recién entonces avisa al frontend que el chat ya puede usarse."""
    global enviar_a_gemini, motor_ia, VOZ_DISPONIBLE, capturar_voz_micro, detener_voz

    try:
        import modulos.ia as _motor_ia
        from modulos.ia import enviar_a_gemini as _enviar_a_gemini
        motor_ia = _motor_ia
        enviar_a_gemini = _enviar_a_gemini
    except Exception as e:
        print(f"❌ Error crítico cargando modulos.ia: {e}")
        api_ref._safe_evaluate_js(
            f"addMessage('system', {json.dumps('Error cargando el motor de IA: ' + str(e))});",
            forzar=True,
        )
        return

    try:
        from modulos.audio_custom import capturar_voz_micro as _cap, detener_voz as _det
        capturar_voz_micro = _cap
        detener_voz = _det
        VOZ_DISPONIBLE = True
    except Exception:
        VOZ_DISPONIBLE = False

    IA_LISTA.set()
    api_ref._safe_evaluate_js("onMotorListo();", forzar=True)
    print("✅ [IA] Motor de IA y memoria cargados, chat habilitado.")

# =====================================================================
# API PUENTE (PYTHON <-> JAVASCRIPT)
# =====================================================================
class Api:
    def __init__(self):
        self.window = None
        self.texto_ia_acumulado = "" # <-- Aquí guardamos el texto mientras streamea
        self.grabando_voz = False

        # ✅ Lock + throttle para evaluate_js: evita saturar el puente WinForms/WebView2
        # desde el hilo de streaming (causa de "CoreWebView2Controller members can only
        # be accessed from the UI thread" / cascada de errores de AccessibilityObject).
        self._js_lock = threading.Lock()
        self._ultimo_evaluate_js = 0.0
        self._intervalo_min_js = 0.05  # 50ms entre llamadas como máximo

    def _safe_evaluate_js(self, codigo, forzar=False):
        """Envoltorio seguro alrededor de window.evaluate_js.

        - Throttlea llamadas muy frecuentes (streaming chunk por chunk) para no
          inundar el puente nativo, que en Windows (WinForms + WebView2) puede
          fallar si se lo llama desde un hilo secundario a muy alta frecuencia.
        - Atrapa cualquier excepción para que un fallo puntual de UI no tire
          abajo el hilo de la IA ni deje la conversación a medio enviar.
        """
        if not self.window:
            return
        with self._js_lock:
            ahora = time.monotonic()
            if not forzar and (ahora - self._ultimo_evaluate_js) < self._intervalo_min_js:
                time.sleep(self._intervalo_min_js - (ahora - self._ultimo_evaluate_js))
            self._ultimo_evaluate_js = time.monotonic()
            try:
                self.window.evaluate_js(codigo)
            except Exception as e:
                print(f"⚠️ [UI] evaluate_js falló (se ignora para no romper el streaming): {e}")

    def recibir_mensaje(self, texto):
        """Javascript llama a esto cuando el usuario aprieta Enviar"""
        if not IA_LISTA.is_set():
            msg = "Todavía estoy cargando la memoria y los modelos, dame unos segundos más…"
            self._safe_evaluate_js(f"addMessage('system', {json.dumps(msg)});", forzar=True)
            return
        threading.Thread(target=enviar_a_gemini,
                         args=(texto, False, self.callback_ia),
                         daemon=True).start()

    def callback_ia(self, remitente, texto: str, color=None, nueva_linea=True):
        """Gemini llama a esto cuando tiene un fragmento de respuesta."""
        # 1. Mensajes del Sistema (Buscando en web, cargando...)
        if remitente == "⚙️ Sistema" and texto.strip():
            safe_text = json.dumps(texto)
            self._safe_evaluate_js(f"addMessage('system', {safe_text});", forzar=True)
            return

        # 2. IA Empieza a hablar (Creamos la burbuja)
        if remitente == "🤖 Argus" and not texto:
            self.texto_ia_acumulado = ""
            self._safe_evaluate_js("startAIMessage();", forzar=True)
            return

        # 3. Fin del mensaje (Renderizamos por última vez y cerramos)
        if nueva_linea and texto == "":
            html_texto = markdown.markdown(self.texto_ia_acumulado, extensions=['fenced_code', 'tables'])
            safe_html = json.dumps(html_texto)
            safe_raw = json.dumps(self.texto_ia_acumulado)
            self._safe_evaluate_js(f"updateLastMessage({safe_html}, {safe_raw});", forzar=True)
            self._safe_evaluate_js("finalizeLastMessage();", forzar=True)
            return

        # 4. Streaming Chunk (Se actualiza la burbuja actual en tiempo real)
        if texto:
            self.texto_ia_acumulado += texto
            html_texto = markdown.markdown(self.texto_ia_acumulado, extensions=['fenced_code', 'tables'])
            safe_html = json.dumps(html_texto) # Transforma a un string válido para JS
            safe_raw = json.dumps(self.texto_ia_acumulado)
            self._safe_evaluate_js(f"updateLastMessage({safe_html}, {safe_raw});")

    # =================================================================
    # VOZ (botón de micrófono / F8 desde el frontend)
    # =================================================================
    def iniciar_voz(self):
        """JS llama a esto cuando el usuario presiona el botón de mic o F8."""
        if not IA_LISTA.is_set():
            msg = "Todavía estoy cargando la memoria y los modelos, dame unos segundos más…"
            self._safe_evaluate_js(f"addMessage('system', {json.dumps(msg)});", forzar=True)
            self._safe_evaluate_js("onVoiceFinished();", forzar=True)
            return

        if not VOZ_DISPONIBLE:
            msg = "El módulo de voz no está disponible en este entorno."
            self._safe_evaluate_js(f"addMessage('system', {json.dumps(msg)});", forzar=True)
            self._safe_evaluate_js("onVoiceFinished();", forzar=True)
            return

        if self.grabando_voz:
            return  # ya hay una grabación en curso

        self.grabando_voz = True
        threading.Thread(target=self._hilo_voz, daemon=True).start()

    def _hilo_voz(self):
        try:
            texto_voz = capturar_voz_micro()
        except Exception as e:
            texto_voz = None
            print(f"❌ Error capturando voz: {e}")
        finally:
            self.grabando_voz = False

        # Avisamos al frontend que terminó la grabación (vuelve el ícono a su estado normal)
        self._safe_evaluate_js("onVoiceFinished();", forzar=True)

        if texto_voz:
            safe_text = json.dumps(f"🎤 {texto_voz}")
            self._safe_evaluate_js(f"addMessage('user', {safe_text});", forzar=True)
            enviar_a_gemini(texto_voz, True, self.callback_ia)

    def detener_voz_manual(self):
        """JS llama a esto si el usuario suelta F8 / vuelve a tocar el botón antes de que termine de grabar."""
        if VOZ_DISPONIBLE:
            try:
                detener_voz()
            except Exception:
                pass
        self.grabando_voz = False

    def cambiar_modo(self, modo):
        """Javascript llama a esto cuando haces click en el Sidebar"""
        config.estado.modo_actual = modo

        nombres_modelos = {
            "general": "🧠 Modelo: Gemini Flash",
            "planificador": "🧠 Modelo: DeepSeek V4 (Thinking)",
            "programador": "🧠 Modelo: DeepSeek V4 (Fast)"
        }
        
        # Actualizamos el texto del modelo en el frontend
        lbl_text = json.dumps(nombres_modelos[modo])
        self._safe_evaluate_js(f"document.getElementById('lbl_modelo').innerText = {lbl_text};", forzar=True)

        if modo in ["planificador", "programador"]:
            # Si este modo YA tiene un workspace anclado de antes, no volvemos
            # a pedir la carpeta — eso es lo que hacía que "se perdiera la
            # referencia" al volver a un modo: se pisaba con un diálogo nuevo
            # (o quedaba huérfana porque se guardaba en un lugar que ia.py
            # nunca lee). Solo pedimos carpeta si no hay ninguna anclada aún.
            if config.estado.workspace_actual:
                msg = f"Workspace ya anclado: {config.estado.workspace_actual}"
                self._safe_evaluate_js(f"addMessage('system', {json.dumps(msg)});", forzar=True)
                return

            # USAMOS EL DIÁLOGO NATIVO DE PYWEBVIEW (Modo Carpeta)
            resultado = self.window.create_file_dialog(webview.FOLDER_DIALOG)

            if resultado and len(resultado) > 0:
                ruta = resultado[0]
                # ✅ FIX: ia.py y controlador_acciones.py leen el workspace
                # desde config.estado.workspace_actual, NO desde
                # modulos.ia.WORKSPACE_ACTUAL (esa variable de módulo no
                # existe ni se lee en ningún lado). Por eso el anclaje se
                # "perdía" al cambiar de modo: nunca había llegado al lugar
                # correcto en primer lugar.
                config.estado.workspace_actual = ruta
                msg = f"Workspace anclado: {ruta}"
                self._safe_evaluate_js(f"addMessage('system', {json.dumps(msg)});", forzar=True)
            else:
                # El usuario canceló el diálogo: no lo dejamos en modo
                # planificador/programador sin workspace de forma silenciosa.
                msg = "No se ancló ningún workspace. Podés intentarlo de nuevo cambiando de modo."
                self._safe_evaluate_js(f"addMessage('system', {json.dumps(msg)});", forzar=True)

    def anclar_otro_workspace(self):
        """JS puede llamar a esto (ej. botón 'Cambiar carpeta') para forzar
        un nuevo diálogo de carpeta aunque ya haya un workspace anclado."""
        resultado = self.window.create_file_dialog(webview.FOLDER_DIALOG)
        if resultado and len(resultado) > 0:
            ruta = resultado[0]
            config.estado.workspace_actual = ruta
            msg = f"Workspace anclado: {ruta}"
            self._safe_evaluate_js(f"addMessage('system', {json.dumps(msg)});", forzar=True)

    def adjuntar(self):
        """Javascript llama a esto al hacer click en el clip"""
        # USAMOS EL DIÁLOGO NATIVO DE PYWEBVIEW (Modo Archivo Múltiple)
        rutas = self.window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True)
        
        if rutas:
            cadenas = " ".join([f"[adjunto: {r}]" for r in rutas])
            cadenas_js = json.dumps(cadenas + " ")
            self._safe_evaluate_js(f"document.getElementById('user-input').value += {cadenas_js};", forzar=True)

# =====================================================================
# INICIALIZACIÓN DE LA VENTANA
# =====================================================================
if __name__ == '__main__':
    api = Api()
    
    # 1. Obtenemos la ruta ABSOLUTA de donde está guardado este main_web.py
    directorio_actual = os.path.dirname(os.path.abspath(__file__))
    
    # 2. Armamos la ruta hacia web/index.html
    ruta_html = os.path.join(directorio_actual, 'web', 'index.html')

    # Creamos la ventana nativa
    api.window = webview.create_window(
        title='Argus Híbrido', 
        url=ruta_html, 
        js_api=api,
        width=1100, 
        height=750,
        background_color='#1e1e1e'
    )

    # ✅ Esperamos a que la página haya terminado de cargar (evento 'loaded')
    # antes de permitir el primer evaluate_js. En Windows, llamar a evaluate_js
    # demasiado pronto (antes de que CoreWebView2Controller esté listo en el
    # hilo de UI) es lo que dispara los errores de threading/accesibilidad
    # vistos en consola ("CoreWebView2Controller members can only be accessed
    # from the UI thread", cascada de AccessibilityObject.Bounds.Empty...).
    #
    # ✅ Además, recién acá disparamos la carga pesada de modulos.ia (que
    # arrastra ChromaDB/sentence-transformers/torch vía modulos.memoria) en
    # un hilo de background. Antes esa carga pasaba al importar el archivo,
    # bloqueando el hilo principal 10-15s justo cuando WebView2 necesitaba
    # ese mismo hilo para terminar de inicializarse — esa contención era la
    # causa del freeze de arranque y la cascada de errores en consola.
    def _on_loaded():
        print("✅ Ventana cargada y lista (WebView2 inicializado).")
        api._safe_evaluate_js(
            "addMessage('system', " + json.dumps("Cargando memoria y modelos de IA…") + ");",
            forzar=True,
        )
        threading.Thread(target=_cargar_motor_ia_en_background, args=(api,), daemon=True).start()

    api.window.events.loaded += _on_loaded

    # Arrancamos la aplicación.
    webview.start(debug=False)