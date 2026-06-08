import os
import datetime
import winsound
import google.generativeai as genai
from openai import OpenAI # Cliente para DeepSeek

# Importación de llaves
from config import GEMINI_API_KEY, DEEPSEEK_API_KEY

from modulos.archivos import crear_carpeta, crear_archivo, eliminar_elemento, leer_contenido_archivo, buscar_archivo_local, escribir_archivo
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
MODO_ACTUAL = "general" # Controla el cerebro de Cortana (general, planificador, programador)

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
    global CONTEXTO_CHAT, ARCHIVO_PENDIENTE_INYECCION, DOCUMENTO_VOLATIL, PENDIENTE_DE_BORRADO, PENDIENTE_DE_GIT, WORKSPACE_ACTUAL, SNAPSHOT_ACTUAL, MODO_ACTUAL
    texto_usuario_lower = texto_usuario.lower().strip()

    # =================================================================
    # 🛡️ ESCUDOS DE SEGURIDAD (Se evalúan rápido con Gemini Flash)
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

        # --- SELECCIÓN DEL ROL Y MODELO ---
        thinking_config = None # Por defecto desactivado/nulo

        if MODO_ACTUAL == "planificador":
            contexto_sistema = (
                "Eres el Arquitecto de Software Senior de Luis. Tu objetivo es analizar el código y diseñar soluciones.\n"
                f"{texto_workspace}\n{texto_snapshot}{texto_doc_volatil}"
                "REGLAS OBLIGATORIAS:\n"
                "1. NO escribas código final de implementación.\n"
                "2. Analiza riesgos, dependencias y estructura lógica paso a paso.\n"
                "⚠️ REGLAS DE ACCIONES RÁPIDAS (SIEMPRE al inicio de línea):\n"
                "- Para ACTUALIZAR EL PLAN: guardar_archivo: plan.md || contenido_del_plan\n"
                "- Para ACTUALIZAR EL ESTADO REAL: guardar_archivo: PROJECT_STATE.md || contenido_del_estado\n"
                "- Para CREAR CARPETAS de doc: crear_carpeta: ruta\n"
                "⚠️ IMPORTANTE: SIEMPRE usa 'guardar_archivo:' para generar el plan.md físico."
            )
            modelo_activo = "deepseek-v4-flash"
            thinking_config = {"type": "enabled"} # <-- ACTIVAMOS THINKING

        elif MODO_ACTUAL == "programador":
            contexto_sistema = (
                "Eres el Ingeniero de Software Principal de Luis. Tu objetivo es ejecutar planes y escribir código seguro.\n"
                f"{texto_workspace}\n{texto_snapshot}{texto_doc_volatil}"
                "REGLAS OBLIGATORIAS:\n"
                "1. Escribe únicamente el código necesario según el plan.\n"
                "2. Mantén consistencia con la arquitectura.\n"
                "⚠️ REGLAS DE ACCIONES RÁPIDAS (SIEMPRE al inicio de línea):\n"
                "- Para CREAR CARPETAS: crear_carpeta: ruta\n"
                "- Para CREAR/EDITAR ARCHIVOS: guardar_archivo: ruta || contenido\n"
                "- Para ELIMINAR obsoleto: eliminar: ruta\n"
                "- Para PUSH a GitHub: github: ruta\n"
                "- Para comandos Git: git_comando: ruta || tu_comando\n"
                "⚠️ IMPORTANTE: NUNCA te limites a imprimir código en chat. USÁ 'guardar_archivo:' siempre."
            )
            modelo_activo = "deepseek-v4-flash"
            thinking_config = {"type": "disabled"} 

        else: # MODO GENERAL (Gemini)
            contexto_sistema = (
                "tu nombre es: Cortana, un asistente de IA integrado a la PC de Luis. Hablále de forma súper natural.\n"
                "⚠️ REGLA DE PERSONALIDAD: Sé breve. NUNCA expliques tus procesos.\n\n"
                f"[CONTEXTO OCULTO] Fecha: {fecha_hoy}\n"
                f"[VENTANAS ABIERTAS]: {ventanas_abiertas}\n\n"
                f"{texto_workspace}\n{texto_snapshot}{texto_doc_volatil}"
                "⚠️ REGLAS DE ACCIONES RÁPIDAS (SIEMPRE al inicio de línea):\n"
                "- Para GUARDAR ESTADO MANUAL: snapshot: resumen_tecnico\n"
                "- Para ABRIR o MOSTRAR: abrir: nombre_app\n"
                "- Para MOVER ventanas: abrir: nombre_app @ num\n"
                "- Para CERRAR: cerrar: nombre_app\n"
                "- Para ELIMINAR: eliminar: ruta\n"
                "- Para buscar en INTERNET: buscar: tu consulta\n" 
                "- Para CREAR CARPETAS: crear_carpeta: ruta\n"
                "- Para GUARDAR ARCHIVOS: guardar_archivo: ruta || contenido\n"
                "- Para GITHUB: github: ruta\n"
                "- Para GITHUB RESET: github_reset: ruta || url\n"
                "- Para GIT COMANDO: git_comando: ruta || comando\n"
                "- Para ESCANEAR y analizar TODO el proyecto generando el PROJECT_STATE.md: escanear_proyecto:\n"
            )
            modelo_activo = "gemini"

        respuesta_ia = ""
        usaste_mcp = False
        resultado_mcp = ""

        print(f"\n🤖 Cortana dice:\n---")
        
        # =================================================================
        # EJECUCIÓN GEMINI (Modo General)
        # =================================================================
        if modelo_activo == "gemini":
            modelo_gemini = genai.GenerativeModel("gemini-flash-lite-latest", system_instruction=contexto_sistema, tools=lista_herramientas_mcp)
            mensajes_para_gemini = list(CONTEXTO_CHAT)
            partes_usuario = [texto_usuario]
            
            # Lógica de Visión (Solo Gemini)
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

            if usaste_mcp:
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
            # Formatear el historial de Gemini al formato de OpenAI/DeepSeek
            mensajes_ds = [{"role": "system", "content": contexto_sistema}]
            for msg in CONTEXTO_CHAT:
                rol_ds = "assistant" if msg['role'] == "model" else "user"
                texto_historico = "".join([p for p in msg['parts'] if isinstance(p, str)])
                mensajes_ds.append({"role": rol_ds, "content": texto_historico})
            
            mensajes_ds.append({"role": "user", "content": texto_usuario})

            if ui_callback: ui_callback("🤖 Cortana", "", "#A8C7FA", nueva_linea=False)
            
            # --- NUEVA LÓGICA DE LLAMADA CON EXTRA_BODY ---
            parametros_api = {
                "model": modelo_activo,
                "messages": mensajes_ds,
                "stream": True
            }
            
            # Si el modo tiene configuración de thinking, la agregamos
            if thinking_config:
                parametros_api["extra_body"] = {"thinking": thinking_config}

            # Llamamos a la API desempaquetando los parámetros
            response = cliente_deepseek.chat.completions.create(**parametros_api)
            
            for chunk in response:
                delta = chunk.choices[0].delta
                # Imprimir el razonamiento interno en la consola (si está enabled)
                if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                    print(delta.reasoning_content, end='', flush=True)
                # Enviar el texto final a la UI
                if getattr(delta, 'content', None):
                    texto_chunk = delta.content
                    print(texto_chunk, end='', flush=True)
                    respuesta_ia += texto_chunk
                    if ui_callback: ui_callback("", texto_chunk, "#E8EAED", nueva_linea=False)

        print("\n---")
        if ui_callback: ui_callback("", "", "#E8EAED", nueva_linea=True)
        
        # =================================================================
        # INTERCEPTOR DE ACCIONES (Universal para todos los modelos)
        # =================================================================
        reportes_acciones = []
        comando_busqueda_detectado = None

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
                    
                if WORKSPACE_ACTUAL and not os.path.isabs(ruta_f):
                    ruta_en_workspace = None
                    nombre_archivo_buscado = os.path.basename(ruta_f).lower()
                    for raiz, _, archivos in os.walk(WORKSPACE_ACTUAL):
                        if nombre_archivo_buscado in [a.lower() for a in archivos]:
                            ruta_en_workspace = os.path.join(raiz, os.path.basename(ruta_f))
                            break
                    ruta_f = ruta_en_workspace if ruta_en_workspace else os.path.join(WORKSPACE_ACTUAL, os.path.basename(ruta_f))
                elif not os.path.isabs(ruta_f):
                    ruta_real = buscar_archivo_local(ruta_f)
                    ruta_f = ruta_real if ruta_real else os.path.join(os.path.expanduser("~"), "Desktop", ruta_f)
                
                reportes_acciones.append(f"Archivo guardado: {escribir_archivo(ruta_f, contenido_f.strip())}")

        lineas = respuesta_ia.split('\n')
        
        for linea in lineas:
            linea_limpia = linea.lower().replace("[", "").replace("]", "").replace("*", "").strip()
            if linea_limpia.startswith("guardar_archivo:"): continue
            
            elif linea_limpia.startswith("snapshot:"):
                if WORKSPACE_ACTUAL:
                    resumen_estado = linea[linea.lower().find("snapshot:") + 9:].strip()
                    guardar_snapshot(WORKSPACE_ACTUAL, resumen_estado)
                    SNAPSHOT_ACTUAL = cargar_snapshot(WORKSPACE_ACTUAL)
                    msg = f"📸 Snapshot físico guardado."
                    print(msg)
                    if ui_callback: ui_callback("⚙️ Sistema", msg, "#FFA500")
                    reportes_acciones.append("Snapshot guardado exitosamente.")

            elif linea_limpia.startswith("buscar:"): 
                comando_busqueda_detectado = linea_limpia[7:].strip()
                
            elif linea_limpia.startswith("eliminar:"):
                ruta_corta = linea_limpia[9:].strip()
                if WORKSPACE_ACTUAL and not os.path.isabs(ruta_corta):
                    ruta_real = os.path.join(WORKSPACE_ACTUAL, os.path.basename(ruta_corta))
                    if not os.path.exists(ruta_real): ruta_real = buscar_archivo_o_carpeta(ruta_corta) or ruta_corta
                else:
                    ruta_real = ruta_corta if os.path.exists(ruta_corta) else (buscar_archivo_o_carpeta(ruta_corta) or ruta_corta)
                
                PENDIENTE_DE_BORRADO = ruta_real
                msg_alerta = f"⚠️ ALERTA: Vas a eliminar:\n'{ruta_real}'\n\n¿Seguro? Respondé SÍ para proceder o NO."
                if ui_callback: ui_callback("🤖 Cortana", msg_alerta, "#FF4500")
                if modo_voz: hablar_no_bloqueante("Alerta de seguridad. ¿Confirmás el borrado?")
                CONTEXTO_CHAT.extend([{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [msg_alerta]}])
                return 
                
            elif linea_limpia.startswith("github:"):
                ruta_corta = linea_limpia[7:].strip()
                ruta_real = WORKSPACE_ACTUAL if WORKSPACE_ACTUAL else buscar_archivo_o_carpeta(ruta_corta) 
                if ruta_real:
                    PENDIENTE_DE_GIT = {"accion": "github", "ruta": ruta_real, "url_custom": None}
                    msg_alerta = f"⚠️ ALERTA: Vas a subir el proyecto a GitHub:\n'{ruta_real}'\n\n¿Autorizás el Push? (SÍ / NO)."
                    if ui_callback: ui_callback("🤖 Cortana", msg_alerta, "#FF4500")
                    CONTEXTO_CHAT.extend([{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [msg_alerta]}])
                    return
                
            elif linea_limpia.startswith("github_reset:"):
                datos_git = linea[linea.lower().find("github_reset:") + 13:].replace("[", "").replace("]", "").replace("*", "").strip()
                partes = datos_git.split("||", 1) if "||" in datos_git else [datos_git, ""]
                ruta_real = WORKSPACE_ACTUAL if WORKSPACE_ACTUAL else buscar_archivo_o_carpeta(partes[0].strip())
                if ruta_real:
                    PENDIENTE_DE_GIT = {"accion": "github_reset", "ruta": ruta_real, "url_custom": partes[1].strip() if len(partes)>1 else None}
                    msg_alerta = f"⚠️ ALERTA CRÍTICA: Vas a DESVINCULAR y subir el repo.\n\n¿Autorizás esta operación crítica? (SÍ / NO)"
                    if ui_callback: ui_callback("🤖 Cortana", msg_alerta, "#FF4500")
                    CONTEXTO_CHAT.extend([{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [msg_alerta]}])
                    return
            
            elif linea_limpia.startswith("git_comando:"):
                datos_git = linea[linea.lower().find("git_comando:") + 12:].replace("[", "").replace("]", "").replace("*", "").strip()
                partes = datos_git.split("||", 1) if "||" in datos_git else ["", ""]
                ruta_real = WORKSPACE_ACTUAL if WORKSPACE_ACTUAL else buscar_archivo_o_carpeta(partes[0].strip())
                if ruta_real and partes[1].strip():
                    PENDIENTE_DE_GIT = {"accion": "git_libre", "ruta": ruta_real, "url_custom": partes[1].strip()}
                    msg_alerta = f"⚠️ ALERTA: Vas a ejecutar un comando libre en Git.\nComando: {partes[1].strip()}\n\n¿Autorizás? (SÍ / NO)"
                    if ui_callback: ui_callback("🤖 Cortana", msg_alerta, "#FF4500")
                    CONTEXTO_CHAT.extend([{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [msg_alerta]}])
                    return
                
            elif linea_limpia.startswith("crear_carpeta:"):
                ruta_corta = linea[linea.lower().find("crear_carpeta:") + 14:].replace("[", "").replace("]", "").replace("*", "").strip()
                ruta_final = os.path.join(WORKSPACE_ACTUAL, ruta_corta) if WORKSPACE_ACTUAL and not os.path.isabs(ruta_corta) else ruta_corta
                reportes_acciones.append(f"Carpeta: {crear_carpeta(ruta_final)}")
            # ==========================================================
            # INICIO DEL NUEVO BLOQUE DEL CRAWLER
            # ==========================================================
            elif linea_limpia.startswith("escanear_proyecto:"):
                if WORKSPACE_ACTUAL:
                    if ui_callback: ui_callback("⚙️ Sistema", "🔍 Iniciando Crawler... Extrayendo todo tu código base.", "#80868B")
                    
                    from modulos.crawler import extraer_codigo_proyecto
                    from modulos.archivos import escribir_archivo
                    
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
                    print("\n[CRAWLER] Enviando mega-contexto a DeepSeek V4...")
                    
                    try:
                        # Llamada especial directa a DeepSeek para el mega-análisis
                        response = cliente_deepseek.chat.completions.create(
                            model="deepseek-v4-flash",
                            messages=[{"role": "user", "content": prompt_analisis}],
                            extra_body={"thinking": {"type": "enabled"}}
                        )
                        
                        estado_md = response.choices[0].message.content
                        
                        # Limpiamos los backticks si la IA los pone
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
            # ==========================================================
            # FIN DEL NUEVO BLOQUE DEL CRAWLER
            # ==========================================================    
            
            elif linea_limpia.startswith("abrir:") or linea_limpia.startswith("cerrar:") or linea_limpia.startswith("mover:"):
                cmd_extraido = linea_limpia[linea_limpia.find(":")+1:].strip()
                if "mover:" in linea_limpia: cmd_extraido = cmd_extraido.replace("@ 1", "@ 2") if "@ 1" in cmd_extraido else cmd_extraido.replace("@ 2", "@ 1")
                reportes_acciones.append(f"Acción SO: {ejecutar_comando_sistema(linea_limpia.split(':')[0] + ':' + cmd_extraido)}")

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
        
        # Guardamos el historial usando el formato estándar de la aplicación
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