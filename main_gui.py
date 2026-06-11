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

# Importaciones de tu backend
from config import TECLA_HABLAR
from modulos.ia import enviar_a_gemini
from modulos.audio import capturar_voz_micro, detener_voz
import modulos.audio as audio_modulo
import modulos.ia as motor_ia
from modulos.memoria import guardar_snapshot

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
TEXT_PRIMARY   = "#f0f0f0"
TEXT_DIM       = "#4a4a5a"
TEXT_USER      = "#e8e8f0"
TEXT_AI        = "#d1d1e0"
BORDER_COLOR   = "#1e1e2e"
BORDER_INPUT   = "#2a2a3e"
BORDER_CODE    = "#2d2d4e"
BORDER_TABLE   = "#2a2a4a"
SIDEBAR_LINE   = "#2a2a3e"   # línea divisoria sidebar

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

# tk.Text nativo usa puntos tipográficos; negativo = píxeles (igual que CTk)
# Esto hace que el texto de la IA se vea del mismo tamaño que el del usuario
_TK_SIZE     = -TAMANO_BASE        # px equivalente para tk.Text normal
_TK_SIZE_CO  = -(TAMANO_BASE - 1)  # px equivalente para código inline

MAX_USER_LINES    = 5
LINE_HEIGHT_PX    = 24
USER_BUBBLE_MAX_H = MAX_USER_LINES * LINE_HEIGHT_PX + 20

# Márgenes tipo Bootstrap container — se aplica como padx en pack/grid
CHAT_PAD_X = 110

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


# ─── Helpers ──────────────────────────────────────────────────────────────────
_KW  = r'\b(def|class|return|import|from|as|if|elif|else|for|while|with|try|except|finally|pass|break|continue|lambda|yield|in|not|and|or|is|None|True|False|raise|del|global|nonlocal|assert|async|await)\b'
_BLT = r'\b(print|len|range|int|str|float|list|dict|set|tuple|type|isinstance|hasattr|getattr|setattr|open|super|property|staticmethod|classmethod|zip|map|filter|sorted|enumerate|any|all|sum|min|max|abs|round|input|format|repr|id|dir)\b'
_STR = r'("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')'
_CMT = r'(#[^\n]*)'
_NUM = r'\b(\d+\.?\d*)\b'

def _highlight_code(tw: tk.Text, code: str):
    tw.configure(state="normal")
    tw.delete("1.0", "end")
    tw.insert("1.0", code)
    for tag, pat in [("comment",_CMT),("string",_STR),("keyword",_KW),("builtin",_BLT),("number",_NUM)]:
        for m in re.finditer(pat, code):
            tw.tag_add(tag, f"1.0+{m.start()}c", f"1.0+{m.end()}c")
    tw.configure(state="disabled")

def _strip_md(text: str) -> str:
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*',     r'\1', text)
    text = re.sub(r'`(.+?)`',       r'\1', text)
    return text.strip()


# ─── CodeBlock ────────────────────────────────────────────────────────────────
class CodeBlock(ctk.CTkFrame):
    def __init__(self, parent, code: str, lang: str = "", **kwargs):
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


# ─── TableBlock ───────────────────────────────────────────────────────────────
class TableBlock(ctk.CTkFrame):
    """Renderiza tablas Markdown como grid de labels."""

    def __init__(self, parent, rows: list[list[str]], **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        if not rows:
            return

        headers = rows[0]
        data    = [r for r in rows[2:] if r]   # skip separator row

        # Calcular anchos de columna proporcionales
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


def _parse_table(lines: list[str]) -> list[list[str]] | None:
    """Devuelve lista de filas si las líneas forman una tabla MD, sino None."""
    rows = []
    for line in lines:
        if not line.strip().startswith("|"):
            return None
        cells = [c for c in line.strip().split("|")]
        # quitar primero y último si están vacíos (pipes de borde)
        if cells and cells[0].strip() == "":
            cells = cells[1:]
        if cells and cells[-1].strip() == "":
            cells = cells[:-1]
        rows.append(cells)
    return rows if len(rows) >= 2 else None


# ─── Texto inline con negrita/itálica ─────────────────────────────────────────
def _make_inline_text(parent, text: str, wrap_px: int) -> tk.Text:
    """tk.Text de una o más líneas con soporte **bold** *italic* `code`."""
    t = tk.Text(parent, bg=BG_CHAT, fg=TEXT_AI, font=(_F, _TK_SIZE),
                wrap="word", bd=0, relief="flat", highlightthickness=0,
                state="normal", cursor="xterm", height=1,
                width=1,   # width=1 → se expande via pack fill="x"
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

def _auto_height(t: tk.Text, wrap_px: int = 0):
    """Ajusta altura de tk.Text usando displaylines (cuenta líneas visuales tras wrap)."""
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

def _pack_text(t: tk.Text, parent, pady=(1,1)):
    """Pack un tk.Text y ajusta su altura sincrónicamente."""
    t.pack(fill="x", pady=pady)
    t.update_idletasks()
    _auto_height(t)


# ─── UserBubble ───────────────────────────────────────────────────────────────
class UserBubble(ctk.CTkFrame):
    MAX_WIDTH_RATIO = 0.60

    def __init__(self, parent, texto: str, **kwargs):
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


# ─── AIBubble ─────────────────────────────────────────────────────────────────
class AIBubble(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._raw       = ""
        self._streaming = True
        self._wrap_px   = 600   # se recalcula en finalizar()

        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=4, pady=(12, 4))
        ctk.CTkLabel(hdr, text="◆", font=(_F, TAMANO_BASE), text_color=ACCENT, width=20
                     ).pack(side="left", padx=(0, 6))
        
        # --- NUEVO: LEER EL MODELO ACTIVO PARA EL TÍTULO ---
        nombres_modelos = {
            "general": "Gemini Flash",
            "planificador": "DeepSeek V4 (Thinking)",
            "programador": "DeepSeek V4 (Fast)"
        }
        modo_actual = getattr(motor_ia, 'MODO_ACTUAL', 'general')
        nombre_modelo = nombres_modelos.get(modo_actual, "IA")
        
        ctk.CTkLabel(hdr, text=f"Cortana ({nombre_modelo})", font=(_F, TAMANO_BASE - 1, "bold"), text_color=TEXT_DIM
                     ).pack(side="left")

        # Botón copiar respuesta completa (aparece a la derecha del header)
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

        # Contenedor de contenido
        self._content = ctk.CTkFrame(self, fg_color="transparent")
        self._content.pack(fill="x", padx=(28, 4), pady=(0, 14))

        # Textbox provisional para streaming
        self._stream_box = ctk.CTkTextbox(
            self._content, fg_color="transparent",
            font=FONT_CHAT_MD, text_color=TEXT_AI,
            wrap="word", 
            border_width=0, height=LINE_HEIGHT_PX + 10)
        self._stream_box.pack(fill="x")
        self._stream_box.configure(state="disabled")

    # ── Stream ────────────────────────────────────────────────────────────────
    def append_text(self, texto: str):
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
        """Copia el texto plano de la respuesta al portapapeles con feedback visual."""
        if not self._raw.strip():
            return
        self.clipboard_clear()
        self.clipboard_append(self._raw)
        # Feedback: el ícono cambia brevemente a ✓
        self._btn_copy.configure(text="✓", text_color="#86efac")
        self.after(1500, lambda: self._btn_copy.configure(text="⎘", text_color=TEXT_DIM))

    # ── Finalizar: reemplazar stream por Markdown renderizado ─────────────────
    def finalizar(self):
        if not self._streaming:
            return
        self._streaming = False
        self._stream_box.destroy()

        # Estimar wrap_px a partir del ancho del widget
        self.update_idletasks()
        self._wrap_px = max(300, self.winfo_width() - 60)

        if self._raw.strip():
            self._render_markdown(self._raw)



    # ── Parser de Markdown ────────────────────────────────────────────────────
    def _render_markdown(self, text: str):
        # Indicadores FUERTES de que una línea es código (nunca texto narrativo)
        CODE_STRONG = re.compile(
            r'^(import |from \w+ import |def |class |\s+def |\s+class |'
            r'\s+return |\s+if |\s+elif |\s+else:|\s+for |\s+while |\s+try:'
            r'|\s+except|\s+with |\s+raise |\s+yield |\s+self\.\w|'
            r'var |const |let |function |#include|public |private |static )'
        )

        def _is_code_context(block: str) -> bool:
            """Devuelve True si el bloque contiene suficiente código real."""
            strong = sum(1 for l in block.splitlines() if CODE_STRONG.match(l))
            return strong >= 2

        # Paso 1: extraer bloques con backticks explícitos
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

        # Paso 2: segmentos de texto que huelen a código → CodeBlock completo
        # La clave: si el bloque tiene contexto de código lo mostramos entero,
        # sin intentar separar las líneas de comentario/sección que hay dentro.
        final = []
        for seg in segments:
            if seg[0] == "code":
                final.append(seg)
                continue
            raw = seg[1]
            # Separar intro narrativa (antes del primer indicador fuerte de código)
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

        # Paso 3: fusionar bloques de codigo consecutivos (ej: ```python\nimport os```
        # seguido de mas codigo sin backticks — deben quedar en un solo CodeBlock)
        merged = []
        for seg in final:
            if seg[0] == "text" and not seg[1].strip():
                # texto vacio: ignorar si estamos entre dos bloques de codigo
                merged.append(seg)
                continue
            merged.append(seg)

        # Colapsar: code → (texto solo whitespace) → code = un solo code
        final2 = []
        i2 = 0
        while i2 < len(merged):
            seg = merged[i2]
            if seg[0] == "code":
                # mirar hacia adelante: ¿texto vacio + code?
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

        # Paso 4: renderizar
        for seg in final2:
            if seg[0] == "code":
                CodeBlock(self._content, seg[1], lang=seg[2]).pack(fill="x", pady=(4, 4))
            else:
                self._render_text_block(self._content, seg[1])

    def _render_text_block(self, parent, text: str):
        lines = text.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            if not stripped:
                i += 1
                continue

            # ── Encabezados ─────────────────────────────────────────────────
            if stripped.startswith("### "):
                self._add_label(parent, stripped[4:], (_F,15,"bold"), TEXT_PRIMARY, (8,2))
                i += 1; continue
            if stripped.startswith("## "):
                self._add_label(parent, stripped[3:], (_F,16,"bold"), TEXT_PRIMARY, (10,2))
                i += 1; continue
            if stripped.startswith("# "):
                self._add_label(parent, stripped[2:], (_F,18,"bold"), TEXT_PRIMARY, (12,2))
                i += 1; continue

            # ── Separador ───────────────────────────────────────────────────
            if re.match(r'^[-*_]{3,}$', stripped):
                ctk.CTkFrame(parent, height=1, fg_color=BORDER_COLOR).pack(fill="x", pady=8)
                i += 1; continue

            # ── Tabla Markdown ───────────────────────────────────────────────
            if stripped.startswith("|"):
                # Recolectar todas las líneas de la tabla
                table_lines = []
                while i < len(lines) and lines[i].strip().startswith("|"):
                    table_lines.append(lines[i])
                    i += 1
                rows = _parse_table(table_lines)
                if rows:
                    TableBlock(parent, rows).pack(fill="x", pady=(6,6))
                continue

            # ── Lista no ordenada — recolectar todos los ítems en un bloque ──
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
                        i += 1  # línea vacía entre ítems: ignorar
                    else:
                        break
                self._add_text_block(parent, "\n".join(items))
                continue

            # ── Lista ordenada — recolectar todos los ítems en un bloque ────
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

            # ── Párrafo normal ──────────────────────────────────────────────
            para_lines = []
            while i < len(lines) and lines[i].strip() and \
                  not lines[i].strip().startswith(("#","- ","* ","• ","|")) and \
                  not re.match(r'^\d+\. ', lines[i].strip()) and \
                  not re.match(r'^[-*_]{3,}$', lines[i].strip()):
                para_lines.append(lines[i].strip())
                i += 1
            if para_lines:
                self._add_text_block(parent, " ".join(para_lines))

        # fin while

    def _add_text_block(self, parent, text: str, pady=(1, 1)):
        """Un solo tk.Text seleccionable para bloques de varias líneas (listas, párrafos)."""
        t = tk.Text(parent, bg=BG_CHAT, fg=TEXT_AI, font=(_F, _TK_SIZE),
                    wrap="word", bd=0, relief="flat", highlightthickness=0,
                    state="normal", cursor="xterm", height=1, width=1,
                    selectbackground=ACCENT_SOFT, selectforeground=TEXT_PRIMARY)
        # Insertar con soporte básico de bold/italic por línea
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
        """Texto seleccionable (headings) con altura sincrónica."""
        # Convertir tamaño a píxeles negativos si viene en puntos positivos
        px_font = (font[0], -abs(font[1])) + font[2:] if len(font) >= 2 else font
        t = tk.Text(parent, bg=BG_CHAT, fg=color, font=px_font,
                    wrap="word", bd=0, relief="flat", highlightthickness=0,
                    state="normal", cursor="xterm", height=1, width=1,
                    selectbackground=ACCENT_SOFT, selectforeground=TEXT_PRIMARY)
        t.insert("1.0", _strip_md(text))
        t.configure(state="disabled")
        _pack_text(t, parent, pady)

    def _add_inline(self, parent, text: str):
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

        # tk.Text con bold/italic/code_inline
        t = _make_inline_text(parent, text, self._wrap_px)
        _pack_text(t, parent)


# ─── LogRedirector ────────────────────────────────────────────────────────────
class LogRedirector:
    def __init__(self, target_widget):
        self.target = target_widget
        self._buffer = ""
    def write(self, string):
        self._buffer += string
        # Flush líneas completas al widget; retener el resto en buffer
        if "\n" in self._buffer:
            partes = self._buffer.split("\n")
            for linea in partes[:-1]:
                if linea.strip():
                    texto = linea.strip()
                    self.target.after(0, lambda t=texto: self._add_log(t))
            self._buffer = partes[-1]  # lo que sobró sin \n
    def flush(self):
        # Al hacer flush manual, volcamos lo que quede en el buffer
        if self._buffer.strip():
            texto = self._buffer.strip()
            self._buffer = ""
            self.target.after(0, lambda t=texto: self._add_log(t))
    def _add_log(self, text):
        self.target.configure(state="normal")
        self.target.insert("end", text + "\n")
        self.target.see("end")
        self.target.configure(state="disabled")


# ─── OmniApp ──────────────────────────────────────────────────────────────────
class OmniApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        ancho, alto = 980, 700
        pw, ph = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{ancho}x{alto}+{(pw-ancho)//2}+{(ph-alto)//2}")
        self.title("Cortana")
        self.configure(fg_color=BG_MAIN)
        self.resizable(True, True)
        self.minsize(640, 420)

        # col 0 = sidebar fijo, col 1 = separador 1px, col 2 = chat
        self.grid_columnconfigure(0, weight=0, minsize=215)
        self.grid_columnconfigure(1, weight=0, minsize=1)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_separator()
        self._build_main_area()

        self.burbuja_ia_actual: AIBubble | None = None
        self.texto_sin_enviar: str = ""      # Paso 2: guarda texto real al perder foco
        self.historiales: dict = {}          # Paso 3: {modo: [(tipo, texto), ...]}
        self.modo_actual = "general"         # se sobreescribe en _build_sidebar
        threading.Thread(target=self.motor_microfono, daemon=True).start()

    # ── Separador vertical sidebar/chat ───────────────────────────────────────
    def _build_separator(self):
        sep = ctk.CTkFrame(self, width=1, fg_color=SIDEBAR_LINE, corner_radius=0)
        sep.grid(row=0, column=1, rowspan=2, sticky="ns")

    # ── Sidebar ────────────────────────────────────────────────────────────────
    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, fg_color=BG_SIDEBAR, corner_radius=0)
        sb.grid(row=0, column=0, rowspan=2, sticky="nsew")
        sb.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(sb, text="◆ Cortana", font=(_F, TAMANO_BASE, "bold"),
                     text_color=ACCENT).grid(row=0, column=0, padx=18, pady=(24,2), sticky="w")
        
        # --- NUEVA ETIQUETA DINÁMICA DE MODELO ---
        self.lbl_modelo_activo = ctk.CTkLabel(sb, text="🧠 Modelo: Gemini Flash", font=FONT_UI_SM,
                     text_color="#86efac")
        self.lbl_modelo_activo.grid(row=1, column=0, padx=18, pady=(0,14), sticky="w")

        ctk.CTkFrame(sb, height=1, fg_color=SIDEBAR_LINE).grid(
            row=2, column=0, padx=0, sticky="ew")

        # --- NUEVA LISTA DE BOTONES (Sin el botón manual de anclar) ---
        self.modo_actual = "general"

        botones = [
            ("💬  Chat General",       lambda: self._cambiar_modo("general")),
            ("📐  Modo Planificador",  lambda: self._cambiar_modo("planificador")),
            ("💻  Modo Programador",   lambda: self._cambiar_modo("programador"))
        ]
        
        self.botones_ui = []
        for i, (txt, cmd) in enumerate(botones, start=3):
            btn = ctk.CTkButton(sb, text=txt, anchor="w", font=FONT_UI,
                          fg_color="transparent", hover_color="#16162a",
                          text_color=TEXT_PRIMARY, corner_radius=6,
                          command=cmd)
            btn.grid(row=i, column=0, padx=10, pady=2, sticky="ew")
            self.botones_ui.append(btn)

        ctk.CTkLabel(sb, text="v0.2.0 - Multi-Modo", font=FONT_UI_SM,
                     text_color=TEXT_DIM).grid(row=10, column=0, padx=18, pady=16, sticky="sw")
        sb.grid_rowconfigure(10, weight=1)

    # --- FUNCIÓN _CAMBIAR_MODO CON ANCLAJE AUTOMÁTICO + HISTORIAL (Paso 3) ---
    def _cambiar_modo(self, nuevo_modo):
        if nuevo_modo == self.modo_actual:
            return  # ya estamos en este modo, nada que hacer

        # 1. Verificación automática de entorno para los modos avanzados
        if nuevo_modo in ["planificador", "programador"]:
            if not getattr(motor_ia, 'WORKSPACE_ACTUAL', None):
                ruta = filedialog.askdirectory(title=f"Selecciona el proyecto para el Modo {nuevo_modo.capitalize()}")
                if not ruta:
                    return
                motor_ia.WORKSPACE_ACTUAL = ruta
                nombre_proj = os.path.basename(ruta)
                estructura = []
                for raiz, carpetas, archivos in os.walk(ruta):
                    carpetas[:] = [d for d in carpetas if d not in ['.git','__pycache__','venv','node_modules']]
                    nivel = raiz.replace(ruta,'').count(os.sep)
                    ind  = ' ' * 4 * nivel
                    sind = ' ' * 4 * (nivel + 1)
                    estructura.append(f"{ind}📂 {os.path.basename(raiz)}/")
                    for f in archivos: estructura.append(f"{sind}📄 {f}")
                arbol = f"Estructura del proyecto '{nombre_proj}':\n" + "\n".join(estructura)
                guardar_snapshot(ruta, arbol)
                motor_ia.SNAPSHOT_ACTUAL = arbol

        # 2. PASO 3 — Guardar historial visual del modo ACTUAL antes de limpiar
        snapshot_actual = []
        for widget in self.chat_scroll.winfo_children():
            if isinstance(widget, UserBubble):
                # Extraer texto del CTkTextbox interno
                try:
                    txt = widget._tb.get("1.0", "end").strip()
                    if txt:
                        snapshot_actual.append(("usuario", txt))
                except Exception:
                    pass
            elif isinstance(widget, AIBubble):
                # Guardar el markdown crudo, que es la fuente de verdad
                if widget._raw.strip():
                    snapshot_actual.append(("ia", widget._raw))
            elif isinstance(widget, ctk.CTkLabel):
                # Capturar mensajes de sistema (⚙ ...)
                try:
                    txt = widget.cget("text")
                    if txt and txt.startswith("⚙"):
                        snapshot_actual.append(("sistema", txt[2:].strip()))
                except Exception:
                    pass
        # Limitar a últimos 50 mensajes para no sobrecargar
        self.historiales[self.modo_actual] = snapshot_actual[-50:]

        # 3. Aplicamos el cambio de modo
        self.modo_actual = nuevo_modo
        motor_ia.MODO_ACTUAL = nuevo_modo

        # 4. Limpiar UI
        for w in self.chat_scroll.winfo_children():
            w.destroy()
        self.burbuja_ia_actual = None

        # 5. Restaurar historial del nuevo modo si existe
        historial_previo = self.historiales.get(nuevo_modo, [])
        if historial_previo:
            for tipo, texto in historial_previo:
                if tipo == "usuario":
                    self._agregar_usuario(texto)
                elif tipo == "ia":
                    burbuja = AIBubble(self.chat_scroll)
                    burbuja.pack(fill="x", padx=CHAT_PAD_X, pady=(2,6))
                    burbuja._raw = texto
                    burbuja._streaming = False
                    burbuja._stream_box.destroy()
                    burbuja._render_markdown(texto)
                elif tipo == "sistema":
                    self._agregar_sistema(texto)
        else:
            # Primera vez en este modo: mostrar bienvenida
            ruta_corta = os.path.basename(getattr(motor_ia, 'WORKSPACE_ACTUAL', '')) if getattr(motor_ia, 'WORKSPACE_ACTUAL', None) else ""
            mensajes_bienvenida = {
                "general":      "¿En qué puedo ayudarte hoy?",
                "planificador": f"📐 Modo Planificador\n[ {ruta_corta} ]\n¿Qué vamos a diseñar?",
                "programador":  f"💻 Modo Programador\n[ {ruta_corta} ]\nListo para ejecutar."
            }
            self._welcome_label = ctk.CTkLabel(
                self.chat_scroll, text=mensajes_bienvenida[nuevo_modo],
                font=(_F, TAMANO_BASE + 6, "bold"), text_color="#2a2a3e")
            self._welcome_label.pack(expand=True, pady=(120,0))
            self._agregar_sistema(f"Modo cambiado a: {nuevo_modo.upper()}")

        # 6. Actualizar etiqueta de modelo en sidebar
        textos_modelos = {
            "general":      "🧠 Modelo: Gemini Flash",
            "planificador": "🧠 Modelo: DeepSeek V4 (Thinking)",
            "programador":  "🧠 Modelo: DeepSeek V4 (Fast)"
        }
        self.lbl_modelo_activo.configure(text=textos_modelos[nuevo_modo])
        self._scroll_abajo()

    # ── Main area (tabs) ───────────────────────────────────────────────────────
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

    # ── Chat area ──────────────────────────────────────────────────────────────
    def _build_chat_area(self, parent):
        self.chat_scroll = ctk.CTkScrollableFrame(
            parent, fg_color=BG_CHAT, corner_radius=0,
            scrollbar_button_color="#2a2a3e",
            scrollbar_button_hover_color="#3d3d5c"
        )
        self.chat_scroll.pack(fill="both", expand=True)
        self.chat_scroll.grid_columnconfigure(0, weight=1)

        self._welcome_label = ctk.CTkLabel(
            self.chat_scroll, text="¿En qué puedo ayudarte hoy?",
            font=(_F, TAMANO_BASE + 11, "bold"), text_color="#2a2a3e")
        self._welcome_label.pack(expand=True, pady=(120,0))
        self._build_input_bar()

    # ── Input bar ──────────────────────────────────────────────────────────────
    def _build_input_bar(self):
        outer = ctk.CTkFrame(self, fg_color=BG_MAIN, corner_radius=0)
        outer.grid(row=1, column=2, sticky="ew")
        outer.grid_columnconfigure(0, weight=1)

        bar = ctk.CTkFrame(outer, fg_color=BG_INPUT, corner_radius=16,
                           border_width=1, border_color=BORDER_INPUT)
        bar.grid(row=0, column=0, padx=CHAT_PAD_X, pady=(12,4), sticky="ew")
        bar.grid_columnconfigure(0, weight=1)
        bar.grid_columnconfigure(1, weight=0)
        bar.grid_columnconfigure(2, weight=0)

        self.entry = ctk.CTkTextbox(bar, height=48, fg_color="transparent",
                                    font=FONT_CHAT, text_color=TEXT_PRIMARY,
                                    wrap="word", border_width=0)
        self.entry.grid(row=0, column=0, padx=(8,4), pady=6, sticky="ew")
        self.entry.bind("<Return>",       self._on_enter)
        self.entry.bind("<Shift-Return>", self._on_shift_enter)
        self._set_placeholder()

        # Botón adjuntar (📎)
        self.btn_attach = ctk.CTkButton(
            bar, text="📎", width=38, height=38,
            corner_radius=8, fg_color="transparent",
            hover_color=ACCENT_SOFT,
            font=(_F, TAMANO_BASE + 1), text_color=TEXT_DIM,
            command=self._adjuntar_archivo)
        self.btn_attach.grid(row=0, column=1, padx=(0,2), pady=6)

        self.btn_send = ctk.CTkButton(bar, text="▲", width=42, height=42,
                                      corner_radius=10, fg_color=ACCENT,
                                      hover_color=ACCENT_HOVER,
                                      font=(_F, TAMANO_BASE, "bold"), text_color="#f0f0f0",
                                      command=self.enviar_mensaje)
        self.btn_send.grid(row=0, column=2, padx=(0,8), pady=6)

        ctk.CTkLabel(outer, text="Enter · enviar   Shift+Enter · nueva línea",
                     font=FONT_UI_SM, text_color=TEXT_DIM).grid(row=1, column=0, pady=(2,10))

    # ── Placeholder ────────────────────────────────────────────────────────────
    def _set_placeholder(self):
        self.entry.insert("1.0", "Escribí tu mensaje...")
        self.entry.configure(text_color=TEXT_DIM)
        self._placeholder_active = True
        self.entry.bind("<FocusIn>",  self._clear_placeholder)
        self.entry.bind("<FocusOut>", self._restore_placeholder)

    def _clear_placeholder(self, event=None):
        if self._placeholder_active:
            # Solo borramos si el contenido ES el placeholder, no texto real
            self.entry.delete("1.0", "end")
            self.entry.configure(text_color=TEXT_PRIMARY)
            self._placeholder_active = False
            # Restaurar texto real que el usuario había escrito antes
            if self.texto_sin_enviar:
                self.entry.insert("1.0", self.texto_sin_enviar)
                self.texto_sin_enviar = ""

    def _restore_placeholder(self, event=None):
        contenido = self.entry.get("1.0", "end").strip()
        if not contenido:
            self.entry.insert("1.0", "Escribí tu mensaje...")
            self.entry.configure(text_color=TEXT_DIM)
            self._placeholder_active = True
        else:
            # Guardar el texto real antes de perder el foco
            self.texto_sin_enviar = contenido

    def _adjuntar_archivo(self):
        """Abre diálogo para adjuntar archivo e inserta la ruta en el input."""
        rutas = filedialog.askopenfilenames(
            title="Adjuntar archivos",
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

    def _on_enter(self, event):
        self.enviar_mensaje(); return "break"

    def _on_shift_enter(self, event):
        return

    # ── Motor de micrófono ─────────────────────────────────────────────────────
    def motor_microfono(self):
        while True:
            try:
                if audio_modulo.hablando_actualmente and keyboard.is_pressed('space'):
                    detener_voz()
                    while keyboard.is_pressed('space'): time.sleep(0.05)
                    continue
                if keyboard.is_pressed(TECLA_HABLAR):
                    if audio_modulo.hablando_actualmente: detener_voz()
                    texto_voz = capturar_voz_micro()
                    if texto_voz:
                        self.after(0, self._agregar_usuario, f"🎤 {texto_voz}")
                        self.burbuja_ia_actual = None
                        threading.Thread(target=enviar_a_gemini,
                                         args=(texto_voz, True, self.callback_ia),
                                         daemon=True).start()
                    while keyboard.is_pressed(TECLA_HABLAR): time.sleep(0.05)
                time.sleep(0.02)
            except Exception:
                pass

    # ── Envío ──────────────────────────────────────────────────────────────────
    def enviar_mensaje(self):
        if self._placeholder_active: return
        texto = self.entry.get("1.0","end").strip()
        if not texto: return
        if hasattr(self,"_welcome_label") and self._welcome_label.winfo_exists():
            self._welcome_label.destroy()
        self.entry.delete("1.0","end")
        self._placeholder_active = False
        self._agregar_usuario(texto)
        self.burbuja_ia_actual = None
        threading.Thread(target=enviar_a_gemini,
                         args=(texto, False, self.callback_ia),
                         daemon=True).start()

    # ── Callback IA ───────────────────────────────────────────────────────────
    def callback_ia(self, remitente, texto: str, color=None, nueva_linea=True):
        def _update():
            if hasattr(self,"_welcome_label") and self._welcome_label.winfo_exists():
                self._welcome_label.destroy()

            # Mensaje de sistema
            if remitente and remitente != "🤖 Cortana" and texto.strip():
                self._agregar_sistema(texto)
                self._scroll_abajo()
                return

            # FIN del stream
            if nueva_linea and texto == "":
                if self.burbuja_ia_actual:
                    self.burbuja_ia_actual.finalizar()
                    self.burbuja_ia_actual = None
                self._scroll_abajo()
                return

            # Crear burbuja si no existe
            if not self.burbuja_ia_actual:
                self.burbuja_ia_actual = AIBubble(self.chat_scroll)
                self.burbuja_ia_actual.pack(fill="x", padx=CHAT_PAD_X, pady=(2,6))

            # Chunk de texto
            if texto:
                self.burbuja_ia_actual.append_text(texto)

            self.after(50, self._scroll_abajo) # <--- CAMBIO AQUÍ
        self.after(0, _update)

    def _agregar_sistema(self, texto: str):
        lbl = ctk.CTkLabel(self.chat_scroll, text=f"⚙ {texto}",
                           font=FONT_UI_SM, text_color=TEXT_DIM,
                           anchor="w", justify="left", wraplength=0)
        lbl.pack(fill="x", padx=CHAT_PAD_X + 20, pady=(2,2))

    def _agregar_usuario(self, texto: str):
        if hasattr(self,"_welcome_label") and self._welcome_label.winfo_exists():
            self._welcome_label.destroy()
        burbuja = UserBubble(self.chat_scroll, texto)
        burbuja.pack(fill="x", padx=CHAT_PAD_X, pady=(6,2))
        self.update_idletasks()
        self._scroll_abajo()

    def _scroll_abajo(self):
        self.update_idletasks() # Fuerza el renderizado primero
        try:
            if hasattr(self.chat_scroll, "_parent_canvas"):
                self.chat_scroll._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    def _nueva_conversacion(self):
        for w in self.chat_scroll.winfo_children():
            w.destroy()
        self.burbuja_ia_actual = None
        self._welcome_label = ctk.CTkLabel(
            self.chat_scroll, text="¿En qué puedo ayudarte hoy?",
            font=(_F, TAMANO_BASE + 11, "bold"), text_color="#2a2a3e")
        self._welcome_label.pack(expand=True, pady=(120,0))

if __name__ == "__main__":
    app = OmniApp()
    app.mainloop()