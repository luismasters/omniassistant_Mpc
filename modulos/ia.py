import os
import datetime
import winsound
import re
import difflib 
import google.generativeai as genai
from openai import OpenAI 
import config 

# Importación de llaves
from config import GEMINI_API_KEY, DEEPSEEK_API_KEY

from modulos.archivos import eliminar_elemento, leer_contenido_archivo
from modulos.sistema import obtener_ventanas_activas
from modulos.busqueda import buscar_en_internet
from modulos.audio import hablar_no_bloqueante
from modulos.vision import capturar_pantalla
from modulos.git_bot import sincronizar_proyecto_git, ejecutar_comando_git_libre
from modulos.memoria import guardar_recuerdo
from modulos.cliente_mcp import cliente_sistema 

# Importación de Prompts Separados
from modulos.prompts import obtener_prompt_planificador, obtener_prompt_programador, obtener_prompt_general

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
ARCHIVOS_EN_MEMORIA = set() 

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
    # 🛡️ ESCUDOS DE SEGURIDAD (Con Parche Anti-Hilos / Race Condition)
    # =================================================================
    if PENDIENTE_DE_BORRADO:
        tarea_borrado = PENDIENTE_DE_BORRADO
        PENDIENTE_DE_BORRADO = ""
        
        print("🧠 [SEMÁFORO DE BORRADO] Evaluando...")
        evaluador = genai.GenerativeModel("gemini-flash-lite-latest")
        prompt_juez = f"El usuario debe confirmar borrar: '{tarea_borrado}'. Su respuesta: '{texto_usuario}'. Responde CONFIRMADO o CANCELADO."
        try: decision_borrado = evaluador.generate_content(prompt_juez).text.strip().upper()
        except: decision_borrado = "CANCELADO"
        
        if "CONFIRMADO" in decision_borrado:
            resultado = eliminar_elemento(tarea_borrado)
            msg = f"Protocolo autorizado. {resultado}"
        else: msg = "Protocolo abortado. Archivos a salvo."
            
        if ui_callback: ui_callback("🤖 Cortana", msg, "#FF4500" if "abortado" in msg else "#00E5FF")
        if modo_voz: hablar_no_bloqueante(msg)
        CONTEXTO_CHAT.extend([{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [msg]}])
        return

    if PENDIENTE_DE_GIT:
        tarea_git = PENDIENTE_DE_GIT
        PENDIENTE_DE_GIT = None
        
        print("🧠 [SEMÁFORO DE GIT] Evaluando...")
        evaluador = genai.GenerativeModel("gemini-flash-lite-latest")
        prompt_juez = f"El usuario debe confirmar una operación de GitHub. Su respuesta: '{texto_usuario}'. Responde CONFIRMADO o CANCELADO."
        try: decision_git = evaluador.generate_content(prompt_juez).text.strip().upper()
        except: decision_git = "CANCELADO"
        
        if "CONFIRMADO" in decision_git:
            if ui_callback: ui_callback("⚙️ Sistema", "Iniciando operación en GitHub. Esto puede tardar unos segundos...", "#80868B")
            accion = tarea_git.get("accion")
            ruta = tarea_git.get("ruta")
            url_custom = tarea_git.get("url_custom")
            
            if accion == "github_reset":
                resultado = sincronizar_proyecto_git(ruta, reset_remote=True, url_custom=url_custom)
            elif accion == "git_libre":
                resultado = ejecutar_comando_git_libre(ruta, url_custom)
            else:
                resultado = sincronizar_proyecto_git(ruta)
            msg = f"Operación Git completada:\n{resultado}"
        else: 
            msg = "Operación en GitHub cancelada de forma segura."
            
        if ui_callback: ui_callback("🤖 Cortana", msg, "#FF4500" if "cancelada" in msg else "#00E5FF")
        if modo_voz: hablar_no_bloqueante("Operación finalizada." if "completada" in msg else "Operación cancelada.")
        CONTEXTO_CHAT.extend([{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [msg]}])
        return

    if ARCHIVO_PENDIENTE_INYECCION:
        tarea_inyeccion = ARCHIVO_PENDIENTE_INYECCION
        ARCHIVO_PENDIENTE_INYECCION = None
        
        evaluador = genai.GenerativeModel("gemini-flash-lite-latest")
        prompt_juez = f"El usuario debe confirmar guardar adjuntos. Su respuesta: '{texto_usuario}'. Responde CONFIRMADO o CANCELADO."
        try: decision = evaluador.generate_content(prompt_juez).text.strip().upper()
        except: decision = "CANCELADO"
        
        if "CONFIRMADO" in decision:
            for archivo_dict in tarea_inyeccion:
                nombre = archivo_dict["nombre"]
                contenido = archivo_dict["contenido"]
                chunks = [contenido[i:i+1500] for i in range(0, len(contenido), 1500)]
                for chunk in chunks: guardar_recuerdo(texto_a_guardar=chunk, etiqueta_tema=f"Doc: {nombre}")
            msg = f"¡Perfecto! Inyecté los archivos en la bóveda permanente."
            DOCUMENTO_VOLATIL = "" 
        else: msg = "Entendido. Dejé los archivos en mi memoria a corto plazo."
            
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
            contexto_sistema = obtener_prompt_planificador(texto_workspace, texto_snapshot, texto_doc_volatil)
            modelo_activo = "deepseek-reasoner"
        elif MODO_ACTUAL == "programador":
            contexto_sistema = obtener_prompt_programador(texto_workspace, texto_snapshot, texto_doc_volatil)
            modelo_activo = "deepseek-chat"
        else:
            ruta_home = os.path.expanduser("~") 
            contexto_sistema = obtener_prompt_general(fecha_hoy, ruta_home, ventanas_abiertas, texto_workspace, texto_snapshot, texto_doc_volatil)
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
        # INTERCEPTOR DE ACCIONES (CONTROLADOR SEPARADO)
        # =================================================================
        from modulos.controlador_acciones import procesar_acciones_ia
        comando_busqueda = procesar_acciones_ia(respuesta_ia, texto_usuario, ui_callback, modo_voz)
        
        if comando_busqueda == "INTERRUPTED":
            return # Detenemos el flujo aquí (Ej. Se activó semáforo de Git)

        if comando_busqueda and modelo_activo == "gemini":
            if ui_callback: ui_callback("⚙️ Sistema", f"🌍 Buscando en internet: {comando_busqueda}", "#80868B")
            datos_encontrados = buscar_en_internet(comando_busqueda)
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