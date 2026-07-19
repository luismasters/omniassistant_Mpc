import math
import random
import tkinter as tk
try:
    import modulos.audio_custom as audio_modulo
except ModuleNotFoundError:
    import audio_custom as audio_modulo

try:
    import customtkinter as ctk
    _TIENE_CTK = True
except ImportError:
    _TIENE_CTK = False

# ─── PALETA DE ESTADOS ──────────────────────────────────────────────────────
COLOR_FONDO = "#0b0b18"
COLOR_VISOR = "#14142a"

PALETA_ESTADOS = {
    "idle":      "#7c3aed",
    "listening": "#5eead4",
    "thinking":  "#a78bfa",
    "speaking":  "#8b5cf6",
    "happy":     "#ffd166",
    "surprised": "#4fd1ff",
    "confused":  "#34d399",
    "sad":       "#6e8cae",
    "angry":     "#ff2d55",
    "sleepy":    "#8686a8",
    "error":     "#ff9f1c",
    "confirm":   "#5eead4",
}

ETIQUETAS_ESTADOS = {
    "idle": "Reposo", "listening": "Escuchando", "thinking": "Procesando",
    "speaking": "Hablando", "happy": "Contento", "surprised": "Sorprendido",
    "confused": "Confundido", "sad": "Triste", "angry": "Alerta",
    "sleepy": "Con sueño", "error": "Error", "confirm": "Confirmación",
}

# Parámetros objetivo por estado
PARAMS_ESTADOS = {
    #            ojo_izq ojo_der  ceja_izq(ang,dy)  ceja_der(ang,dy)  pupila(dx,dy)
    "idle":      (1.00, 1.00,  (0, 0),    (0, 0),    (0, 0)),
    "listening": (1.16, 1.16,  (0, -6),   (0, -6),   (0, 0)),
    "thinking":  (0.68, 0.68,  (6, 2),    (-6, 2),   (0, 0)),
    "speaking":  (1.00, 1.00,  (0, 0),    (0, 0),    (0, 0)),
    "happy":     (0.32, 0.32,  (-4, -3),  (4, -3),   (0, 0)),
    "surprised": (1.40, 1.40,  (0, -13),  (0, -13),  (0, 0)),
    "confused":  (0.55, 1.18,  (2, 0),    (-10, -12),(0, 0)),
    "sad":       (0.70, 0.70,  (-16, -2), (16, -2),  (0, 4)),
    "angry":     (0.50, 0.50,  (20, 6),   (-20, 6),  (0, 0)),
    "sleepy":    (0.20, 0.20,  (-3, 4),   (3, 4),    (0, 0)),
    "error":     (0.30, 0.30,  (4, -2),   (-4, -2),  (0, 0)),
    "confirm":   (0.32, 1.10,  (-4, -3),  (4, -3),   (0, 0)),
}

DURACION_TRANSICION_MS = 320
PASOS_TRANSICION = 16


def _interpolar(a, b, t):
    return a + (b - a) * t


def _interpolar_color(c1, c2, t):
    c1 = c1.lstrip("#")
    c2 = c2.lstrip("#")
    r1, g1, b1 = int(c1[0:2], 16), int(c1[2:4], 16), int(c1[4:6], 16)
    r2, g2, b2 = int(c2[0:2], 16), int(c2[2:4], 16), int(c2[4:6], 16)
    r = int(_interpolar(r1, r2, t))
    g = int(_interpolar(g1, g2, t))
    b = int(_interpolar(b1, b2, t))
    return f"#{r:02x}{g:02x}{b:02x}"


class RostroArgus(ctk.CTkFrame if _TIENE_CTK else tk.Frame):
    """Widget de rostro expresivo de Argus, dibujado con tkinter.Canvas."""

    def __init__(self, parent, size=280, **kwargs):
        fg = kwargs.pop("fg_color", COLOR_FONDO) if _TIENE_CTK else None
        if _TIENE_CTK:
            super().__init__(parent, fg_color=fg, **kwargs)
        else:
            super().__init__(parent, bg=COLOR_FONDO, **kwargs)

        self.size = size
        self.estado_actual = "idle"
        self.msg_confirmacion = "COMANDO RECIBIDO"
        self._job_transicion = None
        self._job_parpadeo = None
        self._job_habla = None
        self._job_ambiente = None
        self._parpadeando = False
        
        self.canvas = tk.Canvas(
            self, width=size, height=int(size * 0.72),
            bg=COLOR_FONDO, highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True)

        self._sx = size / 400.0
        self._sy = (size * 0.72) / 260.0

        self._construir_escena()
        self._valores_actuales = PARAMS_ESTADOS["idle"]
        self._aplicar_valores(PARAMS_ESTADOS["idle"], PALETA_ESTADOS["idle"])
        self._dibujar_boca("idle", PALETA_ESTADOS["idle"])
        self._programar_parpadeo()
        self._programar_ambiente()

    def _px(self, x): return x * self._sx
    def _py(self, y): return y * self._sy

    def _construir_escena(self):
        c = self.canvas
        color0 = PALETA_ESTADOS["idle"]

        self.id_visor = c.create_rectangle(
            self._px(30), self._py(52), self._px(370), self._py(184),
            outline=color0, width=2, fill=COLOR_VISOR
        )

        self.id_ojo_izq = c.create_oval(0, 0, 0, 0, fill=color0, outline="")
        self.id_ojo_der = c.create_oval(0, 0, 0, 0, fill=color0, outline="")
        self.id_pupila_izq = c.create_oval(0, 0, 0, 0, fill=COLOR_FONDO, outline="")
        self.id_pupila_der = c.create_oval(0, 0, 0, 0, fill=COLOR_FONDO, outline="")

        self.id_ceja_izq = c.create_line(0, 0, 0, 0, fill=color0, width=self._px(6), capstyle="round")
        self.id_ceja_der = c.create_line(0, 0, 0, 0, fill=color0, width=self._px(6), capstyle="round")

        self.ids_boca = []
        self.id_lagrima = c.create_oval(0, 0, 0, 0, fill=color0, outline="", state="hidden")
        self.ids_zzz = []

        # Partículas ambientales eliminadas por solicitud del usuario
        self._particulas = []

    def _programar_ambiente(self):
        # Detección automática del habla basada en el motor de audio
        if self.estado_actual not in ("confirm", "error", "thinking", "listening"):
            if audio_modulo.hablando_actualmente:
                if self.estado_actual != "speaking":
                    self.set_state("speaking")
            else:
                if self.estado_actual == "speaking":
                    self.set_state("idle")
                    
        self._job_ambiente = self.after(45, self._programar_ambiente)

    def _programar_parpadeo(self):
        espera = random.randint(2600, 6000)
        self._job_parpadeo = self.after(espera, self._ejecutar_parpadeo)

    def _ejecutar_parpadeo(self):
        if self.estado_actual in ("idle", "listening", "thinking", "happy", "confused") and not self._parpadeando:
            self._parpadeando = True
            valores = self._valores_actuales
            cerrado = list(PARAMS_ESTADOS[self.estado_actual])
            cerrado[0], cerrado[1] = 0.06, 0.06
            self._aplicar_valores(tuple(cerrado), PALETA_ESTADOS[self.estado_actual])
            self.after(90, lambda: (
                self._aplicar_valores(PARAMS_ESTADOS[self.estado_actual], PALETA_ESTADOS[self.estado_actual]),
                setattr(self, "_parpadeando", False)
            ))
        self._programar_parpadeo()

    def cambiar_estado(self, nuevo_estado, msg=""):
        """Método de compatibilidad con la interfaz de main_gui.py."""
        if nuevo_estado == "talking":
            nuevo_estado = "speaking"
        if nuevo_estado == "confirm" and msg:
            self.msg_confirmacion = msg
        self.set_state(nuevo_estado)

    def set_state(self, nombre):
        if nombre not in PARAMS_ESTADOS or nombre == self.estado_actual:
            return
        if self._job_transicion:
            self.after_cancel(self._job_transicion)

        val_origen = self._valores_actuales
        val_destino = PARAMS_ESTADOS[nombre]
        color_origen = PALETA_ESTADOS[self.estado_actual]
        color_destino = PALETA_ESTADOS[nombre]
        self.estado_actual = nombre

        paso = [0]

        def tick():
            t = paso[0] / PASOS_TRANSICION
            valores_interp = self._mezclar(val_origen, val_destino, t)
            color_interp = _interpolar_color(color_origen, color_destino, t)
            self._aplicar_valores(valores_interp, color_interp)
            paso[0] += 1
            if paso[0] <= PASOS_TRANSICION:
                self._job_transicion = self.after(DURACION_TRANSICION_MS // PASOS_TRANSICION, tick)
            else:
                self._valores_actuales = val_destino
                self._dibujar_boca(nombre, color_destino)
                self._actualizar_extras(nombre, color_destino)

        tick()

        if nombre == "speaking":
            self._iniciar_habla(color_destino)
        else:
            self._detener_habla()

        if nombre == "error":
            self._efecto_glitch()

    def _mezclar(self, origen, destino, t):
        oi = _interpolar(origen[0], destino[0], t)
        od = _interpolar(origen[1], destino[1], t)
        ci = (_interpolar(origen[2][0], destino[2][0], t), _interpolar(origen[2][1], destino[2][1], t))
        cd = (_interpolar(origen[3][0], destino[3][0], t), _interpolar(origen[3][1], destino[3][1], t))
        pu = (_interpolar(origen[4][0], destino[4][0], t), _interpolar(origen[4][1], destino[4][1], t))
        return (oi, od, ci, cd, pu)

    def _aplicar_valores(self, valores, color):
        ojo_i, ojo_d, ceja_i, ceja_d, pupila = valores
        c = self.canvas

        cx_i, cy_i = self._px(150), self._py(120)
        cx_d, cy_d = self._px(250), self._py(120)
        w = self._px(28)

        h_i = self._py(32) * ojo_i
        h_d = self._py(32) * ojo_d
        c.coords(self.id_ojo_izq, cx_i - w, cy_i - h_i, cx_i + w, cy_i + h_i)
        c.coords(self.id_ojo_der, cx_d - w, cy_d - h_d, cx_d + w, cy_d + h_d)
        c.itemconfig(self.id_ojo_izq, fill=color)
        c.itemconfig(self.id_ojo_der, fill=color)

        r_pupila = self._px(9)
        dx, dy = self._px(pupila[0]), self._py(pupila[1])
        c.coords(self.id_pupila_izq, cx_i - r_pupila + dx, cy_i - r_pupila + dy,
                  cx_i + r_pupila + dx, cy_i + r_pupila + dy)
        c.coords(self.id_pupila_der, cx_d - r_pupila + dx, cy_d - r_pupila + dy,
                  cx_d + r_pupila + dx, cy_d + r_pupila + dy)

        self._posicionar_ceja(self.id_ceja_izq, self._px(150), self._py(78), ceja_i, invertir=False)
        self._posicionar_ceja(self.id_ceja_der, self._px(250), self._py(78), ceja_d, invertir=True)
        c.itemconfig(self.id_ceja_izq, fill=color)
        c.itemconfig(self.id_ceja_der, fill=color)
        c.itemconfig(self.id_visor, outline=color)

    def _posicionar_ceja(self, item, cx, cy, params, invertir):
        angulo_deg, dy = params
        largo = self._px(20)
        ang = math.radians(angulo_deg if not invertir else -angulo_deg)
        y = cy + self._py(dy)
        x1 = cx - largo * math.cos(ang)
        y1 = y - largo * math.sin(ang)
        x2 = cx + largo * math.cos(ang)
        y2 = y + largo * math.sin(ang)
        self.canvas.coords(item, x1, y1, x2, y2)

    def _dibujar_boca(self, estado, color):
        c = self.canvas
        for item in self.ids_boca:
            c.delete(item)
        self.ids_boca = []

        cx, cy = self._px(200), self._py(208)

        if estado in ("idle", "thinking", "sleepy"):
            self.ids_boca.append(c.create_line(
                cx - self._px(22), cy, cx + self._px(22), cy,
                fill=color, width=self._px(5), capstyle="round"
            ))
        elif estado == "listening":
            r = self._px(10)
            self.ids_boca.append(c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=color, outline=""))
        elif estado == "speaking":
            self._id_boca_habla = c.create_rectangle(
                cx - self._px(18), cy - self._px(5), cx + self._px(18), cy + self._px(5),
                fill=color, outline=""
            )
            self.ids_boca.append(self._id_boca_habla)
        elif estado == "happy":
            self.ids_boca.append(c.create_arc(
                cx - self._px(28), cy - self._px(26), cx + self._px(28), cy + self._px(22),
                start=200, extent=140, style="arc", outline=color, width=self._px(5)
            ))
        elif estado == "surprised":
            r = self._px(12)
            self.ids_boca.append(c.create_oval(cx - r, cy - r, cx + r, cy + r, outline=color, width=self._px(4)))
        elif estado == "confused":
            puntos = []
            for i in range(5):
                px = cx - self._px(24) + i * self._px(12)
                py = cy + (self._py(8) if i % 2 == 0 else -self._py(4))
                puntos.extend([px, py])
            self.ids_boca.append(c.create_line(*puntos, fill=color, width=self._px(4), smooth=True))
        elif estado == "sad":
            self.ids_boca.append(c.create_arc(
                cx - self._px(26), cy - self._px(6), cx + self._px(26), cy + self._px(38),
                start=20, extent=140, style="arc", outline=color, width=self._px(5)
            ))
        elif estado == "angry":
            puntos = [cx - self._px(28), cy + self._px(4), cx - self._px(6), cy - self._px(6),
                      cx + self._px(6), cy, cx + self._px(28), cy - self._px(8)]
            self.ids_boca.append(c.create_line(*puntos, fill=color, width=self._px(5)))
        elif estado == "error":
            puntos = [cx - self._px(28), cy, cx - self._px(14), cy - self._px(10),
                      cx, cy + self._px(8), cx + self._px(14), cy - self._px(10),
                      cx + self._px(28), cy]
            self.ids_boca.append(c.create_line(*puntos, fill=color, width=self._px(4)))
        elif estado == "confirm":
            self.ids_boca.append(c.create_arc(
                cx - self._px(28), cy - self._px(26), cx + self._px(28), cy + self._px(22),
                start=200, extent=140, style="arc", outline=color, width=self._px(5)
            ))
            msg_disp = getattr(self, "msg_confirmacion", "COMANDO RECIBIDO").upper()
            if len(msg_disp) > 28:
                msg_disp = msg_disp[:25] + "..."
            self.ids_boca.append(c.create_text(
                self.size // 2, self._py(234),
                text=msg_disp,
                font=("Consolas", max(7, int(self._px(9))), "bold"),
                fill=color, justify="center"
            ))

    def _iniciar_habla(self, color):
        self._detener_habla()

        def tick():
            if self.estado_actual != "speaking":
                return
            if not hasattr(self, "_id_boca_habla") or self._id_boca_habla not in self.ids_boca:
                self._job_habla = self.after(50, tick)
                return
            cx, cy = self._px(200), self._py(208)
            alto = random.uniform(2, 11) * self._sy
            try:
                self.canvas.coords(
                    self._id_boca_habla,
                    cx - self._px(18), cy - alto, cx + self._px(18), cy + alto
                )
                self.canvas.itemconfig(self._id_boca_habla, fill=color)
            except Exception:
                pass
            self._job_habla = self.after(110, tick)

        tick()

    def _detener_habla(self):
        if self._job_habla:
            self.after_cancel(self._job_habla)
            self._job_habla = None

    def _actualizar_extras(self, estado, color):
        c = self.canvas
        for item in self.ids_zzz:
            c.delete(item)
        self.ids_zzz = []
        c.itemconfig(self.id_lagrima, state="hidden")

        if estado == "sad":
            self._animar_lagrima(color)
        elif estado == "sleepy":
            self._animar_zzz(color)

    def _animar_lagrima(self, color):
        if self.estado_actual != "sad":
            return
        cx, cy = self._px(178), self._py(150)
        r = self._px(4)
        self.canvas.itemconfig(self.id_lagrima, state="normal", fill=color)
        pasos = 22

        def tick(i=0):
            if self.estado_actual != "sad":
                self.canvas.itemconfig(self.id_lagrima, state="hidden")
                return
            t = i / pasos
            y = cy + t * self._py(24)
            col = _interpolar_color(color, COLOR_VISOR, t)
            self.canvas.coords(self.id_lagrima, cx - r, y - r, cx + r, y + r)
            self.canvas.itemconfig(self.id_lagrima, fill=col)
            if i < pasos:
                self.after(90, lambda: tick(i + 1))
            else:
                self.after(500, lambda: self._animar_lagrima(color))

        tick()

    def _animar_zzz(self, color):
        if self.estado_actual != "sleepy":
            return
        c = self.canvas
        cx, cy = self._px(272), self._py(66)
        item = c.create_text(cx, cy, text="Z", fill=color, font=("Consolas", max(8, int(self._px(9)))))
        self.ids_zzz.append(item)
        pasos = 24

        def tick(i=0):
            if self.estado_actual != "sleepy":
                c.delete(item)
                return
            t = i / pasos
            c.coords(item, cx + t * self._px(14), cy - t * self._py(26))
            col = _interpolar_color(color, COLOR_FONDO, t)
            c.itemconfig(item, fill=col)
            if i < pasos:
                self.after(120, lambda: tick(i + 1))
            else:
                c.delete(item)

        tick()
        self.after(1400, lambda: self._animar_zzz(color))

    def _efecto_glitch(self):
        offsets = [(-3, 2), (3, -2), (-2, 1), (2, 0), (0, 0)]

        def tick(i=0):
            if i >= len(offsets):
                return
            dx, dy = offsets[i]
            self.canvas.move("all", dx, dy)
            self.after(40, lambda: (self.canvas.move("all", -dx, -dy), tick(i + 1)))

        tick()

    def destroy(self):
        for job in (self._job_transicion, self._job_parpadeo, self._job_habla, self._job_ambiente):
            if job:
                try:
                    self.after_cancel(job)
                except Exception:
                    pass
        super().destroy()


# ─── DEMO STANDALONE ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    if _TIENE_CTK:
        ctk.set_appearance_mode("dark")
        app = ctk.CTk()
    else:
        app = tk.Tk()
        app.configure(bg=COLOR_FONDO)

    app.title("Argus — Rostro (demo Tkinter)")
    app.geometry("420x560")

    rostro = RostroArgus(app, size=320)
    rostro.pack(pady=(24, 10))

    etiqueta_estado = (ctk.CTkLabel(app, text="REPOSO", font=("Consolas", 14, "bold"))
                        if _TIENE_CTK else tk.Label(app, text="REPOSO", bg=COLOR_FONDO, fg="#7c3aed"))
    etiqueta_estado.pack(pady=(0, 14))

    dock = (ctk.CTkFrame(app, fg_color="transparent") if _TIENE_CTK else tk.Frame(app, bg=COLOR_FONDO))
    dock.pack(pady=8, padx=16, fill="x")

    def cambiar(nombre):
        rostro.set_state(nombre)
        etiqueta_estado.configure(text=ETIQUETAS_ESTADOS[nombre].upper())

    for i, (clave, etiqueta) in enumerate(ETIQUETAS_ESTADOS.items()):
        fila, col = divmod(i, 4)
        color = PALETA_ESTADOS[clave]
        if _TIENE_CTK:
            btn = ctk.CTkButton(
                dock, text=etiqueta, width=90, height=30,
                fg_color="transparent", border_width=1, border_color=color,
                text_color=color, hover_color=color,
                command=lambda k=clave: cambiar(k)
            )
        else:
            btn = tk.Button(dock, text=etiqueta, command=lambda k=clave: cambiar(k))
        btn.grid(row=fila, column=col, padx=4, pady=4, sticky="ew")

    for c in range(4):
        dock.grid_columnconfigure(c, weight=1)

    app.mainloop()
