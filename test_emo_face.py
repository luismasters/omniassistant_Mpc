import tkinter as tk
import customtkinter as ctk
import math
import random

class EmoBezelFace(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.ancho = 320
        self.alto = 200
        
        # Canvas negro absoluto
        self.canvas = tk.Canvas(
            self, width=self.ancho, height=self.alto, 
            bg="#000000", highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True)
        
        # --- Configuración Proporcional según Imagen de EMO ---
        # Los ojos de EMO están más juntos en el centro
        self.izq_cx = 125
        self.der_cx = 195
        self.izq_cy = 85  
        self.der_cy = 85
        
        self.boca_cx = 160
        self.boca_cy = 135
        
        # Ojos tipo Rounded-Square (casi cuadrados)
        self.base_rx = 24
        self.base_ry = 26
        self.corner_radius = 10
        
        # --- Físicas e Interpolaciones ---
        self.estado = "idle"
        self.tiempo = 0.0
        self.tiempo_lagrima = 0.0
        self.msg_confirmacion = "COMANDO RECIBIDO"
        
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
            "error": "#ff0033",      # Rojo
            "confirm": "#39ff14"    # Verde confirmación
        }
        
        self._idle_action = "none"
        self._idle_action_timer = 0
        
        # Iniciar bucles
        self.loop_render()
        self.loop_parpadeo()
        self.loop_saccades()
        self.after(5000, self.loop_idle_actions)

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
            # Mirando hacia arriba a la izquierda de forma pensativa
            self.tgt_zoom_x_izq = 0.95
            self.tgt_zoom_y_izq = 0.85
            self.tgt_zoom_x_der = 0.95
            self.tgt_zoom_y_der = 0.85
            self.tgt_look_x = -8.0
            self.tgt_look_y = -6.0
            
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
            self.tgt_look_y = 3.0
            
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

    def loop_idle_actions(self):
        import random
        if self.estado == "idle" and self._idle_action == "none":
            accion = random.choice(["wink", "sigh", "curious", "yawn"])
            self._idle_action = accion
            self._idle_action_timer = 0
            
            duracion = 2000
            if accion == "wink":
                duracion = 1000
                self.tgt_zoom_y_izq = 0.01
            elif accion == "yawn":
                duracion = 2500
            elif accion == "sigh":
                self.tgt_look_y = 6.0
            elif accion == "curious":
                self.tgt_look_x = -8.0
                self.tgt_look_y = -6.0
                self.tgt_zoom_y_izq = 0.7
            
            self.after(duracion, self.finalizar_idle_action)
            
        self.after(random.randint(12000, 22000), self.loop_idle_actions)
        
    def finalizar_idle_action(self):
        self._idle_action = "none"
        if self.estado == "idle":
            self.tgt_zoom_x_izq = 1.0
            self.tgt_zoom_y_izq = 1.0
            self.tgt_zoom_x_der = 1.0
            self.tgt_zoom_y_der = 1.0
            self.tgt_look_x = 0.0
            self.tgt_look_y = 0.0

    def loop_render(self):
        self.canvas.delete("all")
        self.tiempo += 0.04
        self.tiempo_lagrima = (self.tiempo_lagrima + 0.3) % 20.0
        
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
            err_x = random.randint(-2, 2)
            err_y = random.randint(-2, 2)
        elif self.estado == "confirm":
            # Rebote suave de confirmación
            err_y = int(2.5 * math.sin(self.tiempo * 20))
            
        cy_i = self.izq_cy + err_y
        cy_d = self.der_cy + err_y
        
        # Respiración en Idle y Acciones Inactivas
        if self.estado == "idle":
            resp = 1.0 + 0.02 * math.sin(self.tiempo * 2)
            zx_i *= resp; zy_i *= resp
            zx_d *= resp; zy_d *= resp
            
            if self._idle_action == "yawn":
                zy_i *= 0.45
                zy_d *= 0.45
                zx_i *= 1.15
                zx_d *= 1.15
            elif self._idle_action == "sigh":
                zy_i *= 0.75
                zy_d *= 0.75
            
        # Animación de ojos al hablar
        elif self.estado == "talking":
            onda = 0.95 + 0.06 * abs(math.sin(self.tiempo * 15))
            zy_i *= onda
            zy_d *= onda
            
        # Flotación en Listening
        elif self.estado == "listening":
            flot = 3.0 * math.sin(self.tiempo * 3)
            cy_i += flot
            cy_d += flot

        cx_izq = self.izq_cx + self.cur_look_x + err_x
        cx_der = self.der_cx + self.cur_look_x + err_x

        color = self.colores.get(self.estado, "#00f0ff")

        # 1. Dibujar Contorno Grisáceo de EMO (Marco Plateado/Gris Estático)
        self.dibujar_contorno_gris_emo()

        # 2. Dibujar Ojos de Intellar / Animación de Guiño (Wink) en Confirmación
        self.dibujar_ojo_intellar(cx_izq, cy_i, self.base_rx * zx_i, self.base_ry * zy_i, color, izquierdo=True)
        self.dibujar_ojo_intellar(cx_der, cy_d, self.base_rx * zx_d, self.base_ry * zy_d, color, izquierdo=False)
        
        # 3. Dibujar Boca de Eilik Estilizada
        boca_x = self.boca_cx + self.cur_look_x * 0.7 + err_x
        boca_y = self.boca_cy + self.cur_look_y * 0.5 + err_y
        self.dibujar_boca_eilik(boca_x, boca_y, color)
        
        # 4. Si es modo CONFIRM, dibujar texto de acción
        if self.estado == "confirm":
            self.canvas.create_text(
                self.ancho // 2, 172,
                text=self.msg_confirmacion,
                font=("Consolas", 8, "bold"),
                fill=color, justify="center"
            )
        
        if self.estado == "error" and random.random() < 0.12:
            self.canvas.delete("all")
            
        self.after(20, self.loop_render)

    def dibujar_contorno_gris_emo(self):
        """Dibuja un borde de rectángulo redondeado grisáceo/plateado grueso alrededor de la pantalla (idéntico a la foto de EMO)."""
        x1, y1 = 55, 20
        x2, y2 = 265, 180
        r = 34 # Muy redondeado, casi circular en esquinas
        
        c_gris_oscuro = "#6a6a75" # Gris base de contorno
        c_plateado = "#a6a6b2"    # Brillo plateado
        
        # Borde Gris Base Grueso
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            # Desplazamientos para simular sombra o grosor
            self.canvas.create_arc(x1+dx, y1+dy, x1 + 2*r+dx, y1 + 2*r+dy, start=90, extent=90, style="arc", outline=c_gris_oscuro, width=8)
            self.canvas.create_arc(x2 - 2*r+dx, y1+dy, x2+dx, y1 + 2*r+dy, start=0, extent=90, style="arc", outline=c_gris_oscuro, width=8)
            self.canvas.create_arc(x1+dx, y2 - 2*r+dy, x1 + 2*r+dx, y2+dy, start=180, extent=90, style="arc", outline=c_gris_oscuro, width=8)
            self.canvas.create_arc(x2 - 2*r+dx, y2 - 2*r+dy, x2+dx, y2+dy, start=270, extent=90, style="arc", outline=c_gris_oscuro, width=8)
            
            self.canvas.create_line(x1 + r+dx, y1+dy, x2 - r+dx, y1+dy, fill=c_gris_oscuro, width=8)
            self.canvas.create_line(x1 + r+dx, y2+dy, x2 - r+dx, y2+dy, fill=c_gris_oscuro, width=8)
            self.canvas.create_line(x1+dx, y1 + r+dy, x1+dx, y2 - r+dy, fill=c_gris_oscuro, width=8)
            self.canvas.create_line(x2+dx, y1 + r+dy, x2+dx, y2 - r+dy, fill=c_gris_oscuro, width=8)
            
        # Línea de brillo plateada encima
        self.canvas.create_arc(x1, y1, x1 + 2*r, y1 + 2*r, start=90, extent=90, style="arc", outline=c_plateado, width=5)
        self.canvas.create_arc(x2 - 2*r, y1, x2, y1 + 2*r, start=0, extent=90, style="arc", outline=c_plateado, width=5)
        self.canvas.create_arc(x1, y2 - 2*r, x1 + 2*r, y2, start=180, extent=90, style="arc", outline=c_plateado, width=5)
        self.canvas.create_arc(x2 - 2*r, y2 - 2*r, x2, y2, start=270, extent=90, style="arc", outline=c_plateado, width=5)
        
        self.canvas.create_line(x1 + r, y1, x2 - r, y1, fill=c_plateado, width=5)
        self.canvas.create_line(x1 + r, y2, x2 - r, y2, fill=c_plateado, width=5)
        self.canvas.create_line(x1, y1 + r, x1, y2 - r, fill=c_plateado, width=5)
        self.canvas.create_line(x2, y1 + r, x2, y2 - r, fill=c_plateado, width=5)

    def dibujar_ojo_intellar(self, cx, cy, rx, ry, color, izquierdo=True):
        """Dibuja un ojo sólido o un Guiño (Wink) si es confirmación."""
        if rx <= 0 or ry <= 0:
            return
            
        if self.estado == "confirm" or (self.estado == "idle" and self._idle_action == "wink"):
            if izquierdo:
                # Ojo izquierdo guiña: un arco feliz de neón (^ )
                self.canvas.create_arc(
                    cx - rx, cy - ry + 12, cx + rx, cy + ry + 12,
                    start=30, extent=120, style="arc",
                    outline=color, width=9.0
                )
                self.canvas.create_arc(
                    cx - rx, cy - ry + 12, cx + rx, cy + ry + 12,
                    start=35, extent=110, style="arc",
                    outline="#ffffff", width=2.5
                )
            else:
                # Ojo derecho abierto normal
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
            # Ojos en arco curvo brillante
            self.canvas.create_arc(
                cx - rx, cy - ry + 12, cx + rx, cy + ry + 12,
                start=30, extent=120, style="arc",
                outline=color, width=9.0
            )
            self.canvas.create_arc(
                cx - rx, cy - ry + 12, cx + rx, cy + ry + 12,
                start=35, extent=110, style="arc",
                outline="#ffffff", width=2.5
            )
            return

        # Dibujar el rectángulo redondeado sólido del ojo
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
                cx - rx - 10, cy - ry - 10 + (12 * dir_c),
                cx + rx + 10, cy - ry - 10 - (12 * dir_c),
                cx + rx + 10, cy - ry + 4,
                cx - rx - 10, cy - ry + 4
            ]
            self.canvas.create_polygon(pts, fill="#000000", outline="")
            
        elif self.estado in ["sad", "error"]:
            dir_c = 1 if izquierdo else -1
            pts = [
                cx - rx - 10, cy - ry - 10 - (10 * dir_c),
                cx + rx + 10, cy - ry - 10 + (10 * dir_c),
                cx + rx + 10, cy - ry + 8,
                cx - rx - 10, cy - ry + 8
            ]
            self.canvas.create_polygon(pts, fill="#000000", outline="")
            
            # Lágrima deslizante
            if self.estado == "sad":
                tx = cx - rx * 0.5 if izquierdo else cx + rx * 0.5
                ty = cy + ry * 0.8 + self.tiempo_lagrima
                self.canvas.create_oval(tx - 3.5, ty, tx + 3.5, ty + 10, fill="#3b82f6", outline="")
                self.canvas.create_polygon(tx - 3.5, ty + 3, tx, ty - 2, tx + 3.5, ty + 3, fill="#3b82f6", outline="")

    def dibujar_boca_eilik(self, cx, cy, color):
        import math
        
        if self.estado == "idle" and self._idle_action == "yawn":
            self.canvas.create_oval(
                cx - 5, cy - 8, cx + 5, cy + 8,
                fill=color, outline=""
            )
            
        elif self.estado in ["happy", "confirm"] or (self.estado == "idle" and self._idle_action == "wink"):
            self.canvas.create_arc(
                cx - 18, cy - 12, cx + 18, cy + 12,
                start=180, extent=180, style="pieslice",
                fill=color, outline=""
            )
            self.canvas.create_line(
                cx - 18, cy, cx + 18, cy,
                fill="#ffffff", width=2.5, capstyle="round"
            )
            
        elif self.estado in ["sad", "angry"] or (self.estado == "idle" and self._idle_action == "sigh"):
            self.canvas.create_arc(
                cx - 15, cy, cx + 15, cy + 18,
                start=0, extent=180, style="arc",
                outline=color, width=4.5
            )
            
        elif self.estado == "listening":
            r_dot = 4.0 + 1.5 * math.sin(self.tiempo * 3.5)
            self.canvas.create_oval(
                cx - r_dot, cy - r_dot, cx + r_dot, cy + r_dot,
                fill=color, outline=""
            )
            
        elif self.estado == "talking":
            ancho_col = 5.5
            espaciado = 9
            for i in range(-2, 3):
                fase = abs(i)
                h = 4.0 + 18.0 * abs(math.sin(self.tiempo * 15 - fase * 0.7))
                x = cx + i * espaciado
                self.canvas.create_line(
                    x, cy - h/2, x, cy + h/2,
                    fill=color, width=ancho_col, capstyle="round"
                )
            
        elif self.estado == "error":
            self.canvas.create_line(
                cx - 16, cy, cx - 8, cy - 4, cx, cy + 4, cx + 8, cy - 4, cx + 16, cy,
                fill=color, width=4.5, capstyle="round"
            )
            
        else: # idle, thinking
            self.canvas.create_line(
                cx - 12, cy, cx + 12, cy,
                fill=color, width=4.5, capstyle="round"
            )

    def loop_parpadeo(self):
        if self.estado in ["idle", "listening", "talking", "happy", "confirm"] and self._idle_action == "none":
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
        if self.estado in ["idle", "listening"] and self._idle_action == "none":
            if random.random() < 0.65:
                self.tgt_look_x = random.uniform(-10.0, 10.0)
                self.tgt_look_y = random.uniform(-6.0, 6.0)
            else:
                self.tgt_look_x = 0.0
                self.tgt_look_y = 0.0
                
        self.after(random.randint(1200, 3500), self.loop_saccades)

# --- CÓDIGO DE PRUEBA ---
if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    app = ctk.CTk()
    app.title("EMO Screen Replica — Final")
    app.geometry("400x320")
    app.configure(fg_color="#000000")
    
    frame_face = ctk.CTkFrame(
        app, fg_color="#000000", border_width=0
    )
    frame_face.pack(pady=20, padx=20, fill="both", expand=True)
    
    face = EmoBezelFace(frame_face)
    face.pack(fill="both", expand=True, padx=5, pady=5)
    
    panel = ctk.CTkFrame(app, fg_color="transparent")
    panel.pack(pady=(0, 20))
    
    estados = [
        ("Idle 💤", "idle", ""),
        ("Listen 🎤", "listening", ""),
        ("Think 🧠", "thinking", ""),
        ("Talk 🔊", "talking", ""),
        ("Happy 😊", "happy", ""),
        ("Angry 😠", "angry", ""),
        ("Sad 😢", "sad", ""),
        ("Error ⚠️", "error", ""),
        ("Confirm 🎮", "confirm", "ABRIENDO VALORANT..."),
        ("Confirm 🌐", "confirm", "ABRIENDO BRAVE BROWSER...")
    ]
    
    for idx, (lbl, est, msg) in enumerate(estados):
        r = idx // 5
        c = idx % 5
        btn = ctk.CTkButton(
            panel, text=lbl, width=65, height=32,
            font=("Segoe UI", 10, "bold"),
            fg_color="#121212", hover_color="#222222",
            text_color="#00f0ff", border_color="#00f0ff", border_width=1,
            corner_radius=6,
            command=lambda state=est, message=msg: face.cambiar_estado(state, message)
        )
        btn.grid(row=r, column=c, padx=3, pady=3)
        
    app.mainloop()
