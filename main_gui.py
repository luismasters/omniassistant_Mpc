import os
import customtkinter as ctk
from customtkinter import filedialog
import threading
import keyboard
import time
import sys
import re
import tkinter as tk
import tkinter.font as tkfont

# Importaciones del backend
from config import TECLA_HABLAR
from modulos.ia import enviar_a_gemini
from modulos.audio_custom import hablar_no_bloqueante, capturar_voz_micro, detener_voz
import modulos.audio_custom as audio_modulo
import modulos.ia as motor_ia
from modulos.memoria import guardar_snapshot, iniciar_radar_proyecto, guardar_recuerdo
from modulos.archivos import leer_contenido_archivo
from modulos.gamepad_control import GestorGamepad

# ─── Paleta ───────────────────────────────────────────────────────────────────
BG_MAIN        = "#141414"
BG_SIDEBAR     = "#0d0d0d"
BG_CHAT        = "#141414"
BG_INPUT       = "#1e1e1e"
BG_USER_MSG    = "#1e1e2e"
BG_CODE        = "#0d0d1a"
BG_TABLE_HDR   = "#16162a"
BG_TABLE_ROW   = "#111120"
BG_TABLE_ALT   = "#0f0f1c"
ACCENT         = "#7c3aed"
ACCENT_HOVER   = "#6d28d9"
ACCENT_SOFT    = "#3b1f6e"
ACCENT_SECUNDARIO = "#5eead4"   # cian suave — jerarquía secundaria (hints, firma visual)
TEXT_PRIMARY   = "#f0f0f0"
TEXT_DIM       = "#4a4a5a"
TEXT_USER      = "#e8e8f0"
TEXT_AI        = "#d1d1e0"
BORDER_COLOR   = "#1e1e2e"
BORDER_INPUT   = "#2a2a3e"
BORDER_CODE    = "#2d2d4e"
BORDER_TABLE   = "#2a2a4a"
SIDEBAR_LINE   = "#2a2a3e"

SYN = {
    "keyword":  "#c084fc",
    "string":   "#86efac",
    "comment":  "#6b7280",
    "number":   "#fbbf24",
    "builtin":  "#67e8f9",
    "default":  "#e0e0ff",
}

_F  = "Segoe UI"
_FM = "Consolas"
TAMANO_BASE = 15
FONT_CHAT    = (_F, TAMANO_BASE)
FONT_CHAT_MD = (_F, TAMANO_BASE)
FONT_UI      = (_F, TAMANO_BASE - 1)
FONT_UI_SM   = (_F, TAMANO_BASE - 2)
FONT_CODE    = (_FM, TAMANO_BASE - 1)
_TK_SIZE     = -TAMANO_BASE
_TK_SIZE_CO  = -(TAMANO_BASE - 1)

MAX_USER_LINES    = 5
LINE_HEIGHT_PX    = 24
USER_BUBBLE_MAX_H = MAX_USER_LINES * LINE_HEIGHT_PX + 20

# ─── Padding horizontal del chat: RESPONSIVO ─────────────────────────────────
# Antes era una constante fija (CHAT_PAD_X = 110), que a ventana completa se ve
# bien (~22% del ancho) pero al achicar la ventana hacia el minsize se comía
# ~34% del ancho disponible, dejando el chat angosto. Ahora se calcula como un
# porcentaje del ancho actual de la ventana, con piso y techo para que nunca
# quede ni pegado al borde ni absurdamente ancho en pantallas grandes.
CHAT_PAD_X_MIN   = 24
CHAT_PAD_X_MAX   = 140
CHAT_PAD_X_RATIO = 0.09
CHAT_PAD_X       = 110  # valor de referencia usado antes del primer cálculo dinámico

def calcular_chat_pad_x(ancho_ventana: int) -> int:
    return max(CHAT_PAD_X_MIN, min(CHAT_PAD_X_MAX, int(ancho_ventana * CHAT_PAD_X_RATIO)))

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

import config as _config_module

class _StateProxy:
    def __init__(self):
        self._historial_por_modo = {}

    @property
    def modo_actual(self):
        return _config_module.estado.modo_actual
    @modo_actual.setter
    def modo_actual(self, v):
        _config_module.estado.cambiar_modo(v)

    @property
    def workspace_actual(self):
        return _config_module.estado.workspace_actual
    @workspace_actual.setter
    def workspace_actual(self, v):
        _config_module.estado.cambiar_workspace(v)

    @property
    def snapshot_actual(self):
        return _config_module.estado.snapshot_actual
    @snapshot_actual.setter
    def snapshot_actual(self, v):
        _config_module.estado.cambiar_snapshot(v)

    @property
    def contexto_chat(self):
        return _config_module.estado.contexto_chat
    @contexto_chat.setter
    def contexto_chat(self, v):
        # FIX: antes asignaba directo (`_config_module.estado.contexto_chat = v`),
        # saltándose el lock de EstadoGlobal. Se usa en _cambiar_modo() al
        # restaurar el historial de un modo guardado — si eso coincide con
        # otro hilo escribiendo contexto_chat (ej. el radar de cambios de
        # memoria.py), había condición de carrera. Ahora pasa por el método
        # thread-safe centralizado.
        _config_module.estado.reemplazar_contexto_chat(v)

    @property
    def archivos_en_memoria(self):
        return _config_module.estado.archivos_en_memoria

    @property
    def documento_volatil(self):
        return _config_module.estado.documento_volatil
    @documento_volatil.setter
    def documento_volatil(self, v):
        _config_module.estado.cambiar_documento_volatil(v)

    @property
    def modelo_seleccionado(self):
        return _config_module.estado.modelo_seleccionado
    @modelo_seleccionado.setter
    def modelo_seleccionado(self, v):
        _config_module.estado.cambiar_modelo_seleccionado(v)

    def guardar_historial_modo(self, modo, visual, contexto):
        self._historial_por_modo[modo] = {
            "visual": visual[-50:],
            "contexto": contexto[-100:]
        }

    def cargar_historial_modo(self, modo):
        return self._historial_por_modo.get(modo, {"visual": [], "contexto": []})

state = _StateProxy()

# ─── RENDERIZADO DE MARKDOWN ────────────────────────────────────────────────
_KW  = r'\b(def|class|return|import|from|as|if|elif|else|for|while|with|try|except|finally|pass|break|continue|lambda|yield|in|not|and|or|is|None|True|False|raise|del|global|nonlocal|assert|async|await)\b'
_BLT = r'\b(print|len|range|int|str|float|list|dict|set|tuple|type|isinstance|hasattr|getattr|setattr|open|super|property|staticmethod|classmethod|zip|map|filter|sorted|enumerate|any|all|sum|min|max|abs|round|input|format|repr|id|dir)\b'
_STR = r'("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')'
_CMT = r'(#[^\n]*)'
_NUM = r'\b(\d+\.?\d*)\b'

def _highlight_code(tw, code):
    tw.configure(state="normal")
    tw.delete("1.0", "end")
    tw.insert("1.0", code)
    for tag, pat in [("comment",_CMT),("string",_STR),("keyword",_KW),("builtin",_BLT),("number",_NUM)]:
        for m in re.finditer(pat, code):
            tw.tag_add(tag, f"1.0+{m.start()}c", f"1.0+{m.end()}c")
    tw.configure(state="disabled")

def _strip_md(text):
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*',     r'\1', text)
    text = re.sub(r'`(.+?)`',       r'\1', text)
    return text.strip()

def _make_inline_text(parent, text, wrap_px):
    t = tk.Text(parent, bg=BG_CHAT, fg=TEXT_AI, font=(_F, _TK_SIZE),
                wrap="word", bd=0, relief="flat", highlightthickness=0,
                state="normal", cursor="xterm", height=1, width=1,
                selectbackground=ACCENT_SOFT, selectforeground=TEXT_PRIMARY)
    t.tag_configure("bold",        font=(_F, _TK_SIZE, "bold"))
    t.tag_configure("italic",      font=(_F, _TK_SIZE, "italic"))
    t.tag_configure("code_inline", font=(_FM, _TK_SIZE_CO),
                    foreground=SYN["builtin"], background=BG_CODE)
    pat = re.compile(r'\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`')
    last = 0
    for m in pat.finditer(text):
        if m.start() > last:
            t.insert("end", text[last:m.start()])
        if m.group(1):   t.insert("end", m.group(1), "bold")
        elif m.group(2): t.insert("end", m.group(2), "italic")
        elif m.group(3): t.insert("end", m.group(3), "code_inline")
        last = m.end()
    if last < len(text):
        t.insert("end", text[last:])
    t.configure(state="disabled")
    return t

def _auto_height(t, wrap_px=0):
    t.update_idletasks()
    try:
        result = t.count("1.0", "end", "displaylines")
        vis_lines = result[0] if result else 1
        t.configure(height=max(1, vis_lines))
    except Exception:
        try:
            lines = int(t.index("end-1c").split(".")[0])
            t.configure(height=max(1, lines))
        except Exception:
            pass

def _pack_text(t, parent, pady=(1,1)):
    t.pack(fill="x", pady=pady)
    t.update_idletasks()
    _auto_height(t)

def _parse_table(lines):
    rows = []
    for line in lines:
        if not line.strip().startswith("|"):
            return None
        cells = [c for c in line.strip().split("|")]
        if cells and cells[0].strip() == "":
            cells = cells[1:]
        if cells and cells[-1].strip() == "":
            cells = cells[:-1]
        rows.append(cells)
    return rows if len(rows) >= 2 else None

class EmoBezelFace(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="#0d0d0d", border_width=0, **kwargs)
        import math
        import random
        
        self.ancho = 180
        self.alto = 120
        
        # Canvas negro absoluto
        self.canvas = tk.Canvas(
            self, width=self.ancho, height=self.alto, 
            bg="#000000", highlightthickness=0
        )
        self.canvas.pack(pady=4)
        
        # --- Configuración Proporcional según Imagen de EMO ---
        self.izq_cx = 73
        self.der_cx = 107
        self.izq_cy = 52  
        self.der_cy = 52
        
        self.boca_cx = 90
        self.boca_cy = 82
        
        self.base_rx = 13.5
        self.base_ry = 15.0
        self.corner_radius = 6
        
        # --- Físicas e Interpolaciones ---
        self.estado = "idle"
        self.tiempo = 0.0
        self.tiempo_lagrima = 0.0
        self.msg_confirmacion = "HECHO"
        
        # Escala de ojos (X, Y)
        self.cur_zoom_x_izq, self.tgt_zoom_x_izq = 1.0, 1.0
        self.cur_zoom_y_izq, self.tgt_zoom_y_izq = 1.0, 1.0
        self.cur_zoom_x_der, self.tgt_zoom_x_der = 1.0, 1.0
        self.cur_zoom_y_der, self.tgt_zoom_y_der = 1.0, 1.0
        
        # Desplazamiento de mirada en bloque (Saccades)
        self.cur_look_x, self.tgt_look_x = 0.0, 0.0
        self.cur_look_y, self.tgt_look_y = 0.0, 0.0
        
        # Colores temáticos neón según emoción
        self.colores = {
            "idle": "#00f0ff",      # Cyan EMO
            "listening": "#00f0ff", # Cyan EMO
            "thinking": "#bd00ff",  # Púrpura
            "talking": "#39ff14",   # Verde
            "happy": "#00ffcc",     # Turquesa
            "angry": "#ff5500",     # Naranja
            "sad": "#3b82f6",       # Azul
            "error": "#ff0033",     # Rojo
            "confirm": "#39ff14"    # Verde confirmación
        }
        
        # Iniciar bucles
        self.loop_render()
        self.loop_parpadeo()
        self.loop_saccades()

    def cambiar_estado(self, nuevo_estado, msg=""):
        self.estado = nuevo_estado
        self.tiempo = 0.0
        self.tiempo_lagrima = 0.0
        self.tgt_look_x = 0.0
        self.tgt_look_y = 0.0
        
        if msg:
            self.msg_confirmacion = msg
        
        if nuevo_estado == "idle":
            self.tgt_zoom_x_izq = 1.0
            self.tgt_zoom_y_izq = 1.0
            self.tgt_zoom_x_der = 1.0
            self.tgt_zoom_y_der = 1.0
            
        elif nuevo_estado == "listening":
            self.tgt_zoom_x_izq = 1.12
            self.tgt_zoom_y_izq = 1.12
            self.tgt_zoom_x_der = 1.12
            self.tgt_zoom_y_der = 1.12
            
        elif nuevo_estado == "thinking":
            self.tgt_zoom_x_izq = 0.95
            self.tgt_zoom_y_izq = 0.85
            self.tgt_zoom_x_der = 0.95
            self.tgt_zoom_y_der = 0.85
            self.tgt_look_x = -4.0
            self.tgt_look_y = -3.0
            
        elif nuevo_estado == "talking":
            self.tgt_zoom_x_izq = 1.0
            self.tgt_zoom_y_izq = 1.0
            self.tgt_zoom_x_der = 1.0
            self.tgt_zoom_y_der = 1.0
            
        elif nuevo_estado == "happy":
            self.tgt_zoom_x_izq = 1.0
            self.tgt_zoom_y_izq = 1.0
            self.tgt_zoom_x_der = 1.0
            self.tgt_zoom_y_der = 1.0
            
        elif nuevo_estado == "angry":
            self.tgt_zoom_x_izq = 1.0
            self.tgt_zoom_y_izq = 0.8
            self.tgt_zoom_x_der = 1.0
            self.tgt_zoom_y_der = 0.8
            
        elif nuevo_estado == "sad":
            self.tgt_zoom_x_izq = 0.95
            self.tgt_zoom_y_izq = 0.85
            self.tgt_zoom_x_der = 0.95
            self.tgt_zoom_y_der = 0.85
            self.tgt_look_y = 2.0
            
        elif nuevo_estado == "error":
            self.tgt_zoom_x_izq = 0.85
            self.tgt_zoom_y_izq = 0.85
            self.tgt_zoom_x_der = 0.85
            self.tgt_zoom_y_der = 0.85
            
        elif nuevo_estado == "confirm":
            self.tgt_zoom_x_izq = 1.1
            self.tgt_zoom_y_izq = 1.1
            self.tgt_zoom_x_der = 1.1
            self.tgt_zoom_y_der = 1.1

    def loop_render(self):
        import math
        import random
        
        self.canvas.delete("all")
        self.tiempo += 0.04
        self.tiempo_lagrima = (self.tiempo_lagrima + 0.3) % 20.0
        
        # Detección automática del estado "talking" basándose en el motor de audio
        if self.estado not in ["confirm", "error", "thinking", "listening"]:
            if audio_modulo.hablando_actualmente:
                if self.estado != "talking":
                    self.cambiar_estado("talking")
            else:
                if self.estado == "talking":
                    self.cambiar_estado("idle")
        
        # Interpolaciones de escala y mirada
        self.cur_zoom_x_izq += (self.tgt_zoom_x_izq - self.cur_zoom_x_izq) * 0.20
        self.cur_zoom_y_izq += (self.tgt_zoom_y_izq - self.cur_zoom_y_izq) * 0.20
        self.cur_zoom_x_der += (self.tgt_zoom_x_der - self.cur_zoom_x_der) * 0.20
        self.cur_zoom_y_der += (self.tgt_zoom_y_der - self.cur_zoom_y_der) * 0.20
        
        self.cur_look_x += (self.tgt_look_x - self.cur_look_x) * 0.20
        self.cur_look_y += (self.tgt_look_y - self.cur_look_y) * 0.20
        
        zx_i, zy_i = self.cur_zoom_x_izq, self.cur_zoom_y_izq
        zx_d, zy_d = self.cur_zoom_x_der, self.cur_zoom_y_der
        
        # Temblores en error/guiño
        err_x = 0; err_y = 0
        if self.estado == "error":
            err_x = random.randint(-1, 1)
            err_y = random.randint(-1, 1)
        elif self.estado == "confirm":
            err_y = int(1.5 * math.sin(self.tiempo * 20))
            
        cy_i = self.izq_cy + err_y
        cy_d = self.der_cy + err_y
        
        # Respiración en Idle
        if self.estado == "idle":
            resp = 1.0 + 0.02 * math.sin(self.tiempo * 2)
            zx_i *= resp; zy_i *= resp
            zx_d *= resp; zy_d *= resp
            
        # Animación de ojos al hablar
        elif self.estado == "talking":
            onda = 0.95 + 0.06 * abs(math.sin(self.tiempo * 15))
            zy_i *= onda
            zy_d *= onda
            
        # Flotación en Listening
        elif self.estado == "listening":
            flot = 2.0 * math.sin(self.tiempo * 3)
            cy_i += flot
            cy_d += flot

        cx_izq = self.izq_cx + self.cur_look_x + err_x
        cx_der = self.der_cx + self.cur_look_x + err_x

        color = self.colores.get(self.estado, "#00f0ff")

        # 1. Dibujar Contorno Grisáceo de EMO (Marco Plateado/Gris Estático)
        self.dibujar_contorno_gris_emo()

        # 2. Dibujar Ojos / Guiño (Wink) en Confirmación
        self.dibujar_ojo_intellar(cx_izq, cy_i, self.base_rx * zx_i, self.base_ry * zy_i, color, izquierdo=True)
        self.dibujar_ojo_intellar(cx_der, cy_d, self.base_rx * zx_d, self.base_ry * zy_d, color, izquierdo=False)
        
        # 3. Dibujar Boca
        boca_x = self.boca_cx + self.cur_look_x * 0.7 + err_x
        boca_y = self.boca_cy + self.cur_look_y * 0.5 + err_y
        self.dibujar_boca_eilik(boca_x, boca_y, color)
        
        # 4. Si es modo CONFIRM, dibujar texto de acción truncado/limpio
        if self.estado == "confirm":
            msg_disp = self.msg_confirmacion
            if len(msg_disp) > 28:
                msg_disp = msg_disp[:25] + "..."
            self.canvas.create_text(
                self.ancho // 2, 106,
                text=msg_disp.upper(),
                font=("Consolas", 7, "bold"),
                fill=color, justify="center"
            )
        
        if self.estado == "error" and random.random() < 0.12:
            self.canvas.delete("all")
            
        self.after(20, self.loop_render)

    def dibujar_contorno_gris_emo(self):
        """Dibuja un contorno redondeado grisáceo/plateado de 4px."""
        x1, y1 = 30, 12
        x2, y2 = 150, 108
        r = 18
        c_gris_oscuro = "#5a5a63"
        c_plateado = "#9ca3af"
        
        # Borde gris oscuro
        self.canvas.create_arc(x1, y1, x1 + 2*r, y1 + 2*r, start=90, extent=90, style="arc", outline=c_gris_oscuro, width=4)
        self.canvas.create_arc(x2 - 2*r, y1, x2, y1 + 2*r, start=0, extent=90, style="arc", outline=c_gris_oscuro, width=4)
        self.canvas.create_arc(x1, y2 - 2*r, x1 + 2*r, y2, start=180, extent=90, style="arc", outline=c_gris_oscuro, width=4)
        self.canvas.create_arc(x2 - 2*r, y2 - 2*r, x2, y2, start=270, extent=90, style="arc", outline=c_gris_oscuro, width=4)
        self.canvas.create_line(x1 + r, y1, x2 - r, y1, fill=c_gris_oscuro, width=4)
        self.canvas.create_line(x1 + r, y2, x2 - r, y2, fill=c_gris_oscuro, width=4)
        self.canvas.create_line(x1, y1 + r, x1, y2 - r, fill=c_gris_oscuro, width=4)
        self.canvas.create_line(x2, y1 + r, x2, y2 - r, fill=c_gris_oscuro, width=4)
        
        # Línea de brillo plateado
        self.canvas.create_arc(x1, y1, x1 + 2*r, y1 + 2*r, start=90, extent=90, style="arc", outline=c_plateado, width=1.5)
        self.canvas.create_arc(x2 - 2*r, y1, x2, y1 + 2*r, start=0, extent=90, style="arc", outline=c_plateado, width=1.5)
        self.canvas.create_arc(x1, y2 - 2*r, x1 + 2*r, y2, start=180, extent=90, style="arc", outline=c_plateado, width=1.5)
        self.canvas.create_arc(x2 - 2*r, y2 - 2*r, x2, y2, start=270, extent=90, style="arc", outline=c_plateado, width=1.5)
        self.canvas.create_line(x1 + r, y1, x2 - r, y1, fill=c_plateado, width=1.5)
        self.canvas.create_line(x1 + r, y2, x2 - r, y2, fill=c_plateado, width=1.5)
        self.canvas.create_line(x1, y1 + r, x1, y2 - r, fill=c_plateado, width=1.5)
        self.canvas.create_line(x2, y1 + r, x2, y2 - r, fill=c_plateado, width=1.5)

    def dibujar_ojo_intellar(self, cx, cy, rx, ry, color, izquierdo=True):
        import math
        
        if rx <= 0 or ry <= 0:
            return
            
        if self.estado == "confirm":
            if izquierdo:
                # Guiño: Arco feliz
                self.canvas.create_arc(
                    cx - rx, cy - ry + 6, cx + rx, cy + ry + 6,
                    start=30, extent=120, style="arc",
                    outline=color, width=5.0
                )
                self.canvas.create_arc(
                    cx - rx, cy - ry + 6, cx + rx, cy + ry + 6,
                    start=35, extent=110, style="arc",
                    outline="#ffffff", width=1.5
                )
            else:
                # Ojo derecho normal
                x1, y1 = cx - rx, cy - ry
                x2, y2 = cx + rx, cy + ry
                r = min(self.corner_radius, rx, ry)
                self.canvas.create_oval(x1, y1, x1 + 2*r, y1 + 2*r, fill=color, outline="")
                self.canvas.create_oval(x2 - 2*r, y1, x2, y1 + 2*r, fill=color, outline="")
                self.canvas.create_oval(x1, y2 - 2*r, x1 + 2*r, y2, fill=color, outline="")
                self.canvas.create_oval(x2 - 2*r, y2 - 2*r, x2, y2, fill=color, outline="")
                self.canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=color, outline="")
                self.canvas.create_rectangle(x1, y1 + r, x2, y2 - r, fill=color, outline="")
            return
            
        if self.estado == "happy":
            self.canvas.create_arc(
                cx - rx, cy - ry + 6, cx + rx, cy + ry + 6,
                start=30, extent=120, style="arc",
                outline=color, width=5.0
            )
            self.canvas.create_arc(
                cx - rx, cy - ry + 6, cx + rx, cy + ry + 6,
                start=35, extent=110, style="arc",
                outline="#ffffff", width=1.5
            )
            return

        x1, y1 = cx - rx, cy - ry
        x2, y2 = cx + rx, cy + ry
        r = min(self.corner_radius, rx, ry)
        
        self.canvas.create_oval(x1, y1, x1 + 2*r, y1 + 2*r, fill=color, outline="")
        self.canvas.create_oval(x2 - 2*r, y1, x2, y1 + 2*r, fill=color, outline="")
        self.canvas.create_oval(x1, y2 - 2*r, x1 + 2*r, y2, fill=color, outline="")
        self.canvas.create_oval(x2 - 2*r, y2 - 2*r, x2, y2, fill=color, outline="")
        
        self.canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=color, outline="")
        self.canvas.create_rectangle(x1, y1 + r, x2, y2 - r, fill=color, outline="")
        
        # Máscaras de recorte
        if self.estado == "angry":
            dir_c = 1 if izquierdo else -1
            pts = [
                cx - rx - 5, cy - ry - 5 + (6 * dir_c),
                cx + rx + 5, cy - ry - 5 - (6 * dir_c),
                cx + rx + 5, cy - ry + 2,
                cx - rx - 5, cy - ry + 2
            ]
            self.canvas.create_polygon(pts, fill="#000000", outline="")
            
        elif self.estado in ["sad", "error"]:
            dir_c = 1 if izquierdo else -1
            pts = [
                cx - rx - 5, cy - ry - 5 - (5 * dir_c),
                cx + rx + 5, cy - ry - 5 + (5 * dir_c),
                cx + rx + 5, cy - ry + 4,
                cx - rx - 5, cy - ry + 4
            ]
            self.canvas.create_polygon(pts, fill="#000000", outline="")
            
            # Lágrima deslizante
            if self.estado == "sad":
                tx = cx - rx * 0.5 if izquierdo else cx + rx * 0.5
                ty = cy + ry * 0.8 + self.tiempo_lagrima * 0.5
                self.canvas.create_oval(tx - 2.0, ty, tx + 2.0, ty + 6.0, fill="#3b82f6", outline="")
                self.canvas.create_polygon(tx - 2.0, ty + 2, tx, ty - 1, tx + 2.0, ty + 2, fill="#3b82f6", outline="")

    def dibujar_boca_eilik(self, cx, cy, color):
        import math
        
        if self.estado == "happy" or self.estado == "confirm":
            self.canvas.create_arc(
                cx - 10, cy - 7, cx + 10, cy + 7,
                start=180, extent=180, style="pieslice",
                fill=color, outline=""
            )
            self.canvas.create_line(
                cx - 10, cy, cx + 10, cy,
                fill="#ffffff", width=1.5, capstyle="round"
            )
            
        elif self.estado in ["sad", "angry"]:
            self.canvas.create_arc(
                cx - 8, cy, cx + 8, cy + 10,
                start=0, extent=180, style="arc",
                outline=color, width=2.5
            )
            
        elif self.estado == "listening":
            r_dot = 2.5 + 1.0 * math.sin(self.tiempo * 3.5)
            self.canvas.create_oval(
                cx - r_dot, cy - r_dot, cx + r_dot, cy + r_dot,
                fill=color, outline=""
            )
            
        elif self.estado == "talking":
            ancho_col = 3.0
            espaciado = 5
            for i in range(-2, 3):
                fase = abs(i)
                h = 2.5 + 10.0 * abs(math.sin(self.tiempo * 15 - fase * 0.7))
                x = cx + i * espaciado
                self.canvas.create_line(
                    x, cy - h/2, x, cy + h/2,
                    fill=color, width=ancho_col, capstyle="round"
                )
            
        elif self.estado == "error":
            self.canvas.create_line(
                cx - 9, cy, cx - 4, cy - 2, cx, cy + 2, cx + 4, cy - 2, cx + 9, cy,
                fill=color, width=2.5, capstyle="round"
            )
            
        else: # idle, thinking
            self.canvas.create_line(
                cx - 7, cy, cx + 7, cy,
                fill=color, width=2.5, capstyle="round"
            )

    def loop_parpadeo(self):
        import random
        if self.estado in ["idle", "listening", "talking", "happy", "confirm"]:
            ant_y_izq = self.tgt_zoom_y_izq
            ant_y_der = self.tgt_zoom_y_der
            
            self.tgt_zoom_y_izq = 0.01
            self.tgt_zoom_y_der = 0.01
            
            self.after(90, lambda: self.restaurar_ojos(ant_y_izq, ant_y_der))
            
        self.after(random.randint(2500, 6000), self.loop_parpadeo)

    def restaurar_ojos(self, y_izq, y_der):
        if self.estado in ["idle", "listening", "talking", "happy", "confirm"]:
            self.tgt_zoom_y_izq = y_izq
            self.tgt_zoom_y_der = y_der

    def loop_saccades(self):
        import random
        if self.estado in ["idle", "listening"]:
            if random.random() < 0.65:
                self.tgt_look_x = random.uniform(-6.0, 6.0)
                self.tgt_look_y = random.uniform(-3.0, 3.0)
            else:
                self.tgt_look_x = 0.0
                self.tgt_look_y = 0.0
                
        self.after(random.randint(1200, 3500), self.loop_saccades)

class CodeBlock(ctk.CTkFrame):
    def __init__(self, parent, code, lang="", **kwargs):
        super().__init__(parent, fg_color=BG_CODE, corner_radius=8,
                         border_width=1, border_color=BORDER_CODE, **kwargs)
        hdr = ctk.CTkFrame(self, fg_color="#0a0a18", corner_radius=0)
        hdr.pack(fill="x")
        ctk.CTkLabel(hdr, text=lang or "code", font=(_FM, TAMANO_BASE - 3),
                     text_color=TEXT_DIM).pack(side="left", padx=10, pady=5)
        ctk.CTkButton(hdr, text="copiar", width=60, height=24,
                      fg_color="transparent", hover_color=ACCENT_SOFT,
                      font=FONT_UI_SM, text_color=TEXT_DIM, corner_radius=4,
                      command=lambda: (self.clipboard_clear(), self.clipboard_append(code))
                      ).pack(side="right", padx=8, pady=4)
        ctk.CTkFrame(self, height=1, fg_color=BORDER_CODE).pack(fill="x")
        self._txt = tk.Text(self, bg=BG_CODE, fg=SYN["default"], font=FONT_CODE,
                            wrap="none", bd=0, relief="flat", highlightthickness=0,
                            state="disabled", cursor="arrow", padx=14, pady=10)
        self._txt.pack(fill="x")
        for tag, color in SYN.items():
            self._txt.tag_configure(tag, foreground=color)
        _highlight_code(self._txt, code)
        self._txt.configure(height=min(code.count("\n") + 1, 30))

class TableBlock(ctk.CTkFrame):
    def __init__(self, parent, rows, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        if not rows:
            return
        headers = rows[0]
        data    = [r for r in rows[2:] if r]
        n_cols = len(headers)
        for col_i, header in enumerate(headers):
            cell = ctk.CTkFrame(self, fg_color=BG_TABLE_HDR, corner_radius=0,
                                border_width=1, border_color=BORDER_TABLE)
            cell.grid(row=0, column=col_i, sticky="nsew", padx=(0,1), pady=(0,1))
            self.grid_columnconfigure(col_i, weight=1)
            ctk.CTkLabel(cell, text=_strip_md(header.strip()),
                         font=(_F, TAMANO_BASE - 1, "bold"), text_color=TEXT_PRIMARY,
                         anchor="w").pack(padx=10, pady=6, fill="x")
        for row_i, row in enumerate(data):
            bg = BG_TABLE_ROW if row_i % 2 == 0 else BG_TABLE_ALT
            for col_i in range(n_cols):
                cell_text = row[col_i].strip() if col_i < len(row) else ""
                cell = ctk.CTkFrame(self, fg_color=bg, corner_radius=0,
                                    border_width=1, border_color=BORDER_TABLE)
                cell.grid(row=row_i+1, column=col_i, sticky="nsew", padx=(0,1), pady=(0,1))
                ctk.CTkLabel(cell, text=_strip_md(cell_text),
                             font=FONT_CHAT_MD, text_color=TEXT_AI,
                             anchor="w", justify="left", wraplength=0
                             ).pack(padx=10, pady=5, fill="x")

class UserBubble(ctk.CTkFrame):
    MAX_WIDTH_RATIO = 0.60
    def __init__(self, parent, texto, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._pill = ctk.CTkFrame(self, fg_color=BG_USER_MSG, corner_radius=18,
                                  border_width=1, border_color=BORDER_COLOR)
        ctk.CTkFrame(self, fg_color="transparent").pack(side="left", fill="both", expand=True)
        self._pill.pack(side="right", padx=(0, 2))
        self._tb = ctk.CTkTextbox(self._pill, fg_color="transparent", font=FONT_CHAT,
                                  text_color=TEXT_USER, wrap="word", border_width=0,
                                  height=LINE_HEIGHT_PX + 20, width=300)
        self._tb.pack(padx=16, pady=(12, 12))
        self._tb.insert("1.0", texto)
        self._tb.configure(state="disabled")
        self.after(10, self._ajustar)

    def reajustar(self):
        """Alias público: permite recalcular el ancho de la burbuja cuando
        la ventana cambia de tamaño después de que la burbuja ya existe.
        Antes, el ancho se calculaba una única vez al crearse, y quedaba
        obsoleto si el usuario agrandaba/achicaba la ventana después."""
        self._ajustar()

    def _ajustar(self):
        parent_w = self.winfo_width() or self.master.winfo_width()
        max_w = max(200, int(parent_w * self.MAX_WIDTH_RATIO))
        self._tb.configure(width=max_w - 34)
        self.update_idletasks()
        try:
            lineas = self._tb._textbox.count("1.0","end","displaylines")[0] or 1
        except Exception:
            lineas = 1
        if lineas <= MAX_USER_LINES:
            self._tb.configure(height=lineas * LINE_HEIGHT_PX + 24)
        else:
            self._tb.configure(height=USER_BUBBLE_MAX_H)
            self._tb._textbox.yview_moveto(1.0)

class AIBubble(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._raw       = ""
        self._streaming = True
        self._wrap_px   = 600
        self._mostrando_carga = False

        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=4, pady=(12, 4))
        ctk.CTkLabel(hdr, text="◆", font=(_F, TAMANO_BASE), text_color=ACCENT, width=20
                     ).pack(side="left", padx=(0, 6))
        nombres_modelos = {
            "general": "Gemini Flash",
            "programador": "DeepSeek V4 (Reasoner)",
            "planificador": "DeepSeek V4 (Reasoner)"
        }
        modo_actual = state.modo_actual
        nombre_modelo = nombres_modelos.get(modo_actual, "IA")
        ctk.CTkLabel(hdr, text=f"Argus ({nombre_modelo})", font=(_F, TAMANO_BASE - 1, "bold"), text_color=TEXT_DIM
                     ).pack(side="left")
        self._btn_copy = ctk.CTkButton(
            hdr, text="⎘", width=28, height=28,
            corner_radius=6,
            fg_color="transparent",
            hover_color=ACCENT_SOFT,
            border_width=1, border_color="#2a2a3e",
            font=(_F, TAMANO_BASE - 1), text_color=TEXT_DIM,
            command=self._copiar_respuesta
        )
        self._btn_copy.pack(side="right", padx=(0, 4))

        self._content = ctk.CTkFrame(self, fg_color="transparent")
        self._content.pack(fill="x", padx=(28, 4), pady=(0, 14))

        self._stream_box = ctk.CTkTextbox(
            self._content, fg_color="transparent",
            font=FONT_CHAT_MD, text_color=TEXT_AI,
            wrap="word", border_width=0, height=LINE_HEIGHT_PX + 10)
        self._stream_box.pack(fill="x")
        self._stream_box.configure(state="disabled")

    def mostrar_carga(self):
        self._mostrando_carga = True
        self._stream_box.configure(state="normal")
        self._stream_box.insert("end", " ...")
        self._stream_box.configure(state="disabled")
        self._ajustar_stream()

    def append_text(self, texto):
        if self._mostrando_carga:
            self._stream_box.configure(state="normal")
            self._stream_box.delete("1.0", "end")
            self._stream_box.configure(state="disabled")
            self._mostrando_carga = False
        if not texto:
            return
        self._raw += texto
        if self._streaming:
            self._stream_box.configure(state="normal")
            self._stream_box.insert("end", texto)
            self._stream_box.configure(state="disabled")
            self._ajustar_stream()

    def _ajustar_stream(self):
        self.update_idletasks()
        try:
            r = self._stream_box._textbox.count("1.0","end","displaylines")
            lineas = r[0] if r else 1
            self._stream_box.configure(
                height=max(LINE_HEIGHT_PX + 10, lineas * LINE_HEIGHT_PX + 10))
        except Exception:
            pass

    def _copiar_respuesta(self):
        if not self._raw.strip():
            return
        self.clipboard_clear()
        self.clipboard_append(self._raw)
        self._btn_copy.configure(text="✓", text_color="#86efac")
        self.after(1500, lambda: self._btn_copy.configure(text="⎘", text_color=TEXT_DIM))

    def finalizar(self):
        if not self._streaming:
            return
        self._streaming = False
        self._stream_box.destroy()
        self.update_idletasks()
        self._wrap_px = max(300, self.winfo_width() - 60)
        if self._raw.strip():
            self._render_markdown(self._raw)

    def _render_markdown(self, text):
        CODE_STRONG = re.compile(
            r'^(import |from \w+ import |def |class |\s+def |\s+class |'
            r'\s+return |\s+if |\s+elif |\s+else:|\s+for |\s+while |\s+try:'
            r'|\s+except|\s+with |\s+raise |\s+yield |\s+self\.\w|'
            r'var |const |let |function |#include|public |private |static )'
        )

        def _is_code_context(block):
            strong = sum(1 for l in block.splitlines() if CODE_STRONG.match(l))
            return strong >= 2

        CODE_FENCE = re.compile(r'```(\w*)\n?([\s\S]*?)(?:```|$)', re.MULTILINE)
        segments, last = [], 0
        for m in CODE_FENCE.finditer(text):
            if m.start() > last:
                segments.append(("text", text[last:m.start()]))
            body = m.group(2).rstrip()
            if body:
                segments.append(("code", body, m.group(1)))
            last = m.end()
        if last < len(text):
            segments.append(("text", text[last:]))

        final = []
        for seg in segments:
            if seg[0] == "code":
                final.append(seg)
                continue
            raw = seg[1]
            lines = raw.split("\n")
            intro, rest = [], []
            in_code = False
            for line in lines:
                if not in_code and CODE_STRONG.match(line):
                    in_code = True
                if in_code:
                    rest.append(line)
                else:
                    intro.append(line)
            intro_text = "\n".join(intro).strip()
            rest_text  = "\n".join(rest).strip()
            if intro_text:
                final.append(("text", intro_text))
            if rest_text:
                if _is_code_context(rest_text):
                    final.append(("code", rest_text, ""))
                else:
                    final.append(("text", rest_text))

        merged = []
        for seg in final:
            if seg[0] == "text" and not seg[1].strip():
                merged.append(seg)
                continue
            merged.append(seg)

        final2 = []
        i2 = 0
        while i2 < len(merged):
            seg = merged[i2]
            if seg[0] == "code":
                j = i2 + 1
                combined = seg[1]
                lang = seg[2]
                while j < len(merged):
                    nxt = merged[j]
                    if nxt[0] == "text" and not nxt[1].strip():
                        j += 1
                        continue
                    if nxt[0] == "code":
                        combined += "\n" + nxt[1]
                        lang = lang or nxt[2]
                        j += 1
                        continue
                    break
                final2.append(("code", combined, lang))
                i2 = j
            else:
                final2.append(seg)
                i2 += 1

        for seg in final2:
            if seg[0] == "code":
                CodeBlock(self._content, seg[1], lang=seg[2]).pack(fill="x", pady=(4, 4))
            else:
                self._render_text_block(self._content, seg[1])

    def _render_text_block(self, parent, text):
        lines = text.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            if not stripped:
                i += 1
                continue
            if stripped.startswith("### "):
                self._add_label(parent, stripped[4:], (_F,15,"bold"), TEXT_PRIMARY, (8,2))
                i += 1; continue
            if stripped.startswith("## "):
                self._add_label(parent, stripped[3:], (_F,16,"bold"), TEXT_PRIMARY, (10,2))
                i += 1; continue
            if stripped.startswith("# "):
                self._add_label(parent, stripped[2:], (_F,18,"bold"), TEXT_PRIMARY, (12,2))
                i += 1; continue
            if re.match(r'^[-*_]{3,}$', stripped):
                ctk.CTkFrame(parent, height=1, fg_color=BORDER_COLOR).pack(fill="x", pady=8)
                i += 1; continue
            if stripped.startswith("|"):
                table_lines = []
                while i < len(lines) and lines[i].strip().startswith("|"):
                    table_lines.append(lines[i])
                    i += 1
                rows = _parse_table(table_lines)
                if rows:
                    TableBlock(parent, rows).pack(fill="x", pady=(6,6))
                continue
            if stripped.startswith(("- ","* ","• ")):
                items = []
                while i < len(lines):
                    s2 = lines[i].strip()
                    if s2.startswith(("- ","* ","• ")):
                        items.append("  •  " + s2[2:])
                        i += 1
                    elif s2 and not s2.startswith(("- ","* ","• ")) and not re.match(r'^\d+\. ', s2):
                        break
                    elif not s2:
                        i += 1
                    else:
                        break
                self._add_text_block(parent, "\n".join(items))
                continue
            if re.match(r'^\d+\. ', stripped):
                items = []
                while i < len(lines):
                    s2 = lines[i].strip()
                    if re.match(r'^\d+\. ', s2):
                        items.append("  " + s2)
                        i += 1
                    elif s2 and not re.match(r'^\d+\. ', s2):
                        break
                    elif not s2:
                        i += 1
                    else:
                        break
                self._add_text_block(parent, "\n".join(items))
                continue
            para_lines = []
            while i < len(lines) and lines[i].strip() and \
                  not lines[i].strip().startswith(("#","- ","* ","• ","|")) and \
                  not re.match(r'^\d+\. ', lines[i].strip()) and \
                  not re.match(r'^[-*_]{3,}$', lines[i].strip()):
                para_lines.append(lines[i].strip())
                i += 1
            if para_lines:
                self._add_text_block(parent, " ".join(para_lines))

    def _add_text_block(self, parent, text, pady=(1, 1)):
        t = tk.Text(parent, bg=BG_CHAT, fg=TEXT_AI, font=(_F, _TK_SIZE),
                    wrap="word", bd=0, relief="flat", highlightthickness=0,
                    state="normal", cursor="xterm", height=1, width=1,
                    selectbackground=ACCENT_SOFT, selectforeground=TEXT_PRIMARY)
        pat = re.compile(r'\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`')
        t.tag_configure("bold",        font=(_F, _TK_SIZE, "bold"))
        t.tag_configure("italic",      font=(_F, _TK_SIZE, "italic"))
        t.tag_configure("code_inline", font=(_FM, _TK_SIZE_CO),
                        foreground=SYN["builtin"], background=BG_CODE)
        for line_idx, line in enumerate(text.split("\n")):
            if line_idx > 0:
                t.insert("end", "\n")
            last = 0
            for m in pat.finditer(line):
                if m.start() > last:
                    t.insert("end", line[last:m.start()])
                if m.group(1):   t.insert("end", m.group(1), "bold")
                elif m.group(2): t.insert("end", m.group(2), "italic")
                elif m.group(3): t.insert("end", m.group(3), "code_inline")
                last = m.end()
            if last < len(line):
                t.insert("end", line[last:])
        t.configure(state="disabled")
        _pack_text(t, parent, pady)

    def _add_label(self, parent, text, font, color, pady=(2,2)):
        px_font = (font[0], -abs(font[1])) + font[2:] if len(font) >= 2 else font
        t = tk.Text(parent, bg=BG_CHAT, fg=color, font=px_font,
                    wrap="word", bd=0, relief="flat", highlightthickness=0,
                    state="normal", cursor="xterm", height=1, width=1,
                    selectbackground=ACCENT_SOFT, selectforeground=TEXT_PRIMARY)
        t.insert("1.0", _strip_md(text))
        t.configure(state="disabled")
        _pack_text(t, parent, pady)

    def _add_inline(self, parent, text):
        pat = re.compile(r'\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`')
        has_md = bool(pat.search(text))
        if not has_md:
            t = tk.Text(parent, bg=BG_CHAT, fg=TEXT_AI, font=(_F, _TK_SIZE),
                        wrap="word", bd=0, relief="flat", highlightthickness=0,
                        state="normal", cursor="xterm", height=1, width=1,
                        selectbackground=ACCENT_SOFT, selectforeground=TEXT_PRIMARY)
            t.insert("1.0", text)
            t.configure(state="disabled")
            _pack_text(t, parent)
            return
        t = _make_inline_text(parent, text, self._wrap_px)
        _pack_text(t, parent)

class LogRedirector:
    def __init__(self, target_widget):
        self.target = target_widget
        self._buffer = ""
    def write(self, string):
        self._buffer += string
        if "\n" in self._buffer:
            partes = self._buffer.split("\n")
            for linea in partes[:-1]:
                if linea.strip():
                    texto = linea.strip()
                    self.target.after(0, lambda t=texto: self._add_log(t))
            self._buffer = partes[-1]
    def flush(self):
        if self._buffer.strip():
            texto = self._buffer.strip()
            self._buffer = ""
            self.target.after(0, lambda t=texto: self._add_log(t))
    def _add_log(self, text):
        self.target.configure(state="normal")
        self.target.insert("end", text + "\n")
        self.target.see("end")
        self.target.configure(state="disabled")

class OmniApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ancho, alto = 980, 700
        pw, ph = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{ancho}x{alto}+{(pw-ancho)//2}+{(ph-alto)//2}")
        self.title("Argus")
        self.configure(fg_color=BG_MAIN)
        self.resizable(True, True)
        # Antes 640x420: era tan angosto que, sumado al sidebar (215px fijo)
        # y al padding del chat, dejaba prácticamente sin aire el área de
        # conversación. Se sube un poco el piso para que la ventana siga
        # siendo usable incluso en su tamaño mínimo.
        self.minsize(720, 460)

        self.grid_columnconfigure(0, weight=0, minsize=215)
        self.grid_columnconfigure(1, weight=0, minsize=1)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._modo_pausa_gaming = False
        self._buffer_inicio_ia = ""
        self._emocion_extraida = False

        # ─── Padding responsivo del chat ─────────────────────────────────
        # Se recalcula dinámicamente según el ancho real de la ventana en
        # vez de usar una constante fija (ver calcular_chat_pad_x arriba).
        self.chat_pad_x = calcular_chat_pad_x(ancho)
        self._resize_job = None

        self._build_sidebar()
        self._build_separator()
        self._build_main_area()

        self.burbuja_ia_actual = None
        self.texto_sin_enviar  = ""
        self._stop_micro_event = threading.Event()
        self._detener_extraccion_perfil = threading.Event()
        threading.Thread(target=self.motor_microfono, daemon=True).start()
        threading.Thread(target=self._ciclo_extraccion_perfil, daemon=True).start()

        self._gestor_gamepad = GestorGamepad(
            callback_activar_voz=self._activar_voz_desde_gamepad
        )

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Se registra DESPUÉS de construir la UI para que el primer evento
        # de <Configure> (que dispara CTk al crear la ventana) no intente
        # tocar widgets que todavía no existen.
        self.bind("<Configure>", self._on_window_resize)

    def _on_window_resize(self, event):
        """
        Handler de resize de la ventana principal. Filtra eventos de
        widgets hijos (bind en Tkinter dispara <Configure> también para
        cambios internos de layout, no solo para la ventana), y aplica
        debounce con self.after() para no recalcular en cada píxel
        mientras el usuario arrastra el borde de la ventana.
        """
        if event.widget is not self:
            return
        if self._resize_job is not None:
            try:
                self.after_cancel(self._resize_job)
            except Exception:
                pass
        self._resize_job = self.after(80, self._aplicar_padding_responsivo)

    def _aplicar_padding_responsivo(self):
        self._resize_job = None
        nuevo_pad = calcular_chat_pad_x(self.winfo_width())
        if nuevo_pad == self.chat_pad_x:
            return
        self.chat_pad_x = nuevo_pad

        # Barra de entrada
        if hasattr(self, "_input_bar_frame") and self._input_bar_frame.winfo_exists():
            self._input_bar_frame.grid_configure(padx=self.chat_pad_x)

        # Burbujas y mensajes ya existentes en el chat
        for widget in self.chat_scroll.winfo_children():
            try:
                if isinstance(widget, (UserBubble, AIBubble)):
                    widget.pack_configure(padx=self.chat_pad_x)
                    if isinstance(widget, UserBubble):
                        widget.reajustar()
                elif isinstance(widget, ctk.CTkLabel):
                    texto = widget.cget("text")
                    if texto.startswith("⚙"):
                        widget.pack_configure(padx=self.chat_pad_x + 20)
            except Exception:
                pass

    def _activar_voz_desde_gamepad(self, condicion_sigue_presionado):
        if audio_modulo.hablando_actualmente:
            detener_voz()
        self.after(0, lambda: self.face_widget.cambiar_estado("listening"))
        self._buffer_inicio_ia = ""
        self._emocion_extraida = False
        texto_voz = capturar_voz_micro(condicion_seguir_grabando=condicion_sigue_presionado)
        self.after(0, lambda: self.face_widget.cambiar_estado("thinking" if texto_voz else "idle"))
        if texto_voz:
            self.after(0, self._agregar_usuario, f"🎮 {texto_voz}")
            self.burbuja_ia_actual = None
            threading.Thread(
                target=enviar_a_gemini,
                args=(texto_voz, True, self.callback_ia),
                daemon=True
            ).start()

    def _ciclo_extraccion_perfil(self):
        """
        Hilo de fondo que verifica periódicamente si se acumularon mensajes
        nuevos desde la última extracción de perfil. Cuando se alcanza el umbral
        (definido en perfil_usuario.UMBRAL_MENSAJES_EXTRACCION), dispara
        extraer_y_procesar_sesion() con la nueva arquitectura de hechos atómicos.
        """
        while not self._detener_extraccion_perfil.is_set():
            time.sleep(5)  # check cada 5 segundos
            try:
                import config as _cfg
                from modulos.perfil_usuario import (
                    extraer_y_procesar_sesion,
                    UMBRAL_MENSAJES_EXTRACCION
                )
                count = _cfg.estado.obtener_y_reiniciar_mensajes_pendientes()
                if count >= UMBRAL_MENSAJES_EXTRACCION:
                    mensajes = _cfg.estado.obtener_contexto_copia()
                    if mensajes:
                        extraer_y_procesar_sesion(mensajes[-count:])
            except Exception:
                try:
                    from modulos.logger import logger
                    logger.exception("Error en ciclo de extracción de perfil")
                except Exception:
                    pass

    def on_closing(self):
        self._detener_extraccion_perfil.set()
        self._stop_micro_event.set()
        # Extracción final de respaldo para capturar mensajes que no llegaron al umbral
        try:
            import config as _cfg
            from modulos.perfil_usuario import extraer_y_procesar_sesion
            count = _cfg.estado.obtener_y_reiniciar_mensajes_pendientes()
            mensajes = _cfg.estado.obtener_contexto_copia()
            if count > 0 and mensajes:
                extraer_y_procesar_sesion(mensajes[-count:])
                from modulos.logger import logger
                logger.info(f"📋 Perfil respaldado al cerrar ({count} mensajes)")
        except Exception:
            try:
                from modulos.logger import logger
                logger.exception("Error en extracción final de perfil")
            except Exception:
                pass
        try:
            self._gestor_gamepad.detener()
        except Exception:
            pass
        try:
            import modulos.audio_custom as _audio
            if _audio._modelo_whisper is not None:
                del _audio._modelo_whisper
                _audio._modelo_whisper = None
        except Exception:
            pass
        time.sleep(0.2)
        self.destroy()

    def _build_sidebar(self):
        import config
        sb = ctk.CTkFrame(self, fg_color=BG_SIDEBAR, corner_radius=0)
        sb.grid(row=0, column=0, rowspan=2, sticky="nsew")
        sb.grid_columnconfigure(0, weight=1)

        # NUEVO: Cara interactiva de EMO en el sidebar
        self.face_widget = EmoBezelFace(sb)
        self.face_widget.grid(row=0, column=0, pady=(15, 5))

        ctk.CTkLabel(sb, text="◆ Argus", font=(_F, TAMANO_BASE, "bold"),
                     text_color=ACCENT).grid(row=1, column=0, padx=18, pady=(12,2), sticky="w")
        self.lbl_modelo_activo = ctk.CTkLabel(
            sb, text="🧠 Modelo: Gemini Flash",
            font=FONT_UI_SM, text_color="#86efac"
        )
        self.lbl_modelo_activo.grid(row=2, column=0, padx=18, pady=(0,4), sticky="w")

        self.opt_modelo = ctk.CTkOptionMenu(
            sb,
            values=[
                "Por Defecto",
                "Gemini 3.1 Flash Lite",
                "DeepSeek Reasoner",
                "Groq Llama 3.3 70B",
                "Groq Llama 3.1 8B",
                "Groq Qwen 3.6 27B",
                "Groq GPT-OSS 120B"
            ],
            command=self._on_modelo_changed,
            font=FONT_UI_SM,
            fg_color="#1a1a2e",
            button_color="#23233c",
            button_hover_color="#303054",
            dropdown_fg_color="#131324",
            dropdown_hover_color="#23233c",
            dropdown_text_color=TEXT_PRIMARY,
            height=28
        )
        self.opt_modelo.grid(row=3, column=0, padx=18, pady=(0, 14), sticky="ew")
        self.opt_modelo.set("Por Defecto")

        ctk.CTkFrame(sb, height=1, fg_color=SIDEBAR_LINE).grid(
            row=4, column=0, padx=0, sticky="ew")

        textos_modelos = {
            "general":      "🧠 Modelo: Gemini Flash",
            "programador":  "🧠 Modelo: DeepSeek V4 (Reasoner)",
            "planificador": "🧠 Modelo: DeepSeek V4 (Reasoner)"
        }
        self.lbl_modelo_activo.configure(
            text=textos_modelos.get(state.modo_actual, textos_modelos["general"])
        )

        botones = [
            ("💬  Chat General",     lambda: self._cambiar_modo("general")),
            ("💻  Modo Programador", lambda: self._cambiar_modo("programador")),
        ]
        self.botones_ui = []
        for i, (txt, cmd) in enumerate(botones, start=5):
            btn = ctk.CTkButton(
                sb, text=txt, anchor="w", font=FONT_UI,
                fg_color="transparent", hover_color="#16162a",
                text_color=TEXT_PRIMARY, corner_radius=6,
                command=cmd
            )
            btn.grid(row=i, column=0, padx=10, pady=2, sticky="ew")
            self.botones_ui.append(btn)

        # ── Separador ──────────────────────────────────────────────────
        ctk.CTkFrame(sb, height=1, fg_color=SIDEBAR_LINE).grid(
            row=8, column=0, padx=0, sticky="ew", pady=(8, 0))

        # ── Botón Limpiar Contexto ─────────────────────────────────────
        ctk.CTkButton(
            sb, text="🧹  Limpiar contexto",
            anchor="w", font=FONT_UI,
            fg_color="transparent", hover_color="#16162a",
            text_color=TEXT_DIM, corner_radius=6,
            command=self._limpiar_contexto_directo
        ).grid(row=9, column=0, padx=10, pady=(4, 2), sticky="ew")

        # ── NUEVO: Botón Manual de Actualización de Memoria ───────────
        ctk.CTkButton(
            sb, text="🧠  Actualizar memoria",
            anchor="w", font=FONT_UI,
            fg_color="transparent", hover_color="#16162a",
            text_color=TEXT_DIM, corner_radius=6,
            command=self._actualizar_memoria_manual
        ).grid(row=10, column=0, padx=10, pady=(2, 2), sticky="ew")

        # ── Botón Modo Gaming ──────────────────────────────────────────
        self.btn_gaming = ctk.CTkButton(
            sb, text="🎮  Modo Gaming: OFF",
            anchor="w", font=FONT_UI,
            fg_color="transparent", hover_color="#16162a",
            text_color=TEXT_DIM, corner_radius=6,
            command=self._toggle_modo_gaming
        )
        self.btn_gaming.grid(row=11, column=0, padx=10, pady=(4, 2), sticky="ew")

        # ── Indicador de gamepad ───────────────────────────────────────
        self.lbl_gamepad = ctk.CTkLabel(
            sb, text="🎮 Mando: inactivo",
            font=FONT_UI_SM, text_color=TEXT_DIM
        )
        self.lbl_gamepad.grid(row=12, column=0, padx=18, pady=(2, 0), sticky="w")

        ctk.CTkLabel(
            sb, text="v0.3.1 — Optimizado",
            font=FONT_UI_SM, text_color=TEXT_DIM
        ).grid(row=14, column=0, padx=18, pady=16, sticky="sw")
        sb.grid_rowconfigure(14, weight=1)

    def _on_modelo_changed(self, valor):
        state.modelo_seleccionado = valor
        if valor == "Por Defecto":
            textos_modelos = {
                "general":      "🧠 Modelo: Gemini Flash",
                "programador":  "🧠 Modelo: DeepSeek V4 (Reasoner)",
                "planificador": "🧠 Modelo: DeepSeek V4 (Reasoner)"
            }
            txt = textos_modelos.get(state.modo_actual, "🧠 Modelo: Gemini Flash")
        else:
            txt = f"🧠 Modelo: {valor}"
        self.lbl_modelo_activo.configure(text=txt)
        self._agregar_sistema(f"🧠 Modelo cambiado a: {valor}")

    # ── NUEVO: Actualización manual de memoria (botón en sidebar) ────
    def _actualizar_memoria_manual(self):
        """
        Dispara extraer_y_procesar_sesion() manualmente en un hilo aparte,
        sin esperar el umbral de 20 mensajes. Muestra feedback al usuario.
        """
        import config as _cfg
        mensajes = _cfg.estado.obtener_contexto_copia()
        if not mensajes:
            self._agregar_sistema("🧠 No hay mensajes para analizar.")
            return
        self._agregar_sistema("🧠 Actualizando memoria de perfil...")
        threading.Thread(
            target=self._ejecutar_extraccion_manual,
            args=(mensajes,),
            daemon=True
        ).start()

    def _ejecutar_extraccion_manual(self, mensajes):
        """Ejecuta la extracción y muestra feedback al terminar."""
        try:
            from modulos.perfil_usuario import extraer_y_procesar_sesion
            extraer_y_procesar_sesion(mensajes)
            # Feedback en el hilo principal
            self.after(0, lambda: self._agregar_sistema(
                "🧠 Memoria de perfil actualizada."))
        except Exception as e:
            from modulos.logger import logger
            logger.exception("Error en extracción manual de perfil")
            self.after(0, lambda: self._agregar_sistema(
                f"❌ Error actualizando memoria: {str(e)[:80]}"))

    # ── NUEVO: Limpiar contexto directo, sin pasar por Gemini ─────────
    def _limpiar_contexto_directo(self):
        """
        Limpia el contexto DIRECTAMENTE sin pasar por Gemini.
        Útil cuando Argus entra en loop de alucinación.
        """
        import config
        config.estado.limpiar_memoria()
        self._agregar_sistema("🧹 Contexto limpiado. Argus empieza desde cero.")

    def _actualizar_estado_gamepad(self):
        try:
            if hasattr(self, '_gestor_gamepad') and self._gestor_gamepad._disponible:
                nombre = self._gestor_gamepad._joystick.get_name() if self._gestor_gamepad._joystick else "Conectado"
                nombre_corto = (nombre[:22] + "…") if len(nombre) > 22 else nombre
                self.lbl_gamepad.configure(text=f"🎮 {nombre_corto}", text_color="#86efac")
            else:
                self.lbl_gamepad.configure(text="🎮 Mando: no detectado", text_color=TEXT_DIM)
        except Exception:
            pass
        self.after(3000, self._actualizar_estado_gamepad)

    def _toggle_modo_gaming(self):
        import modulos.audio_custom as _audio

        if not self._modo_pausa_gaming:
            try:
                mandos = GestorGamepad.listar_mandos_disponibles()
            except Exception as e:
                self._agregar_sistema(f"🎮 Error al escanear mandos: {e}. Intentá reconectar el control.")
                return

            if not mandos:
                self._agregar_sistema("🎮 No se detectó ningún mando conectado. Conectá uno y volvé a intentar.")
                return

            indice_elegido = 0
            if len(mandos) > 1:
                indice_elegido = self._mostrar_selector_mando(mandos)
                if indice_elegido is None:
                    return
            else:
                indice_elegido = mandos[0]["indice"]
                self._agregar_sistema(f"🎮 Mando detectado: {mandos[0]['nombre']}")

            self._gestor_gamepad.detener()
            self._gestor_gamepad._stop_event.clear()
            self._gestor_gamepad.iniciar_con_indice(indice_elegido)

            if _audio._modelo_whisper is not None:
                try:
                    del _audio._modelo_whisper
                    _audio._modelo_whisper = None
                    self._agregar_sistema("🎮 Modo Gaming ON — Whisper descargado de VRAM. Micrófono de teclado en pausa.")
                except Exception as e:
                    self._agregar_sistema(f"🎮 Modo Gaming ON — Micrófono en pausa. (VRAM: {e})")
            else:
                self._agregar_sistema("🎮 Modo Gaming ON — Usá L3+R3 para hablar.")

            self._modo_pausa_gaming = True
            self.btn_gaming.configure(
                text="🎮  Modo Gaming: ON",
                text_color="#86efac",
                fg_color=ACCENT_SOFT
            )
            self.after(500, self._actualizar_estado_gamepad)

        else:
            self._gestor_gamepad.detener()
            self._agregar_sistema("🎮 Modo Gaming OFF — Control desconectado. Micrófono de teclado reactivado.")
            self._modo_pausa_gaming = False
            self.btn_gaming.configure(
                text="🎮  Modo Gaming: OFF",
                text_color=TEXT_DIM,
                fg_color="transparent"
            )
            self.lbl_gamepad.configure(text="🎮 Mando: inactivo", text_color=TEXT_DIM)

    def _mostrar_selector_mando(self, mandos):
        dialogo = ctk.CTkToplevel(self)
        dialogo.title("Elegir mando")
        dialogo.geometry("360x200")
        dialogo.resizable(False, False)
        dialogo.configure(fg_color=BG_SIDEBAR)
        dialogo.grab_set()
        dialogo.lift()
        dialogo.focus_force()

        resultado = {"indice": None}

        ctk.CTkLabel(
            dialogo,
            text="¿Qué mando querés usar?",
            font=(_F, TAMANO_BASE, "bold"),
            text_color=TEXT_PRIMARY
        ).pack(pady=(20, 10), padx=20)

        for mando in mandos:
            nombre_corto = (mando["nombre"][:38] + "…") if len(mando["nombre"]) > 38 else mando["nombre"]
            def _elegir(idx=mando["indice"], nombre=mando["nombre"]):
                resultado["indice"] = idx
                self._agregar_sistema(f"🎮 Mando seleccionado: {nombre}")
                dialogo.destroy()

            ctk.CTkButton(
                dialogo,
                text=nombre_corto,
                anchor="w",
                font=FONT_UI,
                fg_color=ACCENT_SOFT,
                hover_color=ACCENT,
                text_color=TEXT_PRIMARY,
                corner_radius=6,
                command=_elegir
            ).pack(fill="x", padx=20, pady=4)

        ctk.CTkButton(
            dialogo,
            text="Cancelar",
            font=FONT_UI,
            fg_color="transparent",
            hover_color="#16162a",
            text_color=TEXT_DIM,
            corner_radius=6,
            command=dialogo.destroy
        ).pack(pady=(4, 16))

        self.wait_window(dialogo)
        return resultado["indice"]

    def _cambiar_modo(self, nuevo_modo):
        import config
        if nuevo_modo == state.modo_actual:
            return

        if nuevo_modo in ["planificador", "programador"]:
            if not state.workspace_actual:
                ruta = filedialog.askdirectory(
                    title=f"Selecciona el proyecto para el Modo {nuevo_modo.capitalize()}"
                )
                if not ruta:
                    return
                state.workspace_actual = ruta
                nombre_proj = os.path.basename(ruta)
                estructura = []
                for raiz, carpetas, archivos in os.walk(ruta):
                    carpetas[:] = [d for d in carpetas if d not in ['.git','__pycache__','venv','node_modules']]
                    nivel = raiz.replace(ruta,'').count(os.sep)
                    ind  = ' ' * 4 * nivel
                    sind = ' ' * 4 * (nivel + 1)
                    estructura.append(f"{ind}📂 {os.path.basename(raiz)}/")
                    for f in archivos:
                        estructura.append(f"{sind}📄 {f}")
                arbol = f"Estructura del proyecto '{nombre_proj}':\n" + "\n".join(estructura)
                guardar_snapshot(ruta, arbol)
                state.snapshot_actual = arbol
                iniciar_radar_proyecto(ruta, ui_callback=self.callback_ia)

        visual = []
        for widget in self.chat_scroll.winfo_children():
            if isinstance(widget, UserBubble):
                try:
                    txt = widget._tb.get("1.0", "end").strip()
                    if txt:
                        visual.append(("usuario", txt))
                except Exception:
                    pass
            elif isinstance(widget, AIBubble):
                if widget._raw.strip():
                    visual.append(("ia", widget._raw))
            elif isinstance(widget, ctk.CTkLabel):
                try:
                    txt = widget.cget("text")
                    if txt and txt.startswith("⚙"):
                        visual.append(("sistema", txt[2:].strip()))
                except Exception:
                    pass

        if visual:
            state.guardar_historial_modo(state.modo_actual, visual, state.contexto_chat)

        state.modo_actual = nuevo_modo

        if state.modelo_seleccionado == "Por Defecto":
            textos_modelos = {
                "general":      "🧠 Modelo: Gemini Flash",
                "programador":  "🧠 Modelo: DeepSeek V4 (Reasoner)",
                "planificador": "🧠 Modelo: DeepSeek V4 (Reasoner)"
            }
            self.lbl_modelo_activo.configure(
                text=textos_modelos.get(nuevo_modo, textos_modelos["general"])
            )
        else:
            self.lbl_modelo_activo.configure(
                text=f"🧠 Modelo: {state.modelo_seleccionado}"
            )

        self._agregar_sistema(f"🔁 Cambiado a modo {nuevo_modo.upper()}")

        if not any(isinstance(w, (UserBubble, AIBubble)) for w in self.chat_scroll.winfo_children()):
            ruta_corta = os.path.basename(state.workspace_actual) if state.workspace_actual else ""
            mensajes = {
                "general":      "¿En qué puedo ayudarte hoy?",
                "programador":  f"💻 Modo Programador\n[ {ruta_corta} ]\n¿Qué vamos a diseñar o programar?",
                "planificador": f"📐 Modo Planificador\n[ {ruta_corta} ]\n(redirigido a Programador)"
            }
            self._welcome_label = ctk.CTkLabel(
                self.chat_scroll,
                text=mensajes.get(nuevo_modo, mensajes["programador"]),
                font=(_F, TAMANO_BASE + 6, "bold"), text_color="#2a2a3e"
            )
            self._welcome_label.pack(expand=True, pady=(120, 0))

        self._scroll_abajo()

    def _build_separator(self):
        sep = ctk.CTkFrame(self, width=1, fg_color=SIDEBAR_LINE, corner_radius=0)
        sep.grid(row=0, column=1, rowspan=2, sticky="ns")

    def _build_main_area(self):
        self.tabs = ctk.CTkTabview(
            self, fg_color="transparent",
            segmented_button_fg_color=BG_INPUT,
            segmented_button_selected_color=ACCENT,
            segmented_button_selected_hover_color=ACCENT_HOVER
        )
        self.tabs.grid(row=0, column=2, sticky="nsew")
        self.tab_chat = self.tabs.add("Chat")
        self.tab_logs = self.tabs.add("Logs")
        self._build_chat_area(self.tab_chat)
        self._build_log_area(self.tab_logs)

    def _build_log_area(self, parent):
        self.log_box = ctk.CTkTextbox(parent, fg_color=BG_SIDEBAR,
                                      text_color="#7c7c9c", font=("Consolas", 12),
                                      wrap="word")
        self.log_box.pack(fill="both", expand=True, padx=10, pady=10)
        self.log_box.configure(state="disabled")
        sys.stdout = LogRedirector(self.log_box)
        sys.stderr = LogRedirector(self.log_box)

    def _build_chat_area(self, parent):
        self.chat_scroll = ctk.CTkScrollableFrame(
            parent, fg_color=BG_CHAT, corner_radius=0,
            scrollbar_button_color="#2a2a3e",
            scrollbar_button_hover_color="#3d3d5c"
        )
        self.chat_scroll.pack(fill="both", expand=True)
        self.chat_scroll.grid_columnconfigure(0, weight=1)

        self._welcome_label = self._crear_bienvenida(
            self.chat_scroll,
            titulo="¿En qué puedo ayudarte hoy?",
            hint=f"Presioná {TECLA_HABLAR.upper()} o L3+R3 en tu mando para hablar"
        )
        self._build_input_bar()

    def _crear_bienvenida(self, parent, titulo, subtitulo=None, hint=None):
        """
        Pantalla de estado vacío del chat. Antes era un único CTkLabel con
        texto genérico ("¿En qué puedo ayudarte hoy?") que no reflejaba que
        Argus es, ante todo, un asistente de VOZ — cualquier chatbot de IA
        podría mostrar ese mismo texto. Ahora reutiliza el mismo acento "◆"
        que ya se usa en el header de las burbujas de Argus (firma visual
        consistente) y agrega el atajo real de activación por voz como
        contenido concreto del propio producto, no relleno decorativo.
        """
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        ctk.CTkLabel(frame, text="◆", font=(_F, TAMANO_BASE + 20),
                     text_color=ACCENT).pack(pady=(0, 10))
        ctk.CTkLabel(frame, text=titulo, font=(_F, TAMANO_BASE + 9, "bold"),
                     text_color="#3a3a4a", justify="center").pack()
        if subtitulo:
            ctk.CTkLabel(frame, text=subtitulo, font=FONT_UI,
                         text_color=TEXT_DIM, justify="center").pack(pady=(8, 0))
        if hint:
            ctk.CTkLabel(frame, text=hint, font=FONT_UI_SM,
                         text_color=ACCENT_SECUNDARIO, justify="center").pack(pady=(16, 0))
        frame.pack(expand=True, pady=(90, 0))
        return frame

    def _build_input_bar(self):
        outer = ctk.CTkFrame(self, fg_color=BG_MAIN, corner_radius=0)
        outer.grid(row=1, column=2, sticky="ew")
        outer.grid_columnconfigure(0, weight=1)

        bar = ctk.CTkFrame(outer, fg_color=BG_INPUT, corner_radius=16,
                           border_width=1, border_color=BORDER_INPUT)
        bar.grid(row=0, column=0, padx=self.chat_pad_x, pady=(12,4), sticky="ew")
        self._input_bar_frame = bar  # referencia para actualizar el padding en resize
        bar.grid_columnconfigure(0, weight=1)
        bar.grid_columnconfigure(1, weight=0)
        bar.grid_columnconfigure(2, weight=0)
        bar.grid_columnconfigure(3, weight=0)

        self.entry = ctk.CTkTextbox(bar, height=48, fg_color="transparent",
                                    font=FONT_CHAT, text_color=TEXT_PRIMARY,
                                    wrap="word", border_width=0)
        self.entry.grid(row=0, column=0, padx=(8,4), pady=6, sticky="ew")
        self.entry.bind("<Return>",       self._on_enter)
        self.entry.bind("<Shift-Return>", self._on_shift_enter)
        self._placeholder_active = True
        self._texto_real = ""
        self._set_placeholder()

        self.btn_attach = ctk.CTkButton(
            bar, text="📎", width=38, height=38,
            corner_radius=8, fg_color="transparent",
            hover_color=ACCENT_SOFT,
            font=(_F, TAMANO_BASE + 1), text_color=TEXT_DIM,
            command=self._adjuntar_archivo)
        self.btn_attach.grid(row=0, column=1, padx=(0,2), pady=6)

        self.btn_save_memory = ctk.CTkButton(
            bar, text="💾", width=38, height=38,
            corner_radius=8, fg_color="transparent",
            hover_color=ACCENT_SOFT,
            font=(_F, TAMANO_BASE + 1), text_color=TEXT_DIM,
            command=self._guardar_archivos_en_memoria)
        self.btn_save_memory.grid(row=0, column=2, padx=(0,2), pady=6)

        self.btn_send = ctk.CTkButton(bar, text="▲", width=42, height=42,
                                      corner_radius=10, fg_color=ACCENT,
                                      hover_color=ACCENT_HOVER,
                                      font=(_F, TAMANO_BASE, "bold"), text_color="#f0f0f0",
                                      command=self.enviar_mensaje)
        self.btn_send.grid(row=0, column=3, padx=(0,8), pady=6)

        ctk.CTkLabel(outer, text="Enter · enviar   Shift+Enter · nueva línea",
                     font=FONT_UI_SM, text_color=TEXT_DIM).grid(row=1, column=0, pady=(2,10))

    def _set_placeholder(self):
        self.entry.insert("1.0", "Escribí tu mensaje...")
        self.entry.configure(text_color=TEXT_DIM)
        self._placeholder_active = True
        self.entry.bind("<FocusIn>",  self._clear_placeholder)
        self.entry.bind("<FocusOut>", self._restore_placeholder)

    def _clear_placeholder(self, event=None):
        if self._placeholder_active:
            self.entry.delete("1.0", "end")
            self.entry.configure(text_color=TEXT_PRIMARY)
            self._placeholder_active = False
            if self._texto_real:
                self.entry.insert("1.0", self._texto_real)
                self._texto_real = ""

    def _restore_placeholder(self, event=None):
        contenido = self.entry.get("1.0", "end").strip()
        if not contenido:
            self.entry.insert("1.0", "Escribí tu mensaje...")
            self.entry.configure(text_color=TEXT_DIM)
            self._placeholder_active = True
        else:
            self._texto_real = contenido

    def _adjuntar_archivo(self):
        rutas = filedialog.askopenfilenames(
            title="Adjuntar archivos (contexto)",
            filetypes=[
                ("Todos los archivos", "*.*"),
                ("Python", "*.py"),
                ("Texto", "*.txt"),
                ("JSON", "*.json"),
                ("Markdown", "*.md"),
            ]
        )
        if rutas:
            self._clear_placeholder()
            for ruta in rutas:
                self.entry.insert("end", f"[adjunto: {ruta}]")

    def _guardar_archivos_en_memoria(self):
        rutas = filedialog.askopenfilenames(
            title="Guardar archivos en memoria",
            filetypes=[
                ("Todos los archivos", "*.*"),
                ("Python", "*.py"),
                ("Texto", "*.txt"),
                ("JSON", "*.json"),
                ("Markdown", "*.md"),
            ]
        )
        if not rutas:
            return

        contador = 0
        for ruta in rutas:
            nombre = os.path.basename(ruta)
            contenido = leer_contenido_archivo(ruta)
            if contenido.startswith("ERROR"):
                self._agregar_sistema(f"❌ No se pudo leer {nombre}: {contenido}")
                continue
            exito = guardar_recuerdo(
                texto_a_guardar=contenido,
                etiqueta_tema=f"Archivo: {nombre} (guardado manual)"
            )
            if exito:
                contador += 1
                self._agregar_sistema(f"✅ Guardado en memoria: {nombre}")
            else:
                self._agregar_sistema(f"❌ Error al guardar {nombre}")

        self._agregar_sistema(f"📦 {contador} archivo(s) guardados en la bóveda de memoria.")

    def _on_enter(self, event):
        self.enviar_mensaje(); return "break"

    def _on_shift_enter(self, event):
        return

    def motor_microfono(self):
        while not self._stop_micro_event.is_set():
            try:
                if self._modo_pausa_gaming:
                    time.sleep(0.1)
                    continue

                if audio_modulo.hablando_actualmente and keyboard.is_pressed('space'):
                    detener_voz()
                    while keyboard.is_pressed('space'):
                        time.sleep(0.05)
                    continue

                if keyboard.is_pressed(TECLA_HABLAR):
                    if audio_modulo.hablando_actualmente:
                        detener_voz()
                    self.after(0, lambda: self.face_widget.cambiar_estado("listening"))
                    self._buffer_inicio_ia = ""
                    self._emocion_extraida = False
                    texto_voz = capturar_voz_micro()
                    self.after(0, lambda: self.face_widget.cambiar_estado("thinking" if texto_voz else "idle"))
                    if texto_voz:
                        self.after(0, self._agregar_usuario, f"🎤 {texto_voz}")
                        self.burbuja_ia_actual = None
                        threading.Thread(
                            target=enviar_a_gemini,
                            args=(texto_voz, True, self.callback_ia),
                            daemon=True
                        ).start()
                    while keyboard.is_pressed(TECLA_HABLAR):
                        time.sleep(0.05)

                time.sleep(0.05)
            except Exception:
                pass

    def enviar_mensaje(self):
        if self._placeholder_active:
            return
        texto = self.entry.get("1.0","end").strip()
        if not texto:
            return
        if hasattr(self,"_welcome_label") and self._welcome_label.winfo_exists():
            self._welcome_label.destroy()
        self.entry.delete("1.0","end")
        self._placeholder_active = False
        self._texto_real = ""
        self._agregar_usuario(texto)
        self.burbuja_ia_actual = None
        self.face_widget.cambiar_estado("thinking")
        self._buffer_inicio_ia = ""
        self._emocion_extraida = False
        try:
            threading.Thread(target=enviar_a_gemini,
                             args=(texto, False, self.callback_ia),
                             daemon=True).start()
        except Exception as e:
            self._agregar_sistema(f"Error al enviar mensaje: {e}")

    def callback_ia(self, remitente, texto, color=None, nueva_linea=True):
        def _update():
            if hasattr(self,"_welcome_label") and self._welcome_label.winfo_exists():
                self._welcome_label.destroy()

            if remitente and remitente != "🤖 Argus" and texto.strip():
                if "Acción SO:" in texto:
                    msg_limpio = texto.replace("*", "").replace("(", "").replace(")", "").strip()
                    if "Acción SO:" in msg_limpio:
                        msg_limpio = msg_limpio.split("Acción SO:")[1].strip()
                    self.face_widget.cambiar_estado("confirm", msg_limpio)
                    self.after(3500, lambda: self.face_widget.cambiar_estado("idle") if self.face_widget.estado == "confirm" else None)
                elif texto.strip().startswith("❌"):
                    self.face_widget.cambiar_estado("error")
                    self.after(4000, lambda: self.face_widget.cambiar_estado("idle") if self.face_widget.estado == "error" else None)

                self._agregar_sistema(texto)
                self._scroll_abajo()
                return

            if nueva_linea and texto == "":
                if not self._emocion_extraida and self._buffer_inicio_ia:
                    if self.burbuja_ia_actual:
                        self.burbuja_ia_actual.append_text(self._buffer_inicio_ia)
                self._buffer_inicio_ia = ""
                self._emocion_extraida = False
                if self.burbuja_ia_actual:
                    self.burbuja_ia_actual.finalizar()
                    self.burbuja_ia_actual = None
                self._scroll_abajo()
                return

            texto_a_mostrar = texto
            if not self._emocion_extraida:
                self._buffer_inicio_ia += texto
                import re
                match = re.search(r"\[EMOTION:\s*(\w+)\]", self._buffer_inicio_ia)
                if match:
                    emocion = match.group(1).lower()
                    self.face_widget.cambiar_estado(emocion)
                    self._buffer_inicio_ia = re.sub(r"\[EMOTION:\s*\w+\]", "", self._buffer_inicio_ia)
                    self._emocion_extraida = True
                    texto_a_mostrar = self._buffer_inicio_ia
                    self._buffer_inicio_ia = ""
                elif len(self._buffer_inicio_ia) >= 45:
                    self._emocion_extraida = True
                    texto_a_mostrar = self._buffer_inicio_ia
                    self._buffer_inicio_ia = ""
                else:
                    texto_a_mostrar = ""

            if not self.burbuja_ia_actual:
                if self.face_widget.estado == "thinking":
                    self.face_widget.cambiar_estado("idle")
                self.burbuja_ia_actual = AIBubble(self.chat_scroll)
                self.burbuja_ia_actual.pack(fill="x", padx=self.chat_pad_x, pady=(2,6))
                self.burbuja_ia_actual.mostrar_carga()

            if texto_a_mostrar:
                self.burbuja_ia_actual.append_text(texto_a_mostrar)

            self.after(50, self._scroll_abajo)
        self.after(0, _update)

    def _agregar_sistema(self, texto):
        lbl = ctk.CTkLabel(self.chat_scroll, text=f"⚙ {texto}",
                           font=FONT_UI_SM, text_color=TEXT_DIM,
                           anchor="w", justify="left", wraplength=0)
        lbl.pack(fill="x", padx=self.chat_pad_x + 20, pady=(2,2))

    def _agregar_usuario(self, texto):
        if hasattr(self,"_welcome_label") and self._welcome_label.winfo_exists():
            self._welcome_label.destroy()
        burbuja = UserBubble(self.chat_scroll, texto)
        burbuja.pack(fill="x", padx=self.chat_pad_x, pady=(6,2))
        self.update_idletasks()
        self._scroll_abajo()

    def _scroll_abajo(self):
        self.after(10, self._scroll_abajo_impl)

    def _scroll_abajo_impl(self):
        try:
            if hasattr(self.chat_scroll, "_parent_canvas"):
                self.chat_scroll._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

if __name__ == "__main__":
    app = OmniApp()
    app.mainloop()