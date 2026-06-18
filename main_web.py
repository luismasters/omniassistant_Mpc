import os
import threading
import webview
import markdown 
import json 

from modulos.ia import enviar_a_gemini
import modulos.ia as motor_ia
import config

try:
    from modulos.audio_custom import capturar_voz_micro, detener_voz
    VOZ_DISPONIBLE = True
except Exception:
    VOZ_DISPONIBLE = False

# =====================================================================
# API PUENTE (PYTHON <-> JAVASCRIPT)
# =====================================================================
class Api:
    def __init__(self):
        self.window = None
        self.texto_ia_acumulado = "" # <-- Aquí guardamos el texto mientras streamea
        self.grabando_voz = False

    def recibir_mensaje(self, texto):
        """Javascript llama a esto cuando el usuario aprieta Enviar"""
        threading.Thread(target=enviar_a_gemini,
                         args=(texto, False, self.callback_ia),
                         daemon=True).start()

    def callback_ia(self, remitente, texto: str, color=None, nueva_linea=True):
        """Gemini llama a esto cuando tiene un fragmento de respuesta."""
        # 1. Mensajes del Sistema (Buscando en web, cargando...)
        if remitente == "⚙️ Sistema" and texto.strip():
            safe_text = json.dumps(texto)
            self.window.evaluate_js(f"addMessage('system', {safe_text});")
            return

        # 2. IA Empieza a hablar (Creamos la burbuja)
        if remitente == "🤖 Argus" and not texto:
            self.texto_ia_acumulado = ""
            self.window.evaluate_js("startAIMessage();")
            return

        # 3. Fin del mensaje (Renderizamos por última vez y cerramos)
        if nueva_linea and texto == "":
            html_texto = markdown.markdown(self.texto_ia_acumulado, extensions=['fenced_code', 'tables'])
            safe_html = json.dumps(html_texto)
            safe_raw = json.dumps(self.texto_ia_acumulado)
            self.window.evaluate_js(f"updateLastMessage({safe_html}, {safe_raw});")
            self.window.evaluate_js("finalizeLastMessage();")
            return

        # 4. Streaming Chunk (Se actualiza la burbuja actual en tiempo real)
        if texto:
            self.texto_ia_acumulado += texto
            html_texto = markdown.markdown(self.texto_ia_acumulado, extensions=['fenced_code', 'tables'])
            safe_html = json.dumps(html_texto) # Transforma a un string válido para JS
            safe_raw = json.dumps(self.texto_ia_acumulado)
            self.window.evaluate_js(f"updateLastMessage({safe_html}, {safe_raw});")

    # =================================================================
    # VOZ (botón de micrófono / F8 desde el frontend)
    # =================================================================
    def iniciar_voz(self):
        """JS llama a esto cuando el usuario presiona el botón de mic o F8."""
        if not VOZ_DISPONIBLE:
            msg = "El módulo de voz no está disponible en este entorno."
            self.window.evaluate_js(f"addMessage('system', {json.dumps(msg)});")
            self.window.evaluate_js("onVoiceFinished();")
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
        if self.window:
            self.window.evaluate_js("onVoiceFinished();")

        if texto_voz:
            safe_text = json.dumps(f"🎤 {texto_voz}")
            self.window.evaluate_js(f"addMessage('user', {safe_text});")
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
        motor_ia.MODO_ACTUAL = modo
        
        nombres_modelos = {
            "general": "🧠 Modelo: Gemini Flash",
            "planificador": "🧠 Modelo: DeepSeek V4 (Thinking)",
            "programador": "🧠 Modelo: DeepSeek V4 (Fast)"
        }
        
        # Actualizamos el texto del modelo en el frontend
        lbl_text = json.dumps(nombres_modelos[modo])
        self.window.evaluate_js(f"document.getElementById('lbl_modelo').innerText = {lbl_text};")

        if modo in ["planificador", "programador"]:
            # USAMOS EL DIÁLOGO NATIVO DE PYWEBVIEW (Modo Carpeta)
            resultado = self.window.create_file_dialog(webview.FOLDER_DIALOG)
            
            if resultado and len(resultado) > 0:
                ruta = resultado[0]
                motor_ia.WORKSPACE_ACTUAL = ruta
                msg = f"Workspace anclado: {ruta}"
                self.window.evaluate_js(f"addMessage('system', {json.dumps(msg)});")

    def adjuntar(self):
        """Javascript llama a esto al hacer click en el clip"""
        # USAMOS EL DIÁLOGO NATIVO DE PYWEBVIEW (Modo Archivo Múltiple)
        rutas = self.window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True)
        
        if rutas:
            cadenas = " ".join([f"[adjunto: {r}]" for r in rutas])
            cadenas_js = json.dumps(cadenas + " ")
            self.window.evaluate_js(f"document.getElementById('user-input').value += {cadenas_js};")

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
    
    # Arrancamos la aplicación
    webview.start()