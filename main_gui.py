import customtkinter as ctk
import threading
import keyboard
import time
import sys

# Importaciones de tu backend
from config import TECLA_HABLAR
from modulos.ia import enviar_a_gemini
from modulos.audio import capturar_voz_micro, detener_voz
import modulos.audio as audio_modulo

# ─── Paleta de colores (inspirada en Claude.ai) ───────────────────────────────
BG_MAIN       = "#1c1917"
BG_SIDEBAR    = "#141410"
BG_CHAT       = "#1c1917"
BG_INPUT      = "#292524"
BG_USER_MSG   = "#292524"
BG_AI_MSG     = "transparent"
ACCENT        = "#cc785c"
ACCENT_HOVER  = "#b8674d"
TEXT_PRIMARY  = "#e7e5e4"
TEXT_DIM      = "#57534e"
TEXT_USER     = "#e7e5e4"
TEXT_AI       = "#d6d3d1"
BORDER_COLOR  = "#292524"
BORDER_INPUT  = "#3c3835"

FONT_SANS     = ("Segoe UI", 14)
FONT_SANS_SM  = ("Segoe UI", 11)
FONT_SANS_MD  = ("Segoe UI", 13)
FONT_UI       = ("Segoe UI", 12)
FONT_UI_SM    = ("Segoe UI", 10)

MAX_USER_LINES   = 5
LINE_HEIGHT_PX   = 21
USER_BUBBLE_MAX_H = MAX_USER_LINES * LINE_HEIGHT_PX + 20

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# ─────────────────────────────────────────────────────────────────────────────
class LogRedirector:
    def __init__(self, target_widget):
        self.target = target_widget
    def write(self, string):
        if string.strip():
            # Evitamos agregar un salto de línea extra si el string ya lo trae
            self.target.after(0, lambda: self._add_log(string.strip()))
    def flush(self): pass
    def _add_log(self, text):
        self.target.configure(state="normal")
        self.target.insert("end", text + "\n")
        self.target.see("end")
        self.target.configure(state="disabled")

# ─────────────────────────────────────────────────────────────────────────────
class UserBubble(ctk.CTkFrame):
    MAX_WIDTH_RATIO = 0.65

    def __init__(self, parent, texto: str, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)

        self._pill = ctk.CTkFrame(
            self, fg_color=BG_USER_MSG, corner_radius=16,
            border_width=1, border_color=BORDER_COLOR
        )
        self._spacer = ctk.CTkFrame(self, fg_color="transparent")
        self._spacer.pack(side="left", fill="both", expand=True)
        self._pill.pack(side="right", padx=(0, 4))

        self._tb = ctk.CTkTextbox(
            self._pill, fg_color="transparent",
            font=FONT_SANS, text_color=TEXT_USER,
            wrap="word", border_width=0,
            activate_scrollbars=False,
            height=LINE_HEIGHT_PX + 20,
            width=300
        )
        self._tb.pack(padx=14, pady=(10, 10))
        self._tb.insert("1.0", texto)
        self._tb.configure(state="disabled")

        self.after(10, self._ajustar)

    def _ajustar(self):
        parent_w = self.winfo_width() or self.master.winfo_width()
        max_w = max(200, int(parent_w * self.MAX_WIDTH_RATIO))
        tb_w = max_w - 28 - 2
        self._tb.configure(width=tb_w)
        self.update_idletasks()

        try:
            count_result = self._tb._textbox.count("1.0", "end", "displaylines")
            lineas = count_result[0] if count_result else 1
        except Exception:
            lineas = 1

        if lineas <= MAX_USER_LINES:
            h = lineas * LINE_HEIGHT_PX + 20
            self._tb.configure(height=h, activate_scrollbars=False)
        else:
            self._tb.configure(height=USER_BUBBLE_MAX_H, activate_scrollbars=True)
            self._tb._textbox.yview_moveto(1.0)

# ─────────────────────────────────────────────────────────────────────────────
class AIBubble(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=4, pady=(6, 2))
        ctk.CTkLabel(
            header, text="◆", font=("Segoe UI", 12),
            text_color=ACCENT, width=20
        ).pack(side="left", padx=(2, 4))
        ctk.CTkLabel(
            header, text="OmniAssistant",
            font=("Segoe UI", 11, "bold"), text_color=TEXT_DIM
        ).pack(side="left")

        self.textbox = ctk.CTkTextbox(
            self, fg_color="transparent",
            font=FONT_SANS_MD, text_color=TEXT_AI,
            wrap="word", activate_scrollbars=False,
            border_width=0, height=LINE_HEIGHT_PX + 10
        )
        self.textbox.pack(fill="x", padx=(28, 16), pady=(0, 10))
        self.textbox.configure(state="disabled")

    def append_text(self, texto: str):
        self.textbox.configure(state="normal")
        self.textbox.insert("end", texto)
        self.textbox.configure(state="disabled")
        self._ajustar_altura()

    def _ajustar_altura(self):
        self.update_idletasks()
        try:
            count_result = self.textbox._textbox.count("1.0", "end", "displaylines")
            lineas = count_result[0] if count_result else 1
            self.textbox.configure(height=max(LINE_HEIGHT_PX + 10, lineas * LINE_HEIGHT_PX + 10))
        except Exception:
            pass

# ─────────────────────────────────────────────────────────────────────────────
class OmniApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        ancho, alto = 920, 660
        pw, ph = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{ancho}x{alto}+{(pw-ancho)//2}+{(ph-alto)//2}")
        self.title("OmniAssistant")
        self.configure(fg_color=BG_MAIN)
        self.resizable(True, True)
        self.minsize(640, 420)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main_area() # Contenedor principal para pestañas
        
        self.burbuja_ia_actual: AIBubble | None = None
        
        # Iniciar el motor de voz en segundo plano
        threading.Thread(target=self.motor_microfono, daemon=True).start()

    def _build_main_area(self):
        # CORRECCIÓN: Quitamos el 'transparent' de segmented_button_fg_color
        self.tabs = ctk.CTkTabview(
            self, 
            fg_color="transparent", 
            segmented_button_fg_color=BG_INPUT,
            segmented_button_selected_color=ACCENT,
            segmented_button_selected_hover_color=ACCENT_HOVER
        )
        self.tabs.grid(row=0, column=1, sticky="nsew")
        self.tab_chat = self.tabs.add("Chat")
        self.tab_logs = self.tabs.add("Logs")
        
        self._build_chat_area(self.tab_chat)
        self._build_log_area(self.tab_logs)

    def _build_log_area(self, parent):
        self.log_box = ctk.CTkTextbox(parent, fg_color=BG_SIDEBAR, text_color="#a8a29e", font=("Consolas", 12))
        self.log_box.pack(fill="both", expand=True, padx=10, pady=10)
        self.log_box.configure(state="disabled")
        sys.stdout = LogRedirector(self.log_box)

    # ── Sidebar ────────────────────────────────────────────────────────────────
    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, width=210, fg_color=BG_SIDEBAR, corner_radius=0)
        sb.grid(row=0, column=0, rowspan=2, sticky="nsew")
        sb.grid_propagate(False)
        sb.grid_columnconfigure(0, weight=1)
        sb.grid_rowconfigure(8, weight=1)

        ctk.CTkLabel(
            sb, text="◆ OmniAssistant",
            font=("Segoe UI", 14, "bold"), text_color=ACCENT
        ).grid(row=0, column=0, padx=16, pady=(22, 2), sticky="w")

        ctk.CTkLabel(
            sb, text="Asistente local", font=FONT_UI_SM, text_color=TEXT_DIM
        ).grid(row=1, column=0, padx=16, pady=(0, 14), sticky="w")

        ctk.CTkFrame(sb, height=1, fg_color=BORDER_COLOR).grid(
            row=2, column=0, padx=12, sticky="ew", pady=2
        )

        botones = [
            ("＋  Nueva conversación", self._nueva_conversacion),
            ("⚙   Configuración",      lambda: None),
            ("◉   Anclar proyecto",    lambda: None),
        ]
        for i, (txt, cmd) in enumerate(botones, start=3):
            ctk.CTkButton(
                sb, text=txt, anchor="w", font=FONT_UI,
                fg_color="transparent", hover_color="#252220",
                text_color=TEXT_PRIMARY, corner_radius=6, command=cmd
            ).grid(row=i, column=0, padx=8, pady=2, sticky="ew")

        ctk.CTkLabel(
            sb, text="v0.1.0", font=FONT_UI_SM, text_color=TEXT_DIM
        ).grid(row=9, column=0, padx=16, pady=14, sticky="sw")
        sb.grid_rowconfigure(9, weight=1)

    # ── Área de chat ────────────────────────────────────────────────────────────
    def _build_chat_area(self, parent):
        self.chat_scroll = ctk.CTkScrollableFrame(
            parent, fg_color=BG_CHAT, corner_radius=0,
            scrollbar_button_color="#3c3835",
            scrollbar_button_hover_color="#57534e"
        )
        self.chat_scroll.pack(fill="both", expand=True)
        self.chat_scroll.grid_columnconfigure(0, weight=1)

        self._welcome_label = ctk.CTkLabel(
            self.chat_scroll,
            text="¿En qué puedo ayudarte hoy?",
            font=("Segoe UI", 24, "bold"), text_color="#3c3835"
        )
        self._welcome_label.pack(expand=True, pady=(100, 0))
        
        self._build_input_bar()

    # ── Input bar ───────────────────────────────────────────────────────────────
    def _build_input_bar(self):
        outer = ctk.CTkFrame(self, fg_color=BG_MAIN, corner_radius=0)
        outer.grid(row=1, column=1, sticky="ew")
        outer.grid_columnconfigure(0, weight=1)

        bar = ctk.CTkFrame(
            outer, fg_color=BG_INPUT, corner_radius=14,
            border_width=1, border_color=BORDER_INPUT
        )
        bar.grid(row=0, column=0, padx=28, pady=(10, 4), sticky="ew")
        bar.grid_columnconfigure(0, weight=1)

        self.entry = ctk.CTkTextbox(
            bar, height=46, fg_color="transparent",
            font=FONT_SANS, text_color=TEXT_PRIMARY,
            wrap="word", activate_scrollbars=False, border_width=0
        )
        self.entry.grid(row=0, column=0, padx=(16, 6), pady=6, sticky="ew")
        self.entry.bind("<Return>",       self._on_enter)
        self.entry.bind("<Shift-Return>", self._on_shift_enter)
        self._set_placeholder()

        self.btn_send = ctk.CTkButton(
            bar, text="▲", width=40, height=40,
            corner_radius=10, fg_color=ACCENT, hover_color=ACCENT_HOVER,
            font=("Segoe UI", 13, "bold"), text_color="#1c1917",
            command=self.enviar_mensaje
        )
        self.btn_send.grid(row=0, column=1, padx=(0, 8), pady=6)

        ctk.CTkLabel(
            outer, text="Enter · enviar   Shift+Enter · nueva línea",
            font=FONT_UI_SM, text_color=TEXT_DIM
        ).grid(row=1, column=0, pady=(2, 10))

    # ── Teclado y Eventos ───────────────────────────────────────────────────────
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

    def _restore_placeholder(self, event=None):
        if not self.entry.get("1.0", "end").strip():
            self.entry.insert("1.0", "Escribí tu mensaje...")
            self.entry.configure(text_color=TEXT_DIM)
            self._placeholder_active = True

    def _on_enter(self, event):
        self.enviar_mensaje()
        return "break"

    def _on_shift_enter(self, event):
        return  

    # ── Lógica de Voz y Mensajes ────────────────────────────────────────────────
    def motor_microfono(self):
        """Hilo que escucha la tecla F8 para capturar voz"""
        while True:
            try:
                if audio_modulo.hablando_actualmente and keyboard.is_pressed('space'):
                    detener_voz()
                    while keyboard.is_pressed('space'): time.sleep(0.05)
                    continue

                if keyboard.is_pressed(TECLA_HABLAR):
                    if audio_modulo.hablando_actualmente: 
                        detener_voz()
                    
                    texto_voz = capturar_voz_micro()
                    
                    if texto_voz:
                        self.after(0, self._agregar_usuario, f"🎤 {texto_voz}")
                        self.burbuja_ia_actual = None
                        
                        threading.Thread(target=enviar_a_gemini, args=(texto_voz, True, self.callback_ia), daemon=True).start()
                    
                    while keyboard.is_pressed(TECLA_HABLAR): 
                        time.sleep(0.05)
                time.sleep(0.02)
            except Exception:
                pass

    def enviar_mensaje(self):
        if self._placeholder_active:
            return
        texto = self.entry.get("1.0", "end").strip()
        if not texto:
            return

        if hasattr(self, "_welcome_label") and self._welcome_label.winfo_exists():
            self._welcome_label.destroy()

        self.entry.delete("1.0", "end")
        self._placeholder_active = False

        self._agregar_usuario(texto)
        self.burbuja_ia_actual = None

        threading.Thread(target=enviar_a_gemini, args=(texto, False, self.callback_ia), daemon=True).start()

    def callback_ia(self, remitente, texto: str, color=None, nueva_linea=True):
        def _update():
            if hasattr(self, "_welcome_label") and self._welcome_label.winfo_exists():
                self._welcome_label.destroy()
            
            if not self.burbuja_ia_actual:
                self.burbuja_ia_actual = AIBubble(self.chat_scroll)
                self.burbuja_ia_actual.pack(fill="x", padx=16, pady=(2, 6))
            self.burbuja_ia_actual.append_text(texto)
            self._scroll_abajo()
        self.after(0, _update)

    def _agregar_usuario(self, texto: str):
        if hasattr(self, "_welcome_label") and self._welcome_label.winfo_exists():
            self._welcome_label.destroy()
            
        burbuja = UserBubble(self.chat_scroll, texto)
        burbuja.pack(fill="x", padx=16, pady=(6, 2))
        self.update_idletasks()
        self._scroll_abajo()

    def _scroll_abajo(self):
        self.chat_scroll._parent_canvas.yview_moveto(1.0)

    def _nueva_conversacion(self):
        for w in self.chat_scroll.winfo_children():
            w.destroy()
        self.burbuja_ia_actual = None
        self._welcome_label = ctk.CTkLabel(
            self.chat_scroll,
            text="¿En qué puedo ayudarte hoy?",
            font=("Segoe UI", 24, "bold"), text_color="#3c3835"
        )
        self._welcome_label.pack(expand=True, pady=(100, 0))


if __name__ == "__main__":
    app = OmniApp()
    app.mainloop()