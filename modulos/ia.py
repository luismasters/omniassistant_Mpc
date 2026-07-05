import os
import datetime
import winsound
import re
import difflib
import google.generativeai as genai
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

# ─── Usar la instancia global del gestor ────────────────────────────────
gestor_skills = gestor

# =====================================================================
# INICIALIZACIÓN DE CLIENTES IA
# =====================================================================
genai.configure(api_key=GEMINI_API_KEY)
cliente_deepseek = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

# =====================================================================
# HERRAMIENTAS NATIVAS MCP (GEMINI)
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
    Guarda un dato, recuerdo o información importante en la memoria a largo plazo (bóveda).
    OPTIMIZADO: llama directo a ChromaDB sin proceso MCP intermedio.
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
    if contenido == "CODIGO_ERROR_NO_ENCONTRADO" or contenido.startswith("CODIGO_ERROR_LECTURA:"):
        return f"Error: No se pudo encontrar o abrir el archivo '{ruta}'. Verificá que la ruta sea correcta."
    return f"Contenido del archivo:\n{contenido}"

lista_herramientas_mcp = [
    mcp_estado_pc, mcp_hardware_pc, mcp_buscar_en_boveda,
    mcp_guardar_en_boveda, mcp_explorar_ruta, mcp_leer_documento
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
    """Elimina líneas de comandos de acción del texto antes de enviarlo a Edge TTS."""
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
# OPTIMIZACIÓN: reemplaza llamadas a Gemini como juez por lógica local
# simple. Elimina 2-3 segundos de latencia y consumo de tokens.
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
    """
    Evalúa si el usuario confirmó o canceló una acción sin llamar a la IA.
    Retorna 'CONFIRMADO' o 'CANCELADO'.
    """
    texto = respuesta_usuario.lower().strip()
    # Primero verificar coincidencia exacta
    if texto in _PALABRAS_CONFIRMACION:
        return "CONFIRMADO"
    if texto in _PALABRAS_CANCELACION:
        return "CANCELADO"
    # Luego verificar si alguna palabra clave está contenida
    for palabra in _PALABRAS_CONFIRMACION:
        if palabra in texto:
            return "CONFIRMADO"
    for palabra in _PALABRAS_CANCELACION:
        if palabra in texto:
            return "CANCELADO"
    # Si no hay claridad, conservador: cancelar
    logger.warning(f"Respuesta de confirmación ambigua: '{respuesta_usuario}' → CANCELADO")
    return "CANCELADO"

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

    # ─── LIMPIAR CONTEXTO (interceptor pre-IA, Gemini no puede bloquearlo) ─
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
    # ESCUDOS DE SEGURIDAD — CONFIRMACIONES NATIVAS (sin juez IA)
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
    modelo_gemini = None
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

        # ─── BÚSQUEDA ANTICIPADA EN BÓVEDA ───────────────────────────────
        # Lanzar búsqueda en bóveda en paralelo mientras la IA piensa
        # Solo en modo general donde Gemini puede pedir datos de bóveda
        MODO_ACTUAL = config.estado.modo_actual
        if MODO_ACTUAL == "general":
            iniciar_busqueda_anticipada(texto_usuario)

        try:
            fecha_hoy = datetime.datetime.now().strftime("%A, %d de %B de %Y")
            ventanas_abiertas = obtener_ventanas_activas()

            texto_workspace = f"[WORKSPACE ANCLADO]: {WORKSPACE_ACTUAL}\n" if WORKSPACE_ACTUAL else ""
            texto_snapshot = f"[ESTADO DEL PROYECTO]:\n{SNAPSHOT_ACTUAL}\n\n" if SNAPSHOT_ACTUAL else ""
            texto_doc_volatil = f"[DOCUMENTOS EN MEMORIA]:\n{DOCUMENTO_VOLATIL}\n\n" if DOCUMENTO_VOLATIL else ""

            # ─── SELECCIÓN DE MODELO Y CONTEXTO ──────────────────────────────
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

            # ─── INYECCIÓN DE SKILLS RELEVANTES ──────────────────────────────
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

            # ─── GEMINI ────────────────────────────────────────────────────────
            if modelo_activo == "gemini":
                if skill_activa:
                    modelo_gemini = genai.GenerativeModel(
                        "gemini-flash-lite-latest",
                        system_instruction=contexto_sistema
                    )
                else:
                    modelo_gemini = genai.GenerativeModel(
                        "gemini-flash-lite-latest",
                        system_instruction=contexto_sistema,
                        tools=lista_herramientas_mcp
                    )

                mensajes_para_gemini = list(CONTEXTO_CHAT)
                partes_usuario = [texto_usuario]

                verbos_vision = ["captura", "capturá", "capturar", "mirar", "ves"]
                objetivos_vision = ["pantalla", "monitor", "1", "2", "uno", "dos", "la 1", "el 1", "la 2", "el 2"]
                if any(v in texto_usuario_lower for v in verbos_vision) and any(o in texto_usuario_lower for o in objetivos_vision):
                    if ui_callback:
                        ui_callback("⚙️ Sistema", "📸 Capturando pantalla...", "#80868B")
                    winsound.Beep(1500, 100)
                    num_pantalla = 2 if any(p in texto_usuario_lower for p in ["1", "uno", "la 1", "el 1"]) else 1
                    img = capturar_pantalla(num_pantalla)
                    if img:
                        partes_usuario.append(img)

                mensajes_para_gemini.append({'role': 'user', 'parts': partes_usuario})

                try:
                    response = modelo_gemini.generate_content(
                        mensajes_para_gemini,
                        stream=True,
                        generation_config=genai.GenerationConfig(temperature=0.1)
                    )
                except genai.types.generation_types.BlockedPromptException as e:
                    logger.exception("Prompt bloqueado por Gemini")
                    ui_callback("⚙️ Sistema", "⚠️ Mensaje bloqueado por filtros de seguridad.", "#FF4500")
                    error_ocurrido = True
                    return
                except Exception as e:
                    err_str = str(e)
                    if "ResourceExhausted" in err_str or "429" in err_str:
                        ui_callback("⚙️ Sistema", "⚠️ Límite de tokens alcanzado. Limpiá el contexto.", "#FF4500")
                    elif "Unauthenticated" in err_str or "401" in err_str:
                        ui_callback("⚙️ Sistema", "❌ Error de autenticación. Verificá tu API Key.", "#FF4500")
                    elif "PermissionDenied" in err_str or "403" in err_str:
                        ui_callback("⚙️ Sistema", "❌ Permiso denegado. Verificá tu API Key.", "#FF4500")
                    else:
                        ui_callback("⚙️ Sistema", f"❌ Error al iniciar generación: {err_str[:100]}", "#FF4500")
                    logger.exception("Error al iniciar generación en Gemini")
                    error_ocurrido = True
                    return

                if ui_callback:
                    ui_callback("🤖 Argus", "", "#A8C7FA", nueva_linea=False)

                buffer_voz = ""

                try:
                    for chunk in response:
                        try:
                            for part in chunk.parts:
                                if getattr(part, "function_call", None):
                                    usaste_mcp = True
                                    n_func = part.function_call.name
                                    if ui_callback:
                                        ui_callback("⚙️ Sistema", f"Consultando: {n_func}...", "#80868B")
                                    args = {k: v for k, v in part.function_call.args.items()}
                                    try:
                                        if n_func == "mcp_estado_pc":
                                            resultado_mcp = mcp_estado_pc()
                                        elif n_func == "mcp_hardware_pc":
                                            resultado_mcp = mcp_hardware_pc()
                                        elif n_func == "mcp_buscar_en_boveda":
                                            # OPTIMIZADO: directo, sin MCP
                                            resultado_mcp = mcp_buscar_en_boveda(args.get("consulta", ""))
                                        elif n_func == "mcp_guardar_en_boveda":
                                            # OPTIMIZADO: directo, sin MCP
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
                                        ui_callback("⚙️ Sistema", f"❌ Error en {n_func}: {str(e)[:80]}", "#FF4500")
                                elif getattr(part, "text", None):
                                    print(part.text, end='', flush=True)
                                    respuesta_ia += part.text
                                    if ui_callback:
                                        ui_callback("", part.text, "#E8EAED", nueva_linea=False)
                                    if modo_voz and not usaste_mcp:
                                        buffer_voz += part.text
                                        buffer_voz = _procesar_buffer_voz(buffer_voz, forzar=False)
                        except Exception as e:
                            logger.exception("Error procesando chunk de Gemini")
                            ui_callback("⚙️ Sistema", f"❌ Error en streaming: {str(e)[:80]}", "#FF4500")
                            break
                except Exception as e:
                    logger.exception("Error en el bucle de streaming de Gemini")
                    ui_callback("⚙️ Sistema", f"❌ Error en el streaming: {str(e)[:80]}", "#FF4500")
                    error_ocurrido = True
                finally:
                    if modo_voz and buffer_voz.strip() and not usaste_mcp:
                        _procesar_buffer_voz(buffer_voz, forzar=True)

                # ─── MCP SEGUNDA RONDA ────────────────────────────────────────
                if usaste_mcp and modelo_gemini and not error_ocurrido and not skill_activa:
                    try:
                        if not resultado_mcp or "TIMEOUT" in str(resultado_mcp):
                            if ui_callback:
                                ui_callback("⚙️ Sistema", "⚠️ No se obtuvo dato. Verificá conexión.", "#FFA500")
                        else:
                            mensajes_para_gemini.append({'role': 'model', 'parts': ['Obteniendo datos...']})
                            mensajes_para_gemini.append({'role': 'user', 'parts': [
                                f"[DATO OBTENIDO]: {resultado_mcp}\n\n"
                                "Respondé al usuario de forma natural y directa con este dato. "
                                "No inventes valores que no estén en el dato. "
                                "Si falta algún dato, decílo explícitamente."
                            ]})
                            response_2 = modelo_gemini.generate_content(mensajes_para_gemini, stream=True)
                            if ui_callback:
                                ui_callback("🤖 Argus", "", "#A8C7FA", nueva_linea=True)
                            buffer_voz_2 = ""
                            for chunk_2 in response_2:
                                try:
                                    for part in chunk_2.parts:
                                        if getattr(part, "text", None):
                                            print(part.text, end='', flush=True)
                                            respuesta_ia += part.text
                                            if ui_callback:
                                                ui_callback("", part.text, "#E8EAED", nueva_linea=False)
                                            if modo_voz:
                                                buffer_voz_2 += part.text
                                                buffer_voz_2 = _procesar_buffer_voz(buffer_voz_2, forzar=False)
                                except Exception as e:
                                    logger.exception("Error procesando chunk MCP ronda 2")
                                    ui_callback("⚙️ Sistema", f"❌ Error en respuesta MCP: {str(e)[:80]}", "#FF4500")
                                    break
                            if ui_callback:
                                ui_callback("", "", "#E8EAED", nueva_linea=True)
                            if modo_voz and buffer_voz_2.strip():
                                _procesar_buffer_voz(buffer_voz_2, forzar=True)
                    except Exception as e:
                        logger.exception("Error en generación MCP ronda 2")
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
                        ui_callback("⚙️ Sistema", "⚠️ Rate limit DeepSeek. Esperá un momento.", "#FFA500")
                    elif "AuthenticationError" in err_str or "401" in err_str:
                        ui_callback("⚙️ Sistema", "❌ Error de autenticación DeepSeek.", "#FF4500")
                    else:
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
                            ui_callback("⚙️ Sistema", f"❌ Error en streaming: {str(e)[:80]}", "#FF4500")
                            break
                except Exception as e:
                    logger.exception("Error en el bucle de streaming de DeepSeek")
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
            ui_callback("⚙️ Sistema", "❌ Error de conexión. Revisá tu internet.", "#FF4500")
            error_ocurrido = True
        except TimeoutError as e:
            logger.exception("Timeout")
            ui_callback("⚙️ Sistema", "⏱️ Timeout. La respuesta está tardando demasiado.", "#FFA500")
            error_ocurrido = True
        except Exception as e:
            logger.exception("Error crítico en ia.py")
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
            elif modelo_gemini:
                try:
                    mensajes_secundarios = list(CONTEXTO_CHAT) + [
                        {'role': 'user', 'parts': [texto_usuario]},
                        {'role': 'model', 'parts': [respuesta_ia]},
                        {'role': 'user', 'parts': [f"Resultados web:\n{datos_encontrados}\n\nRespondé usando esto."]}
                    ]
                    segunda_respuesta = modelo_gemini.generate_content(mensajes_secundarios, stream=True)
                    respuesta_final = ""
                    buffer_voz_web = ""
                    for chunk in segunda_respuesta:
                        if getattr(chunk, 'text', None):
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
                    ui_callback("⚙️ Sistema", f"❌ Error al procesar resultados web: {str(e)[:100]}", "#FF4500")

    if modo_voz and comando_directo:
        hablar_no_bloqueante(respuesta_ia)

    if respuesta_ia and not error_ocurrido:
        CONTEXTO_CHAT.extend([
            {'role': 'user', 'parts': [texto_usuario]},
            {'role': 'model', 'parts': [respuesta_ia]}
        ])
    if len(CONTEXTO_CHAT) > 100:
        config.estado.contexto_chat = CONTEXTO_CHAT[-100:]


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
            if contenido == "CODIGO_ERROR_NO_ENCONTRADO" or contenido.startswith("CODIGO_ERROR_LECTURA:"):
                if ui_callback:
                    ui_callback("⚙️ Sistema", f"❌ No se pudo leer: {identificador_unico}", "#FF4500")
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
        resumen = genai.GenerativeModel("gemini-flash-lite-latest").generate_content(
            f"Resume en 2 líneas el contenido de estos archivos:\n\n{contenido_volatil_acumulado[:8000]}"
        ).text.strip()
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