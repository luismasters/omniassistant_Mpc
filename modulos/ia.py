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
from modulos.audio_custom import hablar_no_bloqueante, encolar_texto_para_hablar, detener_voz
from modulos.vision import capturar_pantalla
from modulos.git_bot import sincronizar_proyecto_git, ejecutar_comando_git_libre
from modulos.memoria import guardar_recuerdo
from modulos.cliente_mcp import cliente_sistema 

from modulos.prompts import (
    obtener_prompt_planificador,
    obtener_prompt_programador,
    obtener_prompt_general,
    obtener_prompt_programador_unificado
)

# =====================================================================
# INICIALIZACIÓN DE CLIENTES IA
# =====================================================================
genai.configure(api_key=GEMINI_API_KEY)
cliente_deepseek = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

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


# =====================================================================
# HELPER: STREAMING DE VOZ PARALELO AL STREAMING DE IA
# =====================================================================
_PATRON_CORTE_VOZ = re.compile(r'(?<=[.!?])\s+')
_MIN_CHARS_CHUNK_VOZ = 80

def _procesar_buffer_voz(buffer: str, forzar: bool = False) -> str:
    while True:
        match = _PATRON_CORTE_VOZ.search(buffer)
        if match and len(buffer[:match.end()].strip()) >= _MIN_CHARS_CHUNK_VOZ:
            fragmento = buffer[:match.end()].strip()
            encolar_texto_para_hablar(fragmento)
            buffer = buffer[match.end():]
        else:
            break
    if forzar and buffer.strip():
        encolar_texto_para_hablar(buffer.strip())
        buffer = ""
    return buffer


def enviar_a_gemini(texto_usuario, modo_voz=False, ui_callback=None):
    """Enrutador Universal y traductor de acciones."""
    import config
    CONTEXTO_CHAT = config.estado.contexto_chat
    DOCUMENTO_VOLATIL = config.estado.documento_volatil
    PENDIENTE_DE_BORRADO = config.estado.pendiente_de_borrado
    PENDIENTE_DE_GIT = config.estado.pendiente_de_git
    WORKSPACE_ACTUAL = config.estado.workspace_actual
    SNAPSHOT_ACTUAL = config.estado.snapshot_actual
    MODO_ACTUAL = config.estado.modo_actual  # Leer de config.estado
    ARCHIVOS_EN_MEMORIA = config.estado.archivos_en_memoria
    
    config.RUTA_WORKSPACE_ACTUAL = WORKSPACE_ACTUAL
    texto_usuario_lower = texto_usuario.lower().strip()

    if texto_usuario_lower in ["limpiar memoria", "olvidar contexto"]:
        ARCHIVOS_EN_MEMORIA.clear()
        CONTEXTO_CHAT.clear()
        if ui_callback: ui_callback("⚙️ Sistema", "🧹 Contexto y caché limpiados.", "#80868B")
        return

    # =================================================================
    # 🩹 INTERCEPTOR DE ADJUNTOS (SIEMPRE A CONTEXTO VOLÁTIL)
    # =================================================================
    if "[adjunto:" in texto_usuario.lower():
        rutas_extraidas = re.findall(r'\[adjunto:\s*(.*?)\]', texto_usuario, re.IGNORECASE)
        if rutas_extraidas:
            texto_usuario = re.sub(r'\[adjunto:\s*.*?\]', '', texto_usuario, flags=re.IGNORECASE).strip()
            cargar_adjuntos_en_contexto(rutas_extraidas, ui_callback)
            if not texto_usuario:
                return

    # =================================================================
    # 🛡️ ESCUDOS DE SEGURIDAD (Confirmaciones de UI)
    # =================================================================
    if PENDIENTE_DE_BORRADO:
        tarea_borrado = PENDIENTE_DE_BORRADO
        config.estado.pendiente_de_borrado = ""
        
        print("🧠 [SEMÁFORO DE BORRADO] Evaluando...")
        evaluador = genai.GenerativeModel("gemini-flash-lite-latest")
        prompt_juez = f"El usuario debe confirmar borrar: '{tarea_borrado}'. Su respuesta: '{texto_usuario}'. Responde CONFIRMADO o CANCELADO."
        try: decision_borrado = evaluador.generate_content(prompt_juez).text.strip().upper()
        except: decision_borrado = "CANCELADO"
        
        if "CONFIRMADO" in decision_borrado:
            resultado = eliminar_elemento(tarea_borrado)
            msg = f"Protocolo autorizado. {resultado}"
        else: msg = "Protocolo abortado. Archivos a salvo."
            
        if ui_callback: ui_callback("🤖 Argus", msg, "#FF4500" if "abortado" in msg else "#00E5FF")
        if modo_voz: hablar_no_bloqueante(msg)
        CONTEXTO_CHAT.extend([{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [msg]}])
        return

    if PENDIENTE_DE_GIT:
        tarea_git = PENDIENTE_DE_GIT
        config.estado.pendiente_de_git = None
        
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
            
        if ui_callback: ui_callback("🤖 Argus", msg, "#FF4500" if "cancelada" in msg else "#00E5FF")
        if modo_voz: hablar_no_bloqueante("Operación finalizada." if "completada" in msg else "Operación cancelada.")
        CONTEXTO_CHAT.extend([{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [msg]}])
        return

    # =================================================================
    # 🧠 TRADUCTOR INSTANTÁNEO DE INTENCIONES NATURALES
    # =================================================================
    intentos_naturales = {
        "subir cambios": "github: .",
        "sube los cambios": "github: .",
        "sincronizar proyecto": "github: .",
        "sincroniza": "github: .",
        "escanear proyecto": "escanear_proyecto:"
    }
    
    comando_directo = None
    for frase, comando in intentos_naturales.items():
        if frase in texto_usuario_lower:
            comando_directo = comando
            break

    respuesta_ia = ""
    usaste_mcp = False
    resultado_mcp = ""
    modelo_gemini = None

    if comando_directo:
        respuesta_ia = comando_directo
        if ui_callback: ui_callback("🤖 Argus", f"Entendido, ejecutando acción solicitada...", "#A8C7FA", nueva_linea=True)
        if modo_voz: hablar_no_bloqueante("Entendido, ejecutando acción.")

    else:
        print(f"\n🧠 PENSANDO ({MODO_ACTUAL.upper()})...")
        try:
            fecha_hoy = datetime.datetime.now().strftime("%A, %d de %B de %Y") 
            ventanas_abiertas = obtener_ventanas_activas()
            
            texto_workspace = f"[WORKSPACE ANCLADO]: {WORKSPACE_ACTUAL}\n" if WORKSPACE_ACTUAL else ""
            texto_snapshot = f"[ESTADO DEL PROYECTO]:\n{SNAPSHOT_ACTUAL}\n\n" if SNAPSHOT_ACTUAL else ""
            texto_doc_volatil = f"[DOCUMENTOS EN MEMORIA]:\n{DOCUMENTO_VOLATIL}\n\n" if DOCUMENTO_VOLATIL else ""

            # ─── SELECCIÓN DE MODELO Y CONTEXTO (USANDO config.estado.modo_actual) ──
            MODO_ACTUAL = config.estado.modo_actual
            if MODO_ACTUAL in ["programador", "planificador"]:
                contexto_sistema = obtener_prompt_programador_unificado(
                    texto_workspace, texto_snapshot, texto_doc_volatil
                )
                modelo_activo = "deepseek-reasoner"
            else:
                ruta_home = os.path.expanduser("~") 
                contexto_sistema = obtener_prompt_general(
                    fecha_hoy, ruta_home, ventanas_abiertas,
                    texto_workspace, texto_snapshot, texto_doc_volatil
                )
                modelo_activo = "gemini"

            print(f"\n🤖 Argus dice:\n---")
            
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
                
                if ui_callback: ui_callback("🤖 Argus", "", "#A8C7FA", nueva_linea=False)

                buffer_voz = ""

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
                                
                                if modo_voz and not usaste_mcp:
                                    buffer_voz += part.text
                                    buffer_voz = _procesar_buffer_voz(buffer_voz, forzar=False)

                    except Exception: pass

                if modo_voz and buffer_voz.strip() and not usaste_mcp:
                    _procesar_buffer_voz(buffer_voz, forzar=True)

                if usaste_mcp and modelo_gemini:
                    mensajes_para_gemini.append({'role': 'model', 'parts': ['Analizando los datos del sistema...']})
                    mensajes_para_gemini.append({'role': 'user', 'parts': [f"[DATO DEL SISTEMA: {resultado_mcp}]. Responde naturalmente."]})
                    response_2 = modelo_gemini.generate_content(mensajes_para_gemini, stream=True)
                    
                    buffer_voz_2 = ""
                    for chunk_2 in response_2:
                        try:
                            for part in chunk_2.parts:
                                if getattr(part, "text", None):
                                    print(part.text, end='', flush=True)
                                    respuesta_ia += part.text
                                    if ui_callback: ui_callback("", part.text, "#E8EAED", nueva_linea=False)
                                    if modo_voz:
                                        buffer_voz_2 += part.text
                                        buffer_voz_2 = _procesar_buffer_voz(buffer_voz_2, forzar=False)
                        except Exception: pass
                    if modo_voz and buffer_voz_2.strip():
                        _procesar_buffer_voz(buffer_voz_2, forzar=True)

            else:
                # DeepSeek (programador / planificador)
                mensajes_ds = [{"role": "system", "content": contexto_sistema}]
                for msg in CONTEXTO_CHAT:
                    rol_ds = "assistant" if msg['role'] == "model" else "user"
                    texto_historico = "".join([p for p in msg['parts'] if isinstance(p, str)])
                    mensajes_ds.append({"role": rol_ds, "content": texto_historico})
                
                mensajes_ds.append({"role": "user", "content": texto_usuario})
                if ui_callback: ui_callback("🤖 Argus", "", "#A8C7FA", nueva_linea=False)
                
                parametros_api = {"model": modelo_activo, "messages": mensajes_ds, "stream": True}
                response = cliente_deepseek.chat.completions.create(**parametros_api)
                
                buffer_voz_ds = ""
                for chunk in response:
                    delta = chunk.choices[0].delta
                    if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                        print(delta.reasoning_content, end='', flush=True)
                    if getattr(delta, 'content', None):
                        texto_chunk = delta.content
                        print(texto_chunk, end='', flush=True)
                        respuesta_ia += texto_chunk
                        if ui_callback: ui_callback("", texto_chunk, "#E8EAED", nueva_linea=False)
                        if modo_voz:
                            buffer_voz_ds += texto_chunk
                            buffer_voz_ds = _procesar_buffer_voz(buffer_voz_ds, forzar=False)

                if modo_voz and buffer_voz_ds.strip():
                    _procesar_buffer_voz(buffer_voz_ds, forzar=True)

            print("\n---")
            if ui_callback: ui_callback("", "", "#E8EAED", nueva_linea=True)
            
        except Exception as e:
            print(f"\n❌ Error Crítico: {e}")

    # =================================================================
    # INTERCEPTOR DE ACCIONES
    # =================================================================
    from modulos.controlador_acciones import procesar_acciones_ia
    comando_busqueda = procesar_acciones_ia(respuesta_ia, texto_usuario, ui_callback, modo_voz)
    
    if comando_busqueda == "INTERRUPTED":
        return

    if comando_busqueda and getattr(config.estado, 'modo_actual', 'general') == "general":
        if ui_callback: ui_callback("⚙️ Sistema", f"🌍 Buscando en internet: {comando_busqueda}", "#80868B")
        datos_encontrados = buscar_en_internet(comando_busqueda)
        if "No se encontraron" not in datos_encontrados and modelo_gemini:
            mensajes_secundarios = list(CONTEXTO_CHAT) + [{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [respuesta_ia]}, {'role': 'user', 'parts': [f"Resultados web:\n{datos_encontrados}\n\nRespondé usando esto."]}]
            segunda_respuesta = modelo_gemini.generate_content(mensajes_secundarios, stream=True)
            respuesta_final = ""
            buffer_voz_web = ""
            for chunk in segunda_respuesta:
                if getattr(chunk, 'text', None):
                    respuesta_final += chunk.text
                    if ui_callback: ui_callback("", chunk.text, "#E8EAED", nueva_linea=False)
                    if modo_voz:
                        buffer_voz_web += chunk.text
                        buffer_voz_web = _procesar_buffer_voz(buffer_voz_web, forzar=False)
            if modo_voz and buffer_voz_web.strip():
                _procesar_buffer_voz(buffer_voz_web, forzar=True)
            if ui_callback: ui_callback("", "", "#E8EAED", nueva_linea=True)
            CONTEXTO_CHAT.extend([{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [respuesta_final]}])
            return

    if modo_voz and comando_directo:
        hablar_no_bloqueante(respuesta_ia)
    
    if respuesta_ia:
        CONTEXTO_CHAT.extend([{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [respuesta_ia]}])
    if len(CONTEXTO_CHAT) > 100:
        config.estado.contexto_chat = CONTEXTO_CHAT[-100:]


# =====================================================================
# PROCESAMIENTO DE ARCHIVOS ADJUNTOS (SIEMPRE A CONTEXTO)
# =====================================================================
def cargar_adjuntos_en_contexto(rutas_archivos, ui_callback=None):
    import config
    if isinstance(rutas_archivos, str):
        rutas_archivos = [rutas_archivos]
    
    if ui_callback:
        ui_callback("⚙️ Sistema", f"📄 Leyendo {len(rutas_archivos)} archivo(s)...", "#80868B")
    
    archivos_procesados = []
    contenido_volatil_acumulado = ""
    
    for ruta in rutas_archivos:
        nombre_archivo = os.path.basename(ruta)
        carpeta_padre = os.path.basename(os.path.dirname(ruta)) or "Proyecto_General"
        identificador_unico = f"{carpeta_padre}/{nombre_archivo}"
        contenido = leer_contenido_archivo(ruta)
        
        if contenido == "CODIGO_ERROR_NO_ENCONTRADO" or contenido.startswith("CODIGO_ERROR_LECTURA:"):
            if ui_callback:
                ui_callback("⚙️ Sistema", f"❌ No se pudo leer: {identificador_unico}", "#FF4500")
            continue
        
        archivos_procesados.append({"nombre": identificador_unico, "contenido": contenido})
        contenido_volatil_acumulado += f"\n\n--- INICIO: {identificador_unico} ---\n{contenido}\n--- FIN: {identificador_unico} ---"

    if not archivos_procesados:
        if ui_callback:
            ui_callback("⚙️ Sistema", "❌ No se pudo leer ningún archivo.", "#FF4500")
        return

    config.estado.documento_volatil = contenido_volatil_acumulado

    try:
        resumen = genai.GenerativeModel("gemini-flash-lite-latest").generate_content(
            f"Resume en 2 líneas el contenido de estos archivos:\n\n{contenido_volatil_acumulado[:8000]}"
        ).text.strip()
    except:
        resumen = "Documentos cargados en contexto."

    nombres_str = ", ".join([f"'{a['nombre']}'" for a in archivos_procesados])
    msg = f"✅ {len(archivos_procesados)} archivo(s) cargado(s) en contexto:\n{nombres_str}\n\n{resumen}"
    
    if ui_callback:
        ui_callback("⚙️ Sistema", msg, "#86EFAC")
    
    config.estado.contexto_chat.append({'role': 'user', 'parts': [f"[SISTEMA] Archivos cargados en contexto: {nombres_str}"]})