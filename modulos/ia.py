import os
import datetime
import winsound
import google.generativeai as genai

from config import GEMINI_API_KEY
from modulos.archivos import crear_carpeta, crear_archivo, eliminar_elemento, leer_contenido_archivo, buscar_archivo_local, escribir_archivo
from modulos.sistema import ejecutar_comando_sistema, obtener_ventanas_activas, buscar_archivo_o_carpeta, explorar_directorio
from modulos.busqueda import buscar_en_internet
from modulos.audio import hablar_no_bloqueante
from modulos.vision import capturar_pantalla
from modulos.git_bot import sincronizar_proyecto_git
from modulos.memoria import guardar_recuerdo 

from modulos.cliente_mcp import cliente_sistema 

genai.configure(api_key=GEMINI_API_KEY)

CONTEXTO_CHAT = []
ARCHIVO_PENDIENTE_INYECCION = None
DOCUMENTO_VOLATIL = ""
PENDIENTE_DE_BORRADO = "" 
WORKSPACE_ACTUAL = None # <-- LA NUEVA ANCLA GLOBAL

# =====================================================================
# HERRAMIENTAS NATIVAS MCP (SOLO VÍA COGNITIVA LENTA)
# =====================================================================
def mcp_estado_pc(): return cliente_sistema.ejecutar("reporte_estado_pc")
def mcp_hardware_pc(): return cliente_sistema.ejecutar("reporte_hardware")
def mcp_buscar_en_boveda(consulta: str): return cliente_sistema.ejecutar("buscar_en_boveda", {"consulta": consulta})
def mcp_guardar_en_boveda(dato: str): return cliente_sistema.ejecutar("guardar_en_boveda", {"dato": dato})
def mcp_explorar_ruta(ruta: str): return cliente_sistema.ejecutar("explorar_ruta", {"ruta": ruta})
def mcp_leer_documento(ruta: str): return cliente_sistema.ejecutar("leer_documento", {"ruta": ruta})

lista_herramientas_mcp = [
    mcp_estado_pc, mcp_hardware_pc, mcp_buscar_en_boveda, 
    mcp_guardar_en_boveda, mcp_explorar_ruta, mcp_leer_documento
]

def enviar_a_gemini(texto_usuario, modo_voz=False, ui_callback=None):
    global CONTEXTO_CHAT, ARCHIVO_PENDIENTE_INYECCION, DOCUMENTO_VOLATIL, PENDIENTE_DE_BORRADO, WORKSPACE_ACTUAL
    texto_usuario_lower = texto_usuario.lower().strip()

    if PENDIENTE_DE_BORRADO:
        print("🧠 [SEMÁFORO DE BORRADO] Evaluando...")
        evaluador = genai.GenerativeModel("gemini-flash-lite-latest")
        prompt_juez = f"El usuario debe confirmar borrar: '{PENDIENTE_DE_BORRADO}'. Su respuesta: '{texto_usuario}'. Responde CONFIRMADO o CANCELADO."
        try: decision_borrado = evaluador.generate_content(prompt_juez).text.strip().upper()
        except: decision_borrado = "CANCELADO"
        
        if "CONFIRMADO" in decision_borrado:
            resultado = eliminar_elemento(PENDIENTE_DE_BORRADO)
            msg = f"Protocolo autorizado. {resultado}"
        else: msg = "Protocolo abortado. Archivos a salvo."
            
        PENDIENTE_DE_BORRADO = ""
        if ui_callback: ui_callback("🤖 Cortana", msg, "#FF4500" if "abortado" in msg else "#00E5FF")
        if modo_voz: hablar_no_bloqueante(msg)
        CONTEXTO_CHAT.extend([{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [msg]}])
        return

    if ARCHIVO_PENDIENTE_INYECCION:
        evaluador = genai.GenerativeModel("gemini-flash-lite-latest")
        prompt_juez = f"El usuario debe confirmar guardar adjuntos. Su respuesta: '{texto_usuario}'. Responde CONFIRMADO o CANCELADO."
        try: decision = evaluador.generate_content(prompt_juez).text.strip().upper()
        except: decision = "CANCELADO"
        
        if "CONFIRMADO" in decision:
            total_chunks = 0
            for archivo_dict in ARCHIVO_PENDIENTE_INYECCION:
                nombre = archivo_dict["nombre"]
                contenido = archivo_dict["contenido"]
                chunks = [contenido[i:i+1500] for i in range(0, len(contenido), 1500)]
                for chunk in chunks: guardar_recuerdo(texto_a_guardar=chunk, etiqueta_tema=f"Doc: {nombre}")
                total_chunks += len(chunks)
            msg = f"¡Perfecto! Inyecté los archivos en la bóveda permanente."
            DOCUMENTO_VOLATIL = "" 
        else: msg = "Entendido, no ensucio la bóveda. Dejé los archivos en mi memoria a corto plazo."
            
        ARCHIVO_PENDIENTE_INYECCION = None
        if ui_callback: ui_callback("🤖 Cortana", msg, "#A8C7FA")
        if modo_voz: hablar_no_bloqueante("Listo, decisión aplicada.")
        CONTEXTO_CHAT.extend([{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [msg]}])
        return 

    # =================================================================
    # FLUJO PRINCIPAL
    # =================================================================
    print("\n🧠 PENSANDO (Gemini)...")
    try:
        fecha_hoy = datetime.datetime.now().strftime("%A, %d de %B de %Y") 
        ventanas_abiertas = obtener_ventanas_activas()
        
        # INYECCIÓN DEL WORKSPACE EN EL CEREBRO
        texto_workspace = f"[WORKSPACE ANCLADO]: {WORKSPACE_ACTUAL}\n" if WORKSPACE_ACTUAL else "[WORKSPACE ANCLADO]: Ninguno. Estás en modo global.\n"
        texto_doc_volatil = f"[DOCUMENTOS EN MEMORIA VOLÁTIL]:\n{DOCUMENTO_VOLATIL}\n\n" if DOCUMENTO_VOLATIL else ""

        contexto_sistema = (
            "tu nombre es: Cortana, un asistente de IA integrado a la PC de Luis. Hablále de forma súper natural y directa.\n"
            "⚠️ REGLA DE PERSONALIDAD: Sé breve. NUNCA expliques tus procesos internos ni digas 'usé una herramienta'.\n\n"
            f"[CONTEXTO OCULTO] Fecha: {fecha_hoy}\n"
            f"[VENTANAS ABIERTAS]: {ventanas_abiertas}\n\n"
            f"{texto_workspace}\n"
            f"{texto_doc_volatil}"
            "⚠️ REGLA DE ACCIONES RÁPIDAS (Escribe estos comandos por fuera de las herramientas y SIEMPRE al inicio de una nueva línea):\n"
            "- Para ANCLARTE a un proyecto específico: anclar: ruta_o_nombre_carpeta\n"
            "- Para ABRIR o MOSTRAR: abrir: nombre_app_o_ruta\n"
            "- Para MOVER ventanas: abrir: nombre_app @ num\n"
            "- Para CERRAR: cerrar: nombre_app\n"
            "- Para ELIMINAR: eliminar: ruta\n"
            "- Para buscar en INTERNET: buscar: tu consulta\n" 
            "- Para CREAR CARPETAS vacías: crear_carpeta: ruta\n"
            "- Para CREAR o MODIFICAR ARCHIVOS FÍSICAMENTE: guardar_archivo: ruta || contenido_completo\n"
            "- Para SINCRONIZAR con GitHub: github: ruta\n"
            "- Para RESETEAR el origen y SINCRONIZAR con un repo nuevo: github_reset: ruta\n"
            "⚠️ IMPORTANTE: Si estás modificando un archivo del proyecto, ESTÁS OBLIGADA a usar 'guardar_archivo:' para inyectar los cambios en el disco duro. NUNCA te limites a imprimir el código en el chat.\n\n"
            "🚫 REGLAS DE LECTURA Y EXPLORACIÓN INTERNA:\n"
            "- Si necesitas saber qué archivos hay dentro de una ruta para analizarlos o leerlos, usa la herramienta MCP 'explorar_ruta'.\n"
            "- Si el usuario te pide EXPLÍCITAMENTE 'abrir' o 'mostrar' una carpeta, NO USES MCP. Usa el comando 'abrir:' de acción rápida.\n"
        )

        modelo_gemini = genai.GenerativeModel("gemini-flash-lite-latest", system_instruction=contexto_sistema, tools=lista_herramientas_mcp)
        mensajes_para_gemini = list(CONTEXTO_CHAT)
        partes_usuario = [texto_usuario]
        
        verbos_vision = ["captura", "capturá", "capturar", "mirar", "ves"]
        objetivos_vision = ["pantalla", "monitor", "1", "2", "uno", "dos", "la 1", "el 1", "la 2", "el 2"]
        if any(v in texto_usuario_lower for v in verbos_vision) and any(o in texto_usuario_lower for o in objetivos_vision):
            if ui_callback: ui_callback("⚙️ Sistema", "📸 Capturando pantalla...", "#80868B")
            winsound.Beep(1500, 100)
            num_pantalla = 2 if any(p in texto_usuario_lower for p in ["1", "uno", "la 1", "el 1"]) else 1
            img = capturar_pantalla(num_pantalla)
            if img: partes_usuario.append(img) 
                
        mensajes_para_gemini.append({'role': 'user', 'parts': partes_usuario})
        response = modelo_gemini.generate_content(mensajes_para_gemini, stream=True, generation_config=genai.GenerationConfig(temperature=0.1))
        
        respuesta_ia, usaste_mcp, resultado_mcp = "", False, ""
        
        print(f"\n🤖 Cortana dice:\n---")
        if ui_callback: ui_callback("🤖 Cortana", "", "#A8C7FA", nueva_linea=False)
        
        for chunk in response:
            try:
                for part in chunk.parts:
                    if getattr(part, "function_call", None):
                        usaste_mcp = True
                        n_func = part.function_call.name
                        print(f"\n⚙️ [MCP ACTIVADO] {n_func}")
                        if ui_callback: ui_callback("⚙️ Sistema", f"Consultando servidor: {n_func}...", "#80868B")
                        
                        args = {k: v for k, v in part.function_call.args.items()}
                        if n_func == "mcp_estado_pc": resultado_mcp = mcp_estado_pc()
                        elif n_func == "mcp_hardware_pc": resultado_mcp = mcp_hardware_pc()
                        elif n_func == "mcp_buscar_en_boveda": resultado_mcp = mcp_buscar_en_boveda(args.get("consulta", ""))
                        elif n_func == "mcp_guardar_en_boveda": resultado_mcp = mcp_guardar_en_boveda(args.get("dato", ""))
                        elif n_func == "mcp_explorar_ruta": resultado_mcp = mcp_explorar_ruta(args.get("ruta", ""))
                        elif n_func == "mcp_leer_documento": resultado_mcp = mcp_leer_documento(args.get("ruta", ""))
                    elif getattr(part, "text", None):
                        print(part.text, end='', flush=True) 
                        respuesta_ia += part.text
                        if ui_callback: ui_callback("", part.text, "#E8EAED", nueva_linea=False)
            except Exception: pass

        if usaste_mcp:
            mensajes_para_gemini.append({'role': 'user', 'parts': [f"[DATO DEL SISTEMA: {resultado_mcp}]. Responde naturalmente sin decir que usaste una herramienta."]})
            response_2 = modelo_gemini.generate_content(mensajes_para_gemini, stream=True)
            for chunk_2 in response_2:
                try:
                    for part in chunk_2.parts:
                        if getattr(part, "text", None):
                            print(part.text, end='', flush=True)
                            respuesta_ia += part.text
                            if ui_callback: ui_callback("", part.text, "#E8EAED", nueva_linea=False)
                except Exception: pass

        print("\n---")
        if ui_callback: ui_callback("", "", "#E8EAED", nueva_linea=True)
        
        # =================================================================
        # INTERCEPTOR DE VELOCIDAD LUZ (El Fix Híbrido)
        # =================================================================
        reportes_acciones = []
        comando_busqueda_detectado = None

        # Fix Especial: Procesamos guardar_archivo antes de dividir por líneas 
        if "guardar_archivo:" in respuesta_ia.lower():
            idx = respuesta_ia.lower().find("guardar_archivo:")
            texto_comando = respuesta_ia[idx + 16:].strip()
            if "||" in texto_comando:
                ruta_f, contenido_f = texto_comando.split("||", 1)
                ruta_f = ruta_f.strip()
                contenido_f = contenido_f.strip()
                
                if contenido_f.startswith("```"):
                    partes = contenido_f.split("\n", 1)
                    if len(partes) > 1: contenido_f = partes[1]
                if contenido_f.endswith("```"):
                    contenido_f = contenido_f.rsplit("```", 1)[0].strip()
                    
                # --- LA MAGIA DEL ESCUDO DEL WORKSPACE ---
                if WORKSPACE_ACTUAL and not os.path.isabs(ruta_f):
                    ruta_en_workspace = None
                    nombre_archivo_buscado = os.path.basename(ruta_f).lower()
                    
                    # Buscamos en qué subcarpeta del proyecto está realmente el archivo
                    for raiz, _, archivos in os.walk(WORKSPACE_ACTUAL):
                        if nombre_archivo_buscado in [a.lower() for a in archivos]:
                            ruta_en_workspace = os.path.join(raiz, os.path.basename(ruta_f))
                            break
                    
                    if ruta_en_workspace:
                        # Si lo encuentra en una subcarpeta (ej: modulos/), lo sobreescribe ahí
                        ruta_f = ruta_en_workspace 
                    else:
                        # Si es un archivo totalmente nuevo, va a la raíz del proyecto
                        ruta_f = os.path.join(WORKSPACE_ACTUAL, os.path.basename(ruta_f))
                        
                elif not os.path.isabs(ruta_f):
                    # Comportamiento normal global
                    ruta_real = buscar_archivo_local(ruta_f)
                    if not ruta_real:
                        ruta_real = buscar_archivo_o_carpeta(ruta_f)
                    ruta_f = ruta_real if ruta_real else os.path.join(os.path.expanduser("~"), "Desktop", ruta_f)
                # -----------------------------------------
                
                reportes_acciones.append(f"Archivo guardado: {escribir_archivo(ruta_f, contenido_f.strip())}")

        lineas = respuesta_ia.split('\n')
        
        for linea in lineas:
            linea_limpia = linea.lower().replace("[", "").replace("]", "").replace("*", "").strip()
            
            if linea_limpia.startswith("guardar_archivo:"): continue
            
            # --- NUEVO COMANDO: ANCLAR AL WORKSPACE ---
            if linea_limpia.startswith("anclar:"):
                nombre_proyecto = linea_limpia[7:].strip()
                ruta_encontrada = buscar_archivo_o_carpeta(nombre_proyecto)
                
                if ruta_encontrada:
                    WORKSPACE_ACTUAL = ruta_encontrada
                    msg_ancla = f"⚓ Anclada al proyecto: {WORKSPACE_ACTUAL}"
                    print(f"\n{msg_ancla}")
                    if ui_callback: ui_callback("⚙️ Sistema", msg_ancla, "#81C995")
                    reportes_acciones.append(f"Workspace fijado con éxito.")
                else:
                    reportes_acciones.append(f"Error: No encontré la carpeta '{nombre_proyecto}'")

            elif linea_limpia.startswith("buscar:"): 
                comando_busqueda_detectado = linea_limpia[7:].strip()
                
            elif linea_limpia.startswith("eliminar:"):
                ruta_corta = linea_limpia[9:].strip()
                # Si estamos en un workspace, buscamos primero ahí
                if WORKSPACE_ACTUAL and not os.path.isabs(ruta_corta):
                    ruta_real = os.path.join(WORKSPACE_ACTUAL, os.path.basename(ruta_corta))
                    if not os.path.exists(ruta_real): ruta_real = buscar_archivo_o_carpeta(ruta_corta) or ruta_corta
                else:
                    ruta_real = ruta_corta if os.path.exists(ruta_corta) else (buscar_archivo_o_carpeta(ruta_corta) or ruta_corta)
                
                PENDIENTE_DE_BORRADO = ruta_real
                msg_alerta = f"⚠️ ALERTA DE SEGURIDAD: Vas a eliminar:\n'{ruta_real}'\n\n¿Seguro? Respondé SÍ para proceder o NO para cancelar."
                print(f"\n🤖 Cortana:\n---\n{msg_alerta}\n---")
                if ui_callback: ui_callback("🤖 Cortana", msg_alerta, "#FF4500")
                if modo_voz: hablar_no_bloqueante("Alerta de seguridad. ¿Confirmás el borrado?")
                CONTEXTO_CHAT.extend([{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [msg_alerta]}])
                return 
                
            elif linea_limpia.startswith("github:"):
                ruta_corta = linea_limpia[7:].strip()
                ruta_real = WORKSPACE_ACTUAL if WORKSPACE_ACTUAL else buscar_archivo_o_carpeta(ruta_corta) 
                reportes_acciones.append(sincronizar_proyecto_git(ruta_real) if ruta_real else f"Git: No encontré '{ruta_corta}'")
                
            elif linea_limpia.startswith("github_reset:"):
                ruta_corta = linea_limpia[13:].strip()
                ruta_real = WORKSPACE_ACTUAL if WORKSPACE_ACTUAL else buscar_archivo_o_carpeta(ruta_corta) 
                reportes_acciones.append(sincronizar_proyecto_git(ruta_real, reset_remote=True) if ruta_real else f"Git: No encontré '{ruta_corta}'")
                
            elif linea_limpia.startswith("crear_carpeta:"):
                ruta_corta = linea[linea.lower().find("crear_carpeta:") + 14:].replace("[", "").replace("]", "").replace("*", "").strip()
                if WORKSPACE_ACTUAL and not os.path.isabs(ruta_corta):
                    ruta_corta = os.path.join(WORKSPACE_ACTUAL, ruta_corta)
                elif "\\" not in ruta_corta and "/" not in ruta_corta:
                    ruta_corta = os.path.join(os.path.expanduser("~"), "Desktop", ruta_corta)
                reportes_acciones.append(f"Carpeta: {crear_carpeta(ruta_corta)}")
            
            elif linea_limpia.startswith("abrir:") or linea_limpia.startswith("cerrar:") or linea_limpia.startswith("navegar:") or linea_limpia.startswith("mover:"):
                linea_limpia = linea_limpia.replace("mover:", "abrir:")
                inicio_idx = linea_limpia.find("abrir:") if "abrir:" in linea_limpia else linea_limpia.find("cerrar:") if "cerrar:" in linea_limpia else linea_limpia.find("navegar:")
                cmd_extraido = linea_limpia[inicio_idx:].strip()
                
                # FIX MONITORES DE LUIS
                if "@ 1" in cmd_extraido: cmd_extraido = cmd_extraido.replace("@ 1", "@ 2")
                elif "@ 2" in cmd_extraido: cmd_extraido = cmd_extraido.replace("@ 2", "@ 1")
                
                reportes_acciones.append(f"Acción Instántanea: {ejecutar_comando_sistema(cmd_extraido)}")

        if reportes_acciones:
            texto_reporte = "\n".join([f"*({r})*" for r in reportes_acciones])
            print(texto_reporte)
            if ui_callback: ui_callback("⚙️ Sistema", texto_reporte, "#80868B")

        if comando_busqueda_detectado:
            if ui_callback: ui_callback("⚙️ Sistema", f"🌍 Buscando en internet: {comando_busqueda_detectado}", "#80868B")
            datos_encontrados = buscar_en_internet(comando_busqueda_detectado)
            if "No se encontraron resultados" in datos_encontrados or not datos_encontrados.strip():
                if modo_voz: hablar_no_bloqueante("No encontré nada en la web.")
            else:
                mensajes_secundarios = list(CONTEXTO_CHAT) + [{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [respuesta_ia]}, {'role': 'user', 'parts': [f"Resultados web:\n{datos_encontrados}\n\nRespondé usando esto."]}]
                segunda_respuesta = modelo_gemini.generate_content(mensajes_secundarios, stream=True)
                respuesta_final = ""
                for chunk in segunda_respuesta:
                    if chunk.text:
                        print(chunk.text, end='', flush=True) 
                        respuesta_final += chunk.text
                        if ui_callback: ui_callback("", chunk.text, "#E8EAED", nueva_linea=False)
                print("\n---")
                if ui_callback: ui_callback("", "", "#E8EAED", nueva_linea=True)
                if modo_voz: hablar_no_bloqueante(respuesta_final)
                CONTEXTO_CHAT.extend([{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [respuesta_final]}])
                return

        if modo_voz: hablar_no_bloqueante(respuesta_ia)
        CONTEXTO_CHAT.extend([{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [respuesta_ia]}])
        if len(CONTEXTO_CHAT) > 100: CONTEXTO_CHAT = CONTEXTO_CHAT[-100:]
            
    except Exception as e:
        print(f"\n❌ Error en Gemini: {e}")

def procesar_archivo_adjunto(rutas_archivos, ui_callback=None):
    global ARCHIVO_PENDIENTE_INYECCION, DOCUMENTO_VOLATIL
    if isinstance(rutas_archivos, str): rutas_archivos = [rutas_archivos]
    if ui_callback: ui_callback("⚙️ Sistema", f"📄 Leyendo {len(rutas_archivos)} archivo(s)...", "#80868B")
    archivos_procesados = []
    contenido_volatil_acumulado = ""
    for ruta in rutas_archivos:
        nombre_archivo = os.path.basename(ruta)
        carpeta_padre = os.path.basename(os.path.dirname(ruta)) or "Proyecto_General"
        identificador_unico = f"{carpeta_padre}/{nombre_archivo}"
        contenido = leer_contenido_archivo(ruta)
        if contenido == "CODIGO_ERROR_NO_ENCONTRADO" or contenido.startswith("CODIGO_ERROR_LECTURA:"): continue
        archivos_procesados.append({"nombre": identificador_unico, "contenido": contenido})
        contenido_volatil_acumulado += f"\n\n--- INICIO: {identificador_unico} ---\n{contenido}\n--- FIN: {identificador_unico} ---"

    if not archivos_procesados: return
    ARCHIVO_PENDIENTE_INYECCION = archivos_procesados
    DOCUMENTO_VOLATIL = contenido_volatil_acumulado
    nombres_str = ", ".join([f"'{a['nombre']}'" for a in archivos_procesados])
    try:
        resumen = genai.GenerativeModel("gemini-flash-lite-latest").generate_content(f"Resume en 2 líneas:\n\n{contenido_volatil_acumulado[:8000]}").text.strip()
    except: resumen = "Documentos cargados."
    msg = f"Cargué {len(archivos_procesados)} archivo(s): {nombres_str}.\n\n*{resumen}*\n\n¿Querés que los guarde en la bóveda permanente, o solo charlamos de esto ahora?"
    if ui_callback: ui_callback("🤖 Cortana", msg, "#FFA500")
    CONTEXTO_CHAT.append({'role': 'model', 'parts': [msg]})
# probando la inserción de texto, ahora sí funciona]. Responde naturalmente sin decir que usaste una herramienta.