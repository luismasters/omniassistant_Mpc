import os
import datetime
import winsound
import re
import difflib # FASE 1.4: Importamos difflib para búsqueda difusa
import google.generativeai as genai
from openai import OpenAI # Cliente para DeepSeek
import config # Importación global para el parche del Sandbox

# Importación de llaves
from config import GEMINI_API_KEY, DEEPSEEK_API_KEY

from modulos.archivos import crear_carpeta,eliminar_elemento, leer_contenido_archivo, buscar_archivo_local, escribir_archivo
from modulos.sistema import ejecutar_comando_sistema, obtener_ventanas_activas, buscar_archivo_o_carpeta, explorar_directorio
from modulos.busqueda import buscar_en_internet
from modulos.audio import hablar_no_bloqueante
from modulos.vision import capturar_pantalla
from modulos.git_bot import sincronizar_proyecto_git, ejecutar_comando_git_libre
from modulos.memoria import guardar_recuerdo, guardar_snapshot, cargar_snapshot 
from modulos.cliente_mcp import cliente_sistema 

# =====================================================================
# INICIALIZACIÓN DE CLIENTES IA
# =====================================================================
genai.configure(api_key=GEMINI_API_KEY)
cliente_deepseek = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

# =====================================================================
# VARIABLES GLOBALES DE ESTADO
# =====================================================================
CONTEXTO_CHAT = []
ARCHIVO_PENDIENTE_INYECCION = None
DOCUMENTO_VOLATIL = ""
PENDIENTE_DE_BORRADO = "" 
PENDIENTE_DE_GIT = None 
WORKSPACE_ACTUAL = None 
SNAPSHOT_ACTUAL = "" 
MODO_ACTUAL = "general"
ARCHIVOS_EN_MEMORIA = set() # FASE 1.4: Caché para evitar recargar contexto

# =====================================================================
# HERRAMIENTAS NATIVAS MCP (GEMINI)
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
    """Enrutador Universal: Llama a Gemini o a DeepSeek según el modo activo."""
    global CONTEXTO_CHAT, ARCHIVO_PENDIENTE_INYECCION, DOCUMENTO_VOLATIL, PENDIENTE_DE_BORRADO, PENDIENTE_DE_GIT, WORKSPACE_ACTUAL, SNAPSHOT_ACTUAL, MODO_ACTUAL, ARCHIVOS_EN_MEMORIA
    
    # --- PARCHE SANDBOX: Sincronizar ruta actual con la seguridad ---
    config.RUTA_WORKSPACE_ACTUAL = WORKSPACE_ACTUAL
    config.MODO_ACTUAL = MODO_ACTUAL
    # -----------------------------------------------------------------

    # Limpiar caché de memoria si cambiamos de proyecto o explícitamente lo pedimos
    if texto_usuario.lower() in ["limpiar memoria", "olvidar contexto"]:
        ARCHIVOS_EN_MEMORIA.clear()
        CONTEXTO_CHAT.clear()
        if ui_callback: ui_callback("⚙️ Sistema", "🧹 Contexto y caché limpiados.", "#80868B")
        return

    # =================================================================
    # 🩹 INTERCEPTOR DE ADJUNTOS DE LA INTERFAZ
    # =================================================================
    if "[adjunto:" in texto_usuario.lower():
        rutas_extraidas = re.findall(r'\[adjunto:\s*(.*?)\]', texto_usuario, re.IGNORECASE)
        if rutas_extraidas:
            texto_usuario = re.sub(r'\[adjunto:\s*.*?\]', '', texto_usuario, flags=re.IGNORECASE).strip()
            procesar_archivo_adjunto(rutas_extraidas, ui_callback)
            return

    texto_usuario_lower = texto_usuario.lower().strip()

    # =================================================================
    # 🛡️ ESCUDOS DE SEGURIDAD
    # =================================================================
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

    if PENDIENTE_DE_GIT:
        print("🧠 [SEMÁFORO DE GIT] Evaluando...")
        evaluador = genai.GenerativeModel("gemini-flash-lite-latest")
        prompt_juez = f"El usuario debe confirmar una operación de GitHub. Su respuesta: '{texto_usuario}'. Responde CONFIRMADO o CANCELADO."
        try: decision_git = evaluador.generate_content(prompt_juez).text.strip().upper()
        except: decision_git = "CANCELADO"
        
        if "CONFIRMADO" in decision_git:
            if ui_callback: ui_callback("⚙️ Sistema", "Iniciando operación en GitHub. Esto puede tardar unos segundos...", "#80868B")
            accion = PENDIENTE_DE_GIT.get("accion")
            ruta = PENDIENTE_DE_GIT.get("ruta")
            url_custom = PENDIENTE_DE_GIT.get("url_custom")
            
            if accion == "github_reset":
                resultado = sincronizar_proyecto_git(ruta, reset_remote=True, url_custom=url_custom)
            elif accion == "git_libre":
                resultado = ejecutar_comando_git_libre(ruta, url_custom)
            else:
                resultado = sincronizar_proyecto_git(ruta)
            msg = f"Operación Git completada:\n{resultado}"
        else: 
            msg = "Operación en GitHub cancelada de forma segura."
            
        PENDIENTE_DE_GIT = None
        if ui_callback: ui_callback("🤖 Cortana", msg, "#FF4500" if "cancelada" in msg else "#00E5FF")
        if modo_voz: hablar_no_bloqueante("Operación finalizada." if "completada" in msg else "Operación cancelada.")
        CONTEXTO_CHAT.extend([{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [msg]}])
        return

    if ARCHIVO_PENDIENTE_INYECCION:
        evaluador = genai.GenerativeModel("gemini-flash-lite-latest")
        prompt_juez = f"El usuario debe confirmar guardar adjuntos. Su respuesta: '{texto_usuario}'. Responde CONFIRMADO o CANCELADO."
        try: decision = evaluador.generate_content(prompt_juez).text.strip().upper()
        except: decision = "CANCELADO"
        
        if "CONFIRMADO" in decision:
            for archivo_dict in ARCHIVO_PENDIENTE_INYECCION:
                nombre = archivo_dict["nombre"]
                contenido = archivo_dict["contenido"]
                chunks = [contenido[i:i+1500] for i in range(0, len(contenido), 1500)]
                for chunk in chunks: guardar_recuerdo(texto_a_guardar=chunk, etiqueta_tema=f"Doc: {nombre}")
            msg = f"¡Perfecto! Inyecté los archivos en la bóveda permanente."
            DOCUMENTO_VOLATIL = "" 
        else: msg = "Entendido. Dejé los archivos en mi memoria a corto plazo."
            
        ARCHIVO_PENDIENTE_INYECCION = None
        if ui_callback: ui_callback("🤖 Cortana", msg, "#A8C7FA")
        if modo_voz: hablar_no_bloqueante("Listo, decisión aplicada.")
        CONTEXTO_CHAT.extend([{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [msg]}])
        return 

    # =================================================================
    # FLUJO PRINCIPAL: ENRUTADOR Y CONSTRUCCIÓN DE CONTEXTO
    # =================================================================
    print(f"\n🧠 PENSANDO ({MODO_ACTUAL.upper()})...")
    try:
        fecha_hoy = datetime.datetime.now().strftime("%A, %d de %B de %Y") 
        ventanas_abiertas = obtener_ventanas_activas()
        
        texto_workspace = f"[WORKSPACE ANCLADO]: {WORKSPACE_ACTUAL}\n" if WORKSPACE_ACTUAL else ""
        texto_snapshot = f"[ESTADO DEL PROYECTO]:\n{SNAPSHOT_ACTUAL}\n\n" if SNAPSHOT_ACTUAL else ""
        texto_doc_volatil = f"[DOCUMENTOS EN MEMORIA]:\n{DOCUMENTO_VOLATIL}\n\n" if DOCUMENTO_VOLATIL else ""

        if MODO_ACTUAL == "planificador":
            contexto_sistema = (
                "Eres el Arquitecto de Software Senior de Luis. Tu objetivo es analizar el código y diseñar soluciones.\n"
                f"{texto_workspace}\n{texto_snapshot}{texto_doc_volatil}"
                "REGLAS OBLIGATORIAS:\n"
                "1. NO escribas código final de implementación.\n"
                "2. Analiza riesgos, dependencias y estructura lógica paso a paso.\n"
                "⚠️ REGLAS DE ACCIONES RÁPIDAS (SIEMPRE al inicio de línea):\n"
                "- Para ACTUALIZAR EL PLAN: guardar_archivo: plan.md ---CONTENIDO--- [contenido_del_plan]\n"
                "- Para ACTUALIZAR EL ESTADO REAL: guardar_archivo: PROJECT_STATE.md ---CONTENIDO--- [contenido_del_estado]\n"
                "- CUANDO LUIS PIDA ESCANEAR EL PROYECTO, DEBES IMPRIMIR EXACTAMENTE ESTO: escanear_proyecto:\n"
                "- Para CREAR CARPETAS de doc: crear_carpeta: ruta\n"
                "⚠️ IMPORTANTE: SIEMPRE usa 'guardar_archivo:' para generar el plan.md físico."
            )
            modelo_activo = "deepseek-reasoner"

        elif MODO_ACTUAL == "programador":
            contexto_sistema = (
                "Eres el Ingeniero de Mantenimiento de Software de Luis. Tu objetivo es editar código de forma QUIRÚRGICA y minimalista.\n"
                f"{texto_workspace}\n{texto_snapshot}{texto_doc_volatil}"
                "⚠️ REGLAS DE ORO (SKILL DE EDICIÓN SENIOR):\n"
                "1. PROHIBIDO REESCRIBIR ARCHIVOS GRANDES. NUNCA uses 'guardar_archivo:' para modificar un archivo que ya existe.\n"
                "2. OPERACIÓN QUIRÚRGICA: Para cambiar código, usa ÚNICAMENTE 'reemplazar_bloque:'.\n"
                "3. MINIMALISMO: En la sección ---BUSCAR--- pon SOLO las 3 o 4 líneas exactas que van a cambiar, más 1 línea de contexto. NUNCA incluyas la función entera si solo cambian 2 líneas.\n"
                "4. INSPECCIÓN PREVIA: Si dudas del código exacto, usa 'leer_archivo:' primero y espera la respuesta antes de editar.\n"
                "⚠️ REGLAS DE ACCIONES RÁPIDAS (PROHIBIDO usar etiquetas XML como <reemplazar_bloque> o <replace_block>. Usa ESTRICTAMENTE los guiones ---):\n"
                "- Para LEER: leer_archivo: ruta\n"
                "- Para CREAR NUEVO (solo si no existe): guardar_archivo: ruta ---CONTENIDO--- [codigo]\n"
                "- Para MODIFICAR CÓDIGO (Usa siempre este formato markdown):\n"
                "reemplazar_bloque: ruta\n"
                "---BUSCAR---\n"
                "[3-4 líneas de código viejo exacto]\n"
                "---REEMPLAZAR---\n"
                "[3-4 líneas de código nuevo]\n"
                "---FIN---\n"
                "- Para EDICIÓN DE 1 LÍNEA: editar_archivo: ruta | buscar: texto | reemplazar: texto\n"
                "- Para PUSH: github: ruta\n"
            )
            modelo_activo = "deepseek-chat"

        else: # MODO GENERAL (Gemini)
            ruta_home = os.path.expanduser("~") 
            contexto_sistema = (
                "tu nombre es: Cortana, un asistente de IA integrado a la PC de Luis. Hablále de forma súper natural y directa.\n"
                "⚠️ REGLA DE PERSONALIDAD: Sé breve. NUNCA expliques tus procesos internos, solo da la respuesta final.\n\n"
                f"[CONTEXTO OCULTO] Fecha: {fecha_hoy}\n"
                f"[RUTA DEL SISTEMA]: Tu usuario de Windows está en '{ruta_home}'. Por lo tanto, el Escritorio es '{ruta_home}\\Desktop'.\n"
                f"[VENTANAS ABIERTAS]: {ventanas_abiertas}\n\n"
                f"{texto_workspace}\n{texto_snapshot}{texto_doc_volatil}"
                "⚠️ REGLAS DE ACCIONES RÁPIDAS (CRÍTICO: Si debes ejecutar una acción, escribe la orden exacta sola en una nueva línea):\n"
                "- Para ABRIR o MOSTRAR una app/web: abrir: nombre_app\n"
                "- Para CERRAR una app: cerrar: nombre_app\n"
                "- Para MOVER ventanas: mover: nombre_app @ [1 o 2]\n"
                "- Para buscar info en INTERNET: buscar: tu consulta\n"
                "- Para GUARDAR RECUREDOS en memoria a largo plazo: mcp_guardar_en_boveda\n"
                "- Para BUSCAR RECUERDOS: mcp_buscar_en_boveda\n"
                "- SI LUIS PIDE ESCANEAR EL PROYECTO O ARQUITECTURA IMPRIME ESTO EXACTO: escanear_proyecto:\n"
                "- Para CREAR CARPETAS en Windows: crear_carpeta: ruta_absoluta\n" 
                "- Para LEER UN ARCHIVO: leer_archivo: ruta_absoluta\n" 
                "- Para GUARDAR TEXTO O CÓDIGO NUEVO: guardar_archivo: ruta_absoluta ---CONTENIDO--- [texto_real_a_guardar]\n"
                "- Si te piden mirar la pantalla 1 o 2, espera silenciosamente, el sistema te enviará la foto.\n"
            )
            modelo_activo = "gemini"

        respuesta_ia = ""
        usaste_mcp = False
        resultado_mcp = ""
        modelo_gemini = None

        print(f"\n🤖 Cortana dice:\n---")
        
        # =================================================================
        # EJECUCIÓN GEMINI (Modo General)
        # =================================================================
        if modelo_activo == "gemini":
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
            
            if ui_callback: ui_callback("🤖 Cortana", "", "#A8C7FA", nueva_linea=False)
            
            for chunk in response:
                try:
                    for part in chunk.parts:
                        if getattr(part, "function_call", None):
                            usaste_mcp = True
                            n_func = part.function_call.name
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

            if usaste_mcp and modelo_gemini:
                mensajes_para_gemini.append({'role': 'model', 'parts': ['Analizando los datos del sistema...']})
                mensajes_para_gemini.append({'role': 'user', 'parts': [f"[DATO DEL SISTEMA: {resultado_mcp}]. Responde naturalmente."]})
                response_2 = modelo_gemini.generate_content(mensajes_para_gemini, stream=True)
                for chunk_2 in response_2:
                    try:
                        for part in chunk_2.parts:
                            if getattr(part, "text", None):
                                print(part.text, end='', flush=True)
                                respuesta_ia += part.text
                                if ui_callback: ui_callback("", part.text, "#E8EAED", nueva_linea=False)
                    except Exception: pass

        # =================================================================
        # EJECUCIÓN DEEPSEEK (Modo Planificador / Programador)
        # =================================================================
        else:
            mensajes_ds = [{"role": "system", "content": contexto_sistema}]
            for msg in CONTEXTO_CHAT:
                rol_ds = "assistant" if msg['role'] == "model" else "user"
                texto_historico = "".join([p for p in msg['parts'] if isinstance(p, str)])
                mensajes_ds.append({"role": rol_ds, "content": texto_historico})
            
            mensajes_ds.append({"role": "user", "content": texto_usuario})

            if ui_callback: ui_callback("🤖 Cortana", "", "#A8C7FA", nueva_linea=False)
            
            parametros_api = {"model": modelo_activo, "messages": mensajes_ds, "stream": True}
            response = cliente_deepseek.chat.completions.create(**parametros_api)
            
            for chunk in response:
                delta = chunk.choices[0].delta
                if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                    print(delta.reasoning_content, end='', flush=True)
                if getattr(delta, 'content', None):
                    texto_chunk = delta.content
                    print(texto_chunk, end='', flush=True)
                    respuesta_ia += texto_chunk
                    if ui_callback: ui_callback("", texto_chunk, "#E8EAED", nueva_linea=False)

        print("\n---")
        if ui_callback: ui_callback("", "", "#E8EAED", nueva_linea=True)
        
        # =================================================================
        # INTERCEPTOR DE ACCIONES (PARSER TRILINGÜE Y ACTUALIZACIÓN EN MEMORIA)
        # =================================================================
        reportes_acciones = []
        comando_busqueda_detectado = None

        # --- PROTECCIÓN SANDBOX INTELIGENTE ---
        if MODO_ACTUAL != "general" and not WORKSPACE_ACTUAL and any(cmd in respuesta_ia.lower() for cmd in ["guardar_archivo:", "editar_archivo:", "reemplazar_bloque:", "crear_carpeta:", "eliminar:", "<replace_block>", "<write_file>"]):
            msg_err = "⚠️ Error de seguridad: No se pueden modificar archivos sin un Workspace seleccionado."
            print(f"[ERROR] {msg_err}")
            if ui_callback: ui_callback("⚙️ Sistema", msg_err, "#ff4500")
            CONTEXTO_CHAT.append({'role': 'user', 'parts': [f"[SISTEMA] {msg_err}"]})
            return

        # 0. LECTURAS EN FORMATO XML (DeepSeek V4 Fallback)
        if "<read_file>" in respuesta_ia.lower():
            for m in re.finditer(r'<read_file>\s*<path>\s*(.+?)\s*</path>\s*</read_file>', respuesta_ia, re.IGNORECASE):
                ruta_corta = m.group(1).replace('<', '').replace('>', '').strip()
                ruta_real = os.path.join(WORKSPACE_ACTUAL, ruta_corta) if WORKSPACE_ACTUAL and not os.path.isabs(ruta_corta) else ruta_corta
                
                if ruta_real in ARCHIVOS_EN_MEMORIA:
                    if ui_callback: ui_callback("⚙️ Sistema", f"📄 (Caché) Archivo {ruta_corta} ya está en memoria.", "#80868B")
                    continue
                
                contenido_leido = leer_contenido_archivo(ruta_real)
                if len(contenido_leido) > 80000:
                    contenido_leido = contenido_leido[:80000] + "\n... [CONTENIDO TRUNCADO POR SEGURIDAD]"
                
                ARCHIVOS_EN_MEMORIA.add(ruta_real)
                CONTEXTO_CHAT.append({'role': 'user', 'parts': [f"[CONTENIDO DE '{ruta_real}']:\n{contenido_leido}"]})
                if ui_callback: ui_callback("⚙️ Sistema", f"📄 Archivo cargado (XML): {ruta_corta}", "#80868B")

        # 1. GUARDAR ARCHIVO (Soporta Markdown y XML)
        if "guardar_archivo:" in respuesta_ia.lower() or "<write_file>" in respuesta_ia.lower():
            try:
                operaciones_guardar = []
                for m in re.finditer(r'guardar_archivo:\s*(.+?)\s*-{3,}CONTENIDO-{3,}\s*([\s\S]*?)(?=\nguardar_archivo:|<write_file>|$)', respuesta_ia, re.IGNORECASE):
                    operaciones_guardar.append((m.group(1), m.group(2)))
                for m in re.finditer(r'<write_file>\s*<path>\s*(.+?)\s*</path>\s*<content>\s*([\s\S]*?)\s*</content>\s*</write_file>', respuesta_ia, re.IGNORECASE):
                    operaciones_guardar.append((m.group(1), m.group(2)))

                for ruta_f, contenido_f in operaciones_guardar:
                    ruta_f = ruta_f.replace('`', '').replace('*', '').replace('<', '').replace('>', '').strip()
                    contenido_f = contenido_f.strip()
                    contenido_f = re.sub(r'^```\w*\n?|\n?```$', '', contenido_f).strip()
                        
                    ruta_f_abs = os.path.join(WORKSPACE_ACTUAL, ruta_f) if WORKSPACE_ACTUAL and not os.path.isabs(ruta_f) else ruta_f
                    resultado_escritura = escribir_archivo(ruta_f_abs, contenido_f)
                    
                    if "ERROR" in resultado_escritura:
                        CONTEXTO_CHAT.append({'role': 'user', 'parts': [f"[RESULTADO ESCRITURA] Fallo al guardar {ruta_f}: {resultado_escritura}"]})
                        if ui_callback: ui_callback("⚙️ Sistema", f"❌ Error guardando {ruta_f}: {resultado_escritura}", "#ff4500")
                    else:
                        # FASE 1.4: Actualizar caché
                        if ruta_f_abs in ARCHIVOS_EN_MEMORIA:
                            for msg in CONTEXTO_CHAT:
                                if isinstance(msg.get('parts', [''])[0], str) and f"[CONTENIDO DE '{ruta_f_abs}']:" in msg['parts'][0]:
                                    msg['parts'][0] = f"[CONTENIDO DE '{ruta_f_abs}']:\n{contenido_f}"
                        CONTEXTO_CHAT.append({'role': 'user', 'parts': [f"[RESULTADO ESCRITURA] Archivo {ruta_f} guardado correctamente."] })
                        if ui_callback: ui_callback("⚙️ Sistema", f"✅ Archivo guardado: {ruta_f}", "#86efac")
            except Exception as e:
                print(f"❌ Error local al guardar el archivo: {e}")

        # 2. REEMPLAZAR BLOQUE (MOTOR TRILINGÜE Y QUIRÚRGICO CON FUZZY MATCH)
        if "reemplazar_bloque:" in respuesta_ia.lower() or "<replace_block>" in respuesta_ia.lower() or "<reemplazar_bloque>" in respuesta_ia.lower():
            try:
                operaciones_reemplazo = []
                # Formato Markdown Original
                for m in re.finditer(r'reemplazar_bloque:\s*(.+?)\s*-{3,}BUSCAR-{3,}\s*([\s\S]*?)\s*-{3,}REEMPLAZAR-{3,}\s*([\s\S]*?)\s*-{3,}FIN-{3,}', respuesta_ia, re.IGNORECASE):
                    operaciones_reemplazo.append((m.group(1), m.group(2), m.group(3)))
                # Formato XML Inglés
                for m in re.finditer(r'<replace_block>\s*<path>\s*(.+?)\s*</path>\s*<search>\s*([\s\S]*?)\s*</search>\s*<replace>\s*([\s\S]*?)\s*</replace>\s*</replace_block>', respuesta_ia, re.IGNORECASE):
                    operaciones_reemplazo.append((m.group(1), m.group(2), m.group(3)))
                # Formato XML ESPAÑOL
                for m in re.finditer(r'<reemplazar_bloque>\s*<ruta>\s*(.+?)\s*</ruta>\s*<buscar>\s*([\s\S]*?)\s*</buscar>\s*<reemplazar>\s*([\s\S]*?)\s*</reemplazar>\s*</reemplazar_bloque>', respuesta_ia, re.IGNORECASE):
                    operaciones_reemplazo.append((m.group(1), m.group(2), m.group(3)))

                for ruta_edit, buscar_edit, reemplazar_edit in operaciones_reemplazo:
                    ruta_edit = ruta_edit.replace('`','').replace('*','').replace('<', '').replace('>', '').strip()
                    buscar_edit = re.sub(r'^```\w*\n?|\n?```$', '', buscar_edit.strip()).strip('\n')
                    reemplazar_edit = re.sub(r'^```\w*\n?|\n?```$', '', reemplazar_edit.strip()).strip('\n')
                    
                    ruta_real_edit = os.path.join(WORKSPACE_ACTUAL, ruta_edit) if WORKSPACE_ACTUAL and not os.path.isabs(ruta_edit) else ruta_edit
                    contenido_actual = leer_contenido_archivo(ruta_real_edit)
                    
                    if not contenido_actual.startswith("ERROR"):
                        # Intento 1: Reemplazo Exacto
                        if buscar_edit in contenido_actual:
                            nuevo_contenido = contenido_actual.replace(buscar_edit, reemplazar_edit, 1)
                            escribir_archivo(ruta_real_edit, nuevo_contenido)
                            
                            # FASE 1.4: Actualizamos el archivo en la memoria oculta de la IA
                            for msg in CONTEXTO_CHAT:
                                if isinstance(msg.get('parts', [''])[0], str) and f"[CONTENIDO DE '{ruta_real_edit}']:" in msg['parts'][0]:
                                    msg['parts'][0] = f"[CONTENIDO DE '{ruta_real_edit}']:\n{nuevo_contenido}"
                                    
                            CONTEXTO_CHAT.append({'role': 'user', 'parts': [f"[RESULTADO EDICIÓN] Modificación exitosa y exacta en {ruta_edit}"]})
                            if ui_callback: ui_callback("⚙️ Sistema", f"✅ Bloque actualizado con precisión en {ruta_edit}", "#86efac")
                        
                        # Intento 2: FUZZY MATCHING
                        else:
                            source_lines = contenido_actual.splitlines()
                            search_lines = buscar_edit.splitlines()
                            mejor_ratio = 0; mejor_idx = -1; len_encontrado = 0; bloque_encontrado = ""
                            
                            if search_lines and source_lines:
                                window_size = len(search_lines)
                                for w_size in range(max(1, window_size - 2), min(len(source_lines), window_size + 3)):
                                    for i in range(len(source_lines) - w_size + 1):
                                        window = '\n'.join(source_lines[i:i+w_size])
                                        ratio = difflib.SequenceMatcher(None, buscar_edit, window).ratio()
                                        if ratio > mejor_ratio:
                                            mejor_ratio = ratio; mejor_idx = i; len_encontrado = w_size; bloque_encontrado = window
                            
                            if mejor_ratio >= 0.80: 
                                before = '\n'.join(source_lines[:mejor_idx])
                                after = '\n'.join(source_lines[mejor_idx+len_encontrado:])
                                nuevo_contenido = (before + '\n' if before else '') + reemplazar_edit + ('\n' + after if after else '')
                                escribir_archivo(ruta_real_edit, nuevo_contenido)
                                
                                # FASE 1.4: Actualizamos caché en fuzzy
                                for msg in CONTEXTO_CHAT:
                                    if isinstance(msg.get('parts', [''])[0], str) and f"[CONTENIDO DE '{ruta_real_edit}']:" in msg['parts'][0]:
                                        msg['parts'][0] = f"[CONTENIDO DE '{ruta_real_edit}']:\n{nuevo_contenido}"
                                        
                                CONTEXTO_CHAT.append({'role': 'user', 'parts': [f"[RESULTADO EDICIÓN] Modificación fuzzy exitosa en {ruta_edit} (Similitud: {mejor_ratio:.2f})"]})
                                if ui_callback: ui_callback("⚙️ Sistema", f"✅ Bloque ajustado ({(mejor_ratio*100):.1f}%) en {ruta_edit}", "#86efac")
                            else:
                                msg_fallo = f"No encontré el bloque. ¿Querías decir esto?\n{bloque_encontrado[:100]}..."
                                CONTEXTO_CHAT.append({'role': 'user', 'parts': [f"[RESULTADO EDICIÓN] Fallo. Lo más parecido fue:\n{bloque_encontrado}"]})
                                if ui_callback: ui_callback("⚙️ Sistema", f"❌ Fallo edición en {ruta_edit}. Similitud {(mejor_ratio*100):.1f}%", "#ff4500")
                    else:
                        msg_fallo = f"❌ Error leyendo '{ruta_edit}' para editar: {contenido_actual}"
                        print(msg_fallo)
                        if ui_callback: ui_callback("⚙️ Sistema", msg_fallo, "#ff4500")
                        CONTEXTO_CHAT.append({'role': 'user', 'parts': [msg_fallo]})

            except Exception as e:
                print(f"❌ Error en reemplazo de bloque: {e}")

        # Análisis línea por línea para el resto de comandos cortos
        lineas = respuesta_ia.split('\n')
        for linea in lineas:
            linea_limpia = linea.lower().replace("[", "").replace("]", "").replace("*", "").replace("`", "").strip()
            
            if "guardar_archivo:" in linea_limpia or "---contenido---" in linea_limpia or "<write_file>" in linea_limpia: continue
            
            # PARCHE: Ignorar etiquetas de bloques en español/inglés
            if any(t in linea_limpia for t in ["reemplazar_bloque:", "---buscar---", "---reemplazar---", "---fin---", "<replace_block>", "<reemplazar_bloque>", "<buscar>", "<reemplazar>"]): continue
            
            if "<read_file>" in linea_limpia: continue
            
            if "leer_archivo:" in linea_limpia:
                idx = linea_limpia.find("leer_archivo:") + 13
                raw_path = linea[idx:].strip()
                ruta_corta = raw_path.split('|')[0].replace('*', '').replace('`', '').replace('<', '').replace('>', '').strip()
                ruta_real = os.path.join(WORKSPACE_ACTUAL, ruta_corta) if WORKSPACE_ACTUAL and not os.path.isabs(ruta_corta) else ruta_corta
                
                if ruta_real in ARCHIVOS_EN_MEMORIA:
                    if ui_callback: ui_callback("⚙️ Sistema", f"📄 (Caché) Archivo {ruta_corta} ya está en memoria.", "#80868B")
                    continue
                
                contenido_leido = leer_contenido_archivo(ruta_real)
                if len(contenido_leido) > 80000:
                    contenido_leido = contenido_leido[:80000] + "\n... [CONTENIDO TRUNCADO POR SEGURIDAD]"
                
                ARCHIVOS_EN_MEMORIA.add(ruta_real)
                CONTEXTO_CHAT.append({'role': 'user', 'parts': [f"[CONTENIDO DE '{ruta_real}']:\n{contenido_leido}"]})
                if ui_callback: ui_callback("⚙️ Sistema", f"📄 Archivo cargado en memoria: {ruta_corta}", "#80868B")

            elif "editar_archivo:" in linea_limpia:
                match = re.search(r'editar_archivo:\s*(.+?)\s*\*?\|\*?\s*buscar:\s*(.+?)\s*\*?\|\*?\s*reemplazar:\s*(.+)', linea, re.IGNORECASE)
                if match:
                    ruta_edit = match.group(1).replace('`','').replace('*','').replace('<', '').replace('>', '').strip()
                    buscar_edit = match.group(2).strip().strip('"\'`')
                    reemplazar_edit = match.group(3).strip().strip('"\'`')
                    
                    ruta_real_edit = os.path.join(WORKSPACE_ACTUAL, ruta_edit) if WORKSPACE_ACTUAL and not os.path.isabs(ruta_edit) else ruta_edit
                    contenido_actual = leer_contenido_archivo(ruta_real_edit)
                    
                    if not contenido_actual.startswith("ERROR"):
                        buscar_norm = " ".join(buscar_edit.split())
                        contenido_norm = " ".join(contenido_actual.split())
                        
                        if buscar_norm in contenido_norm:
                            if buscar_edit in contenido_actual:
                                nuevo_contenido = contenido_actual.replace(buscar_edit, reemplazar_edit, 1)
                                if nuevo_contenido != contenido_actual:
                                    escribir_archivo(ruta_real_edit, nuevo_contenido)
                                    
                                    # FASE 1.4: Actualizar caché 1 línea
                                    for msg in CONTEXTO_CHAT:
                                        if isinstance(msg.get('parts', [''])[0], str) and f"[CONTENIDO DE '{ruta_real_edit}']:" in msg['parts'][0]:
                                            msg['parts'][0] = f"[CONTENIDO DE '{ruta_real_edit}']:\n{nuevo_contenido}"
                                            
                                    CONTEXTO_CHAT.append({'role': 'user', 'parts': [f"[RESULTADO EDICIÓN] Modificación exitosa en {ruta_edit}"]})
                                    if ui_callback: ui_callback("⚙️ Sistema", f"✅ Edición rápida en {ruta_edit}", "#86efac")
                            else:
                                CONTEXTO_CHAT.append({'role': 'user', 'parts': [f"[RESULTADO EDICIÓN] Difiere en espacios. Sé más preciso."]})
                        else:
                            CONTEXTO_CHAT.append({'role': 'user', 'parts': [f"[RESULTADO EDICIÓN] Fallo: Texto no encontrado."]})
                            if ui_callback: ui_callback("⚙️ Sistema", f"❌ Texto no encontrado en {ruta_edit}", "#ff4500")
                    else:
                        msg_fallo = f"❌ Error leyendo '{ruta_edit}' para editar: {contenido_actual}"
                        if ui_callback: ui_callback("⚙️ Sistema", msg_fallo, "#ff4500")

            elif "snapshot:" in linea_limpia:
                if WORKSPACE_ACTUAL:
                    resumen_estado = linea[linea.lower().find("snapshot:") + 9:].replace('<', '').replace('>', '').strip()
                    guardar_snapshot(WORKSPACE_ACTUAL, resumen_estado)
                    SNAPSHOT_ACTUAL = cargar_snapshot(WORKSPACE_ACTUAL)
                    if ui_callback: ui_callback("⚙️ Sistema", "📸 Snapshot guardado", "#FFA500")

            elif "buscar:" in linea_limpia and not "editar_archivo:" in linea_limpia: 
                comando_busqueda_detectado = linea[linea.lower().find("buscar:") + 7:].replace('<', '').replace('>', '').strip()
                
            elif "github:" in linea_limpia:
                ruta_corta = linea[linea.lower().find("github:") + 7:].replace('<', '').replace('>', '').strip()
                ruta_real = WORKSPACE_ACTUAL if WORKSPACE_ACTUAL else buscar_archivo_o_carpeta(ruta_corta) 
                if ruta_real:
                    PENDIENTE_DE_GIT = {"accion": "github", "ruta": ruta_real, "url_custom": None}
                    msg_alerta = f"⚠️ ALERTA: Vas a subir el proyecto a GitHub:\n'{ruta_real}'\n\n¿Autorizás el Push? (SÍ / NO)."
                    if ui_callback: ui_callback("🤖 Cortana", msg_alerta, "#FF4500")
                    CONTEXTO_CHAT.extend([{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [msg_alerta]}])
                    return
                
            elif "github_reset:" in linea_limpia:
                datos_git = linea[linea.lower().find("github_reset:") + 13:].replace("[", "").replace("]", "").replace("*", "").replace('<', '').replace('>', '').strip()
                partes = datos_git.split("||", 1) if "||" in datos_git else [datos_git, ""]
                ruta_real = WORKSPACE_ACTUAL if WORKSPACE_ACTUAL else buscar_archivo_o_carpeta(partes[0].strip())
                if ruta_real:
                    PENDIENTE_DE_GIT = {"accion": "github_reset", "ruta": ruta_real, "url_custom": partes[1].strip() if len(partes)>1 else None}
                    msg_alerta = f"⚠️ ALERTA CRÍTICA: Vas a DESVINCULAR y subir el repo.\n\n¿Autorizás esta operación crítica? (SÍ / NO)"
                    if ui_callback: ui_callback("🤖 Cortana", msg_alerta, "#FF4500")
                    CONTEXTO_CHAT.extend([{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [msg_alerta]}])
                    return
            
            elif "git_comando:" in linea_limpia:
                datos_git = linea[linea.lower().find("git_comando:") + 12:].replace("[", "").replace("]", "").replace("*", "").replace('<', '').replace('>', '').strip()
                partes = datos_git.split("||", 1) if "||" in datos_git else ["", ""]
                ruta_real = WORKSPACE_ACTUAL if WORKSPACE_ACTUAL else buscar_archivo_o_carpeta(partes[0].strip())
                if ruta_real and partes[1].strip():
                    PENDIENTE_DE_GIT = {"accion": "git_libre", "ruta": ruta_real, "url_custom": partes[1].strip()}
                    msg_alerta = f"⚠️ ALERTA: Vas a ejecutar un comando libre en Git.\nComando: {partes[1].strip()}\n\n¿Autorizás? (SÍ / NO)"
                    if ui_callback: ui_callback("🤖 Cortana", msg_alerta, "#FF4500")
                    CONTEXTO_CHAT.extend([{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [msg_alerta]}])
                    return
                
            elif "crear_carpeta:" in linea_limpia:
                ruta_corta = linea[linea.lower().find("crear_carpeta:") + 14:].replace("[", "").replace("]", "").replace("*", "").replace('<', '').replace('>', '').strip()
                ruta_final = os.path.join(WORKSPACE_ACTUAL, ruta_corta) if WORKSPACE_ACTUAL and not os.path.isabs(ruta_corta) else ruta_corta
                res_carp = crear_carpeta(ruta_final)
                if ui_callback: ui_callback("⚙️ Sistema", f"📁 {res_carp}", "#80868B")

            elif "escanear_proyecto:" in linea_limpia:
                if WORKSPACE_ACTUAL:
                    if ui_callback: ui_callback("⚙️ Sistema", "🔍 Iniciando Crawler...", "#80868B")
                    from modulos.crawler import extraer_codigo_proyecto
                    codigo_completo = extraer_codigo_proyecto(WORKSPACE_ACTUAL)
                    
                    prompt_analisis = f"""Actúa como el Arquitecto Principal del proyecto.
A continuación te proporciono el código completo de mi aplicación actual:

{codigo_completo}

Tu tarea es crear un documento de estado (PROJECT_STATE.md) que servirá como 'Fuente de la Verdad' para futuras planificaciones.
El documento DEBE contener estrictamente:
1. **Resumen Ejecutivo:** Propósito general del software.
2. **Arquitectura:** Lista de los módulos principales y para qué sirve cada archivo.
3. **Estado Actual:** Qué funcionalidades ya están construidas y operativas.
4. **Deuda Técnica / Próximos Pasos:** Posibles errores ocultos, funciones repetitivas que deban limpiarse o mejoras de arquitectura.

Responde ÚNICAMENTE con el Markdown final estructurado. No uses saludos, ni confirmaciones."""

                    if ui_callback: ui_callback("⚙️ Sistema", "🧠 Analizando arquitectura global con DeepSeek (Thinking)...", "#80868B")
                    
                    try:
                        response = cliente_deepseek.chat.completions.create(
                            model="deepseek-reasoner",
                            messages=[{"role": "user", "content": prompt_analisis}]
                        )
                        
                        estado_md = response.choices[0].message.content
                        
                        if estado_md.startswith("```markdown"):
                            estado_md = estado_md.split("```markdown")[1].rsplit("```", 1)[0].strip()
                        elif estado_md.startswith("```"):
                            estado_md = estado_md.split("```")[1].rsplit("```", 1)[0].strip()
                            
                        ruta_state = os.path.join(WORKSPACE_ACTUAL, "PROJECT_STATE.md")
                        escribir_archivo(ruta_state, estado_md)
                        
                        msg_exito = "✅ ¡PROJECT_STATE.md generado con éxito! El Planificador ya tiene visión total del código."
                        if ui_callback: ui_callback("⚙️ Sistema", msg_exito, "#86efac")
                        print(msg_exito)
                        
                    except Exception as e:
                        if ui_callback: ui_callback("⚙️ Sistema", f"❌ Error en el Crawler: {e}", "#ff4500")
                else:
                    if ui_callback: ui_callback("🤖 Cortana", "Necesito estar dentro del Modo Planificador o Programador para saber qué proyecto escanear.", "#FFA500")

            elif "abrir:" in linea_limpia or "cerrar:" in linea_limpia or "mover:" in linea_limpia:
                cmd_idx = max(linea_limpia.find("abrir:"), linea_limpia.find("cerrar:"), linea_limpia.find("mover:"))
                if cmd_idx != -1:
                    verbo = linea_limpia[cmd_idx:linea_limpia.find(":", cmd_idx)]
                    cmd_extraido = linea_limpia[linea_limpia.find(":", cmd_idx)+1:].replace('<', '').replace('>', '').strip()
                    if verbo == "mover": cmd_extraido = cmd_extraido.replace("@ 1", "@ 2") if "@ 1" in cmd_extraido else cmd_extraido.replace("@ 2", "@ 1")
                    reportes_acciones.append(f"Acción SO: {ejecutar_comando_sistema(verbo + ':' + cmd_extraido)}")

        if reportes_acciones:
            texto_reporte = "\n".join([f"*({r})*" for r in reportes_acciones])
            print(texto_reporte)
            if ui_callback: ui_callback("⚙️ Sistema", texto_reporte, "#80868B")

        if comando_busqueda_detectado and modelo_activo == "gemini":
            if ui_callback: ui_callback("⚙️ Sistema", f"🌍 Buscando en internet: {comando_busqueda_detectado}", "#80868B")
            datos_encontrados = buscar_en_internet(comando_busqueda_detectado)
            if "No se encontraron" not in datos_encontrados:
                mensajes_secundarios = list(CONTEXTO_CHAT) + [{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [respuesta_ia]}, {'role': 'user', 'parts': [f"Resultados web:\n{datos_encontrados}\n\nRespondé usando esto."]}]
                segunda_respuesta = modelo_gemini.generate_content(mensajes_secundarios, stream=True)
                respuesta_final = ""
                for chunk in segunda_respuesta:
                    if chunk.text:
                        respuesta_final += chunk.text
                        if ui_callback: ui_callback("", chunk.text, "#E8EAED", nueva_linea=False)
                if ui_callback: ui_callback("", "", "#E8EAED", nueva_linea=True)
                if modo_voz: hablar_no_bloqueante(respuesta_final)
                CONTEXTO_CHAT.extend([{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [respuesta_final]}])
                return

        if modo_voz: hablar_no_bloqueante(respuesta_ia)
        
        CONTEXTO_CHAT.extend([{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [respuesta_ia]}])
        if len(CONTEXTO_CHAT) > 100: CONTEXTO_CHAT = CONTEXTO_CHAT[-100:]
            
    except Exception as e:
        print(f"\n❌ Error Crítico: {e}")

# =====================================================================
# PROCESAMIENTO DE ARCHIVOS ADJUNTOS
# =====================================================================
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