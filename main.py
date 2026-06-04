import os
import time
import threading
import keyboard
import msvcrt
import warnings
import tkinter as tk
from tkinter import scrolledtext
from tkinter import filedialog 

warnings.filterwarnings("ignore", category=RuntimeWarning)

from config import TECLA_HABLAR
from modulos.audio import capturar_voz_micro, detener_voz, hablar_no_bloqueante
import modulos.audio as audio_modulo
from modulos.ia import enviar_a_gemini, procesar_archivo_adjunto 
from modulos.sistema import obtener_estado_pc_valores

root = None
lbl_estado = None
historial_chat = None
entrada_chat = None
frame_chat = None
chat_expandido = False

def actualizar_estado_ui(nuevo_texto, color="#00E5FF"):
    if lbl_estado and root:
        try:
            root.after(0, lambda: lbl_estado.config(text=nuevo_texto, fg=color))
        except:
            pass

def agregar_mensaje_ui(remitente, texto, color="#E8EAED", nueva_linea=True):
    if historial_chat and root:
        def actualizar():
            historial_chat.config(state=tk.NORMAL)
            
            if remitente:
                color_remitente = color
                if "luis" in remitente.lower(): color_remitente = "#81C995" 
                elif "cortana" in remitente.lower(): color_remitente = "#A8C7FA" 
                elif "sistema" in remitente.lower(): color_remitente = "#80868B" 
                
                if color_remitente not in historial_chat.tag_names():
                    historial_chat.tag_config(color_remitente, foreground=color_remitente)
                
                historial_chat.insert(tk.END, f"{remitente}: ", ("bold", color_remitente))
                
            if texto:
                color_texto = "#E8EAED" 
                if remitente and "sistema" in remitente.lower(): color_texto = "#80868B"
                elif remitente and "luis" in remitente.lower(): color_texto = "#C4EDD0" 
                    
                if color_texto not in historial_chat.tag_names():
                    historial_chat.tag_config(color_texto, foreground=color_texto)
                    
                historial_chat.insert(tk.END, texto, (color_texto,))
                
            if nueva_linea: historial_chat.insert(tk.END, "\n\n")
            historial_chat.see(tk.END)
            historial_chat.config(state=tk.DISABLED)
        root.after(0, actualizar)

def toggle_chat(event=None):
    global chat_expandido
    if not chat_expandido:
        root.geometry("550x650")
        frame_chat.pack(fill="both", expand=True)
        chat_expandido = True
    else:
        root.geometry("350x60") 
        frame_chat.pack_forget()
        chat_expandido = False

def procesar_envio_texto(event=None):
    texto = entrada_chat.get("1.0", tk.END).strip()
    if texto:
        if texto.lower() in ["cerrar", "salir", "chau"]: os._exit(0)
            
        agregar_mensaje_ui("Luis", texto, "#81C995")
        entrada_chat.delete("1.0", tk.END)
        actualizar_estado_ui("🧠 Pensando...", "#FF00FF")
        
        threading.Thread(target=enviar_a_gemini, args=(texto, False, agregar_mensaje_ui), daemon=True).start()
        root.after(2000, lambda: actualizar_estado_ui("🔵 Cortana | En línea", "#A8C7FA"))
    return "break" 

def accion_adjuntar():
    rutas_archivos = filedialog.askopenfilenames(
        title="Selecciona los archivos para Cortana (Puedes elegir varios)",
        filetypes=[("Documentos y Código", "*.pdf *.txt *.docx *.py *.js *.cs *.html *.json *.md *.csv")]
    )
    if rutas_archivos:
        threading.Thread(target=procesar_archivo_adjunto, args=(rutas_archivos, agregar_mensaje_ui), daemon=True).start()

ALERTA_GPU_DISPARADA = False
ALERTA_RAM_DISPARADA = False

def _hilo_alerta_hardware():
    global ALERTA_GPU_DISPARADA, ALERTA_RAM_DISPARADA
    while True:
        time.sleep(30)
        try:
            _, ram_uso, _, gpu_temp = obtener_estado_pc_valores()
            if gpu_temp >= 82:
                if not ALERTA_GPU_DISPARADA and not audio_modulo.hablando_actualmente:
                    actualizar_estado_ui(f"🚨 GPU a {gpu_temp}°C!", "#FF0000")
                    hablar_no_bloqueante(f"Luis, la placa de video llegó a {gpu_temp} grados.")
                    ALERTA_GPU_DISPARADA = True
            else: ALERTA_GPU_DISPARADA = False
                
            if ram_uso >= 92:
                if not ALERTA_RAM_DISPARADA and not audio_modulo.hablando_actualmente:
                    actualizar_estado_ui(f"🚨 RAM saturada al {ram_uso}%!", "#FF0000")
                    hablar_no_bloqueante(f"Luis, memoria RAM al {ram_uso} por ciento.")
                    ALERTA_RAM_DISPARADA = True
            else: ALERTA_RAM_DISPARADA = False
        except: pass

def motor_microfono():
    while msvcrt.kbhit(): msvcrt.getch()
    actualizar_estado_ui("🔵 Cortana | En línea (TAB para abrir chat)", "#A8C7FA")

    while True:
        try:
            if audio_modulo.hablando_actualmente and keyboard.is_pressed('esc'):
                detener_voz()
                actualizar_estado_ui("🛑 Interrumpida", "#FFA500")
                while keyboard.is_pressed('esc'): time.sleep(0.05)
                actualizar_estado_ui("🔵 Cortana | En línea", "#A8C7FA")
                continue

            if keyboard.is_pressed(TECLA_HABLAR):
                if audio_modulo.hablando_actualmente: detener_voz()
                
                actualizar_estado_ui("🎙️ Escuchando...", "#81C995")
                texto_voz = capturar_voz_micro()
                
                if texto_voz:
                    agregar_mensaje_ui("Luis (Voz)", texto_voz, "#81C995")
                    texto_corto = texto_voz[:27] + "..." if len(texto_voz) > 30 else texto_voz
                    actualizar_estado_ui(f"🗣️ {texto_corto}", "#E8EAED")
                    
                    if texto_voz.lower().strip(".,¿?") in ["cerrar", "salir", "chau"]: os._exit(0)
                        
                    actualizar_estado_ui("🧠 Pensando...", "#FF00FF")
                    enviar_a_gemini(texto_voz, modo_voz=True, ui_callback=agregar_mensaje_ui)
                    actualizar_estado_ui("🔵 Cortana | En línea", "#A8C7FA")
                else:
                    actualizar_estado_ui("🔵 Cortana | En línea", "#A8C7FA")
                
                while keyboard.is_pressed(TECLA_HABLAR): time.sleep(0.05)
                continue
            
            time.sleep(0.02)
        except KeyboardInterrupt:
            os._exit(0)

if __name__ == "__main__":
    threading.Thread(target=_hilo_alerta_hardware, daemon=True).start()
    threading.Thread(target=motor_microfono, daemon=True).start()

    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-alpha", 0.93)
    root.attributes("-topmost", True)
    root.configure(bg="#1E1E1E") 
    root.geometry("350x60+100+100")
    
    frame_superior = tk.Frame(root, bg="#111111", height=60)
    frame_superior.pack(fill="x")
    frame_superior.pack_propagate(False)
    
    lbl_estado = tk.Label(frame_superior, text="🔵 Iniciando sistemas...", fg="#A8C7FA", bg="#111111", font=("Consolas", 11, "bold"))
    lbl_estado.pack(expand=True, fill="both")

    frame_chat = tk.Frame(root, bg="#1E1E1E")
    
    frame_input = tk.Frame(frame_chat, bg="#111111", padx=8, pady=8)
    frame_input.pack(fill="x", side=tk.BOTTOM)
    
    btn_adjuntar = tk.Button(
        frame_input, text="📎", bg="#262626", fg="#A8C7FA", 
        font=("Segoe UI", 12), bd=0, cursor="hand2", command=accion_adjuntar
    )
    btn_adjuntar.pack(side=tk.LEFT, padx=(0, 8), fill="y")
    
    entrada_chat = tk.Text(
        frame_input, height=2, bg="#262626", fg="#F3F4F6", 
        font=("Segoe UI", 11), insertbackground="white", bd=0, padx=5, pady=5
    )
    entrada_chat.pack(side=tk.LEFT, fill="x", expand=True)
    entrada_chat.bind("<Return>", procesar_envio_texto)

    historial_chat = scrolledtext.ScrolledText(
        frame_chat, bg="#18181B", fg="#E8EAED", font=("Segoe UI", 11),
        state=tk.DISABLED, wrap=tk.WORD, bd=0, padx=12, pady=12
    )
    historial_chat.pack(fill="both", expand=True, side=tk.TOP)
    historial_chat.tag_config("bold", font=("Segoe UI", 11, "bold"))

    def mover_ventana(event): root.geometry(f'+{event.x_root - 175}+{event.y_root - 30}')
    def cerrar_interfaz(event): os._exit(0)

    frame_superior.bind("<B1-Motion>", mover_ventana)
    lbl_estado.bind("<B1-Motion>", mover_ventana)
    root.bind("<Escape>", cerrar_interfaz)
    root.bind("<Tab>", toggle_chat)
    frame_superior.bind("<Double-Button-1>", toggle_chat)

    agregar_mensaje_ui("Sistema", "OmniAssistant RAG Multi-Archivo inicializado. Presioná Tab para contraer.", "#80868B")

    root.mainloop() 