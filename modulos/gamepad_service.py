"""
gamepad_service.py
===================
Servicio independiente en subproceso para lectura de mandos (Xbox / DualSense).
Usa XInput (API nativa de Microsoft) como respaldo cuando Pygame/SDL no puede
leer el mando porque un juego lo tiene capturado en primer plano.
"""

import os
import sys
import time

# CRÍTICO: Prevenir que SDL inicialice controladores de video de Windows
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

try:
    import pygame
except ImportError:
    print("ERROR: Pygame no está instalado", flush=True)
    sys.exit(1)

# Asegurar que el directorio raíz del proyecto esté en sys.path
_script_dir = os.path.dirname(os.path.abspath(__file__))
_proj_root = os.path.abspath(os.path.join(_script_dir, ".."))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

# Importar lector XInput nativo
try:
    from modulos.xinput_reader import (
        MandoXInput, escanear_mandos_xinput, XInputButtons
    )
    XINPUT_DISPONIBLE = True
except Exception as e:
    print(f"XInput no disponible: {e}", flush=True)
    XINPUT_DISPONIBLE = False

MAPEOS_ORDENADOS = [
    ("xbox", (8, 9)),
    ("xinput", (8, 9)),
    ("dualsense", (7, 8)),
    ("ps5", (7, 8)),
    ("playstation", (7, 8)),
    ("sony", (7, 8)),
    ("wireless controller", (7, 8)),
]
MAPEO_DEFECTO = (8, 9)
MAPEOS_ALTERNATIVOS = [(8, 9), (7, 8), (9, 10)]


def obtener_mapeo(nombre_mando: str, total_botones: int):
    nombre = nombre_mando.lower()
    for clave, (l3, r3) in MAPEOS_ORDENADOS:
        if clave in nombre:
            if l3 < total_botones and r3 < total_botones:
                return l3, r3

    for l3, r3 in MAPEOS_ALTERNATIVOS:
        if l3 < total_botones and r3 < total_botones:
            return l3, r3

    return MAPEO_DEFECTO


def main():
    try:
        pygame.init()
        pygame.joystick.init()
    except Exception as e:
        print(f"ERROR: No se pudo inicializar Pygame: {e}", flush=True)
        sys.exit(1)

    mandos_activos = {}
    indices_fallidos = set()
    combo_presionado = False
    ultimo_refresh = 0.0

    # Estado de mandos XInput (funcionan incluso cuando el juego captura el mando)
    mandos_xinput = {}  # indice -> MandoXInput
    xinput_conectados_prev = set()

    while True:
        try:
            pygame.event.pump()
            cant = pygame.joystick.get_count()

            # ========== LECTURA XINPUT (funciona aunque el juego tenga el foco) ==========
            if XINPUT_DISPONIBLE:
                xinput_actuales = set()
                for mando in escanear_mandos_xinput():
                    xinput_actuales.add(mando.indice)
                    if mando.indice not in mandos_xinput:
                        mandos_xinput[mando.indice] = mando
                        nombre = mando.nombre
                        print(f"MANDO_ADDED:{mando.indice}:{nombre}", flush=True)
                    # Actualizar estado
                    mandos_xinput[mando.indice] = mando

                # Detectar desconexiones en XInput
                for idx in list(mandos_xinput.keys()):
                    if idx not in xinput_actuales:
                        del mandos_xinput[idx]
                        print(f"MANDO_REMOVED:{idx}", flush=True)
                        # También limpiar de pygame si estaba
                        if idx in mandos_activos:
                            del mandos_activos[idx]

                xinput_conectados_prev = xinput_actuales

            # ========== LECTURA PYGAME (mandos no-Xbox como DualSense) ==========
            # Reintentar mandos que fallaron en intentos anteriores
            for i in list(indices_fallidos):
                if i >= cant:
                    indices_fallidos.discard(i)
                    continue
                try:
                    joy = pygame.joystick.Joystick(i)
                    joy.init()
                    nombre = joy.get_name()
                    l3, r3 = obtener_mapeo(nombre, joy.get_numbuttons())
                    mandos_activos[i] = {"joy": joy, "l3": l3, "r3": r3, "nombre": nombre}
                    print(f"MANDO_ADDED:{i}:{nombre}", flush=True)
                    indices_fallidos.discard(i)
                except Exception:
                    pass

            # Escanear y registrar mandos nuevos
            for i in range(cant):
                if i not in mandos_activos and i not in indices_fallidos:
                    try:
                        joy = pygame.joystick.Joystick(i)
                        joy.init()
                        nombre = joy.get_name()
                        l3, r3 = obtener_mapeo(nombre, joy.get_numbuttons())
                        mandos_activos[i] = {"joy": joy, "l3": l3, "r3": r3, "nombre": nombre}
                        print(f"MANDO_ADDED:{i}:{nombre}", flush=True)
                    except Exception:
                        indices_fallidos.add(i)

            # Si hay índices fallidos y pasaron >3s, forzar re-escaneo SDL
            if indices_fallidos and (time.time() - ultimo_refresh) > 3.0:
                ultimo_refresh = time.time()
                try:
                    pygame.joystick.quit()
                    pygame.joystick.init()
                    mandos_activos.clear()
                    indices_fallidos.clear()
                except Exception:
                    pass

            # Detectar mandos desconectados
            for i in list(mandos_activos.keys()):
                if i >= cant:
                    del mandos_activos[i]
                    print(f"MANDO_REMOVED:{i}", flush=True)

            # ========== DETECTAR L3+R3 (combinando ambas fuentes) ==========
            combo_activo = False
            mando_origen = ""

            # Intentar con Pygame primero
            if not combo_activo:
                for m in mandos_activos.values():
                    try:
                        joy = m["joy"]
                        total = joy.get_numbuttons()
                        l3, r3 = m["l3"], m["r3"]
                        if l3 < total and r3 < total:
                            if joy.get_button(l3) and joy.get_button(r3):
                                combo_activo = True
                                mando_origen = m["nombre"]
                                break
                    except Exception:
                        pass

            # Si Pygame no lo detectó, probar con XInput (funciona aunque el juego
            # tenga capturado el mando en modo exclusivo)
            if not combo_activo and XINPUT_DISPONIBLE:
                for idx, mando in mandos_xinput.items():
                    try:
                        if mando.esta_presionado_l3_r3():
                            combo_activo = True
                            mando_origen = mando.nombre + " (XInput)"
                            break
                    except Exception:
                        pass

            # Notificar cambios de combo
            if combo_activo and not combo_presionado:
                combo_presionado = True
                print(f"COMBO_START:{mando_origen}", flush=True)
            elif not combo_activo and combo_presionado:
                combo_presionado = False
                print("COMBO_STOP", flush=True)

            time.sleep(0.03)
        except KeyboardInterrupt:
            break
        except Exception as e:
            time.sleep(1.0)


if __name__ == "__main__":
    main()