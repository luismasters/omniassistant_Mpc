"""
diagnostico_gamepad.py
========================
Script standalone para identificar el índice EXACTO de los botones
L3 (click stick izquierdo) y R3 (click stick derecho) en tu mando.

CÓMO USARLO:
1. Corré este script directo: python diagnostico_gamepad.py
2. Va a mostrar el nombre de tu mando y la cantidad total de botones.
3. Presioná y soltá CADA botón del mando uno por uno (no los sticks
   todavía, solo botones de cara, gatillos, bumpers).
4. Después presioná SOLO el stick izquierdo (click) — anotá el número.
5. Después presioná SOLO el stick derecho (click) — anotá el número.
6. Pasame esos dos números y ajusto el mapeo en gamepad_control.py.

El script corre en bucle infinito, cerralo con Ctrl+C cuando termines.
"""

import pygame
import sys
import time

def main():
    pygame.init()
    pygame.joystick.init()

    cantidad = pygame.joystick.get_count()
    if cantidad == 0:
        print("❌ No se detectó ningún mando. Verificá que esté conectado y encendido.")
        sys.exit(1)

    joy = pygame.joystick.Joystick(0)
    joy.init()

    print("=" * 60)
    print(f"✅ Mando detectado: {joy.get_name()}")
    print(f"📊 Total de botones reportados: {joy.get_numbuttons()}")
    print(f"📊 Total de ejes (sticks/gatillos analógicos): {joy.get_numaxes()}")
    print("=" * 60)
    print()
    print("Presioná botones del mando uno por uno (Ctrl+C para salir).")
    print("Cuando presiones L3 (click stick izquierdo) y R3 (click")
    print("stick derecho), prestá atención a qué número aparece.")
    print()

    estado_anterior = [False] * joy.get_numbuttons()

    try:
        while True:
            pygame.event.pump()

            for i in range(joy.get_numbuttons()):
                estado_actual = joy.get_button(i)
                if estado_actual and not estado_anterior[i]:
                    print(f"🔘 BOTÓN PRESIONADO → índice {i}")
                elif not estado_actual and estado_anterior[i]:
                    print(f"   (soltado índice {i})")
                estado_anterior[i] = estado_actual

            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\n\nDiagnóstico finalizado.")
        pygame.quit()


if __name__ == "__main__":
    main()