import os
import time
import threading
import keyboard
import msvcrt
import warnings

# Silenciamos advertencias molestas
warnings.filterwarnings("ignore", category=RuntimeWarning)

# Importamos configuraciones
from config import TECLA_HABLAR

# Importamos nuestros módulos recién creados
from modulos.audio import capturar_voz_micro, detener_voz, hablar_no_bloqueante
import modulos.audio as audio_modulo # Para acceder a su variable de estado (hablando_actualmente)
from modulos.ia import enviar_a_gemini
from modulos.sistema import obtener_estado_pc_valores

# =====================================================================
# HILO PROACTIVO: MODO ALERTA DE HARDWARE
# =====================================================================
ALERTA_GPU_DISPARADA = False
ALERTA_RAM_DISPARADA = False

def _hilo_alerta_hardware():
    global ALERTA_GPU_DISPARADA, ALERTA_RAM_DISPARADA
    print("🔔 [MAIN] Hilo proactivo 'Modo Alerta' iniciado.")
    
    while True:
        time.sleep(30)
        try:
            _, ram_uso, _, gpu_temp = obtener_estado_pc_valores()
            
            if gpu_temp >= 82:
                if not ALERTA_GPU_DISPARADA and not audio_modulo.hablando_actualmente:
                    print(f"🚨 [ALERTA DE HARDWARE] GPU a {gpu_temp}°C!")
                    hablar_no_bloqueante(f"Che Luis, disculpa que te interrumpa, pero la placa de video llegó a {gpu_temp} grados. Fíjate si no se taparon los coolers o si hay que bajarle un toque a los gráficos.")
                    ALERTA_GPU_DISPARADA = True
            else:
                ALERTA_GPU_DISPARADA = False
                
            if ram_uso >= 92:
                if not ALERTA_RAM_DISPARADA and not audio_modulo.hablando_actualmente:
                    print(f"🚨 [ALERTA DE HARDWARE] RAM saturada al {ram_uso}%!")
                    hablar_no_bloqueante("Luis, ojo que nos estamos quedando sin memoria RAM. Tenes el noventa y dos por ciento ocupado, fíjate de cerrar lo que no uses.")
                    ALERTA_RAM_DISPARADA = True
            else:
                ALERTA_RAM_DISPARADA = False

        except Exception as e:
            print(f"⚠️ Error en hilo de monitoreo proactivo: {e}")

# Iniciamos el vigilante de hardware en segundo plano
threading.Thread(target=_hilo_alerta_hardware, daemon=True).start()

# =====================================================================
# BUCLE PRINCIPAL (ENTRY POINT)
# =====================================================================
if __name__ == "__main__":
    print("\n⌨️ [MODO HÍBRIDO ACTIVO - ARQUITECTURA MODULAR]")
    print(f"- Para HABLAR/INTERRUMPIR: Mantené presionado [{TECLA_HABLAR.upper()}].")
    print("- Para CALLARLO rápido: Presioná [ESC].")
    print("- Para ESCRIBIR: Escribí abajo y dale Enter.")
    
    # Limpiamos pulsaciones residuales del teclado
    while msvcrt.kbhit(): msvcrt.getch()

    while True:
        try:
            # 1. Lógica para silenciar a la IA con ESC
            if audio_modulo.hablando_actualmente and keyboard.is_pressed('esc'):
                detener_voz()
                while keyboard.is_pressed('esc'): time.sleep(0.05)
                continue

            # 2. Lógica para capturar voz
            if keyboard.is_pressed(TECLA_HABLAR):
                if audio_modulo.hablando_actualmente:
                    detener_voz()
                
                texto_voz = capturar_voz_micro()
                if texto_voz:
                    print(f"\n> Luis (Voz): {texto_voz}")
                    if texto_voz.lower().strip(".,¿?") in ["cerrar", "salir", "chau"]:
                        os._exit(0)
                    enviar_a_gemini(texto_voz, modo_voz=True)
                
                while keyboard.is_pressed(TECLA_HABLAR): time.sleep(0.05)
                while msvcrt.kbhit(): msvcrt.getch()
                continue

            # 3. Lógica para capturar texto escrito
            if msvcrt.kbhit():
                if keyboard.is_pressed(TECLA_HABLAR): continue
                if audio_modulo.hablando_actualmente:
                    detener_voz()
                    
                entrada_texto = input("\n⌨️ Texto > ")
                if entrada_texto.strip():
                    if entrada_texto.lower().strip() in ["cerrar", "salir", "chau"]:
                        os._exit(0)
                    enviar_a_gemini(entrada_texto, modo_voz=False)
            
            time.sleep(0.02)
            
        except KeyboardInterrupt:
            print("\nApagando sistema OmniAssistant...")
            break