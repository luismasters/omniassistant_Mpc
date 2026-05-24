from PIL import ImageGrab
from screeninfo import get_monitors

def capturar_pantalla(numero_monitor=None):
    """Saca una captura de pantalla de un monitor específico o de todos si no se le pasa número."""
    try:
        if numero_monitor:
            monitores = get_monitors()
            # Chequeamos si el monitor que pediste existe realmente
            if numero_monitor <= len(monitores):
                # Restamos 1 porque en programación las listas empiezan en 0
                m = monitores[numero_monitor - 1] 
                
                # Calculamos las coordenadas: (Izquierda, Arriba, Derecha, Abajo)
                caja_del_monitor = (m.x, m.y, m.x + m.width, m.y + m.height)
                
                # Sacamos la foto solo de ese cuadradito
                captura = ImageGrab.grab(bbox=caja_del_monitor, all_screens=True)
                print(f"📸 [PYTHON REAL] Captura de la pantalla {numero_monitor} realizada.")
                return captura
            else:
                print(f"⚠️ [PYTHON REAL] El monitor {numero_monitor} no existe. Sacando foto de todo...")

        # Si no le decís qué pantalla querés, o si falla, saca la panorámica de siempre
        captura = ImageGrab.grab(all_screens=True)
        print("📸 [PYTHON REAL] Captura panorámica realizada.")
        return captura
    except Exception as e:
        print(f"⚠️ [PYTHON REAL] Error al capturar pantalla: {e}")
        return None