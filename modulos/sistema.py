import os
import time
import threading
import subprocess
import psutil
import win32gui
import win32con
from screeninfo import get_monitors
import win32process
from thefuzz import process

# =====================================================================
# GESTIÓN MULTIMONITOR Y VENTANAS
# =====================================================================
def buscar_todas_las_ventanas():
    ventanas = []
    def callback(hwnd, extra):
        if win32gui.IsWindowVisible(hwnd):
            titulo = win32gui.GetWindowText(hwnd)
            if titulo: ventanas.append((hwnd, titulo))
        return True
    win32gui.EnumWindows(callback, None)
    return ventanas

def ventana_visible_existe(nombre_parcial):
    for hwnd, titulo in buscar_todas_las_ventanas():
        if nombre_parcial.lower() in titulo.lower() or (nombre_parcial.lower() == "code" and "visual studio code" in titulo.lower()):
            return True
    return False

def forzar_ventana_a_monitor(nombre_parcial_ventana, numero_monitor):
    monitors = get_monitors()
    if numero_monitor > len(monitors):
        print(f"⚠️ [WINDOWS REAL] Monitor {numero_monitor} no detectado.")
        return

    monitor_objetivo = monitors[numero_monitor - 1]
    
    for _ in range(15): 
        time.sleep(0.3)
        for hwnd, titulo in buscar_todas_las_ventanas():
            if nombre_parcial_ventana.lower() in titulo.lower() or (nombre_parcial_ventana.lower() == "code" and "visual studio code" in titulo.lower()):
                print(f"🎯 [WINDOWS REAL] Ventana encontrada: '{titulo}'. Moviendo a Monitor {numero_monitor}...")
                win32gui.ShowWindow(hwnd, win32con.SW_SHOWNORMAL)
                win32gui.MoveWindow(hwnd, monitor_objetivo.x + 100, monitor_objetivo.y + 100, 1280, 720, True)
                win32gui.ShowWindow(hwnd, win32con.SW_SHOWMAXIMIZED)
                return

# =====================================================================
# BÚSQUEDA DE ARCHIVOS, CARPETAS Y RUTAS
# =====================================================================
def buscar_archivo_o_carpeta(nombre_elemento):
    """Busca en tiempo real un archivo o carpeta dentro de las rutas del usuario."""
    print(f"📂 [PYTHON REAL] Radar mixto activado buscando: '{nombre_elemento}'")
    usuario = os.path.expanduser("~")
    zonas_busqueda = [
        os.path.expanduser(r"~\Desktop"),
        os.path.expanduser(r"~\Documents"),
        os.path.expanduser(r"~\Downloads"),
        os.path.expanduser(r"~\OneDrive\Escritorio"),
        os.path.expanduser(r"~\OneDrive\Descargas"),
        os.path.expanduser(r"~\OneDrive\Documentos"),
        os.path.expanduser(r"~\Pictures"),
        os.path.expanduser(r"~\OneDrive\Imágenes")
    ]
    
    nombre_puro = os.path.basename(nombre_elemento.replace("\\", "/")).lower()
    nombre_limpio = nombre_puro.replace(" ", "").replace("_", "").strip()
    
    for zona in zonas_busqueda:
        if not os.path.exists(zona): continue
        for raiz, directorios, archivos in os.walk(zona):
            directorios[:] = [d for d in directorios if d not in ['.git', 'node_modules', 'venv', '__pycache__', 'AppData', 'My Games']]
            
            for dir_name in directorios:
                dir_name_limpio = dir_name.lower().replace(" ", "").replace("_", "")
                if nombre_limpio in dir_name_limpio:
                    ruta_encontrada = os.path.join(raiz, dir_name)
                    print(f"✅ [PYTHON REAL] Carpeta encontrada en: {ruta_encontrada}")
                    return ruta_encontrada
                    
            for file_name in archivos:
                file_name_limpio = file_name.lower().replace(" ", "").replace("_", "")
                if nombre_limpio in file_name_limpio:
                    ruta_encontrada = os.path.join(raiz, file_name)
                    print(f"✅ [PYTHON REAL] Archivo encontrado en: {ruta_encontrada}")
                    return ruta_encontrada
    return None

def obtener_ruta_dinamica(opciones):
    for ruta in opciones:
        if os.path.exists(ruta): return ruta
    return opciones[0] 

# =====================================================================
# EXPLORADOR JUEZ 
# =====================================================================
def explorar_directorio(ruta_base):
    """Devuelve una lista de archivos y carpetas en una ruta."""
    if "@" in ruta_base: ruta_base = ruta_base.split("@")[0].strip()
    if "||" in ruta_base: ruta_base = ruta_base.split("||")[0].strip()
        
    print(f"👀 [EXPLORADOR] Cortana está mirando dentro de: '{ruta_base}'")
    
    try:
        usuario_real = os.path.expanduser("~")
        if "c:\\users\\luis\\" in ruta_base.lower() and "luism" not in ruta_base.lower():
            ruta_base = ruta_base.lower().replace("c:\\users\\luis", usuario_real)

        usuario = os.path.expanduser("~")
        ruta_docs = obtener_ruta_dinamica([os.path.join(usuario, "Documents"), os.path.join(usuario, "OneDrive", "Documentos")])
        ruta_desk = obtener_ruta_dinamica([os.path.join(usuario, "Desktop"), os.path.join(usuario, "OneDrive", "Escritorio")])
        ruta_pics = obtener_ruta_dinamica([os.path.join(usuario, "Pictures"), os.path.join(usuario, "OneDrive", "Imágenes")])
        ruta_capturas = obtener_ruta_dinamica([os.path.join(ruta_pics, "Screenshots"), os.path.join(ruta_pics, "Capturas de pantalla")])

        atajos = {
            "descargas": os.path.expanduser(r"~\Downloads"),
            "downloads": os.path.expanduser(r"~\Downloads"),
            "escritorio": ruta_desk,
            "desktop": ruta_desk,
            "documentos": ruta_docs,
            "imagenes": ruta_pics,
            "imágenes": ruta_pics,
            "fotos": ruta_pics,
            "capturas de pantalla": ruta_capturas,
            "capturas": ruta_capturas
        }
        
        ruta_real = atajos.get(ruta_base.lower().strip(), ruta_base.strip())

        if not os.path.exists(ruta_real) and "\\" not in ruta_real:
            ruta_buscada = buscar_archivo_o_carpeta(ruta_base)
            if ruta_buscada: ruta_real = ruta_buscada

        if not os.path.exists(ruta_real):
            return f"[RESULTADO EXPLORACIÓN]: La ruta '{ruta_real}' no existe en este equipo."

        elementos = os.listdir(ruta_real)
        carpetas = [e for e in elementos if os.path.isdir(os.path.join(ruta_real, e))]
        archivos = [e for e in elementos if not os.path.isdir(os.path.join(ruta_real, e))]

        resultado = f"[RESULTADO EXPLORACIÓN DE '{ruta_real}']:\n"
        resultado += f"📁 Carpetas ({len(carpetas)}): {', '.join(carpetas[:20])}\n"
        resultado += f"📄 Archivos ({len(archivos)}): {', '.join(archivos[:40])}\n"
        
        if len(archivos) > 40:
            resultado += "... (Hay más archivos, pero te muestro los primeros 40)\n"
            
        return resultado
    except Exception as e:
        return f"[RESULTADO EXPLORACIÓN]: Hubo un error de lectura: {e}"

# =====================================================================
# RADAR DE JUEGOS Y PROGRAMAS (Buscador Windows)
# =====================================================================
def radar_inteligente(nombre_buscado):
    usuario = os.path.expanduser("~")
    rutas_a_escanear = [
        os.path.expanduser(r"~\Desktop"),
        r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
        os.path.join(usuario, r"AppData\Roaming\Microsoft\Windows\Start Menu\Programs"),
        r"E:\Mis_Juegos_Yiri" 
    ]
    archivos_encontrados = {} 
    carpetas_ignoradas = ["venv", ".git", "node_modules", "__pycache__", "obj", "bin"]

    for ruta in rutas_a_escanear:
        if os.path.exists(ruta):
            for raiz, directorios, archivos in os.walk(ruta):
                directorios[:] = [d for d in directorios if d.lower() not in carpetas_ignoradas]
                for archivo in archivos:
                    archivo_baja = archivo.lower()
                    prohibidos = ["support", "soporte", "uninstall", "desinstalar", "help", "ayuda"]
                    if any(p in archivo_baja for p in prohibidos): continue
                    
                    if archivo_baja.endswith(('.lnk', '.exe', '.url')): 
                        nombre_limpio = os.path.splitext(archivo)[0]
                        if nombre_limpio.lower().endswith('.exe'):
                            nombre_limpio = nombre_limpio[:-4]
                            
                        ruta_completa = os.path.join(raiz, archivo)
                        archivos_encontrados[nombre_limpio] = ruta_completa

    if not archivos_encontrados: return None
    nombre_buscado_limpio = os.path.splitext(nombre_buscado)[0]
    nombres_posibles = list(archivos_encontrados.keys())
    mejor_coincidencia, puntaje = process.extractOne(nombre_buscado_limpio, nombres_posibles)

    print(f"🔍 [RADAR INTELIGENTE] Buscando Programa: '{nombre_buscado_limpio}'")
    print(f"📊 Mejor coincidencia: '{mejor_coincidencia}' (Similitud: {puntaje}%)")

    if puntaje >= 70:
        ruta_final = archivos_encontrados[mejor_coincidencia]
        print(f"✅ [ÉXITO] Programa encontrado: {ruta_final}")
        return ruta_final
    else:
        print("❌ [FALLO] No se encontró ningún programa parecido.")
        return None

def cerrar_programa_dinamico(nombre_programa):
    nombre_limpio = nombre_programa.lower().replace(".exe", "").strip()
    procesos_cerrados = 0
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if nombre_limpio in proc.info['name'].lower():
                proc.kill()
                procesos_cerrados += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess): pass
    return procesos_cerrados > 0

# =====================================================================
# EJECUCIÓN PRINCIPAL DE COMANDOS
# =====================================================================
def ejecutar_comando_sistema(comando_clave):
    comando_clave = comando_clave.lower().strip()
    url = ""
    
    if "||" in comando_clave:
        partes = comando_clave.split("||", 1)
        comando_clave = partes[0].strip()
        url = partes[1].strip()
        if url.startswith("url:"): url = url[4:].strip()

    num_monitor = None
    if "@" in comando_clave:
        partes_monitor = comando_clave.split("@")
        comando_clave = partes_monitor[0].strip()
        try:
            texto_monitor = partes_monitor[1]
            num_str = "".join(filter(str.isdigit, texto_monitor))
            if num_str: num_monitor = int(num_str)
        except Exception: pass

    if "navegar: brave" in comando_clave or "navegar: navegador" in comando_clave:
        comando_clave = comando_clave.replace("navegar:", "abrir:")

    es_navegacion = False
    objetivo = ""
    
    if "navegar:" in comando_clave:
        es_navegacion = True
        objetivo = comando_clave.replace("navegar:", "").strip()
    elif "abrir:" in comando_clave:
        objetivo = comando_clave.replace("abrir:", "").strip()
        if objetivo in ["youtube", "netflix", "amazon", "facebook", "twitch", "google", "github", "gmail"] or objetivo.startswith("http") or ".com" in objetivo:
            es_navegacion = True
    elif "cerrar:" in comando_clave:
        objetivo = comando_clave.replace("cerrar:", "").strip()
    elif "explorar:" in comando_clave:
        objetivo_explorar = comando_clave.replace("explorar:", "").strip().replace('"', '').replace("'", "")
        return explorar_directorio(objetivo_explorar)
    else:
        objetivo = comando_clave 

    try:
        if "apagar pc" in objetivo:
            os.system("shutdown /s /t 1800")
            return "Apagado programado en 30 min."
        elif "cancelar apagado" in objetivo:
            os.system("shutdown /a")
            return "Apagado cancelado."

        if es_navegacion:
            sitio = url if url else objetivo
            if not sitio: sitio = "google.com"
            if sitio.startswith("http"): destino = sitio
            else: destino = f"https://www.{sitio.replace(' ', '')}.com" if "." not in sitio else f"https://{sitio}"
            
            if ventana_visible_existe("brave"):
                if num_monitor: threading.Thread(target=forzar_ventana_a_monitor, args=("brave", num_monitor), daemon=True).start()
                subprocess.Popen(f"start brave {destino}", shell=True)
                return f"Abriendo {destino} en la ventana activa."
            else:
                subprocess.Popen(f"start brave {destino}", shell=True)
                if num_monitor: threading.Thread(target=forzar_ventana_a_monitor, args=("brave", num_monitor), daemon=True).start()
                return f"Navegando a {destino}."

        elif "abrir:" in comando_clave:
            if objetivo == "navegador": objetivo = "brave"
            
            if objetivo.startswith("steam://"):
                os.startfile(objetivo)
                return f"Juego de Steam lanzado instantáneamente por ID."
            
            objetivo_limpio = objetivo.replace('explorer.exe', '').replace('explorer', '').replace('"', '').strip()
            ultima_palabra = objetivo_limpio.split("\\")[-1].strip().lower()

            usuario = os.path.expanduser("~")
            ruta_docs = obtener_ruta_dinamica([os.path.join(usuario, "Documents"), os.path.join(usuario, "OneDrive", "Documentos")])
            ruta_desk = obtener_ruta_dinamica([os.path.join(usuario, "Desktop"), os.path.join(usuario, "OneDrive", "Escritorio")])
            ruta_pics = obtener_ruta_dinamica([os.path.join(usuario, "Pictures"), os.path.join(usuario, "OneDrive", "Imágenes")])
            ruta_capturas = obtener_ruta_dinamica([os.path.join(ruta_pics, "Screenshots"), os.path.join(ruta_pics, "Capturas de pantalla")])

            atajos_carpetas = {
                "documentos": ruta_docs,
                "descargas": os.path.expanduser(r"~\Downloads"),
                "downloads": os.path.expanduser(r"~\Downloads"),
                "escritorio": ruta_desk,
                "imagenes": ruta_pics,
                "capturas": ruta_capturas
            }

            if objetivo_limpio.lower() in atajos_carpetas:
                os.startfile(atajos_carpetas[objetivo_limpio.lower()])
                return f"Carpeta '{objetivo_limpio}' abierta al instante."
                
            elif ultima_palabra in atajos_carpetas:
                os.startfile(atajos_carpetas[ultima_palabra])
                return f"Carpeta del sistema abierta al instante desde ruta."

            if os.path.exists(objetivo_limpio):
                os.startfile(objetivo_limpio)
                return f"Ruta exacta '{objetivo_limpio}' abierta."

            if url: 
                destino = url if url.startswith("http") else f"https://{url}"
                subprocess.Popen(f"start {objetivo} {destino}", shell=True)
                if num_monitor: threading.Thread(target=forzar_ventana_a_monitor, args=(objetivo, num_monitor), daemon=True).start()
                return f"Navegador {objetivo} abierto."
                
            if ventana_visible_existe(objetivo) and objetivo in ["brave", "chrome", "edge", "code", "visual studio code", "vscode", "vs code"]:
                if num_monitor: threading.Thread(target=forzar_ventana_a_monitor, args=(objetivo, num_monitor), daemon=True).start()
                return f"Trayendo ventana activa al Monitor."

            # ========================================================
            # EL ORDEN DE PRIORIDAD PARA ABRIR COSAS
            # ========================================================
            # 1. PROGRAMAS Y JUEGOS (EL RADAR VA PRIMERO SIEMPRE)
            ruta_acceso = radar_inteligente(objetivo)
            if ruta_acceso:
                os.startfile(ruta_acceso)
                msg = f"Programa '{objetivo}' abierto."
                es_juego_steam = ruta_acceso.endswith(".url")
                if num_monitor and not es_juego_steam: 
                    threading.Thread(target=forzar_ventana_a_monitor, args=(objetivo, num_monitor), daemon=True).start()
                return msg

            # 2. ARCHIVOS Y CARPETAS
            ruta_elemento = buscar_archivo_o_carpeta(objetivo)
            if ruta_elemento:
                if ruta_elemento.endswith('.py') or ruta_elemento.endswith('.scr'):
                    pass 
                else:
                    os.startfile(ruta_elemento)
                    return f"Elemento '{objetivo}' encontrado y abierto."

            # 3. FUERZA BRUTA
            try:
                if ":" in objetivo or "\\" in objetivo:
                    os.startfile(objetivo)
                else:
                    subprocess.Popen(f'"{objetivo}"', shell=True)
                return f"Programa '{objetivo}' ejecutado por fuerza bruta."
            except Exception:
                return f"No se encontró ni la carpeta ni el programa '{objetivo}'."

        elif "cerrar:" in comando_clave:
            if objetivo == "navegador": objetivo = "brave" 
            if "steam" in objetivo.lower():
                os.system("start steam://exit")
                return "Se envió la señal de apagado oficial a Steam."
            
            cerrado = False
            objetivo_lower = objetivo.lower()

            def cazar_ventana(hwnd, ctx):
                nonlocal cerrado
                if win32gui.IsWindowVisible(hwnd):
                    titulo = win32gui.GetWindowText(hwnd).lower()
                    if objetivo_lower in titulo and objetivo_lower != "":
                        _, pid = win32process.GetWindowThreadProcessId(hwnd)
                        try:
                            proc = psutil.Process(pid)
                            proc.kill()
                            cerrado = True
                        except: pass
            try: win32gui.EnumWindows(cazar_ventana, None)
            except Exception: pass

            if not cerrado:
                for proc in psutil.process_iter(['name']):
                    try:
                        if proc.info['name'] and objetivo_lower in proc.info['name'].lower():
                            proc.kill()
                            cerrado = True
                    except (psutil.NoSuchProcess, psutil.AccessDenied, KeyError): pass

            if not cerrado:
                os.system(f'taskkill /F /IM "{objetivo}.exe" /T >nul 2>&1')
                
            return f"Se ejecutó el protocolo de cierre para '{objetivo}'."

        return f"Comando no ejecutable: {comando_clave}"
    except Exception as e:
        return f"Error de ejecución: {e}"

# =====================================================================
# HARDWARE Y TELEMETRÍA
# =====================================================================
def escanear_hardware_completo():
    try:
        cpu = subprocess.check_output('powershell -Command "(Get-CimInstance Win32_Processor).Name"', shell=True, text=True).strip()
        gpu = subprocess.check_output('powershell -Command "(Get-CimInstance Win32_VideoController).Name"', shell=True, text=True).strip()
        mobo = subprocess.check_output('powershell -Command "(Get-CimInstance Win32_BaseBoard).Manufacturer + \' \' + (Get-CimInstance Win32_BaseBoard).Product"', shell=True, text=True).strip()
        return {"cpu": cpu, "gpu": gpu, "motherboard": mobo}
    except Exception:
        return {"cpu": "Intel", "gpu": "NVIDIA", "motherboard": "Desconocida"}

def obtener_estado_pc_valores():
    cpu_uso = psutil.cpu_percent()
    memoria = psutil.virtual_memory()
    gpu_temp, gpu_vram_usada_gb = 0, 0
    try:
        res = subprocess.check_output("nvidia-smi --query-gpu=temperature.gpu,memory.used --format=csv,noheader,nounits", shell=True, text=True).strip()
        if res:
            partes = res.split(',')
            gpu_temp = int(partes[0].strip())
            gpu_vram_usada_gb = round(int(partes[1].strip()) / 1024, 1) 
    except: pass
    return cpu_uso, memoria.percent, gpu_vram_usada_gb, gpu_temp 

def obtener_estado_pc():
    cpu, ram_percent, gpu_vram, g_temp = obtener_estado_pc_valores()
    ram_gb = round(psutil.virtual_memory().used / (1024 ** 3), 1)
    return f"CPU: {cpu}% | RAM: {ram_percent}% ({ram_gb}GB) | GPU Temp: {g_temp}°C, VRAM: {gpu_vram}GB"

def obtener_ventanas_activas():
    ventanas = buscar_todas_las_ventanas()
    nombres_limpios = []
    ignorados = ["default ime", "program manager", "msctfime ui", "nvidia geforce overlay", "sin título"]
    for hwnd, titulo in ventanas:
        titulo_baja = titulo.lower()
        if not any(ignorado in titulo_baja for ignorado in ignorados) and titulo.strip():
            nombres_limpios.append(titulo)
    if not nombres_limpios: return "Ninguna aplicación a la vista."
    return " | ".join(nombres_limpios)