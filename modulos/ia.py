import os
import datetime
import winsound
import re
import difflib
from google import genai
from google.genai import types
from openai import OpenAI
import config

# ─── Importación de logger ──────────────────────────────────────────────
from modulos.logger import logger

# ─── Importación del gestor de skills ────────────────────────────────────
from modulos.skills.gestor_skills import gestor

# Importación de llaves
from config import GEMINI_API_KEY, DEEPSEEK_API_KEY

from modulos.archivos import eliminar_elemento, leer_contenido_archivo
from modulos.sistema import obtener_ventanas_activas, obtener_estado_pc, escanear_hardware_completo, explorar_directorio
from modulos.busqueda import buscar_en_internet
from modulos.audio_custom import hablar_no_bloqueante, encolar_texto_para_hablar, detener_voz
from modulos.vision import capturar_pantalla
from modulos.git_bot import sincronizar_proyecto_git, ejecutar_comando_git_libre

# ─── OPTIMIZACIÓN: importar memoria directo, sin pasar por MCP ──────────
from modulos.memoria import (
    guardar_recuerdo,
    buscar_contexto,
    iniciar_busqueda_anticipada,
    obtener_resultado_anticipado
)
from modulos.cliente_mcp import cliente_sistema

from modulos.prompts import (
    obtener_prompt_planificador,
    obtener_prompt_programador,
    obtener_prompt_general,
    obtener_prompt_programador_unificado
)

# ─── Perfil de usuario persistente ─────────────────────────────────────
from modulos.perfil_usuario import (
    texto_perfil_para_prompt,
    extraer_hechos_de_sesion,
    guardar_perfil,
    cargar_perfil
)

# ─── Usar la instancia global del gestor ────────────────────────────────
gestor_skills = gestor

# =====================================================================
# INICIALIZACIÓN DE CLIENTES IA (NUEVO SDK google-genai)
# =====================================================================
cliente_genai = genai.Client(api_key=GEMINI_API_KEY)
cliente_deepseek = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

# =====================================================================
# HERRAMIENTAS NATIVAS (GEMINI)
# OPTIMIZACIÓN: buscar/guardar en bóveda ahora van DIRECTO a memoria.py
# sin spawn de proceso externo — latencia reducida de 3-5s a <500ms
# =====================================================================
def mcp_estado_pc():
    """
    Obtiene el estado en tiempo real del PC: uso de CPU en porcentaje,
    uso y cantidad de RAM, temperatura actual de la GPU en °C, y VRAM usada.
    Usar cuando el usuario pregunte por temperatura de GPU, uso de CPU,
    uso de RAM, o rendimiento actual del sistema.
    """
    return obtener_estado_pc()

def mcp_hardware_pc():
    """
    Obtiene información estática del hardware instalado: modelo exacto del
    procesador (CPU), modelo de la tarjeta gráfica (GPU) y placa madre.
    Usar cuando el usuario pregunte QUÉ componentes tiene instalados,
    NO para temperatura ni uso en tiempo real.
    """
    hw = escanear_hardware_completo()
    return f"CPU: {hw['cpu']} | GPU: {hw['gpu']} | Placa madre: {hw['motherboard']}"

def mcp_buscar_en_boveda(consulta: str):
    """
    Busca recuerdos o información guardada previamente en la memoria a largo plazo (bóveda).
    OPTIMIZADO: llama directo a ChromaDB sin proceso MCP intermedio.
    """
    try:
        # Intentar usar resultado anticipado si está disponible
        resultados = obtener_resultado_anticipado(consulta)
        if resultados:
            return f"Recuerdos recuperados de la bóveda:\n{resultados[0]}"
        return "No encontré nada relacionado a ese tema en la bóveda de memoria."
    except Exception as e:
        logger.exception("Error buscando en bóveda directo")
        # Fallback al servidor MCP si falla el acceso directo
        return cliente_sistema.ejecutar("buscar_en_boveda", {"consulta": consulta})

def mcp_guardar_en_boveda(dato: str):
    """
    Guarda un dato en la memoria a largo plazo (bóveda).
    USAR ÚNICAMENTE si el usuario lo pide EXPLÍCITAMENTE con frases como
    "guardá esto", "acordate de...", "no te olvides que...".
    Si el usuario menciona algo de pasada, sin pedir que se recuerde,
    NO llamar a esta herramienta bajo ninguna circunstancia — existe un
    sistema separado (extracción pasiva de perfil) que se encarga de eso
    automáticamente, sin intervención del modelo en tiempo real.
    """
    try:
        exito = guardar_recuerdo(texto_a_guardar=dato, etiqueta_tema="Memoria_IA")
        if exito:
            return "¡Dato guardado exitosamente en la bóveda permanente!"
        return "Error al guardar el dato en la bóveda."
    except Exception as e:
        logger.exception("Error guardando en bóveda directo")
        # Fallback al servidor MCP si falla el acceso directo
        return cliente_sistema.ejecutar("guardar_en_boveda", {"dato": dato})

def mcp_explorar_ruta(ruta: str):
    """
    Lista y muestra el contenido (archivos y carpetas) de un directorio en el chat,
    SIN abrir ninguna ventana en Windows.
    Usar SOLO cuando el usuario pida VER o LISTAR el contenido de una carpeta.
    NO usar si el usuario dice "abrí", "abrir", "mostrame la carpeta" —
    en esos casos se debe usar el comando de texto: abrir: ruta_completa
    """
    return explorar_directorio(ruta)

def mcp_leer_documento(ruta: str):
    """
    Lee y devuelve el contenido completo de un archivo de texto del sistema.
    Usar cuando el usuario pida leer, ver o abrir el contenido de un archivo específico.
    """
    contenido = leer_contenido_archivo(ruta)
    if contenido.startswith("ERROR:"):
        return f"Error: No se pudo encontrar o abrir el archivo '{ruta}'. Detalle: {contenido}"
    return f"Contenido del archivo:\n{contenido}"

lista_herramientas_mcp = [
    mcp_estado_pc, mcp_hardware_pc, mcp_buscar_en_boveda,
    mcp_explorar_ruta, mcp_leer_documento
]

# =====================================================================
# HELPER: STREAMING DE VOZ PARALELO AL STREAMING DE IA
# =====================================================================
_PATRON_CORTE_VOZ = re.compile(r'(?<=[.!?])\s+')
_MIN_CHARS_CHUNK_VOZ = 80
_PATRON_COMANDOS_VOZ = re.compile(
    r'^(audio:|buscar:|abrir:|cerrar:|mover:|guardar_archivo:|leer_archivo:|'
    r'reemplazar_bloque:|editar_archivo:|crear_carpeta:|github:|escanear_proyecto:|'
    r'mcp_\w+)[^\n]*$',
    re.MULTILINE | re.IGNORECASE
)

def _limpiar_para_voz(texto: str) -> str:
    return _PATRON_COMANDOS_VOZ.sub('', texto).strip()

def _procesar_buffer_voz(buffer: str, forzar: bool = False) -> str:
    buffer_limpio = _limpiar_para_voz(buffer)
    while True:
        match = _PATRON_CORTE_VOZ.search(buffer_limpio)
        if match and len(buffer_limpio[:match.end()].strip()) >= _MIN_CHARS_CHUNK_VOZ:
            fragmento = buffer_limpio[:match.end()].strip()
            encolar_texto_para_hablar(fragmento)
            corte = match.end()
            buffer_limpio = buffer_limpio[corte:]
            buffer = buffer[corte:] if corte < len(buffer) else ""
        else:
            break
    if forzar and buffer_limpio.strip():
        encolar_texto_para_hablar(buffer_limpio.strip())
        buffer = ""
    return buffer

# =====================================================================
# CONFIRMACIONES NATIVAS (sin juez IA)
# =====================================================================
_PALABRAS_CONFIRMACION = {
    "si", "sí", "dale", "ok", "okay", "confirmar", "confirmo",
    "confirmado", "procede", "adelante", "hacelo", "ejecuta",
    "autorizo", "autorizado", "yes", "yep", "por supuesto",
    "claro", "obvio", "va", "está bien", "de acuerdo"
}
_PALABRAS_CANCELACION = {
    "no", "nope", "cancelar", "cancela", "cancelado", "abortar",
    "abortado", "para", "detener", "detené", "stop", "espera",
    "olvidalo", "olvidá", "dejalo", "dejá", "mejor no"
}

def _evaluar_confirmacion_local(respuesta_usuario: str) -> str:
    texto = respuesta_usuario.lower().strip()
    if texto in _PALABRAS_CONFIRMACION:
        return "CONFIRMADO"
    if texto in _PALABRAS_CANCELACION:
        return "CANCELADO"
    for palabra in _PALABRAS_CONFIRMACION:
        if palabra in texto:
            return "CONFIRMADO"
    for palabra in _PALABRAS_CANCELACION:
        if palabra in texto:
            return "CANCELADO"
    logger.warning(f"Respuesta de confirmación ambigua: '{respuesta_usuario}' → CANCELADO")
    return "CANCELADO"

# =====================================================================
# HELPER: construir lista de contents para el nuevo SDK
# FIX: en el nuevo SDK, PIL Images se pasan directamente como contenido,
# NO se envuelven en Part.from_image() (que no existe).
# =====================================================================
def _convertir_contexto_a_contents(contexto_chat):
    """
    Convierte el formato de contexto_chat (lista de dicts con 'role' y 'parts')
    al formato que espera el nuevo SDK google-genai.
    Retorna una lista de types.Content (para mensajes de historial) o
    una lista plana de Part/str/PIL.Image (para el mensaje del usuario actual).
    IMPORTANTE: PIL Images se pasan DIRECTAMENTE sin wrapper, el SDK las maneja.
    """
    from PIL import Image
    contents = []
    for msg in contexto_chat:
        role = msg.get('role', 'user')
        parts_raw = msg.get('parts', [])
        parts = []
        for part in parts_raw:
            if isinstance(part, str):
                parts.append(types.Part.from_text(text=part))
            elif isinstance(part, Image.Image):
                # PIL Image se pasa directamente como contenido,
                # el SDK google-genai maneja Image nativamente
                parts.append(part)
            else:
                parts.append(types.Part.from_text(text=str(part)))
        contents.append(types.Content(role=role, parts=parts))
    return contents

def _extraer_funciones_de_respuesta(response):
    """
    Extrae function_calls de una respuesta de streaming del nuevo SDK.
    """
    try:
        if hasattr(response, 'function_calls') and response.function_calls:
            return response.function_calls
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'content') and candidate.content:
                for part in (candidate.content.parts or []):
                    if hasattr(part, 'function_call') and part.function_call:
                        return [part.function_call]
    except Exception:
        pass
    return None

# =====================================================================
# ENRUTADOR PRINCIPAL
# =====================================================================
def enviar_a_gemini(texto_usuario, modo_voz=False, ui_callback=None):
    """Enrutador Universal y traductor de acciones con soporte para Skills."""
    import config
    CONTEXTO_CHAT = config.estado.contexto_chat
    DOCUMENTO_VOLATIL = config.estado.documento_volatil
    PENDIENTE_DE_BORRADO = config.estado.pendiente_de_borrado
    PENDIENTE_DE_GIT = config.estado.pendiente_de_git
    WORKSPACE_ACTUAL = config.estado.workspace_actual
    SNAPSHOT_ACTUAL = config.estado.snapshot_actual
    MODO_ACTUAL = config.estado.modo_actual
    ARCHIVOS_EN_MEMORIA = config.estado.archivos_en_memoria

    config.RUTA_WORKSPACE_ACTUAL = WORKSPACE_ACTUAL
    texto_usuario_lower = texto_usuario.lower().strip()

    # ─── LIMPIAR CONTEXTO ────────────────────────────────────────────────
    _FRASES_LIMPIAR = {
        "limpiar memoria", "olvidar contexto", "limpiar contexto",
        "resetear contexto", "reset contexto", "borrar contexto",
        "limpiar chat", "borrar chat", "nueva conversacion",
        "nueva conversación", "empezar de nuevo", "reiniciar contexto",
        "olvidar todo", "limpia el contexto", "limpia la memoria",
        "borra el contexto", "reseteá el contexto"
    }
    if texto_usuario_lower in _FRASES_LIMPIAR or any(
        frase in texto_usuario_lower for frase in _FRASES_LIMPIAR
    ):
        config.estado.limpiar_memoria()
        if ui_callback:
            ui_callback("⚙️ Sistema", "🧹 Contexto limpiado. Argus empieza desde cero.", "#80868B")
        if modo_voz:
            hablar_no_bloqueante("Contexto limpiado, empezamos de nuevo.")
        return

    # =================================================================
    # INTERCEPTOR DE ADJUNTOS
    # =================================================================
    if "[adjunto:" in texto_usuario.lower():
        rutas_extraidas = re.findall(r'\[adjunto:\s*(.*?)\]', texto_usuario, re.IGNORECASE)
        if rutas_extraidas:
            texto_usuario = re.sub(r'\[adjunto:\s*.*?\]', '', texto_usuario, flags=re.IGNORECASE).strip()
            cargar_adjuntos_en_contexto(rutas_extraidas, ui_callback)
            if not texto_usuario:
                return

    # =================================================================
    # ESCUDOS DE SEGURIDAD — CONFIRMACIONES NATIVAS
    # =================================================================
    if PENDIENTE_DE_BORRADO:
        tarea_borrado = PENDIENTE_DE_BORRADO
        config.estado.pendiente_de_borrado = ""
        logger.info(f"Evaluando confirmación de borrado (local): {tarea_borrado}")
        decision_borrado = _evaluar_confirmacion_local(texto_usuario)
        if "CONFIRMADO" in decision_borrado:
            resultado = eliminar_elemento(tarea_borrado)
            msg = f"Protocolo autorizado. {resultado}"
        else:
            msg = "Protocolo abortado. Archivos a salvo."
        if ui_callback:
            ui_callback("🤖 Argus", msg, "#FF4500" if "abortado" in msg else "#00E5FF")
        if modo_voz:
            hablar_no_bloqueante(msg)
        CONTEXTO_CHAT.extend([
            {'role': 'user', 'parts': [texto_usuario]},
            {'role': 'model', 'parts': [msg]}
        ])
        return

    if PENDIENTE_DE_GIT:
        tarea_git = PENDIENTE_DE_GIT
        config.estado.pendiente_de_git = None
        logger.info(f"Evaluando confirmación de Git (local): {tarea_git}")
        decision_git = _evaluar_confirmacion_local(texto_usuario)
        if "CONFIRMADO" in decision_git:
            if ui_callback:
                ui_callback("⚙️ Sistema", "Iniciando operación en GitHub...", "#80868B")
            accion = tarea_git.get("accion")
            ruta = tarea_git.get("ruta")
            url_custom = tarea_git.get("url_custom")
            try:
                if accion == "github_reset":
                    resultado = sincronizar_proyecto_git(ruta, reset_remote=True, url_custom=url_custom)
                elif accion == "git_libre":
                    resultado = ejecutar_comando_git_libre(ruta, url_custom)
                else:
                    resultado = sincronizar_proyecto_git(ruta)
                msg = f"Operación Git completada:\n{resultado}"
            except Exception as e:
                logger.exception("Error en operación Git")
                msg = f"❌ Error en Git: {str(e)[:200]}"
        else:
            msg = "Operación en GitHub cancelada de forma segura."
        if ui_callback:
            ui_callback("🤖 Argus", msg, "#FF4500" if "cancelada" in msg else "#00E5FF")
        if modo_voz:
            hablar_no_bloqueante("Operación finalizada." if "completada" in msg else "Operación cancelada.")
        CONTEXTO_CHAT.extend([
            {'role': 'user', 'parts': [texto_usuario]},
            {'role': 'model', 'parts': [msg]}
        ])
        return

    # ─── ESCUDO DE CONFIRMACIÓN: GUARDAR EN BÓVEDA ────────────────────
    PENDIENTE_DE_BOVEDA = config.estado.pendiente_de_boveda
    if PENDIENTE_DE_BOVEDA:
        dato_boveda = PENDIENTE_DE_BOVEDA
        config.estado.pendiente_de_boveda = ""
        logger.info(f"Evaluando confirmación de guardado en bóveda (local): {dato_boveda[:60]}...")
        decision_boveda = _evaluar_confirmacion_local(texto_usuario)
        if "CONFIRMADO" in decision_boveda:
            exito = guardar_recuerdo(texto_a_guardar=dato_boveda, etiqueta_tema="Memoria_IA")
            if exito:
                msg = f"✅ Dato guardado en la bóveda: {dato_boveda[:120]}"
            else:
                msg = "❌ Error al guardar el dato en la bóveda."
        else:
            msg = "⏭️ Guardado en bóveda cancelado."
        if ui_callback:
            ui_callback("🤖 Argus", msg, "#00E5FF" if "cancelado" in msg else "#86EFAC")
        if modo_voz:
            hablar_no_bloqueante("Listo." if "cancelado" not in msg else "Cancelado.")
        CONTEXTO_CHAT.extend([
            {'role': 'user', 'parts': [texto_usuario]},
            {'role': 'model', 'parts': [msg]}
        ])
        return

    # =================================================================
    # TRADUCTOR INSTANTÁNEO DE INTENCIONES NATURALES
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
    error_ocurrido = False
    skill_activa = False

    if comando_directo:
        respuesta_ia = comando_directo
        if ui_callback:
            ui_callback("🤖 Argus", "Entendido, ejecutando acción solicitada...", "#A8C7FA", nueva_linea=True)
        if modo_voz:
            hablar_no_bloqueante("Entendido, ejecutando acción.")
    else:
        logger.info(f"PENSANDO ({MODO_ACTUAL.upper()})...")

        MODO_ACTUAL = config.estado.modo_actual
        if MODO_ACTUAL == "general":
            iniciar_busqueda_anticipada(texto_usuario)

        try:
            fecha_hoy = datetime.datetime.now().strftime("%A, %d de %B de %Y")
            ventanas_abiertas = obtener_ventanas_activas()

            from modulos.perfil_usuario import texto_perfil_para_prompt
            texto_perfil = texto_perfil_para_prompt()
            texto_workspace = f"[WORKSPACE ANCLADO]: {WORKSPACE_ACTUAL}\n" if WORKSPACE_ACTUAL else ""
            texto_snapshot = f"[ESTADO DEL PROYECTO]:\n{SNAPSHOT_ACTUAL}\n\n" if SNAPSHOT_ACTUAL else ""
            texto_doc_volatil = f"[DOCUMENTOS EN MEMORIA]:\n{DOCUMENTO_VOLATIL}\n\n" if DOCUMENTO_VOLATIL else ""

            if MODO_ACTUAL in ["programador", "planificador"]:
                contexto_sistema = obtener_prompt_programador_unificado(
                    texto_workspace, texto_snapshot, texto_doc_volatil, texto_perfil
                )
                modelo_activo = "deepseek-reasoner"
            else:
                ruta_home = os.path.expanduser("~")
                contexto_sistema = obtener_prompt_general(
                    fecha_hoy, ruta_home, ventanas_abiertas,
                    texto_workspace, texto_snapshot, texto_doc_volatil, texto_perfil
                )
                modelo_activo = "gemini"

            # ─── INYECCIÓN DE SKILLS ──────────────────────────────────────────
            skill_info = gestor_skills.obtener_skill_relevante(texto_usuario)
            if skill_info:
                nombre_skill, instrucciones = skill_info
                skill_activa = True
                logger.info(f"🧠 Skill activada: {nombre_skill}")
                contexto_sistema += f"\n\n[SKILL ACTIVADA: {nombre_skill}]\n\n"
                contexto_sistema += instrucciones
                contexto_sistema += "\n\n[FIN DE SKILL]\n"
                if ui_callback:
                    ui_callback("⚙️ Sistema", f"🧠 Skill activada: {nombre_skill}", "#A8C7FA")

            logger.debug(f"Modelo activo: {modelo_activo}")
            print(f"\n🤖 Argus dice:\n---")

            # ─── GEMINI (NUEVO SDK google-genai) ──────────────────────────────
            if modelo_activo == "gemini":
                # FIX: En el SDK google-genai v2, las PIL Images se pasan
                # directamente como elementos de la lista contents, NO envueltas
                # en Part ni en Content aparte.
                gemini_config = types.GenerateContentConfig(
                    system_instruction=contexto_sistema,
                    temperature=0.1,
                    max_output_tokens=8192,
                    safety_settings=[
                        types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                        types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                        types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                        types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                        types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_CIVIC_INTEGRITY, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                    ]
                )
                if not skill_activa:
                    gemini_config.tools = lista_herramientas_mcp

                # Convertir historial al formato del nuevo SDK
                mensajes_para_gemini = _convertir_contexto_a_contents(CONTEXTO_CHAT)

                # Construir partes del mensaje del usuario
                partes_usuario = [types.Part.from_text(text=texto_usuario)]
                from PIL import Image as PIL_Image

                verbos_vision = ["captura", "capturá", "capturar", "mirar", "ves"]
                objetivos_vision = ["pantalla", "monitor", "1", "2", "uno", "dos", "la 1", "el 1", "la 2", "el 2"]
                if any(v in texto_usuario_lower for v in verbos_vision) and any(o in texto_usuario_lower for o in objetivos_vision):
                    if ui_callback:
                        ui_callback("⚙️ Sistema", "📸 Capturando pantalla...", "#80868B")
                    winsound.Beep(1500, 100)
                    num_pantalla = 2 if any(p in texto_usuario_lower for p in ["1", "uno", "la 1", "el 1"]) else 1
                    img = capturar_pantalla(num_pantalla)
                    if img:
                        # En el nuevo SDK, PIL Images se pasan directamente
                        partes_usuario.append(img)

                mensajes_para_gemini.append(types.Content(role='user', parts=partes_usuario))

                try:
                    response_stream = cliente_genai.models.generate_content_stream(
                        model="gemini-3.1-flash-lite",
                        contents=mensajes_para_gemini,
                        config=gemini_config
                    )
                except genai.errors.ClientError as e:
                    err_str = str(e)
                    logger.exception(f"Error de cliente Gemini: {err_str[:200]}")
                    if "blocked" in err_str.lower() or "safety" in err_str.lower():
                        if ui_callback:
                            ui_callback("⚙️ Sistema", "⚠️ Mensaje bloqueado por filtros de seguridad.", "#FF4500")
                    elif "429" in err_str or "ResourceExhausted" in err_str:
                        if ui_callback:
                            ui_callback("⚙️ Sistema", "⚠️ Límite de tokens alcanzado. Limpiá el contexto.", "#FF4500")
                    elif "401" in err_str or "Unauthenticated" in err_str:
                        if ui_callback:
                            ui_callback("⚙️ Sistema", "❌ Error de autenticación. Verificá tu API Key.", "#FF4500")
                    elif "403" in err_str or "PermissionDenied" in err_str:
                        if ui_callback:
                            ui_callback("⚙️ Sistema", "❌ Permiso denegado. Verificá tu API Key.", "#FF4500")
                    else:
                        if ui_callback:
                            ui_callback("⚙️ Sistema", f"❌ Error en Gemini: {err_str[:100]}", "#FF4500")
                    error_ocurrido = True
                    return
                except Exception as e:
                    err_str = str(e)
                    if "ResourceExhausted" in err_str or "429" in err_str:
                        if ui_callback:
                            ui_callback("⚙️ Sistema", "⚠️ Límite de tokens alcanzado. Limpiá el contexto.", "#FF4500")
                    elif "Unauthenticated" in err_str or "401" in err_str:
                        if ui_callback:
                            ui_callback("⚙️ Sistema", "❌ Error de autenticación. Verificá tu API Key.", "#FF4500")
                    elif "PermissionDenied" in err_str or "403" in err_str:
                        if ui_callback:
                            ui_callback("⚙️ Sistema", "❌ Permiso denegado. Verificá tu API Key.", "#FF4500")
                    else:
                        if ui_callback:
                            ui_callback("⚙️ Sistema", f"❌ Error al iniciar generación: {err_str[:100]}", "#FF4500")
                    logger.exception("Error al iniciar generación en Gemini")
                    error_ocurrido = True
                    return

                if ui_callback:
                    ui_callback("🤖 Argus", "", "#A8C7FA", nueva_linea=False)

                buffer_voz = ""

                try:
                    for chunk in response_stream:
                        try:
                            # DEBUG: Loggear finish_reason cuando sea SAFETY o RECITATION
                            if hasattr(chunk, 'candidates') and chunk.candidates:
                                candidate = chunk.candidates[0]
                                if hasattr(candidate, 'finish_reason') and candidate.finish_reason:
                                    fr_name = candidate.finish_reason.name if hasattr(candidate.finish_reason, 'name') else str(candidate.finish_reason)
                                    fr_val = candidate.finish_reason.value if hasattr(candidate.finish_reason, 'value') else str(candidate.finish_reason)
                                    # SAFETY=2, RECITATION=4, OTHER=5 son los problemáticos
                                    if fr_val in (2, 4, 5):
                                        logger.warning(f"⚠️ Gemini finish_reason={fr_name} (SAFETY=2, RECITATION=4, OTHER=5)")
                                        if ui_callback:
                                            ui_callback("⚙️ Sistema", f"⚠️ Gemini finalizó con {fr_name}", "#FFA500")
                            func_calls = _extraer_funciones_de_respuesta(chunk)
                            if func_calls:
                                for fc in func_calls:
                                    usaste_mcp = True
                                    n_func = fc.name
                                    if ui_callback:
                                        ui_callback("⚙️ Sistema", f"Consultando: {n_func}...", "#80868B")
                                    args = dict(fc.args) if fc.args else {}
                                    try:
                                        if n_func == "mcp_estado_pc":
                                            resultado_mcp = mcp_estado_pc()
                                        elif n_func == "mcp_hardware_pc":
                                            resultado_mcp = mcp_hardware_pc()
                                        elif n_func == "mcp_buscar_en_boveda":
                                            resultado_mcp = mcp_buscar_en_boveda(args.get("consulta", ""))
                                        elif n_func == "mcp_guardar_en_boveda":
                                            resultado_mcp = mcp_guardar_en_boveda(args.get("dato", ""))
                                        elif n_func == "mcp_explorar_ruta":
                                            resultado_mcp = mcp_explorar_ruta(args.get("ruta", ""))
                                        elif n_func == "mcp_leer_documento":
                                            resultado_mcp = mcp_leer_documento(args.get("ruta", ""))

                                        if resultado_mcp and "TIMEOUT" not in str(resultado_mcp):
                                            if ui_callback:
                                                ui_callback("⚙️ Sistema", f"✅ Dato obtenido: {str(resultado_mcp)[:120]}...", "#80868B")
                                        elif resultado_mcp and "TIMEOUT" in str(resultado_mcp):
                                            if ui_callback:
                                                ui_callback("⚙️ Sistema", "⚠️ Timeout en herramienta MCP.", "#FFA500")
                                    except Exception as e:
                                        logger.exception(f"Error ejecutando herramienta {n_func}")
                                        if ui_callback:
                                            ui_callback("⚙️ Sistema", f"❌ Error en {n_func}: {str(e)[:80]}", "#FF4500")
                            # Extraer texto del chunk: probar varias ubicaciones posibles
                            texto_chunk = None
                            if hasattr(chunk, 'text') and chunk.text:
                                texto_chunk = chunk.text
                            elif (hasattr(chunk, 'candidates') and chunk.candidates 
                                  and hasattr(chunk.candidates[0], 'content') and chunk.candidates[0].content
                                  and hasattr(chunk.candidates[0].content, 'parts') and chunk.candidates[0].content.parts):
                                for part in chunk.candidates[0].content.parts:
                                    if hasattr(part, 'text') and part.text:
                                        texto_chunk = (texto_chunk or "") + part.text
                            if texto_chunk:
                                print(texto_chunk, end='', flush=True)
                                respuesta_ia += texto_chunk
                                if ui_callback:
                                    ui_callback("", texto_chunk, "#E8EAED", nueva_linea=False)
                                if modo_voz and not usaste_mcp:
                                    buffer_voz += texto_chunk
                                    buffer_voz = _procesar_buffer_voz(buffer_voz, forzar=False)
                        except Exception as e:
                            logger.exception("Error procesando chunk de Gemini")
                            if ui_callback:
                                ui_callback("⚙️ Sistema", f"❌ Error en streaming: {str(e)[:80]}", "#FF4500")
                            break
                except Exception as e:
                    logger.exception("Error en el bucle de streaming de Gemini")
                    if ui_callback:
                        ui_callback("⚙️ Sistema", f"❌ Error en el streaming: {str(e)[:80]}", "#FF4500")
                    error_ocurrido = True
                finally:
                    if modo_voz and buffer_voz.strip() and not usaste_mcp:
                        _procesar_buffer_voz(buffer_voz, forzar=True)

                # ─── FALLBACK POR RESPUESTA VACÍA (Safety/PII blocking) ─────
                if not respuesta_ia and not error_ocurrido and not usaste_mcp:
                    logger.warning("⚠️ Respuesta vacía — probable bloqueo por Safety/PII. Fallback a DeepSeek.")
                    if ui_callback:
                        ui_callback("⚙️ Sistema", "⚠️ La API bloqueó esta respuesta. Usando respaldo DeepSeek...", "#FFA500")
                    # Reintentar con DeepSeek como fallback
                    mensajes_ds = [{"role": "system", "content": contexto_sistema}]
                    for msg in CONTEXTO_CHAT:
                        rol_ds = "assistant" if msg['role'] == "model" else "user"
                        texto_historico = "".join([p for p in msg['parts'] if isinstance(p, str)])
                        mensajes_ds.append({"role": rol_ds, "content": texto_historico})
                    mensajes_ds.append({"role": "user", "content": texto_usuario})
                    try:
                        response = cliente_deepseek.chat.completions.create(
                            model="deepseek-chat", messages=mensajes_ds, stream=True
                        )
                        if ui_callback:
                            ui_callback("🤖 Argus (DeepSeek)", "", "#A8C7FA", nueva_linea=False)
                        for chunk in response:
                            delta = chunk.choices[0].delta
                            if getattr(delta, 'content', None):
                                texto_chunk = delta.content
                                print(texto_chunk, end='', flush=True)
                                respuesta_ia += texto_chunk
                                if ui_callback:
                                    ui_callback("", texto_chunk, "#E8EAED", nueva_linea=False)
                    except Exception as e:
                        logger.exception("Error en fallback DeepSeek")
                        if ui_callback:
                            ui_callback("⚙️ Sistema", f"❌ Fallback DeepSeek falló: {str(e)[:100]}", "#FF4500")
                        respuesta_ia = "⚠️ Lo siento, la API bloqueó esta respuesta por políticas de seguridad."

                # ─── MCP SEGUNDA RONDA ────────────────────────────────────────
                if usaste_mcp and not error_ocurrido and not skill_activa:
                    try:
                        if not resultado_mcp or "TIMEOUT" in str(resultado_mcp):
                            if ui_callback:
                                ui_callback("⚙️ Sistema", "⚠️ No se obtuvo dato. Verificá conexión.", "#FFA500")
                        else:
                            mensajes_para_gemini.append(types.Content(role='model', parts=[types.Part.from_text(text='Obteniendo datos...')]))
                            mensajes_para_gemini.append(types.Content(role='user', parts=[types.Part.from_text(
                                text=f"[DATO OBTENIDO]: {resultado_mcp}\n\n"
                                    "Respondé al usuario de forma natural y directa con este dato. "
                                    "No inventes valores que no estén en el dato. "
                                    "Si falta algún dato, decílo explícitamente."
                            )]))

                            config_segunda_ronda = types.GenerateContentConfig(
                                system_instruction=contexto_sistema,
                                temperature=0.1,
                                max_output_tokens=8192,
                                safety_settings=[
                                    types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                                    types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                                    types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                                    types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                                    types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_CIVIC_INTEGRITY, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                                ]
                            )
                            response_2 = cliente_genai.models.generate_content_stream(
                                model="gemini-3.1-flash-lite",
                                contents=mensajes_para_gemini,
                                config=config_segunda_ronda
                            )
                            if ui_callback:
                                ui_callback("🤖 Argus", "", "#A8C7FA", nueva_linea=True)
                            buffer_voz_2 = ""
                            for chunk_2 in response_2:
                                try:
                                    if hasattr(chunk_2, 'text') and chunk_2.text:
                                        texto_chunk = chunk_2.text
                                        print(texto_chunk, end='', flush=True)
                                        respuesta_ia += texto_chunk
                                        if ui_callback:
                                            ui_callback("", texto_chunk, "#E8EAED", nueva_linea=False)
                                        if modo_voz:
                                            buffer_voz_2 += texto_chunk
                                            buffer_voz_2 = _procesar_buffer_voz(buffer_voz_2, forzar=False)
                                except Exception as e:
                                    logger.exception("Error procesando chunk MCP ronda 2")
                                    if ui_callback:
                                        ui_callback("⚙️ Sistema", f"❌ Error en respuesta MCP: {str(e)[:80]}", "#FF4500")
                                    break
                            # ─── FALLBACK POR RESPUESTA VACÍA EN MCP RONDA 2 ─────
                            if not respuesta_ia and not error_ocurrido:
                                logger.warning("⚠️ Respuesta vacía en MCP ronda 2 — Safety/PII blocking.")
                                if ui_callback:
                                    ui_callback("⚙️ Sistema", "⚠️ Datos obtenidos pero la API bloqueó la respuesta.", "#FFA500")
                                respuesta_ia = "⚠️ Obtuve la información solicitada, pero la API bloqueó la respuesta por políticas de seguridad."
                            if ui_callback:
                                ui_callback("", "", "#E8EAED", nueva_linea=True)
                            if modo_voz and buffer_voz_2.strip():
                                _procesar_buffer_voz(buffer_voz_2, forzar=True)
                    except Exception as e:
                        logger.exception("Error en generación MCP ronda 2")
                        if ui_callback:
                            ui_callback("⚙️ Sistema", f"❌ Error en generación MCP: {str(e)[:80]}", "#FF4500")
                        error_ocurrido = True

            # ─── DEEPSEEK ──────────────────────────────────────────────────────
            else:
                mensajes_ds = [{"role": "system", "content": contexto_sistema}]
                for msg in CONTEXTO_CHAT:
                    rol_ds = "assistant" if msg['role'] == "model" else "user"
                    texto_historico = "".join([p for p in msg['parts'] if isinstance(p, str)])
                    mensajes_ds.append({"role": rol_ds, "content": texto_historico})
                mensajes_ds.append({"role": "user", "content": texto_usuario})

                if ui_callback:
                    ui_callback("🤖 Argus", "", "#A8C7FA", nueva_linea=False)

                try:
                    parametros_api = {"model": modelo_activo, "messages": mensajes_ds, "stream": True}
                    response = cliente_deepseek.chat.completions.create(**parametros_api)
                except Exception as e:
                    err_str = str(e)
                    if "RateLimitError" in err_str or "429" in err_str:
                        if ui_callback:
                            ui_callback("⚙️ Sistema", "⚠️ Rate limit DeepSeek. Esperá un momento.", "#FFA500")
                    elif "AuthenticationError" in err_str or "401" in err_str:
                        if ui_callback:
                            ui_callback("⚙️ Sistema", "❌ Error de autenticación DeepSeek.", "#FF4500")
                    else:
                        if ui_callback:
                            ui_callback("⚙️ Sistema", f"❌ Error DeepSeek: {err_str[:100]}", "#FF4500")
                    logger.exception("Error al iniciar generación en DeepSeek")
                    error_ocurrido = True
                    return

                buffer_voz_ds = ""
                try:
                    for chunk in response:
                        try:
                            delta = chunk.choices[0].delta
                            if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                                print(delta.reasoning_content, end='', flush=True)
                            if getattr(delta, 'content', None):
                                texto_chunk = delta.content
                                print(texto_chunk, end='', flush=True)
                                respuesta_ia += texto_chunk
                                if ui_callback:
                                    ui_callback("", texto_chunk, "#E8EAED", nueva_linea=False)
                                if modo_voz:
                                    buffer_voz_ds += texto_chunk
                                    buffer_voz_ds = _procesar_buffer_voz(buffer_voz_ds, forzar=False)
                        except Exception as e:
                            logger.exception("Error procesando chunk de DeepSeek")
                            if ui_callback:
                                ui_callback("⚙️ Sistema", f"❌ Error en streaming: {str(e)[:80]}", "#FF4500")
                            break
                except Exception as e:
                    logger.exception("Error en el bucle de streaming de DeepSeek")
                    if ui_callback:
                        ui_callback("⚙️ Sistema", f"❌ Error en el streaming: {str(e)[:80]}", "#FF4500")
                    error_ocurrido = True
                finally:
                    if modo_voz and buffer_voz_ds.strip():
                        _procesar_buffer_voz(buffer_voz_ds, forzar=True)

            print("\n---")
            if ui_callback:
                ui_callback("", "", "#E8EAED", nueva_linea=True)

        except ConnectionError as e:
            logger.exception("Error de conexión")
            if ui_callback:
                ui_callback("⚙️ Sistema", "❌ Error de conexión. Revisá tu internet.", "#FF4500")
            error_ocurrido = True
        except TimeoutError as e:
            logger.exception("Timeout")
            if ui_callback:
                ui_callback("⚙️ Sistema", "⏱️ Timeout. La respuesta está tardando demasiado.", "#FFA500")
            error_ocurrido = True
        except Exception as e:
            logger.exception("Error crítico en ia.py")
            if ui_callback:
                ui_callback("⚙️ Sistema", f"❌ Error inesperado: {str(e)[:200]}", "#FF4500")
            error_ocurrido = True

        if error_ocurrido and ui_callback:
            ui_callback("", "", "#E8EAED", nueva_linea=True)

    # =================================================================
    # INTERCEPTOR DE ACCIONES
    # =================================================================
    if not error_ocurrido and respuesta_ia:
        from modulos.controlador_acciones import procesar_acciones_ia
        comando_busqueda = procesar_acciones_ia(respuesta_ia, texto_usuario, ui_callback, modo_voz)

        if comando_busqueda == "INTERRUPTED":
            return

        if comando_busqueda and getattr(config.estado, 'modo_actual', 'general') == "general":
            if ui_callback:
                ui_callback("⚙️ Sistema", f"🌍 Buscando en internet: {comando_busqueda}", "#80868B")
            datos_encontrados = buscar_en_internet(comando_busqueda, reciente=skill_activa)
            if "No se encontraron" in datos_encontrados or "error de conexión" in datos_encontrados.lower():
                if ui_callback:
                    ui_callback("⚙️ Sistema", "⚠️ Sin resultados web. Respondiendo con conocimiento interno.", "#FFA500")
            else:
                try:
                    config_web = types.GenerateContentConfig(
                        system_instruction=contexto_sistema,
                        temperature=0.1,
                        max_output_tokens=8192,
                        safety_settings=[
                            types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                            types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                            types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                            types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                            types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_CIVIC_INTEGRITY, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                        ]
                    )
                    mensajes_secundarios = _convertir_contexto_a_contents(CONTEXTO_CHAT) + [
                        types.Content(role='user', parts=[types.Part.from_text(text=texto_usuario)]),
                        types.Content(role='model', parts=[types.Part.from_text(text=respuesta_ia)]),
                        types.Content(role='user', parts=[types.Part.from_text(text=f"Resultados web:\n{datos_encontrados}\n\nRespondé usando esto.")])
                    ]
                    segunda_respuesta = cliente_genai.models.generate_content_stream(
                        model="gemini-3.1-flash-lite",
                        contents=mensajes_secundarios,
                        config=config_web
                    )
                    respuesta_final = ""
                    buffer_voz_web = ""
                    for chunk in segunda_respuesta:
                        if hasattr(chunk, 'text') and chunk.text:
                            respuesta_final += chunk.text
                            if ui_callback:
                                ui_callback("", chunk.text, "#E8EAED", nueva_linea=False)
                            if modo_voz:
                                buffer_voz_web += chunk.text
                                buffer_voz_web = _procesar_buffer_voz(buffer_voz_web, forzar=False)
                    if modo_voz and buffer_voz_web.strip():
                        _procesar_buffer_voz(buffer_voz_web, forzar=True)
                    if ui_callback:
                        ui_callback("", "", "#E8EAED", nueva_linea=True)
                    CONTEXTO_CHAT.extend([
                        {'role': 'user', 'parts': [texto_usuario]},
                        {'role': 'model', 'parts': [respuesta_final]}
                    ])
                    return
                except Exception as e:
                    logger.exception("Error en búsqueda web secundaria")
                    if ui_callback:
                        ui_callback("⚙️ Sistema", f"❌ Error al procesar resultados web: {str(e)[:100]}", "#FF4500")

    if modo_voz and comando_directo:
        hablar_no_bloqueante(respuesta_ia)

    if respuesta_ia and not error_ocurrido:
        CONTEXTO_CHAT.extend([
            {'role': 'user', 'parts': [texto_usuario]},
            {'role': 'model', 'parts': [respuesta_ia]}
        ])

    if len(CONTEXTO_CHAT) > config.MAX_MENSAJES_CONTEXTO:
        config.estado.contexto_chat = CONTEXTO_CHAT[-config.MAX_MENSAJES_CONTEXTO:]


# =====================================================================
# PROCESAMIENTO DE ARCHIVOS ADJUNTOS
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
        try:
            contenido = leer_contenido_archivo(ruta)
            if contenido.startswith("ERROR:"):
                if ui_callback:
                    ui_callback("⚙️ Sistema", f"❌ No se pudo leer: {identificador_unico} ({contenido})", "#FF4500")
                continue
        except Exception as e:
            logger.exception(f"Error leyendo archivo adjunto: {ruta}")
            if ui_callback:
                ui_callback("⚙️ Sistema", f"❌ Error al leer {identificador_unico}: {str(e)[:80]}", "#FF4500")
            continue

        archivos_procesados.append({"nombre": identificador_unico, "contenido": contenido})
        contenido_volatil_acumulado += f"\n\n--- INICIO: {identificador_unico} ---\n{contenido}\n--- FIN: {identificador_unico} ---"

    if not archivos_procesados:
        if ui_callback:
            ui_callback("⚙️ Sistema", "❌ No se pudo leer ningún archivo.", "#FF4500")
        return

    config.estado.documento_volatil = contenido_volatil_acumulado

    try:
        resumen_response = cliente_genai.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=f"Resume en 2 líneas el contenido de estos archivos:\n\n{contenido_volatil_acumulado[:8000]}"
        )
        resumen = resumen_response.text.strip()
    except Exception as e:
        logger.exception("Error generando resumen de adjuntos")
        resumen = "Documentos cargados en contexto."

    nombres_str = ", ".join([f"'{a['nombre']}'" for a in archivos_procesados])
    msg = f"✅ {len(archivos_procesados)} archivo(s) cargado(s) en contexto:\n{nombres_str}\n\n{resumen}"

    if ui_callback:
        ui_callback("⚙️ Sistema", msg, "#86EFAC")

    config.estado.agregar_mensaje_chat({
        'role': 'user',
        'parts': [f"[SISTEMA] Archivos cargados en contexto: {nombres_str}"]
    })