import datetime
import winsound
import google.generativeai as genai

# Importaciones de configuración
from config import GEMINI_API_KEY

# Importaciones de módulos del sistema
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

def enviar_a_gemini(texto_usuario, modo_voz=False, ui_callback=None):
    global CONTEXTO_CHAT, PENDIENTE_DE_GUARDADO
    
    texto_usuario_lower = texto_usuario.lower().strip()

    # =================================================================
    # 1. SEMÁFORO IA
    # =================================================================
    if PENDIENTE_DE_GUARDADO:
        print("🧠 [SEMÁFORO IA] Evaluando tu respuesta con Gemini...")
        evaluador = genai.GenerativeModel("gemini-flash-lite-latest")
        prompt_juez = f"El usuario debe confirmar si aprueba guardar un dato. Su respuesta fue: '{texto_usuario}'. ¿El usuario está afirmando/aprobando o está negando/rechazando? Responde ÚNICAMENTE con la palabra CONFIRMADO o la palabra CANCELADO."
        
        try:
            decision_ia = evaluador.generate_content(prompt_juez).text.strip().upper()
        except Exception as e:
            decision_ia = "CANCELADO" 
            
        if "CONFIRMADO" in decision_ia:
            guardar_recuerdo(texto_a_guardar=PENDIENTE_DE_GUARDADO, etiqueta_tema="Manual")
            msg = "¡Listo! El recuerdo ya está sellado en tu bóveda permanente."
        else:
            msg = "Entendido, descarto esa información. No se guardó nada."
        
        PENDIENTE_DE_GUARDADO = ""
        print(f"\n🤖 Cortana:\n---\n{msg}\n---")
        if ui_callback: ui_callback("🤖 Cortana", msg, "#00E5FF")
        if modo_voz: hablar_no_bloqueante(msg)
        return 

    # =================================================================
    # 2. EXTRACTOR INTELIGENTE
    # =================================================================
    comandos_guardado = [
        "memoriza esto", "memorizá esto", "memorices", "memorizar", "memoriza", "memorizá",
        "guardar recuerdo", "recordá esto", "recuerda esto", "recordar", "recuerda", 
        "acordate de", "acordate que", "guarda esto"
    ]
    
    comando_detectado = next((cmd for cmd in comandos_guardado if cmd in texto_usuario_lower), None)
            
    if comando_detectado:
        print("🧠 [EXTRACTOR IA] Limpiando y estructurando el dato...")
        extractor = genai.GenerativeModel("gemini-flash-lite-latest")
        prompt_extractor = f"El usuario quiere que memorices algo. Su frase fue: '{texto_usuario}'. Extrae ÚNICAMENTE la información relevante. Responde SOLO con el dato a guardar, sin explicaciones."
        
        try:
            dato_limpio = extractor.generate_content(prompt_extractor).text.strip()
            if dato_limpio:
                PENDIENTE_DE_GUARDADO = dato_limpio 
                msg = f"Detecté que querés memorizar esto: '{dato_limpio}'. ¿Me confirmás si lo guardo de forma permanente en tu bóveda?"
                print(f"\n🤖 Cortana:\n---\n{msg}\n---")
                if ui_callback: ui_callback("🤖 Cortana", msg, "#FFA500")
                if modo_voz: hablar_no_bloqueante(msg)
                return 
        except:
            pass

    print("\n🧠 PENSANDO (Gemini)...")
    try:
        estado_en_vivo = obtener_estado_pc()
        fecha_hoy = datetime.datetime.now().strftime("%A, %d de %B de %Y") 
        ventanas_abiertas = obtener_ventanas_activas()

        recuerdos = buscar_contexto(texto_usuario)
        texto_memoria = f"[MEMORIA AUTOMÁTICA RECUPERADA]:\nEl usuario tiene este recuerdo en su bóveda:\n'{recuerdos[0]}'\n\n" if recuerdos else ""

        # =================================================================
        # REGLAS DEL SISTEMA BLINDADAS (AQUÍ ESTÁ LA MAGIA DEL DESEMPATE)
        # =================================================================
        contexto_sistema = (
            "tu nombre es: Cortana, un asistente de IA integrado a la PC de Luis. Hablále como un colega, de forma súper natural y directa.\n"
            "⚠️ REGLA DE PERSONALIDAD: Sé breve. NUNCA menciones la fecha actual, ni expliques tus procesos internos.\n\n"
            f"[CONTEXTO OCULTO] Fecha: {fecha_hoy} | PC: {estado_en_vivo} | HW: {hardware_detectado['gpu']} / {hardware_detectado['cpu']}\n"
            f"[VENTANAS ABIERTAS]: {ventanas_abiertas}\n\n"
            f"{texto_memoria}" 
            "⚠️ REGLA DE MEMORIA Y VERDAD:\n"
            "1. PRIORIDAD: Si recibes datos en [MEMORIA AUTOMÁTICA RECUPERADA], úsalos como fuente ÚNICA Y EXCLUSIVA para datos personales.\n"
            "2. NO ALUCINAR: NUNCA inventes datos personales. Si no lo sabes, di 'No tengo ese dato guardado'.\n\n"
            "⚠️ REGLA DE VISIÓN: Analiza la imagen que se adjunta automáticamente. No digas que 'viste una captura', actúa como si miraras su monitor directamente.\n\n"
            "⚠️ REGLA DE COMANDOS (Escribí uno por línea al final):\n"
            "- Para investigar información, responder dudas o noticias en INTERNET, usá: buscar: tu consulta (Ej: buscar: clima en Buenos Aires hoy)\n" 
            "- ⚠️ IMPORTANTE: Si el usuario te pide 'buscar' o 'encontrar' un PROGRAMA, CARPETA o JUEGO en su PC, asume que quiere abrirlo localmente y usá: abrir: nombre_corto\n"
            "- Para páginas web, usá: navegar: sitio_web @ monitor (Ej: navegar: gmail.com @ 1)\n" 
            "- Para mover ventanas, agregá @ y SOLO el número al final. Ej: abrir: brave @ 2\n"
            "- Para apps o juegos, usá el nombre exacto: abrir: nombre_corto @ monitor (Ej: abrir: street fighter 6 @ 1)\n"
            "- Para cerrar, usá: cerrar: programa\n"
            "- Para LEER y analizar código o texto, usá: leer: nombre_archivo.ext\n"
            "- Para GitHub, usá SOLO el nombre de la carpeta: github: nombre_carpeta\n"
        )

        modelo_gemini = genai.GenerativeModel("gemini-flash-lite-latest", system_instruction=contexto_sistema)
        mensajes_para_gemini = list(CONTEXTO_CHAT)
        partes_usuario = [texto_usuario]
        
        verbos_vision = ["captura", "capturá", "capturar", "mirar", "ves"]
        objetivos_vision = ["pantalla", "monitor", "1", "2", "uno", "dos", "la 1", "el 1", "la 2", "el 2"]
        
        if any(v in texto_usuario_lower for v in verbos_vision) and any(o in texto_usuario_lower for o in objetivos_vision):
            winsound.Beep(1500, 100)
            num_pantalla = 2 if any(p in texto_usuario_lower for p in ["1", "uno", "la 1", "el 1"]) else 1
            imagen_pantalla = capturar_pantalla(num_pantalla)
            if imagen_pantalla: partes_usuario.append(imagen_pantalla) 
                
        mensajes_para_gemini.append({'role': 'user', 'parts': partes_usuario})

        response = modelo_gemini.generate_content(mensajes_para_gemini, stream=True, generation_config=genai.GenerationConfig(temperature=0.1))
        
        respuesta_ia = ""
        print(f"\n🤖 Cortana dice:\n---")
        for chunk in response:
            if chunk.text:
                print(chunk.text, end='', flush=True) 
                respuesta_ia += chunk.text
        print("\n---")
        
        if ui_callback: ui_callback("🤖 Cortana", respuesta_ia, "#00E5FF")
        
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
            if ui_callback:
                ui_callback("⚙️ Sistema", texto_reporte, "#888888")

        if comando_busqueda_detectado:
            datos_encontrados = buscar_en_internet(comando_busqueda_detectado)
            if "No se encontraron resultados" in datos_encontrados or not datos_encontrados.strip() or "error" in datos_encontrados.lower():
                msg_error = "Che Luis, busqué en la web pero no encontré nada relevante."
                if ui_callback: ui_callback("🤖 Cortana", msg_error, "#FF0000")
                if modo_voz: hablar_no_bloqueante(msg_error)
            else:
                contexto_busqueda = f"Resultados de internet:\n{datos_encontrados}\n\nRespondé usando esta info."
                mensajes_secundarios = list(CONTEXTO_CHAT) + [{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [respuesta_ia]}, {'role': 'user', 'parts': [contexto_busqueda]}]
                segunda_respuesta = modelo_gemini.generate_content(mensajes_secundarios, stream=True)
                respuesta_final = "".join([chunk.text for chunk in segunda_respuesta if chunk.text])
                
                if ui_callback: ui_callback("🤖 Cortana (Web)", respuesta_final, "#00E5FF")
                if modo_voz: hablar_no_bloqueante(respuesta_final)
                CONTEXTO_CHAT.extend([{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [respuesta_final]}])

        elif comando_leer_detectado:
            datos_archivo = leer_contenido_archivo(comando_leer_detectado)
            if datos_archivo == "CODIGO_ERROR_NO_ENCONTRADO" or datos_archivo.startswith("CODIGO_ERROR_LECTURA:"):
                msg_error = f"Che, escaneé las carpetas pero no encontré ni pude abrir '{comando_leer_detectado}'."
                if ui_callback: ui_callback("🤖 Cortana", msg_error, "#FF0000")
                if modo_voz: hablar_no_bloqueante(msg_error)
            else:
                contexto_lectura = f"Contenido del archivo '{comando_leer_detectado}':\n{datos_archivo}\n\nRespondé usando esta info."
                mensajes_secundarios = list(CONTEXTO_CHAT) + [{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [respuesta_ia]}, {'role': 'user', 'parts': [contexto_lectura]}]
                segunda_respuesta = modelo_gemini.generate_content(mensajes_secundarios, stream=True)
                respuesta_final = "".join([chunk.text for chunk in segunda_respuesta if chunk.text])
                
                if ui_callback: ui_callback("🤖 Cortana (Doc)", respuesta_final, "#00E5FF")
                if modo_voz: hablar_no_bloqueante(respuesta_final)
                CONTEXTO_CHAT.extend([{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [respuesta_final]}])
        else:
            if modo_voz: hablar_no_bloqueante(respuesta_ia)
            CONTEXTO_CHAT.extend([{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [respuesta_ia]}])

        if len(CONTEXTO_CHAT) > 6: CONTEXTO_CHAT = CONTEXTO_CHAT[-6:]
            
    except Exception as e:
        print(f"\n❌ Error en Gemini: {e}")