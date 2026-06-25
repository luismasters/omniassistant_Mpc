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
# LISTA DE SITIOS WEB COMUNES (SOLO para cuando el usuario dice "abre X" y X es un sitio conocido)
# Pero ahora NO se convierte automáticamente; solo se usa si no se encuentra el programa local.
# =====================================================================
SITIOS_WEB_COMUNES = [
    "twitch", "youtube", "google", "facebook", "twitter", "instagram",
    "github", "gmail", "netflix", "amazon", "reddit", "stackoverflow",
    "spotify", "whatsapp", "telegram", "slack", "trello",
    "notion", "figma", "canva", "zoom", "meet", "teams", "drive",
    "docs", "sheets", "slides", "calendar", "outlook", "yahoo",
    "bing", "duckduckgo", "wikipedia", "medium", "dev.to", "gitlab"
    # NOTA: Discord, Battle.net, etc. NO están aquí para que no se conviertan automáticamente.
]

# =====================================================================
# MAPEO DE MONITORES (intercambia 1 ↔ 2)
# =====================================================================
def _mapear_monitor(numero: int) -> int:
    if numero == 1:
        return 2
    elif numero == 2:
        return 1
    return numero

# =====================================================================
# GESTIÓN MULTIMONITOR Y VENTANAS
# =====================================================================
def buscar_todas_las_ventanas():
    ventanas = []
    def callback(hwnd, extra):
        if win32gui.IsWindowVisible(hwnd):
            titulo = win32gui.GetWindowText(hwnd)
            if titulo:
                ventanas.append((hwnd, titulo))
        return True
    win32gui.EnumWindows(callback, None)
    return ventanas

def ventana_visible_existe(nombre_parcial):
    for hwnd, titulo in buscar_todas_las_ventanas():
        if nombre_parcial.lower() in titulo.lower():
            return True
    return False

def forzar_ventana_a_monitor(nombre_parcial_ventana, numero_monitor):
    numero_monitor = _mapear_monitor(numero_monitor)
    monitors = get_monitors()
    if numero_monitor > len(monitors):
        print(f"⚠️ [WINDOWS REAL] Monitor {numero_monitor} no detectado.")
        return
    monitor_objetivo = monitors[numero_monitor - 1]
    for _ in range(15):
        time.sleep(0.3)
        for hwnd, titulo in buscar_todas_las_ventanas():
            if nombre_parcial_ventana.lower() in titulo.lower():
                print(f"🎯 [WINDOWS REAL] Ventana encontrada: '{titulo}'. Moviendo a Monitor {numero_monitor}...")
                win32gui.ShowWindow(hwnd, win32con.SW_SHOWNORMAL)
                win32gui.MoveWindow(hwnd, monitor_objetivo.x + 100, monitor_objetivo.y + 100, 1280, 720, True)
                win32gui.ShowWindow(hwnd, win32con.SW_SHOWMAXIMIZED)
                return

# =====================================================================
# BÚSQUEDA DE ARCHIVOS, CARPETAS Y RUTAS
# =====================================================================
def buscar_archivo_o_carpeta(nombre_elemento):
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
        if not os.path.exists(zona):
            continue
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
        if os.path.exists(ruta):
            return ruta
    return opciones[0]

# =====================================================================
# EXPLORADOR JUEZ
# =====================================================================
def explorar_directorio(ruta_base):
    if "@" in ruta_base:
        ruta_base = ruta_base.split("@")[0].strip()
    if "||" in ruta_base:
        ruta_base = ruta_base.split("||")[0].strip()
    print(f"👀 [EXPLORADOR] Argus está mirando dentro de: '{ruta_base}'")
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
            if ruta_buscada:
                ruta_real = ruta_buscada
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
# RADAR DE JUEGOS Y PROGRAMAS (Buscador Windows) - DINÁMICO
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
                    if any(p in archivo_baja for p in prohibidos):
                        continue
                    if archivo_baja.endswith(('.lnk', '.exe', '.url')):
                        nombre_limpio = os.path.splitext(archivo)[0]
                        if nombre_limpio.lower().endswith('.exe'):
                            nombre_limpio = nombre_limpio[:-4]
                        ruta_completa = os.path.join(raiz, archivo)
                        archivos_encontrados[nombre_limpio] = ruta_completa
    if not archivos_encontrados:
        return None
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
        # Intentar con variantes comunes (sin hardcodear)
        variantes = [
            nombre_buscado_limpio + " Launcher",
            nombre_buscado_limpio + ".exe",
            nombre_buscado_limpio.replace(" ", ""),
            nombre_buscado_limpio + " Client"
        ]
        for variante in variantes:
            mejor_var, puntaje_var = process.extractOne(variante, nombres_posibles)
            if puntaje_var >= 70:
                print(f"✅ [RADAR] Encontrado con variante '{variante}': {mejor_var} (Score: {puntaje_var}%)")
                return archivos_encontrados[mejor_var]
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
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return procesos_cerrados > 0

# =====================================================================
# EJECUCIÓN PRINCIPAL DE COMANDOS (NUEVA LÓGICA)
# =====================================================================
def ejecutar_comando_sistema(comando_clave):
    """
    Parsea y ejecuta comandos del sistema.
    - 'abrir: X' → busca programa local X; si no existe, sugiere abrir web.
    - 'navegar: X' → abre X como URL en el navegador.
    - 'mover: X @ N' → mueve la ventana X al monitor N.
    - 'cerrar: X' → cierra el programa X.
    - 'explorar: X' → lista el contenido de la carpeta X.
    """
    comando_clave = comando_clave.lower().strip()
    url = ""
    num_monitor = None
    verbo = None
    navegador_especifico = None

    # Extraer URL opcional después de ||
    if "||" in comando_clave:
        partes = comando_clave.split("||", 1)
        comando_clave = partes[0].strip()
        url = partes[1].strip()
        if url.startswith("url:"):
            url = url[4:].strip()

    # Extraer monitor @
    if "@" in comando_clave:
        partes_monitor = comando_clave.split("@")
        comando_clave = partes_monitor[0].strip()
        try:
            texto_monitor = partes_monitor[1]
            num_str = "".join(filter(str.isdigit, texto_monitor))
            if num_str:
                num_monitor = int(num_str)
        except Exception:
            pass

    # Determinar el verbo
    for v in ["abrir:", "navegar:", "cerrar:", "mover:", "explorar:"]:
        if comando_clave.startswith(v):
            verbo = v.replace(":", "")
            comando_clave = comando_clave[len(v):].strip()
            break

    if not verbo:
        return f"Comando no reconocido: {comando_clave}"

    # ── ABRIR (programa local) ──────────────────────────────────────────
    if verbo == "abrir":
        objetivo = comando_clave

        # Detectar si se especificó navegador (ej. "chrome https://...") pero con abrir:
        navegadores = ["chrome", "brave", "edge", "firefox"]
        for nb in navegadores:
            if objetivo.lower().startswith(nb + " "):
                navegador_especifico = nb
                objetivo = objetivo[len(nb):].strip()
                break

        # Si el objetivo es una URL, abrir en navegador (permitir abrir: https://...)
        if objetivo.startswith("http") or "://" in objetivo:
            return _abrir_url_en_navegador(objetivo, num_monitor, navegador_especifico or "brave")

        # Si no es URL, buscar programa local
        return _abrir_programa_o_carpeta(objetivo, num_monitor, navegador_especifico)

    # ── NAVEGAR (abrir URL en navegador) ───────────────────────────────
    if verbo == "navegar":
        objetivo = comando_clave
        # Si no es URL, construir una si es un sitio común
        if not (objetivo.startswith("http") or "://" in objetivo):
            # Si es un sitio conocido, construir URL
            if objetivo.lower() in SITIOS_WEB_COMUNES:
                sitio = objetivo.lower()
                if sitio == "twitch":
                    url = "https://www.twitch.tv"
                elif sitio == "youtube":
                    url = "https://www.youtube.com"
                elif sitio == "google":
                    url = "https://www.google.com"
                else:
                    url = f"https://www.{sitio}.com"
            else:
                # Si no es un sitio conocido, asumir que es una URL incompleta
                url = objetivo if "." in objetivo else f"https://www.{objetivo}.com"
        else:
            url = objetivo
        return _abrir_url_en_navegador(url, num_monitor, navegador_especifico or "brave")

    # ── CERRAR ──────────────────────────────────────────────────────────
    if verbo == "cerrar":
        return _cerrar_programa(comando_clave)

    # ── MOVER ────────────────────────────────────────────────────────────
    if verbo == "mover":
        if num_monitor:
            threading.Thread(target=forzar_ventana_a_monitor, args=(comando_clave, num_monitor), daemon=True).start()
            return f"Moviendo '{comando_clave}' al monitor {num_monitor}."
        else:
            return "Especifica un monitor con @ (ej: mover: brave @ 2)"

    # ── EXPLORAR ─────────────────────────────────────────────────────────
    if verbo == "explorar":
        return explorar_directorio(comando_clave)

    # ── APAGADO ──────────────────────────────────────────────────────────
    if "apagar pc" in comando_clave:
        os.system("shutdown /s /t 1800")
        return "Apagado programado en 30 min."
    if "cancelar apagado" in comando_clave:
        os.system("shutdown /a")
        return "Apagado cancelado."

    return f"Comando no ejecutable: {verbo}:{comando_clave}"

# ─── Funciones auxiliares ──────────────────────────────────────────────

def _abrir_url_en_navegador(url, num_monitor=None, navegador="brave"):
    if not url:
        url = "https://www.google.com"
    if not url.startswith("http"):
        if "." in url:
            url = f"https://{url}"
        else:
            url = f"https://www.{url}.com"

    if navegador == "chrome":
        exe = "chrome"
    elif navegador == "edge":
        exe = "msedge"
    elif navegador == "brave":
        exe = "brave"
    elif navegador == "firefox":
        exe = "firefox"
    else:
        exe = "brave"

    subprocess.Popen(f'start {exe} "{url}"', shell=True)

    if num_monitor:
        time.sleep(0.5)
        threading.Thread(target=forzar_ventana_a_monitor,
                         args=(exe if exe != "brave" else "Brave", num_monitor),
                         daemon=True).start()

    return f"Abriendo {url} en {navegador.capitalize()}."

def _abrir_programa_o_carpeta(objetivo, num_monitor=None, navegador=None):
    """Abre un programa local o carpeta. Si no existe, sugiere abrir la web."""
    if objetivo == "navegador":
        objetivo = "brave"

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

    if ultima_palabra in atajos_carpetas:
        os.startfile(atajos_carpetas[ultima_palabra])
        return f"Carpeta del sistema abierta al instante desde ruta."

    if os.path.exists(objetivo_limpio):
        os.startfile(objetivo_limpio)
        return f"Ruta exacta '{objetivo_limpio}' abierta."

    # Buscar con radar inteligente (dinámico)
    ruta_acceso = radar_inteligente(objetivo)
    if ruta_acceso:
        os.startfile(ruta_acceso)
        msg = f"Programa '{objetivo}' abierto."
        es_juego_steam = ruta_acceso.endswith(".url")
        if num_monitor and not es_juego_steam:
            threading.Thread(target=forzar_ventana_a_monitor, args=(objetivo, num_monitor), daemon=True).start()
        return msg

    # Buscar archivo o carpeta
    ruta_elemento = buscar_archivo_o_carpeta(objetivo)
    if ruta_elemento:
        if ruta_elemento.endswith('.py') or ruta_elemento.endswith('.scr'):
            pass
        else:
            os.startfile(ruta_elemento)
            return f"Elemento '{objetivo}' encontrado y abierto."

    # Si no se encontró, sugerir abrir la web (solo si el nombre no es una URL)
    # Devolvemos un mensaje especial que controlador_acciones.py mostrará como sistema
    # y permitirá al usuario decidir.
    return f"⚠️ No encontré el programa '{objetivo}'. ¿Quieres que abra la página web en su lugar? (responde 'sí' o 'no')"

def _cerrar_programa(objetivo):
    """Cierra un programa por nombre."""
    if objetivo == "navegador":
        objetivo = "brave"
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
                except:
                    pass
    try:
        win32gui.EnumWindows(cazar_ventana, None)
    except Exception:
        pass

    if not cerrado:
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] and objetivo_lower in proc.info['name'].lower():
                    proc.kill()
                    cerrado = True
            except (psutil.NoSuchProcess, psutil.AccessDenied, KeyError):
                pass

    if not cerrado:
        os.system(f'taskkill /F /IM "{objetivo}.exe" /T >nul 2>&1')

    return f"Se ejecutó el protocolo de cierre para '{objetivo}'."

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
    except:
        pass
    return cpu_uso, memoria.percent, gpu_vram_usada_gb, gpu_temp

def obtener_estado_pc():
    cpu, ram_percent, gpu_vram, g_temp = obtener_estado_pc_valores()
    ram_gb = round(psutil.virtual_memory().used / (1024 ** 3), 1)
    cpu_temp_nota = "(psutil no mide temperatura de CPU en Windows — solo carga de trabajo)"
    gpu_temp_str = f"{g_temp}°C" if g_temp > 0 else "no disponible (nvidia-smi no respondió)"
    return (
        f"Uso de CPU: {cpu}% de carga {cpu_temp_nota} | "
        f"RAM: {ram_percent}% usada ({ram_gb} GB) | "
        f"Temperatura GPU: {gpu_temp_str} | "
        f"VRAM usada: {gpu_vram} GB"
    )

def obtener_ventanas_activas():
    ventanas = buscar_todas_las_ventanas()
    nombres_limpios = []
    ignorados = ["default ime", "program manager", "msctfime ui", "nvidia geforce overlay", "sin título"]
    for hwnd, titulo in ventanas:
        titulo_baja = titulo.lower()
        if not any(ignorado in titulo_baja for ignorado in ignorados) and titulo.strip():
            nombres_limpios.append(titulo)
    if not nombres_limpios:
        return "Ninguna aplicación a la vista."
    return " | ".join(nombres_limpios)