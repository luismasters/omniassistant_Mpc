import os
import datetime
import winsound
import google.generativeai as genai

from config import GEMINI_API_KEY
from modulos.archivos import crear_carpeta, crear_archivo, eliminar_elemento, leer_contenido_archivo, obtener_ruta_real
from modulos.sistema import obtener_estado_pc, hardware_detectado, ejecutar_comando_sistema, obtener_ventanas_activas, buscar_carpeta_windows
from modulos.busqueda import buscar_en_internet
from modulos.audio import hablar_no_bloqueante
from modulos.vision import capturar_pantalla
from modulos.git_bot import sincronizar_proyecto_git
from modulos.memoria import buscar_contexto, guardar_recuerdo

genai.configure(api_key=GEMINI_API_KEY)

CONTEXTO_CHAT = []
PENDIENTE_DE_GUARDADO = ""
ARCHIVO_PENDIENTE_INYECCION = None
DOCUMENTO_VOLATIL = ""

def enviar_a_gemini(texto_usuario, modo_voz=False, ui_callback=None):
    global CONTEXTO_CHAT, PENDIENTE_DE_GUARDADO, ARCHIVO_PENDIENTE_INYECCION, DOCUMENTO_VOLATIL
    
    texto_usuario_lower = texto_usuario.lower().strip()

    # =================================================================
    # 0. SEMÁFORO RAG (Soporte Multi-Archivo)
    # =================================================================
    if ARCHIVO_PENDIENTE_INYECCION:
        print("🧠 [SEMÁFORO RAG] Evaluando decisión de guardado masivo...")
        evaluador = genai.GenerativeModel("gemini-flash-lite-latest")
        prompt_juez = f"El usuario acaba de adjuntar archivos y le pregunté si quiere guardarlos permanentemente. Su respuesta fue: '{texto_usuario}'. ¿Está afirmando (sí, guardalo) o negando (no, solo charlemos)? Responde ÚNICAMENTE con CONFIRMADO o CANCELADO."
        
        try: decision = evaluador.generate_content(prompt_juez).text.strip().upper()
        except: decision = "CANCELADO"
        
        if "CONFIRMADO" in decision:
            total_chunks = 0
            for archivo_dict in ARCHIVO_PENDIENTE_INYECCION:
                nombre = archivo_dict["nombre"]
                contenido = archivo_dict["contenido"]
                chunks = [contenido[i:i+1500] for i in range(0, len(contenido), 1500)]
                for chunk in chunks:
                    guardar_recuerdo(texto_a_guardar=chunk, etiqueta_tema=f"Doc: {nombre}")
                total_chunks += len(chunks)
                
            nombres_str = ", ".join([a["nombre"] for a in ARCHIVO_PENDIENTE_INYECCION])
            msg = f"¡Perfecto! Inyecté los archivos ({nombres_str}) en la bóveda permanente ({total_chunks} fragmentos). Ya quedaron guardados."
            DOCUMENTO_VOLATIL = "" 
        else:
            msg = "Entendido, no ensucio la bóveda. Dejé todos los archivos cargados en mi memoria de corto plazo, podés consultarme sobre ellos ahora mismo."
            
        ARCHIVO_PENDIENTE_INYECCION = None
        print(f"\n🤖 Cortana:\n---\n{msg}\n---")
        if ui_callback: ui_callback("🤖 Cortana", msg, "#A8C7FA")
        if modo_voz: hablar_no_bloqueante("Listo, decisión aplicada.")
        CONTEXTO_CHAT.extend([{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [msg]}])
        return 

    # =================================================================
    # 1. SEMÁFORO IA (Textos manuales)
    # =================================================================
    if PENDIENTE_DE_GUARDADO:
        print("🧠 [SEMÁFORO IA] Evaluando confirmación manual...")
        evaluador = genai.GenerativeModel("gemini-flash-lite-latest")
        prompt_juez = f"El usuario debe confirmar si aprueba guardar un dato. Su respuesta fue: '{texto_usuario}'. ¿Aprueba o rechaza? Responde CONFIRMADO o CANCELADO."
        
        try: decision_ia = evaluador.generate_content(prompt_juez).text.strip().upper()
        except: decision_ia = "CANCELADO" 
            
        if "CONFIRMADO" in decision_ia:
            guardar_recuerdo(texto_a_guardar=PENDIENTE_DE_GUARDADO, etiqueta_tema="Manual")
            msg = "¡Listo! El recuerdo ya está sellado en tu bóveda permanente."
        else:
            msg = "Entendido, descarto esa información. No se guardó nada."
        
        PENDIENTE_DE_GUARDADO = ""
        if ui_callback: ui_callback("🤖 Cortana", msg, "#00E5FF")
        if modo_voz: hablar_no_bloqueante(msg)
        return 

    # =================================================================
    # 2. MACRO-EXTRACTOR INTELIGENTE
    # =================================================================
    comandos_guardado = ["memoriza esto", "memorizá esto", "memorizar", "guardar recuerdo", "recordá esto", "acordate de", "guarda el historial", "memoriza lo que hablamos"]
    comando_detectado = next((cmd for cmd in comandos_guardado if cmd in texto_usuario_lower), None)
            
    if comando_detectado:
        extractor = genai.GenerativeModel("gemini-flash-lite-latest")
        historial_formateado = "\n".join([f"{'Luis' if m['role']=='user' else 'Cortana'}: {m['parts'][0]}" for m in CONTEXTO_CHAT])
        prompt_extractor = f"Extrae el dato a memorizar o resume técnicamente la charla:\n'{texto_usuario}'\n\nHistorial:\n{historial_formateado}\n\nResponde SOLO con el dato o resumen."
        try:
            dato_limpio = extractor.generate_content(prompt_extractor).text.strip()
            if dato_limpio:
                PENDIENTE_DE_GUARDADO = dato_limpio 
                msg = f"Preparé esta nota para tu bóveda:\n\n'{dato_limpio}'\n\n¿Me confirmás si la guardo de forma permanente?"
                if ui_callback: ui_callback("🤖 Cortana", msg, "#FFA500")
                if modo_voz: hablar_no_bloqueante("Preparé el resumen. ¿Me confirmás si lo guardo?")
                return 
        except: pass

    # =================================================================
    # FLUJO PRINCIPAL 
    # =================================================================
    print("\n🧠 PENSANDO (Gemini)...")
    try:
        estado_en_vivo = obtener_estado_pc()
        fecha_hoy = datetime.datetime.now().strftime("%A, %d de %B de %Y") 
        ventanas_abiertas = obtener_ventanas_activas()

        recuerdos = buscar_contexto(texto_usuario)
        texto_memoria = f"[MEMORIA AUTOMÁTICA RECUPERADA]:\nEl usuario tiene este recuerdo en su bóveda:\n'{recuerdos[0]}'\n\n" if recuerdos else ""
        
        texto_doc_volatil = f"[DOCUMENTOS EN MEMORIA VOLÁTIL]:\n{DOCUMENTO_VOLATIL}\n\n" if DOCUMENTO_VOLATIL else ""

        contexto_sistema = (
            "tu nombre es: Cortana, un asistente de IA integrado a la PC de Luis. Hablále como un colega, de forma súper natural y directa.\n"
            "⚠️ REGLA DE PERSONALIDAD: Sé breve. NUNCA menciones la fecha actual, ni expliques tus procesos internos.\n\n"
            f"[CONTEXTO OCULTO] Fecha: {fecha_hoy} | PC: {estado_en_vivo} | HW: {hardware_detectado['gpu']} / {hardware_detectado['cpu']}\n"
            f"[VENTANAS ABIERTAS]: {ventanas_abiertas}\n\n"
            f"{texto_memoria}" 
            f"{texto_doc_volatil}"
            "⚠️ REGLA DE MEMORIA Y VERDAD:\n"
            "1. PRIORIDAD: Si recibes datos en [MEMORIA AUTOMÁTICA RECUPERADA] o en [DOCUMENTOS EN MEMORIA VOLÁTIL], úsalos como fuente principal.\n"
            "2. NO ALUCINAR: NUNCA inventes datos personales. Si no lo sabes, di 'No tengo ese dato guardado'.\n\n"
            "⚠️ REGLA DE VISIÓN: Analiza la imagen que se adjunta automáticamente.\n\n"
            "⚠️ REGLA DE COMANDOS (Escribí uno por línea al final):\n"
            "- Para investigar información en INTERNET, usá: buscar: tu consulta\n" 
            "- Si te pide 'buscar' o 'encontrar' un PROGRAMA/JUEGO en su PC, asume abrirlo localmente y usá: abrir: nombre_corto\n"
            "- Para páginas web, usá: navegar: sitio_web @ monitor\n" 
            "- Para mover ventanas: abrir: brave @ 2\n"
            "- Para apps o juegos: abrir: nombre_corto @ monitor\n"
            "- Para cerrar: cerrar: programa\n"
            "- Para LEER archivos en PC: leer: nombre_archivo.ext\n"
            "- Para SUBIR CAMBIOS O SINCRONIZAR GITHUB, usá SOLO el nombre de la carpeta: github: nombre_carpeta\n"
        )

        modelo_gemini = genai.GenerativeModel("gemini-flash-lite-latest", system_instruction=contexto_sistema)
        mensajes_para_gemini = list(CONTEXTO_CHAT)
        partes_usuario = [texto_usuario]
        
        verbos_vision = ["captura", "capturá", "capturar", "mirar", "ves"]
        objetivos_vision = ["pantalla", "monitor", "1", "2", "uno", "dos", "la 1", "el 1", "la 2", "el 2"]
        
        if any(v in texto_usuario_lower for v in verbos_vision) and any(o in texto_usuario_lower for o in objetivos_vision):
            if ui_callback: ui_callback("⚙️ Sistema", "📸 Capturando pantalla...", "#80868B")
            winsound.Beep(1500, 100)
            num_pantalla = 2 if any(p in texto_usuario_lower for p in ["1", "uno", "la 1", "el 1"]) else 1
            imagen_pantalla = capturar_pantalla(num_pantalla)
            if imagen_pantalla: partes_usuario.append(imagen_pantalla) 
                
        mensajes_para_gemini.append({'role': 'user', 'parts': partes_usuario})

        response = modelo_gemini.generate_content(mensajes_para_gemini, stream=True, generation_config=genai.GenerationConfig(temperature=0.1))
        
        respuesta_ia = ""
        print(f"\n🤖 Cortana dice:\n---")
        
        if ui_callback: ui_callback("🤖 Cortana", "", "#A8C7FA", nueva_linea=False)
        for chunk in response:
            if chunk.text:
                print(chunk.text, end='', flush=True) 
                respuesta_ia += chunk.text
                if ui_callback: ui_callback("", chunk.text, "#E8EAED", nueva_linea=False)
        print("\n---")
        if ui_callback: ui_callback("", "", "#E8EAED", nueva_linea=True)
        
        lineas = respuesta_ia.split('\n')
        reportes_acciones = []
        comando_busqueda_detectado = None
        comando_leer_detectado = None
        
        for linea in lineas:
            linea_limpia = linea.lower().replace("[", "").replace("]", "").replace("*", "").strip()
            
            if "buscar:" in linea_limpia:
                comando_busqueda_detectado = linea_limpia[linea_limpia.find("buscar:") + 7:].strip()
            elif "leer:" in linea_limpia:
                comando_leer_detectado = linea_limpia[linea_limpia.find("leer:") + 5:].strip()
            elif "crear_carpeta:" in linea_limpia:
                ruta = linea_limpia[linea_limpia.find("crear_carpeta:") + 14:].strip()
                reportes_acciones.append(f"crear_carpeta: {ruta} -> {crear_carpeta(ruta)}")
            elif "crear_archivo:" in linea_limpia:
                ruta = linea_limpia[linea_limpia.find("crear_archivo:") + 14:].strip()
                reportes_acciones.append(f"crear_archivo: {ruta} -> {crear_archivo(ruta)}")
            elif any(cmd in linea_limpia for cmd in ["abrir:", "cerrar:", "navegar:", "mover:"]):
                linea_limpia = linea_limpia.replace("mover:", "abrir:")
                inicio_idx = linea_limpia.find("abrir:") if "abrir:" in linea_limpia else linea_limpia.find("cerrar:") if "cerrar:" in linea_limpia else linea_limpia.find("navegar:")
                cmd_extraido = linea_limpia[inicio_idx:].strip()
                reportes_acciones.append(f"Comando [{cmd_extraido}]: {ejecutar_comando_sistema(cmd_extraido)}")
            elif "eliminar:" in linea_limpia:
                ruta = linea_limpia[linea_limpia.find("eliminar:") + 9:].strip()
                reportes_acciones.append(f"eliminar: {ruta} -> {eliminar_elemento(ruta)}")
            elif "github:" in linea_limpia:
                ruta_corta = linea_limpia[linea_limpia.find("github:") + 7:].strip()
                ruta_real = buscar_carpeta_windows(ruta_corta) 
                reportes_acciones.append(sincronizar_proyecto_git(ruta_real) if ruta_real else f"Fallo Git: No encontré la carpeta '{ruta_corta}'")

        if reportes_acciones:
            texto_reporte = "\n".join([f"*(Acción ejecutada: {r})*" for r in reportes_acciones])
            print(texto_reporte)
            if ui_callback: ui_callback("⚙️ Sistema", texto_reporte, "#80868B")

        if comando_busqueda_detectado:
            if ui_callback: ui_callback("⚙️ Sistema", f"🌍 Buscando en internet: {comando_busqueda_detectado}", "#80868B")
            datos_encontrados = buscar_en_internet(comando_busqueda_detectado)
            if "No se encontraron resultados" in datos_encontrados or not datos_encontrados.strip() or "error" in datos_encontrados.lower():
                msg_error = "Che Luis, busqué en la web pero no encontré nada."
                if ui_callback: ui_callback("🤖 Cortana", msg_error, "#FF0000")
                if modo_voz: hablar_no_bloqueante(msg_error)
            else:
                contexto_busqueda = f"Resultados de internet:\n{datos_encontrados}\n\nRespondé usando esta info."
                mensajes_secundarios = list(CONTEXTO_CHAT) + [{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [respuesta_ia]}, {'role': 'user', 'parts': [contexto_busqueda]}]
                segunda_respuesta = modelo_gemini.generate_content(mensajes_secundarios, stream=True)
                respuesta_final = ""
                
                if ui_callback: ui_callback("🤖 Cortana (Web)", "", "#A8C7FA", nueva_linea=False)
                for chunk in segunda_respuesta:
                    if chunk.text:
                        print(chunk.text, end='', flush=True) 
                        respuesta_final += chunk.text
                        if ui_callback: ui_callback("", chunk.text, "#E8EAED", nueva_linea=False)
                print("\n---")
                if ui_callback: ui_callback("", "", "#E8EAED", nueva_linea=True)
                
                if modo_voz: hablar_no_bloqueante(respuesta_final)
                CONTEXTO_CHAT.extend([{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [respuesta_final]}])

        elif comando_leer_detectado:
            if ui_callback: ui_callback("⚙️ Sistema", f"📄 Analizando documento: {comando_leer_detectado}", "#80868B")
            datos_archivo = leer_contenido_archivo(comando_leer_detectado)
            if datos_archivo == "CODIGO_ERROR_NO_ENCONTRADO" or datos_archivo.startswith("CODIGO_ERROR_LECTURA:"):
                msg_error = f"Che, no encontré ni pude abrir '{comando_leer_detectado}'."
                if ui_callback: ui_callback("🤖 Cortana", msg_error, "#FF0000")
                if modo_voz: hablar_no_bloqueante(msg_error)
            else:
                contexto_lectura = f"Contenido del archivo '{comando_leer_detectado}':\n{datos_archivo}\n\nRespondé usando esta info."
                mensajes_secundarios = list(CONTEXTO_CHAT) + [{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [respuesta_ia]}, {'role': 'user', 'parts': [contexto_lectura]}]
                segunda_respuesta = modelo_gemini.generate_content(mensajes_secundarios, stream=True)
                respuesta_final = ""
                
                if ui_callback: ui_callback("🤖 Cortana (Doc)", "", "#A8C7FA", nueva_linea=False)
                for chunk in segunda_respuesta:
                    if chunk.text:
                        print(chunk.text, end='', flush=True) 
                        respuesta_final += chunk.text
                        if ui_callback: ui_callback("", chunk.text, "#E8EAED", nueva_linea=False)
                print("\n---")
                if ui_callback: ui_callback("", "", "#E8EAED", nueva_linea=True)
                
                if modo_voz: hablar_no_bloqueante(respuesta_final)
                CONTEXTO_CHAT.extend([{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [respuesta_final]}])
        else:
            if modo_voz: hablar_no_bloqueante(respuesta_ia)
            CONTEXTO_CHAT.extend([{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [respuesta_ia]}])

        if len(CONTEXTO_CHAT) > 16: CONTEXTO_CHAT = CONTEXTO_CHAT[-16:]
            
    except Exception as e:
        print(f"\n❌ Error en Gemini: {e}")

# =====================================================================
# MOTOR HÍBRIDO DE ARCHIVOS MULTIPLES (Adjuntar)
# =====================================================================
def procesar_archivo_adjunto(rutas_archivos, ui_callback=None):
    global ARCHIVO_PENDIENTE_INYECCION, DOCUMENTO_VOLATIL
    
    if isinstance(rutas_archivos, str):
        rutas_archivos = [rutas_archivos]

    if ui_callback: ui_callback("⚙️ Sistema", f"📄 Leyendo {len(rutas_archivos)} archivo(s)...", "#80868B")

    archivos_procesados = []
    contenido_volatil_acumulado = ""

    for ruta in rutas_archivos:
        nombre_archivo = os.path.basename(ruta)
        contenido = leer_contenido_archivo(ruta)
        
        if contenido == "CODIGO_ERROR_NO_ENCONTRADO" or contenido.startswith("CODIGO_ERROR_LECTURA:"):
            if ui_callback: ui_callback("🤖 Cortana", f"Uy, tuve un problema al leer {nombre_archivo}.", "#FF0000")
            continue

        archivos_procesados.append({"nombre": nombre_archivo, "contenido": contenido})
        contenido_volatil_acumulado += f"\n\n--- INICIO DE ARCHIVO: {nombre_archivo} ---\n{contenido}\n--- FIN DE ARCHIVO: {nombre_archivo} ---"

    if not archivos_procesados:
        return

    ARCHIVO_PENDIENTE_INYECCION = archivos_procesados
    DOCUMENTO_VOLATIL = contenido_volatil_acumulado

    nombres_str = ", ".join([f"'{a['nombre']}'" for a in archivos_procesados])

    try:
        extractor = genai.GenerativeModel("gemini-flash-lite-latest")
        prompt = f"Resume en 2 líneas de qué trata este conjunto de archivos de código/texto:\n\n{contenido_volatil_acumulado[:8000]}"
        resumen = extractor.generate_content(prompt).text.strip()
    except:
        resumen = "Es un conjunto de documentos de código o texto."

    msg = f"Ya cargué {len(archivos_procesados)} archivo(s) en mi cabeza: {nombres_str}.\n\n*{resumen}*\n\n¿Querés que los pique y los inyecte en mi bóveda permanente, o solo los usamos para charlar ahora?"

    if ui_callback: ui_callback("🤖 Cortana", msg, "#FFA500")
    if hablar_no_bloqueante: hablar_no_bloqueante(f"Leí los {len(archivos_procesados)} archivos. ¿Los guardo o los charlamos?")
    
    CONTEXTO_CHAT.append({'role': 'model', 'parts': [msg]})