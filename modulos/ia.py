import os
import datetime
import winsound
import re
import difflib
import itertools
from google import genai
from google.genai import types
from openai import OpenAI
import config

# ─── Importación de logger ──────────────────────────────────────────────
from modulos.logger import logger

# ─── Importación del gestor de skills ────────────────────────────────────
from modulos.skills.gestor_skills import gestor

# Importación de llaves
from config import GEMINI_API_KEY, DEEPSEEK_API_KEY, GROQ_API_KEY

from modulos.archivos import eliminar_elemento, leer_contenido_archivo
from modulos.sistema import obtener_ventanas_activas, obtener_estado_pc, escanear_hardware_completo, explorar_directorio
from modulos.busqueda import buscar_en_internet
from modulos.mensajes_web import (
    construir_mensajes_segunda_generacion,
    construir_bloque_evidencia_anterior,
    armar_mensaje_modelo_persistido,
    decidir_contenido_presentacion,
)
from modulos.senal_web import (
    OcultadorStreamWeb,
    parsear_senal_web,
    limpiar_respuesta_web,
    fusionar_comando_busqueda,
    texto_marcador_tema_web_anterior,
)
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
    construir_contexto_sistema,
)

# ─── Perfil de usuario persistente ─────────────────────────────────────
from modulos.perfil_usuario import (
    texto_perfil_para_prompt,
)

# ─── Usar la instancia global del gestor ────────────────────────────────
gestor_skills = gestor

# =====================================================================
# INICIALIZACIÓN DE CLIENTES IA (NUEVO SDK google-genai)
# =====================================================================
# Si faltan las keys, los clientes quedan en None y cada llamada responde
# con un mensaje amigable (ver enviar_a_gemini) en vez de crashear al importar.
cliente_genai = (
    genai.Client(
        api_key=GEMINI_API_KEY,
        http_options=types.HttpOptions(
            # Sin reintentos internos del SDK (attempts=1): el 503/429 llega
            # al instante a _gemini_stream_con_retry / _fallback_deepseek en
            # vez de encadenar esperas internas de tenacity (delay de ~50s
            # observado cuando Gemini está en "high demand").
            retry_options=types.HttpRetryOptions(attempts=1, initial_delay=0.0, max_delay=0.5),
            # Timeout acotado (MILISEGUNDOS en este SDK): si Gemini no responde
            # en este plazo, fallamos y pasamos a DeepSeek de una.
            timeout=30000,
        ),
    )
    if GEMINI_API_KEY
    else None
)
cliente_deepseek = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com") if DEEPSEEK_API_KEY else None
cliente_groq = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1") if GROQ_API_KEY else None

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


def _normalizar_para_match(texto: str) -> str:
    """Normaliza texto para el matcheo por tema (minúsculas, sin tildes)."""
    import unicodedata
    texto = unicodedata.normalize("NFD", str(texto or "").lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn").strip()


def mcp_olvidar_tema(tema: str):
    """
    Olvida de la memoria a largo plazo TODO lo relacionado con un tema que
    el usuario pida (ej. "olvidá lo de volcano", "olvidate de netflix").
    Busca coincidencias en el panel de memoria (perfiles + bóveda), despacha
    resolver_olvidar por id (registra el tombstone) y devuelve qué se olvidó.
    NO es retroactivo sobre la conversación actual (contrato H.1).
    """
    try:
        from modulos.resumen_memoria import preparar_secciones, resolver_olvidar
        tema_norm = _normalizar_para_match(tema)
        if not tema_norm:
            return "No se entendió qué tema olvidar. Repetí qué querés olvidar."

        # Buscar coincidencias en las secciones del panel de memoria.
        coincidencias = []
        datos = preparar_secciones()
        for seccion in datos.get("secciones", []):
            for elem in seccion.get("elementos", []):
                id_ = elem.get("id")
                if not id_:
                    continue
                texto_buscar = _normalizar_para_match(
                    f"{elem.get('etiqueta', '')} {elem.get('texto', '')}"
                )
                if tema_norm in texto_buscar:
                    coincidencias.append(id_)

        if not coincidencias:
            return f"No encontré nada en mi memoria sobre '{tema}' para olvidar."

        olvidados = 0
        for id_ in coincidencias:
            res = resolver_olvidar(id_)
            if res.get("exito"):
                olvidados += 1

        if olvidados:
            return f"Listo, olvidé {olvidados} dato(s) relacionado(s) con '{tema}' de mi memoria a largo plazo."
        return f"No pude olvidar nada de '{tema}' (los datos ya no existen)."
    except Exception as e:
        logger.exception("Error olvidando tema")
        return f"Error al intentar olvidar el tema '{tema}'."


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
    mcp_explorar_ruta, mcp_leer_documento, mcp_guardar_en_boveda,
    mcp_olvidar_tema
]

# =====================================================================
# HELPER: STREAMING DE VOZ PARALELO AL STREAMING DE IA
# =====================================================================
_PATRON_CORTE_VOZ = re.compile(r'(?<=[.!?])\s+')
_MIN_CHARS_CHUNK_VOZ = 30
_PATRON_COMANDOS_VOZ = re.compile(
    r'^(audio:|buscar:|abrir:|cerrar:|mover:|guardar_archivo:|leer_archivo:|'
    r'reemplazar_bloque:|editar_archivo:|crear_carpeta:|github:|escanear_proyecto:|'
    r'mcp_\w+)[^\n]*$',
    re.MULTILINE | re.IGNORECASE
)

def _limpiar_para_voz(texto: str) -> str:
    texto = _PATRON_COMANDOS_VOZ.sub('', texto)
    # Eliminar etiquetas [EMOTION: ...] para que no se lean en audio
    texto = re.sub(r'\[EMOTION:\s*\w+\]', '', texto, flags=re.IGNORECASE)
    return texto.strip()

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

def _es_intencion_comando_directo(texto: str) -> bool:
    """
    Detecta si la solicitud del usuario es para ejecutar un comando de sistema
    o abrir una aplicación/página/audio/ventana, para evitar búsquedas web/bóveda innecesarias.
    """
    if not texto:
        return False
    texto_low = texto.lower().strip()
    patrones_comando = [
        r'\b(abrir|abrí|abre|lanzar|lanza|ejecutar|ejecuta|iniciar|inicia)\b',
        r'\b(cerrar|cerrá|cierra|mover|mové|mueve)\b',
        r'\b(subir|subí|bajar|bajá|silenciar|mutear|desmutear|pon|poné|establecer)\s+(el\s+)?volumen\b',
        r'\b(volumen\s+a\s+\d+|subir\s+volumen|bajar\s+volumen|mutear|desmutear)\b',
        r'\b(pantalla|monitor)\s+[12]\b',
        r'\b(github|subir\s+cambios|escanear\s+proyecto)\b',
        r'^(audio:|abrir:|cerrar:|mover:|crear_carpeta:|guardar_archivo:|leer_archivo:)'
    ]
    for pat in patrones_comando:
        if re.search(pat, texto_low):
            return True
    return False

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

def _modelo_gemini_str(nombre_opcion: str) -> str:
    """Mapa nombre-de-opción → ID de modelo Gemini (para el default global)."""
    return {
        "Gemini 3.1 Flash Lite": "gemini-3.1-flash-lite",
        "Gemini 3.5 Flash Lite": "gemini-3.5-flash-lite",
        "Gemini 3.6 Flash (High)": "gemini-3.6-flash",
        "Gemini 3.1 Pro (High)": "gemini-3.1-pro-preview",
    }.get(str(nombre_opcion or ""), "gemini-3.5-flash-lite")


def _ejecutar_herramienta_mcp(nombre: str, args: dict = None):
    """
    Ejecuta una herramienta MCP por nombre. Dispatcher ÚNICO: si una tool
    está en lista_herramientas_mcp y no está acá, devuelve None (se detecta
    como "no ejecutada"). Facilita tests unitarios del dispatcher.
    """
    args = args or {}
    if nombre == "mcp_estado_pc":
        return mcp_estado_pc()
    if nombre == "mcp_hardware_pc":
        return mcp_hardware_pc()
    if nombre == "mcp_buscar_en_boveda":
        return mcp_buscar_en_boveda(args.get("consulta", ""))
    if nombre == "mcp_guardar_en_boveda":
        return mcp_guardar_en_boveda(args.get("dato", ""))
    if nombre == "mcp_olvidar_tema":
        return mcp_olvidar_tema(args.get("tema", ""))
    if nombre == "mcp_explorar_ruta":
        return mcp_explorar_ruta(args.get("ruta", ""))
    if nombre == "mcp_leer_documento":
        return mcp_leer_documento(args.get("ruta", ""))
    return None


def _es_error_transitorio_gemini(e) -> bool:
    """
    True si el error de Gemini es transitorio (503 high demand / 429 rate
    limit / ResourceExhausted / timeout de red): merece fallback a DeepSeek
    en vez de crashear.
    """
    try:
        texto = str(e).lower()
        codigo = getattr(e, "code", None)
        if codigo in (429, 503):
            return True
        if any(s in texto for s in (
            "503", "429", "resourceexhausted", "high demand", "unavailable",
            "rate limit", "timed out", "handshake", "connect", "read timed out",
            "connection", "timeout",
        )):
            return True
        # Timeouts de red por tipo (httpx / socket).
        for clase in (
            __import__("httpx").ConnectTimeout,
            __import__("httpx").ReadTimeout,
            __import__("httpx").TimeoutException,
            __import__("socket").timeout,
            TimeoutError,
        ):
            if isinstance(e, clase):
                return True
        return False
    except Exception:
        return False


def _gemini_stream_con_retry(modelo, contents, config, intentos=2, backoff_base=0.5, ui_callback=None):
    """
    Generador que consume el stream de Gemini reintentando SOLO si el error
    transitorio (503/429) ocurre ANTES de emitir el primer chunk. Si ya se
    emitieron chunks y luego falla, re-lanza (no se reintenta para no duplicar
    una respuesta a mitad). Al agotar los reintentos, re-lanza la excepción.

    Con el SDK configurado sin reintentos internos (HttpRetryOptions.attempts=1),
    el 503/429 llega acá al instante: un solo reintento rápido y si sigue, el
    turno cae a _fallback_deepseek (DeepSeek de una).
    """
    import time
    ultimo_error = None
    for intento in range(1, intentos + 1):
        emitido = False
        try:
            stream = cliente_genai.models.generate_content_stream(
                model=modelo, contents=contents, config=config
            )
            for chunk in stream:
                if chunk is not None:
                    emitido = True
                yield chunk
            return  # stream completo sin error
        except Exception as e:
            ultimo_error = e
            if not _es_error_transitorio_gemini(e):
                raise
            if emitido:
                # Ya arrancó la respuesta: reintentar duplicaría contenido.
                raise
            if intento < intentos:
                espera = backoff_base * (2 ** (intento - 1))
                logger.warning(f"⚠️ Gemini transitorio (intento {intento}/{intentos}); reintentando en {espera:.1f}s: {str(e)[:80]}")
                if ui_callback:
                    ui_callback("⚙️ Sistema", f"⚠️ Gemini saturado; reintentando ({intento}/{intentos})...", "#FFA500")
                time.sleep(espera)
    raise ultimo_error


# Modelos Gemini de reserva para el default global (Fase D): si el modelo
# activo está saturado (503/429), se prueba el siguiente antes de caer a
# DeepSeek. Solo aplica al modelo "Por Defecto"/Auto, NO a selecciones
# explícitas del usuario.
CADENA_FALLBACK_GEMINI = ("gemini-3.5-flash-lite", "gemini-3.6-flash")


def _cadena_fallback_gemini(modelo_str: str):
    """
    Orden de modelos Gemini a probar ante saturación transitoria del modelo
    activo: primero el modelo en uso, luego los de reserva (económicos/rápidos).
    """
    cadena = [modelo_str]
    for m in CADENA_FALLBACK_GEMINI:
        if m != modelo_str and m not in cadena:
            cadena.append(m)
    return cadena


def _gemini_stream_con_cadena(modelo, contents, config, ui_callback=None, usar_cadena=True, intentos=2, backoff_base=0.5):
    """
    Consume el stream de Gemini probando la CADENA de modelos ante saturación
    transitoria: el modelo activo con su retry/backoff, luego los de reserva.
    Si ya se emitió contenido NO se cambia de modelo (evitaría duplicar la
    respuesta a mitad). Al agotar toda la cadena re-lanza el último error para
    que el turno caiga a _fallback_deepseek. Con usar_cadena=False se comporta
    como _gemini_stream_con_retry puro.
    """
    if not usar_cadena:
        yield from _gemini_stream_con_retry(modelo, contents, config, intentos=intentos, backoff_base=backoff_base, ui_callback=ui_callback)
        return
    cadena = _cadena_fallback_gemini(modelo)
    ultimo_error = None
    emitido_total = False
    for i, m in enumerate(cadena):
        try:
            for chunk in _gemini_stream_con_retry(m, contents, config, intentos=intentos, backoff_base=backoff_base, ui_callback=ui_callback):
                if chunk is not None:
                    emitido_total = True
                yield chunk
            return  # stream completo sin error
        except Exception as e:
            ultimo_error = e
            if emitido_total:
                # Ya arrancó la respuesta: no cambiar de modelo.
                raise
            if not _es_error_transitorio_gemini(e):
                raise
            if i < len(cadena) - 1:
                siguiente = cadena[i + 1]
                logger.warning(f"⚠️ {m} saturado; probando modelo de reserva: {siguiente} ({str(e)[:80]})")
                if ui_callback:
                    ui_callback("⚙️ Sistema", f"⚠️ {m} saturado; probando {siguiente}...", "#FFA500")
    raise ultimo_error


def _fallback_deepseek(contexto_sistema, contexto_chat, texto_usuario, ocultador_stream, modo_voz, ui_callback, motivo="respuesta vacía"):
    """
    Reintenta el turno con DeepSeek (streaming) cuando Gemini falla de forma
    transitoria o devuelve respuesta vacía. Devuelve el texto de respuesta
    ("" si falló del todo) y setea buffer de voz si aplica.
    """
    logger.warning(f"⚠️ Fallback a DeepSeek ({motivo}).")
    if ui_callback:
        ui_callback("⚠️ Sistema", f"Gemini no disponible ({motivo}). Usando respaldo DeepSeek...", "#FFA500")
    mensajes_ds = [{"role": "system", "content": contexto_sistema}]
    for msg in (contexto_chat or []):
        rol_ds = "assistant" if msg['role'] == "model" else "user"
        texto_historico = "".join([p for p in msg['parts'] if isinstance(p, str)])
        mensajes_ds.append({"role": rol_ds, "content": texto_historico})
    mensajes_ds.append({"role": "user", "content": texto_usuario})
    respuesta = ""
    buffer_voz_fallback = ""
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
                respuesta += texto_chunk
                texto_visible = ocultador_stream.procesar(texto_chunk)
                if texto_visible:
                    print(texto_visible, end='', flush=True)
                    if ui_callback:
                        ui_callback("", texto_visible, "#E8EAED", nueva_linea=False)
                    if modo_voz:
                        buffer_voz_fallback += texto_visible
                        buffer_voz_fallback = _procesar_buffer_voz(buffer_voz_fallback, forzar=False)
    except Exception as e:
        logger.exception("Error en fallback DeepSeek")
        if ui_callback:
            ui_callback("⚙️ Sistema", f"❌ Fallback DeepSeek falló: {str(e)[:100]}", "#FF4500")
        respuesta = "⚠️ Lo siento, la API bloqueó esta respuesta por políticas de seguridad."
    finally:
        if modo_voz and buffer_voz_fallback.strip():
            _procesar_buffer_voz(buffer_voz_fallback, forzar=True)
    return respuesta


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
# SERIALIZACIÓN DE TURNOS (C1) Y MARCADOR TEMPORAL (C2)
#
# Todas las entradas (texto, voz, gamepad, wake word) convergen en
# enviar_a_gemini. Un único RLock serializa el procesamiento para que dos
# turnos concurrentes no mezclen contexto, streams ni persistencia.
# El turno_id es un identificador temporal (contador monótono, sin
# persistencia) que viaja hacia la UI dentro del remitente del ui_callback
# con el prefijo @@TURNO:<id>|, de modo que app.js pueda dirigir las
# señales provisionales/verificadas a la burbuja correcta.
# =====================================================================
# Todos los turnos y las mutaciones que rebinden/limpian el contexto por
# modo (config.RLOCK_CONTEXTO: cambiar_modo, limpiar_contexto) comparten el
# MISMO lock canónico: un cambio de modo nunca se intercala con un turno.
_RLOCK_PROC = config.RLOCK_CONTEXTO
_CONTADOR_TURNOS = itertools.count(1)

def _marcar_turno_en_remitente(turno_id, remitente):
    """Prefija el remitente del ui_callback con el turno_id temporal."""
    return f"@@TURNO:{turno_id}|{remitente or ''}"

def _procesar_mensaje(texto_usuario, modo_voz=False, ui_callback=None, turno_id=None):
    """Enrutador Universal y traductor de acciones con soporte para Skills."""
    import config
    if ui_callback is not None:
        ui_callback_original = ui_callback
        if turno_id is not None:
            def ui_callback(remitente, texto, color=None, nueva_linea=True):
                ui_callback_original(_marcar_turno_en_remitente(turno_id, remitente), texto, color, nueva_linea)
    if not config.GEMINI_API_KEY:
        mensaje = ("⚠️ Argus todavía no tiene configurada su API Key de Gemini. "
                   "Agregá GEMINI_API_KEY a tu archivo .env y reiniciá la app.")
        if ui_callback:
            ui_callback("⚙️ Sistema", mensaje, "#FFA000")
        if modo_voz:
            hablar_no_bloqueante("Todavía no tengo mi clave de Gemini configurada. Agregala al archivo punto env y reiniciame.")
        return
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

    # ─── RETOMAR HISTORIAL PERSISTIDO (Fase P) ───────────────────────────
    # Frases naturales que hidratan el contexto con el tail persistido del
    # contexto activo. Solo se dispara si hay historial en disco; si no, la
    # conversación continúa normalmente.
    _FRASES_RETOMAR = (
        "dónde quedamos", "donde quedamos", "retomá la conversación",
        "retoma la conversacion", "retomá la charla", "retoma la charla",
        "seguimos con la conversación", "seguimos con la conversacion",
        "continuá la conversación", "continua la conversacion", "retomar",
    )
    _es_retomar = texto_usuario_lower in _FRASES_RETOMAR or any(
        frase in texto_usuario_lower for frase in _FRASES_RETOMAR
    )
    if _es_retomar:
        try:
            from modulos.persistencia import recuperar_tail, armar_context_id
            mensajes_hist = recuperar_tail(armar_context_id(config.estado.modo_actual))
            if mensajes_hist:
                config.estado.restaurar_historial_persistido(mensajes_hist)
                msg_retomar = f"↩️ Retomé los últimos {len(mensajes_hist)} mensajes de la conversación guardada. ¿Seguimos?"
                if ui_callback:
                    ui_callback("⚙️ Sistema", msg_retomar, "#A8C7FA")
                if modo_voz:
                    hablar_no_bloqueante("Retomé la conversación guardada.")
                return
        except Exception:
            pass

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
    # INTERCEPTOR DE COMANDOS ARGUS (CONTROL DE VENTANA PROPIA)
    # =================================================================
    import re as _re_argus
    _texto_norm = _re_argus.sub(r'[^\w\s]', ' ', texto_usuario_lower)
    _texto_norm = _texto_norm.replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ú","u")
    _words = set(_texto_norm.split())

    # Palabras clave que indican una acción externa/app/web (NO mover la ventana de Argus)
    from modulos.sistema import SITIOS_WEB_COMUNES
    _sitios_set = set(SITIOS_WEB_COMUNES) if SITIOS_WEB_COMUNES else set()
    _verbos_externos = {
        "abrir", "abre", "abrimé", "abrime", "habre", "habré",
        "navegar", "navega", "navegame", "buscar", "busca", "buscame",
        "poner", "pone", "poné", "ponme", "reproducir", "reproduce",
        "escuchar", "escucha", "ver", "jugar", "juega", "ejecutar", "ejecuta",
        "lanzar", "lanza", "crear", "crea", "editar", "edita", "escanear", "escanea",
        "recordatorio", "alarma", "timer", "cancion", "video", "musica", "pagina", "sitio",
        "link", "url", "browser", "navegador", "discord", "chrome", "firefox", "brave",
        "edge", "code", "spotify", "steam", "obs", "game", "calculadora", "notepad"
    }
    _es_accion_externa = bool(_words.intersection(_verbos_externos) or _words.intersection(_sitios_set))

    # Palabras clave de visión/captura (para no interceptar "mirá la pantalla 2")
    _verbos_vision = {"captura", "capturar", "mira", "mirar", "ves", "fijate", "que", "analiza", "analizar"}
    _es_vision = bool(_words.intersection(_verbos_vision))

    if not _es_vision and not _es_accion_externa:
        from modulos.sistema import argus_mover_a_monitor, argus_maximizar_con_topmost, argus_minimizar, argus_traer_al_frente
        from modulos.audio_custom import detener_voz
        
        _ejecutado = False
        
        # Detectar número de monitor
        _nums = _re_argus.findall(r'\b([1-9])\b', _texto_norm)
        if not _nums:
            if "dos" in _words or "segunda" in _words or "segundo" in _words:
                _nums = ["2"]
            elif "uno" in _words or "primera" in _words or "primero" in _words or "principal" in _words:
                _nums = ["1"]
                
        _num_mon = int(_nums[0]) if _nums else None

        # 1. MOVER A MONITOR (ej: "movete a la pantalla 2", "argus pantalla 2", "pasa a la pantalla 1")
        _verbos_mover_argus = {"movete", "muevete", "pasate", "cambiate", "trasladate"}
        _verbos_mover_general = {"mover", "move", "pasar", "pasa", "cambiar", "cambia", "ponete", "ponte", "lleva", "llevame"}
        
        _es_comando_mover = False
        if _num_mon is not None:
            if _words.intersection(_verbos_mover_argus):
                _es_comando_mover = True
            elif "argus" in _words and (_words.intersection(_verbos_mover_general) or _words.intersection({"pantalla", "monitor"})):
                _es_comando_mover = True
            elif _texto_norm.strip() in {"pantalla 1", "pantalla 2", "monitor 1", "monitor 2", "pantalla uno", "pantalla dos", "mover 1", "mover 2"}:
                _es_comando_mover = True

        if _es_comando_mover and _num_mon is not None:
            detener_voz()
            argus_mover_a_monitor(None, _num_mon)
            _ejecutado = True
            
        # 2. MAXIMIZAR (ej: "maximizate", "argus maximizar", "pantalla completa", "agranda")
        elif any(w in _texto_norm for w in ["maximizar", "maximiza", "maximizate", "pantalla completa", "agrandar", "agranda", "agrandate"]):
            detener_voz()
            argus_maximizar_con_topmost(None)
            _ejecutado = True
        elif "argus" in _words and ("max" in _words or "grande" in _words):
            detener_voz()
            argus_maximizar_con_topmost(None)
            _ejecutado = True
            
        # 3. MINIMIZAR (ej: "minimizate", "argus minimizar", "achicar", "esconder", "ocultar")
        elif any(w in _texto_norm for w in ["minimizar", "minimiza", "minimizate", "achicar", "achica", "achicate", "esconder", "esconde", "ocultar", "oculta"]):
            detener_voz()
            argus_minimizar(None)
            _ejecutado = True
        elif "argus" in _words and ("mini" in _words or "chico" in _words):
            detener_voz()
            argus_minimizar(None)
            _ejecutado = True
            
        # 4. MOSTRAR / AL FRENTE (ej: "muestrate", "ponte al frente", "traer al frente", "aparece")
        elif any(w in _texto_norm for w in ["muestrate", "muestra", "mostrar", "muestrame", "al frente", "frente", "delante", "aparece", "aparecé", "veni", "vení"]):
            detener_voz()
            argus_traer_al_frente(None)
            _ejecutado = True

        if _ejecutado:
            logger.info(f"🪟 Comando Argus ejecutado: {texto_usuario}")
            msg_confirmacion = "Listo, acción ejecutada."
            if ui_callback:
                ui_callback("🤖 Argus", msg_confirmacion, "#00E5FF")
            if modo_voz:
                hablar_no_bloqueante(msg_confirmacion)
            config.estado.agregar_mensaje_chat({'role': 'user', 'parts': [texto_usuario]})
            config.estado.agregar_mensaje_chat({'role': 'model', 'parts': [msg_confirmacion]})
            return  # Salir sin llamar a Gemini LLM

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
        config.estado.agregar_mensaje_chat({'role': 'user', 'parts': [texto_usuario]})
        config.estado.agregar_mensaje_chat({'role': 'model', 'parts': [msg]})
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
        config.estado.agregar_mensaje_chat({'role': 'user', 'parts': [texto_usuario]})
        config.estado.agregar_mensaje_chat({'role': 'model', 'parts': [msg]})
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
        config.estado.agregar_mensaje_chat({'role': 'user', 'parts': [texto_usuario]})
        config.estado.agregar_mensaje_chat({'role': 'model', 'parts': [msg]})
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
    ocultador_stream = OcultadorStreamWeb()

    if comando_directo:
        respuesta_ia = comando_directo
        if ui_callback:
            ui_callback("🤖 Argus", "Entendido, ejecutando acción solicitada...", "#A8C7FA", nueva_linea=True)
        if modo_voz:
            hablar_no_bloqueante("Entendido, ejecutando acción.")
    else:
        logger.info(f"PENSANDO ({MODO_ACTUAL.upper()})...")

        MODO_ACTUAL = config.estado.modo_actual
        if MODO_ACTUAL in ("general", "chat", "gamer") and not _es_intencion_comando_directo(texto_usuario):
            iniciar_busqueda_anticipada(texto_usuario)

        try:
            fecha_hoy = datetime.datetime.now().strftime("%A, %d de %B de %Y, %H:%M")
            ventanas_abiertas = obtener_ventanas_activas()

            # ─── DATOS DE CLIMA PARA INYECTAR AL CONTEXTO ────────────────────
            texto_clima = ""
            # En modo gamer no se consulta clima para no gastar tiempo de respuesta
            if MODO_ACTUAL != "gamer":
                try:
                    from modulos.web_bridge import obtener_texto_clima_para_contexto
                    resultado_clima = obtener_texto_clima_para_contexto()
                    if resultado_clima:
                        texto_clima = resultado_clima
                except Exception as e:
                    logger.debug(f"No se pudo obtener clima para contexto: {e}")
            # ─── FIN DATOS DE CLIMA ──────────────────────────────────────────

            # Fase D (Punto 3): la CAPACIDAD activa se decide ANTES de elegir
            # perfil y prompt. Un pin del usuario (capacidad_fijada) manda
            # SIEMPRE; si no, en mentor/gamer manda el toggle y en
            # general/chat se activa por el contenido del mensaje.
            capacidad_fijada = config.estado.obtener_capacidad_fijada()
            if capacidad_fijada:
                capacidad_activa = capacidad_fijada
            elif MODO_ACTUAL in ("mentor", "gamer"):
                capacidad_activa = MODO_ACTUAL
            else:
                from modulos.prompts import detectar_capacidad_por_tema
                capacidad_activa = detectar_capacidad_por_tema(texto_usuario) or "general"

            # Señal a la UI: la capacidad activa del turno (para el chip).
            try:
                if ui_callback:
                    ui_callback("__CAPACIDAD_ACTIVA__", capacidad_activa, "#A8C7FA")
            except Exception:
                pass

            from modulos.perfil_usuario import texto_perfil_para_prompt

            # El perfil se consulta según la CAPACIDAD activa (no solo por
            # modo): si la capacidad es gaming, se usa el perfil gamer.
            if capacidad_activa == "gamer":
                from modulos.perfil_gamer import texto_perfil_gamer_para_prompt
                texto_perfil = texto_perfil_gamer_para_prompt()
            else:
                texto_perfil = texto_perfil_para_prompt()

            texto_workspace = f"[WORKSPACE ANCLADO]: {WORKSPACE_ACTUAL}\n" if WORKSPACE_ACTUAL else ""
            texto_snapshot = f"[ESTADO DEL PROYECTO]:\n{SNAPSHOT_ACTUAL}\n\n" if SNAPSHOT_ACTUAL else ""
            texto_doc_volatil = f"[DOCUMENTOS EN MEMORIA]:\n{DOCUMENTO_VOLATIL}\n\n" if DOCUMENTO_VOLATIL else ""

            if capacidad_activa == "mentor":
                contexto_sistema = construir_contexto_sistema(
                    "mentor", fecha_hoy, os.path.expanduser("~"), ventanas_abiertas,
                    texto_workspace, texto_snapshot, texto_doc_volatil, texto_perfil
                )
            elif capacidad_activa == "gamer":
                contexto_sistema = construir_contexto_sistema(
                    "gamer", fecha_hoy, os.path.expanduser("~"), ventanas_abiertas,
                    texto_workspace, texto_snapshot, texto_doc_volatil, texto_perfil
                )
            else:
                contexto_sistema = construir_contexto_sistema(
                    "general", fecha_hoy, os.path.expanduser("~"), ventanas_abiertas,
                    texto_workspace, texto_snapshot, texto_doc_volatil, texto_perfil
                )

            # ─── INYECTAR DATOS DE CLIMA EN EL CONTEXTO ─────────────────────
            if texto_clima:
                contexto_sistema += f"\n\n⚠️ [CLIMA ACTUAL] (Datos en tiempo real):\n{texto_clima}\n[FIN CLIMA]\n"
                contexto_sistema += "\n⚠️ IMPORTANTE: Cuando el usuario pregunte sobre el clima, actividades al aire libre (lavar ropa, salir, etc.), USÁ estos datos. No necesitás buscar en internet para responder sobre el clima actual.\n"

            # ─── RECUPERACIÓN AUTOMÁTICA DE MEMORIA (Fase 4) ───────────────
            # Reutiliza el mismo filtro que el prefetch (mismos modos, sin
            # intenciones de comando directo). El bloque se inyecta como
            # contexto adicional; si no hay nada relevante devuelve "".
            if MODO_ACTUAL in ("general", "chat", "gamer", "mentor") and not _es_intencion_comando_directo(texto_usuario):
                try:
                    from modulos.recuperador_memoria import bloque_memoria_para_contexto
                    texto_memoria = bloque_memoria_para_contexto(texto_usuario)
                    if texto_memoria:
                        contexto_sistema += f"\n\n{texto_memoria}\n"
                except Exception as e:
                    logger.debug(f"No se pudo recuperar memoria para contexto: {e}")

            # Determinar modelo_activo según la selección del usuario o por defecto
            modelo_sel = getattr(config.estado, 'modelo_seleccionado', 'Por Defecto')
            gemini_model_str = "gemini-3.5-flash-lite"
            # La cadena de reserva de modelos Gemini (ante saturación) solo
            # aplica al default global (Fase D), no a selecciones explícitas.
            gemini_usa_cadena = False
            if modelo_sel == "Gemini 3.5 Flash Lite":
                modelo_activo = "gemini"
                gemini_model_str = "gemini-3.5-flash-lite"
            elif modelo_sel == "Gemini 3.1 Flash Lite":
                modelo_activo = "gemini"
                gemini_model_str = "gemini-3.1-flash-lite"
            elif modelo_sel == "Gemini 3.1 Pro (High)":
                modelo_activo = "gemini"
                gemini_model_str = "gemini-3.1-pro-preview"
            elif modelo_sel == "Gemini 3.6 Flash (High)":
                modelo_activo = "gemini"
                gemini_model_str = "gemini-3.6-flash"
            elif modelo_sel == "DeepSeek Reasoner":
                modelo_activo = "deepseek-v4-flash"
            elif modelo_sel == "Groq Llama 3.3 70B":
                modelo_activo = "groq:llama-3.3-70b-versatile"
            elif modelo_sel == "Groq Llama 3.1 8B":
                modelo_activo = "groq:llama-3.1-8b-instant"
            elif modelo_sel == "Groq Qwen 3.6 27B":
                modelo_activo = "groq:qwen/qwen3.6-27b"
            elif modelo_sel == "Groq GPT-OSS 120B":
                modelo_activo = "groq:openai/gpt-oss-120b"
            else:
                # "Por Defecto"/"Auto" → UNA preferencia global (Fase D Punto 2).
                # Ya no depende del modo: se usa config.MODELO_DEFECTO_GLOBAL.
                # Por defecto es Gemini (único con tool-calling MCP), así el
                # MCP no "parpadea" al cambiar de contexto.
                if config.MODELO_DEFECTO_GLOBAL.startswith("Gemini"):
                    modelo_activo = "gemini"
                    gemini_model_str = _modelo_gemini_str(config.MODELO_DEFECTO_GLOBAL)
                    gemini_usa_cadena = True
                elif "DeepSeek" in config.MODELO_DEFECTO_GLOBAL:
                    modelo_activo = "deepseek-v4-flash"
                else:
                    modelo_activo = "gemini"
                    gemini_usa_cadena = True

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

            # ─── MARCADOR DE HERENCIA TEMÁTICA (solo si hay evidencia previa) ───
            # Es una instrucción semántica para el LLM, no una heurística de
            # Python: el modelo decide si el turno continúa el mismo tema.
            if config.estado.obtener_evidencia_web():
                contexto_sistema += "\n\n" + texto_marcador_tema_web_anterior()

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
                    # FIX (12/08/2026): el SDK google-genai 2.11 tiene AFC
                    # (Automatic Function Calling) activo por defecto: consume
                    # las function_calls del stream y las ejecuta internamente,
                    # dejando `respuesta_ia` vacía y disparando el falso
                    # "bloqueo por Safety/PII" + fallback a DeepSeek. Argus
                    # maneja las tools con su propio dispatcher (ronda manual),
                    # así que AFC debe estar DESACTIVADO.
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
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

                verbos_vision = ["captura", "capturá", "capturar", "mirar", "ves", "fijate"]
                objetivos_vision = ["pantalla", "monitor", "1", "2", "uno", "dos", "la 1", "el 1", "la 2", "el 2"]
                # "compara estos objetos" solo en modo gamer para evitar falsos positivos
                if MODO_ACTUAL == "gamer":
                    verbos_vision.append("compara")
                    verbos_vision.append("comparar")
                    objetivos_vision.append("objetos")
                if any(v in texto_usuario_lower for v in verbos_vision) and any(o in texto_usuario_lower for o in objetivos_vision):
                    if ui_callback:
                        ui_callback("⚙️ Sistema", "📸 Capturando pantalla...", "#80868B")
                    winsound.Beep(1500, 100)
                    # Determinar pantalla: si dice "2" explícitamente, usar 2. Sino 1 por defecto.
                    if any(p in texto_usuario_lower for p in ["pantalla 2", "monitor 2", "la 2", "pantalla dos"]):
                        num_pantalla = 2
                    else:
                        num_pantalla = 1
                    img = capturar_pantalla(num_pantalla)
                    if img:
                        import io
                        img_byte_arr = io.BytesIO()
                        img.save(img_byte_arr, format='PNG')
                        img_bytes = img_byte_arr.getvalue()
                        partes_usuario.append(
                            types.Part.from_bytes(data=img_bytes, mime_type='image/png')
                        )

                mensajes_para_gemini.append(types.Content(role='user', parts=partes_usuario))

                # El stream se consume vía _gemini_stream_con_cadena: retry con
                # backoff ante 503/429 transitorios ANTES de emitir el primer
                # chunk, y si el default global sigue saturado prueba el modelo
                # de reserva de la cadena (3.5-flash-lite ↔ 3.6-flash) antes de
                # caer a DeepSeek. Los errores no-transitorios (auth/safety/
                # blocked) se manejan en el except del bucle de abajo.
                buffer_voz = ""
                if ui_callback:
                    ui_callback("🤖 Argus", "", "#A8C7FA", nueva_linea=False)

                try:
                    for chunk in _gemini_stream_con_cadena(
                        gemini_model_str, mensajes_para_gemini, gemini_config,
                        ui_callback=ui_callback, usar_cadena=gemini_usa_cadena,
                    ):
                        try:
                            # DEBUG: Loggear finish_reason SIEMPRE (no solo cuando
                            # es SAFETY/RECITATION) para distinguir un bloqueo real
                            # de un stream vacío por AFC/otras causas.
                            if hasattr(chunk, 'candidates') and chunk.candidates:
                                candidate = chunk.candidates[0]
                                if hasattr(candidate, 'finish_reason') and candidate.finish_reason:
                                    fr_name = candidate.finish_reason.name if hasattr(candidate.finish_reason, 'name') else str(candidate.finish_reason)
                                    fr_val = candidate.finish_reason.value if hasattr(candidate.finish_reason, 'value') else str(candidate.finish_reason)
                                    logger.info(f"📡 Gemini finish_reason={fr_name} (valor={fr_val})")
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
                                        resultado_mcp = _ejecutar_herramienta_mcp(n_func, args)

                                        if resultado_mcp is None:
                                            logger.warning(f"⚠️ Tool '{n_func}' sin dispatcher: está en lista_herramientas_mcp pero no en _ejecutar_herramienta_mcp.")
                                        elif "TIMEOUT" not in str(resultado_mcp):
                                            if ui_callback:
                                                ui_callback("⚙️ Sistema", f"✅ Dato obtenido: {str(resultado_mcp)[:120]}...", "#80868B")
                                        elif "TIMEOUT" in str(resultado_mcp):
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
                                respuesta_ia += texto_chunk
                                texto_visible = ocultador_stream.procesar(texto_chunk)
                                if texto_visible:
                                    print(texto_visible, end='', flush=True)
                                    if ui_callback:
                                        ui_callback("", texto_visible, "#E8EAED", nueva_linea=False)
                                    if modo_voz:
                                        if "argus:" not in respuesta_ia.lower():
                                            buffer_voz += texto_visible
                                            buffer_voz = _procesar_buffer_voz(buffer_voz, forzar=False)
                                        else:
                                            from modulos.audio_custom import detener_voz
                                            detener_voz()
                                            buffer_voz = ""
                        except Exception as e:
                            logger.exception("Error procesando chunk de Gemini")
                            if ui_callback:
                                ui_callback("⚙️ Sistema", f"❌ Error en streaming: {str(e)[:80]}", "#FF4500")
                            break
                except Exception as e:
                    # Errores de cliente (auth/safety/blocked) → mensaje claro,
                    # sin fallback ni retry.
                    if isinstance(e, genai.errors.ClientError):
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
                    elif _es_error_transitorio_gemini(e):
                        # 503 high demand / 429 rate limit: fallback a DeepSeek
                        # en vez de crashear el turno.
                        logger.warning(f"Error transitorio de Gemini: {str(e)[:120]}")
                        respuesta_ia = _fallback_deepseek(
                            contexto_sistema, CONTEXTO_CHAT, texto_usuario,
                            ocultador_stream, modo_voz, ui_callback,
                            motivo="Gemini transitoriamente no disponible",
                        )
                        # Si el fallback produjo respuesta, el turno NO se
                        # considera fallido: la respuesta fluye al chat.
                        if respuesta_ia and not respuesta_ia.startswith("⚠️"):
                            error_ocurrido = False
                        else:
                            error_ocurrido = True
                    else:
                        logger.exception("Error en el bucle de streaming de Gemini")
                        if ui_callback:
                            ui_callback("⚙️ Sistema", f"❌ Error en el streaming: {str(e)[:80]}", "#FF4500")
                        error_ocurrido = True
                finally:
                    # La voz se ata al MODO DE ENTRADA (habló por micrófono),
                    # no a si se usó una tool MCP: siempre que modo_voz, hablamos
                    # el buffer acumulado. (FIX 13/08: antes `not usaste_mcp`
                    # silenciaba la voz cuando el turno consultaba la bóveda.)
                    if modo_voz and buffer_voz.strip() and "argus:" not in respuesta_ia.lower():
                        _procesar_buffer_voz(buffer_voz, forzar=True)

                # ─── FALLBACK POR RESPUESTA VACÍA (Safety/PII blocking) ─────
                if not respuesta_ia and not error_ocurrido and not usaste_mcp:
                    respuesta_ia = _fallback_deepseek(
                        contexto_sistema, CONTEXTO_CHAT, texto_usuario,
                        ocultador_stream, modo_voz, ui_callback,
                        motivo="respuesta vacía / posible bloqueo",
                    )

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
                                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
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
                                        respuesta_ia += texto_chunk
                                        texto_visible = ocultador_stream.procesar(texto_chunk)
                                        if texto_visible:
                                            print(texto_visible, end='', flush=True)
                                            if ui_callback:
                                                ui_callback("", texto_visible, "#E8EAED", nueva_linea=False)
                                            if modo_voz:
                                                buffer_voz_2 += texto_visible
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

            # ─── DEEPSEEK O GROQ ────────────────────────────────────────────────
            else:
                if modelo_activo.startswith("groq:"):
                    if not cliente_groq:
                        raise ValueError("API Key de Groq (GROQ_API_KEY) no configurada en el archivo .env.")
                    client_to_use = cliente_groq
                    api_model_name = modelo_activo.split("groq:")[1]
                    ui_title = "🤖 Argus (Groq)"
                else:
                    client_to_use = cliente_deepseek
                    api_model_name = modelo_activo
                    ui_title = "🤖 Argus"

                mensajes_ds = [{"role": "system", "content": contexto_sistema}]
                for msg in CONTEXTO_CHAT:
                    rol_ds = "assistant" if msg['role'] == "model" else "user"
                    texto_historico = "".join([p for p in msg['parts'] if isinstance(p, str)])
                    mensajes_ds.append({"role": rol_ds, "content": texto_historico})
                mensajes_ds.append({"role": "user", "content": texto_usuario})

                if ui_callback:
                    ui_callback(ui_title, "", "#A8C7FA", nueva_linea=False)

                try:
                    parametros_api = {"model": api_model_name, "messages": mensajes_ds, "stream": True}
                    response = client_to_use.chat.completions.create(**parametros_api)
                except Exception as e:
                    err_str = str(e)
                    if "RateLimitError" in err_str or "429" in err_str:
                        if ui_callback:
                            ui_callback("⚙️ Sistema", f"⚠️ Rate limit en {ui_title}. Esperá un momento.", "#FFA500")
                    elif "AuthenticationError" in err_str or "401" in err_str:
                        if ui_callback:
                            ui_callback("⚙️ Sistema", f"❌ Error de autenticación en {ui_title}.", "#FF4500")
                    else:
                        if ui_callback:
                            ui_callback("⚙️ Sistema", f"❌ Error en {ui_title}: {err_str[:100]}", "#FF4500")
                    logger.exception(f"Error al iniciar generación en {ui_title}")
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
                                respuesta_ia += texto_chunk
                                texto_visible = ocultador_stream.procesar(texto_chunk)
                                if texto_visible:
                                    print(texto_visible, end='', flush=True)
                                    if ui_callback:
                                        ui_callback("", texto_visible, "#E8EAED", nueva_linea=False)
                                    if modo_voz:
                                        buffer_voz_ds += texto_visible
                                        buffer_voz_ds = _procesar_buffer_voz(buffer_voz_ds, forzar=False)
                        except Exception as e:
                            logger.exception(f"Error procesando chunk de {ui_title}")
                            if ui_callback:
                                ui_callback("⚙️ Sistema", f"❌ Error en streaming: {str(e)[:80]}", "#FF4500")
                            break
                except Exception as e:
                    logger.exception(f"Error en el bucle de streaming de {ui_title}")
                    if ui_callback:
                        ui_callback("⚙️ Sistema", f"❌ Error en el streaming: {str(e)[:80]}", "#FF4500")
                    error_ocurrido = True
                finally:
                    if modo_voz and buffer_voz_ds.strip():
                        _procesar_buffer_voz(buffer_voz_ds, forzar=True)

            print("\n---")
            resto_stream = ocultador_stream.finalizar()
            if resto_stream:
                print(resto_stream, end='', flush=True)
                if ui_callback:
                    ui_callback("", resto_stream, "#E8EAED", nueva_linea=False)
                # FIX (13/08): el texto retenido por el ocultador (respuestas de
                # una sola línea sin \n) salía por finalizar() pero NUNCA se
                # hablaba → el TTS no sonaba en respuestas cortas por voz.
                # Se habla directamente, sin depender del buffer del proveedor.
                if modo_voz:
                    _procesar_buffer_voz(resto_stream, forzar=True)
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
        comando_legacy = procesar_acciones_ia(respuesta_ia, texto_usuario, ui_callback, modo_voz)

        if comando_legacy == "INTERRUPTED":
            return

        # ── Señal estructurada de decisión web (C+D) ─────────────────────────
        # El LLM decide [WEB: SI/NO] y arma la consulta; Python solo ejecuta.
        # Durante la transición, `buscar:` legacy sigue siendo válido (fusión).
        senal_web = parsear_senal_web(respuesta_ia)
        draft_limpio = senal_web['respuesta_limpia']
        comando_busqueda, warning_senal = fusionar_comando_busqueda(senal_web, comando_legacy)
        if warning_senal:
            logger.warning(f"⚠️ {warning_senal}")

        if comando_busqueda and getattr(config.estado, 'modo_actual', 'general') in ("general", "chat", "gamer", "mentor"):
            if ui_callback:
                # La respuesta aún visible en la UI pasa a ser PROVISIONAL:
                # será reemplazada por la respuesta verificada (o desmarcada).
                ui_callback("__MARCAR_PROVISIONAL__", "", "#FFA500")
            if ui_callback:
                ui_callback("⚙️ Sistema", f"🌍 Buscando en internet: {comando_busqueda}", "#80868B")
            datos_encontrados = buscar_en_internet(comando_busqueda, reciente=skill_activa)

            sin_evidencia = (
                "No se encontraron" in datos_encontrados
                or "error de conexión" in datos_encontrados.lower()
            )

            # ── CONSIGNA ESTRICTA DE EVIDENCIA PARA LA SEGUNDA GENERACIÓN ──────
            # Establece la distinción confirmado/inferido/no-encontrado/contradictorio
            # y la regla "no encontrar ≠ no existe". Se usa tanto con resultados
            # como en el caso sin evidencia.
            reglas_evidencia = (
                "Recibiste los resultados de una búsqueda web para la consulta del usuario. "
                "Respondé aplicando estrictamente estas reglas:\n"
                "- Basá tu respuesta PRIORITARIAMENTE en la evidencia web proporcionada. "
                "No uses tu conocimiento interno para completar información que falta.\n"
                "- Diferencialo claramente: dato EXPLÍCITAMENTE confirmado por una fuente vs dato INFERIDO por vos. "
                "Solo lo explícitamente confirmado se presenta como hecho.\n"
                "- Tu respuesta PREVIA de este turno (y cualquier afirmación del historial) NO es evidencia. "
                "La única evidencia externa para verificar son los resultados de búsqueda actuales "
                "y la evidencia web de consultas anteriores incluida más abajo.\n"
                "- Si un dato no está respaldado por ninguna fuente (ej. el tercer puesto de un podio), "
                "respondé literalmente: 'No pude confirmarlo con las fuentes encontradas.' NO lo inventes.\n"
                "- NUNCA interpretes la ausencia de una mención en los resultados como prueba de que ese dato no existe. "
                "Si no lo encontraste, decilo; no digas que no existe.\n"
                "- Si las fuentes se contradicen, señalalo ('fuentes contradictorias') y describí qué sostiene cada una.\n"
                "- Priorizá las fuentes oficiales o especializadas cuando existan.\n"
                "- Cité/identifiqué la fuente (dominio) y la fecha de cada afirmación importante.\n"
            )

            if sin_evidencia:
                if ui_callback:
                    ui_callback("⚙️ Sistema", "⚠️ No se encontraron fuentes. La respuesta debe expresar incertidumbre.", "#FFA500")
                bloque_web = (
                    f"[RESULTADOS DE BÚSQUEDA]\n{datos_encontrados}\n\n"
                    "La búsqueda no devolvió evidencia suficiente para este dato actualizado.\n"
                    "No respondas afirmando el dato como verdadero: "
                    "decí 'No pude encontrar fuentes suficientes para confirmar ese dato.' "
                    "NO afirmes que el dato no existe ni que la información está ausente de la web.\n"
                )
            else:
                bloque_web = f"[RESULTADOS DE BÚSQUEDA]\n{datos_encontrados}\n"

            # Evidencia de turnos anteriores: se antepone a los resultados
            # actuales para que un follow-up pueda re-verificar contra fuentes
            # reales. Viaja siempre etiquetada como EVIDENCIA (nunca como
            # respuesta del asistente).
            bloque_evidencia_anterior = construir_bloque_evidencia_anterior(
                config.estado.obtener_evidencia_web()
            )

            try:
                config_web = types.GenerateContentConfig(
                    system_instruction=contexto_sistema,
                    temperature=0.1,
                    max_output_tokens=8192,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                    safety_settings=[
                        types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                        types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                        types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                        types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                        types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_CIVIC_INTEGRITY, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                    ]
                )
                mensajes_secundarios = construir_mensajes_segunda_generacion(
                    _convertir_contexto_a_contents(CONTEXTO_CHAT),
                    texto_usuario,
                    f"{reglas_evidencia}\n{bloque_evidencia_anterior}\n{bloque_web}",
                )
                segunda_respuesta = cliente_genai.models.generate_content_stream(
                    model="gemini-3.1-flash-lite",
                    contents=mensajes_secundarios,
                    config=config_web
                )
                respuesta_final = ""
                buffer_voz_web_raw = ""
                for chunk in segunda_respuesta:
                    if hasattr(chunk, 'text') and chunk.text:
                        respuesta_final += chunk.text
                        # NO se streamea visualmente la 2da generación: la burbuja
                        # provisional se reemplaza al final con la respuesta verificada.
                        if modo_voz:
                            buffer_voz_web_raw += chunk.text
                # La 2ª generación usa el MISMO contexto de sistema que incluye el
                # protocolo de señal; por eso puede re-emitir `[WEB: ...]`/
                # `[CONSULTA: ...]`. Se sanea siempre (UI, TTS y persistencia).
                respuesta_final_limpia = limpiar_respuesta_web(respuesta_final)
                if modo_voz:
                    texto_voz = limpiar_respuesta_web(buffer_voz_web_raw)
                    if texto_voz.strip():
                        _procesar_buffer_voz(texto_voz, forzar=True)
                    elif draft_limpio and draft_limpio.strip():
                        # A3: si la 2ª generación quedó vacía, hablamos el
                        # borrador provisional (evita "responde pero no habla").
                        _procesar_buffer_voz(draft_limpio, forzar=True)
                # Reemplazar el borrador provisional por la respuesta verificada,
                # o desmarcarlo si la segunda generación quedó vacía.
                if ui_callback:
                    tipo_presentacion, texto_presentacion = decidir_contenido_presentacion(
                        draft_limpio, respuesta_final_limpia
                    )
                    if tipo_presentacion == "verificada":
                        ui_callback("__RESPUESTA_VERIFICADA__", texto_presentacion, "#E8EAED")
                    else:
                        ui_callback("__CANCELAR_PROVISIONAL__", "")
                # Persistir la evidencia de ESTE turno para los próximos follow-ups.
                # Solo se persiste evidencia real (no el bloque de "sin evidencia").
                if not sin_evidencia:
                    config.estado.agregar_evidencia_web(bloque_web)
                config.estado.agregar_mensaje_chat({'role': 'user', 'parts': [texto_usuario]})
                config.estado.agregar_mensaje_chat(armar_mensaje_modelo_persistido(draft_limpio, respuesta_final_limpia))
                return
            except Exception as e:
                logger.exception("Error en búsqueda web secundaria")
                if ui_callback:
                    ui_callback("⚙️ Sistema", f"❌ Error al procesar resultados web: {str(e)[:100]}", "#FF4500")
                    # Sin respuesta verificada: desmarcar la provisional (queda el borrador).
                    ui_callback("__CANCELAR_PROVISIONAL__", "")

    if modo_voz and comando_directo:
        hablar_no_bloqueante(respuesta_ia)

    if respuesta_ia and not error_ocurrido:
        config.estado.agregar_mensaje_chat({'role': 'user', 'parts': [texto_usuario]})
        config.estado.agregar_mensaje_chat(armar_mensaje_modelo_persistido(limpiar_respuesta_web(respuesta_ia)))


def enviar_a_gemini(texto_usuario, modo_voz=False, ui_callback=None):
    """
    Punto de entrada único de todos los turnos (texto, voz, gamepad, wake
    word). Adquiere el RLock de serialización para que los turnos no se
    pisen entre sí y genera un turno_id temporal que acompaña a la UI.
    """
    with _RLOCK_PROC:
        turno_id = next(_CONTADOR_TURNOS)
        _procesar_mensaje(texto_usuario, modo_voz=modo_voz, ui_callback=ui_callback, turno_id=turno_id)


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