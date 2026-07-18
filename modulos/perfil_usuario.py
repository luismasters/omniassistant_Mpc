"""
Módulo de perfil de usuario persistente para Argus.

Mantiene un perfil en JSON (perfil_usuario.json) que se actualiza automáticamente
analizando la conversación normal con un LLM (Gemini Flash-Lite). Es un sistema
separado de la bóveda de ChromaDB (modulos/memoria.py).

Estructura del perfil:
{
    "funcional": {
        "identidad": "",
        "proyecto_actual": "",
        "hardware_relevante": "",
        "preferencias_comunicacion": "",
        "rutina_uso": ""
    },
    "vida_personal": [
        {"tema": "salud", "contenido": "string", "actualizado": "YYYY-MM-DD"}
    ]
}
"""

import json
import os
import re
import threading
import datetime

from modulos.logger import logger

# ─── CONSTANTES ───────────────────────────────────────────────────────────────

# Ruta al archivo de perfil (raíz del proyecto)
RUTA_PERFIL = os.path.join(os.path.dirname(os.path.dirname(__file__)), "perfil_usuario.json")

# Claves FIJAS del apartado funcional. La IA de extracción solo puede completar
# el CONTENIDO de estas claves, nunca agregar claves nuevas.
ESQUEMA_FUNCIONAL_CLAVES = [
    "identidad",
    "proyecto_actual",
    "hardware_relevante",
    "preferencias_comunicacion",
    "rutina_uso"
]

# Umbral de caracteres para activar consolidación (~2000 chars serializado)
UMBRAL_CONSOLIDACION = 2000

# Umbral de importancia mínima para procesar un hecho (0-100)
UMBRAL_IMPORTANCIA = 60

# Umbral de mensajes para disparar extracción automática desde main_gui.py
UMBRAL_MENSAJES_EXTRACCION = 20

# Patrón para detectar secretos/credenciales en valores extraídos
_PATRON_SECRETOS = re.compile(
    r'(contraseña|password|api.?key|token|pin|sk-[a-zA-Z0-9]{20,}|'
    r'[A-Za-z0-9]{20,})',
    re.IGNORECASE
)

# Lock thread-safe para acceso a disco
_lock_perfil = threading.Lock()


# ─── ESTRUCTURA POR DEFECTO ──────────────────────────────────────────────────

def _perfil_vacio() -> dict:
    """Devuelve un perfil con la estructura canónica, todo vacío."""
    return {
        "funcional": {clave: "" for clave in ESQUEMA_FUNCIONAL_CLAVES},
        "vida_personal": []
    }


# ─── CARGA / GUARDADO (THREAD-SAFE) ─────────────────────────────────────────

def cargar_perfil() -> dict:
    """
    Lee el perfil desde disco. Si el archivo no existe, está corrupto o tiene
    una estructura inválida, devuelve un perfil vacío.
    Thread-safe con _lock_perfil.
    """
    with _lock_perfil:
        if not os.path.exists(RUTA_PERFIL):
            logger.info("perfil_usuario.json no encontrado. Creando perfil vacío.")
            perfil = _perfil_vacio()
            _escribir_perfil_sin_lock(perfil)
            return perfil
        try:
            with open(RUTA_PERFIL, "r", encoding="utf-8") as f:
                perfil = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.exception(f"Error leyendo perfil_usuario.json: {e}. Reiniciando perfil.")
            perfil = _perfil_vacio()
            _escribir_perfil_sin_lock(perfil)
            return perfil

    # Sanitizar estructura por si el archivo vino corrupto
    return _sanitizar_perfil_completo(perfil)


def guardar_perfil(perfil: dict) -> None:
    """
    Guarda el perfil en disco de forma thread-safe.
    Antes de escribir, si el JSON supera UMBRAL_CONSOLIDACION caracteres,
    ejecuta consolidación automática.
    """
    perfil = _sanitizar_perfil_completo(perfil)

    # Consolidación automática si está muy grande
    if len(json.dumps(perfil, ensure_ascii=False)) > UMBRAL_CONSOLIDACION:
        try:
            perfil = consolidar_perfil(perfil)
        except Exception as e:
            logger.exception(f"Error en consolidación de perfil: {e}")

    with _lock_perfil:
        _escribir_perfil_sin_lock(perfil)


def _escribir_perfil_sin_lock(perfil: dict) -> None:
    """Escribe el perfil a disco. NO es thread-safe — llamar con _lock_perfil."""
    try:
        with open(RUTA_PERFIL, "w", encoding="utf-8") as f:
            json.dump(perfil, f, ensure_ascii=False, indent=2)
        logger.debug("Perfil de usuario guardado correctamente.")
    except OSError as e:
        logger.exception(f"Error escribiendo perfil_usuario.json: {e}")


# ─── SANITIZACIÓN ────────────────────────────────────────────────────────────

def _sanitizar_perfil_completo(perfil: dict) -> dict:
    """
    Asegura que el perfil tenga la estructura canónica.
    - funcional: solo las claves del esquema (descarta claves extra).
    - vida_personal: lista de dicts con "tema", "contenido", "actualizado".
    Si perfil no es dict, devuelve perfil vacío.
    """
    if not isinstance(perfil, dict):
        return _perfil_vacio()

    # Sanitizar funcional
    funcional_original = perfil.get("funcional", {})
    if not isinstance(funcional_original, dict):
        funcional_original = {}
    funcional_limpio = {}
    for clave in ESQUEMA_FUNCIONAL_CLAVES:
        valor = funcional_original.get(clave, "")
        funcional_limpio[clave] = valor if isinstance(valor, str) else ""

    # Sanitizar vida_personal
    vida_original = perfil.get("vida_personal", [])
    if not isinstance(vida_original, list):
        vida_original = []
    vida_limpia = []
    for entrada in vida_original:
        if isinstance(entrada, dict) and "tema" in entrada:
            vida_limpia.append({
                "tema": str(entrada.get("tema", "")),
                "contenido": str(entrada.get("contenido", "")),
                "actualizado": str(entrada.get("actualizado", ""))
            })

    return {"funcional": funcional_limpio, "vida_personal": vida_limpia}


def _sanitizar_funcional(perfil: dict) -> dict:
    """
    Filtra el apartado funcional del perfil para que SOLO contenga las claves
    definidas en ESQUEMA_FUNCIONAL_CLAVES. Elimina cualquier clave extra que
    el modelo de IA haya generado incorrectamente.
    No modifica vida_personal.
    """
    perfil = _sanitizar_perfil_completo(perfil)
    # _sanitizar_perfil_completo ya hizo el filtrado, pero reiteramos por claridad
    funcional_limpio = {}
    for clave in ESQUEMA_FUNCIONAL_CLAVES:
        funcional_limpio[clave] = perfil["funcional"].get(clave, "")
    perfil["funcional"] = funcional_limpio
    return perfil


# ─── FUSIÓN DE VIDA PERSONAL ────────────────────────────────────────────────

def _normalizar_tema(tema: str) -> str:
    """Normaliza un tema para comparación: minúsculas, sin espacios extras."""
    return tema.strip().lower()


def _fusionar_vida_personal(vida_existente: list, nuevas_entradas: list) -> list:
    """
    Fusiona nuevas entradas de vida_personal en la lista existente.

    - Si el tema YA EXISTE, actualiza 'contenido' y 'actualizado' en la misma
      entrada (nunca crea duplicados).
    - Si el tema es nuevo, agrega una entrada nueva.

    Args:
        vida_existente: lista actual de entradas en el perfil.
        nuevas_entradas: lista de entradas propuestas por la IA.

    Returns:
        Lista fusionada de entradas.
    """
    resultado = list(vida_existente)  # copia

    for nueva in nuevas_entradas:
        if not isinstance(nueva, dict) or "tema" not in nueva:
            continue
        tema_nuevo = _normalizar_tema(nueva.get("tema", ""))
        if not tema_nuevo:
            continue

        # Buscar si el tema ya existe
        encontrado = False
        for i, existente in enumerate(resultado):
            if _normalizar_tema(existente.get("tema", "")) == tema_nuevo:
                # Fusionar: actualizar contenido y fecha
                resultado[i]["contenido"] = nueva.get("contenido", resultado[i].get("contenido", ""))
                resultado[i]["actualizado"] = nueva.get("actualizado",
                    datetime.date.today().strftime("%Y-%m-%d"))
                encontrado = True
                break

        if not encontrado:
            # Crear entrada nueva
            resultado.append({
                "tema": nueva.get("tema", "").strip(),
                "contenido": nueva.get("contenido", ""),
                "actualizado": nueva.get("actualizado",
                    datetime.date.today().strftime("%Y-%m-%d"))
            })

    return resultado


# ─── FILTRO DE SECRETOS ──────────────────────────────────────────────────────

def _es_secreto(valor: str) -> bool:
    """
    Verifica si un valor contiene patrones de credenciales/tokens/contraseñas.
    Si es así, se descarta sin persistir. Se loguea sin incluir el valor real.
    """
    if not isinstance(valor, str):
        return False
    return bool(_PATRON_SECRETOS.search(valor))


# ─── EXTRACCIÓN CON LLM (NUEVA ARQUITECTURA: HECHOS ATÓMICOS) ────────────────

def extraer_hechos_candidatos(ultimos_mensajes: list) -> list:
    """
    Analiza los últimos mensajes de la conversación usando Gemini Flash-Lite
    y devuelve una LISTA de hechos candidatos (no reescribe el perfil entero).

    Cada hecho tiene la forma:
    {"tipo": "perfil_funcional" | "perfil_vida" | "proyecto",
     "clave_o_tema": "string",
     "valor": "string",
     "importancia": 0-100}

    Si no hay nada relevante, devuelve lista vacía [].

    Parseo defensivo: despoja ```json / ```, try/except en json.loads.
    Si falla el parseo, devuelve [] (no propaga la excepción).
    """
    if not ultimos_mensajes:
        return []

    from modulos.ia import cliente_genai
    from google.genai import types

    conversacion = "\n".join(str(m) for m in ultimos_mensajes[-30:])

    prompt = (
        "Eres un extractor de hechos de perfil de usuario. Analizá la conversación "
        "y extraé SOLO información relevante sobre el usuario.\n\n"
        "Devolvé una LISTA JSON de hechos. Cada hecho debe tener esta forma:\n"
        '  {"tipo": "perfil_funcional" | "perfil_vida" | "proyecto",\n'
        '   "clave_o_tema": "string",\n'
        '   "valor": "string",\n'
        '   "importancia": 0-100}\n\n'
        "REGLAS:\n"
        "1. 'perfil_funcional': clave_o_tema debe ser UNA de estas 5 claves exactas:\n"
        "   identidad, proyecto_actual, hardware_relevante, preferencias_comunicacion, "
        "rutina_uso. valor es la info nueva.\n"
        "2. 'perfil_vida': clave_o_tema es el tema libre (salud, actividad_fisica, "
        "vehiculo, familia, mascotas, gustos, etc.). valor describe el hecho.\n"
        "3. 'proyecto': para información sobre el proyecto de software en el que "
        "el usuario está trabajando (tecnologías, features, bugs, etc.). "
        "clave_o_tema no aplica, dejalo vacío. valor describe el hecho.\n"
        "4. 'importancia': 0-100. 0-30 = trivial/menciones al pasar, "
        "40-60 = información útil, 70-100 = información muy relevante.\n"
        "5. Si el usuario menciona algo de pasada sin dar detalle concreto, "
        "NO incluir ese hecho.\n"
        "6. Si no hay información relevante nueva, devolvé [] (lista vacía).\n"
        "7. Devolvé SOLO el JSON, sin explicaciones ni markdown.\n\n"
        f"Conversación reciente:\n{conversacion}\n\n"
        "Lista JSON de hechos:"
    )

    try:
        respuesta = cliente_genai.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=2048
            )
        )
        texto_respuesta = respuesta.text.strip()

        # Parseo defensivo: despojar ```json / ``` si vienen envueltos en markdown
        if texto_respuesta.startswith("```"):
            # Buscar la primera línea que no sea ``` después del opening
            lineas = texto_respuesta.split("\n")
            if lineas[0].strip().startswith("```"):
                lineas = lineas[1:]  # sacar la línea de apertura ``` o ```json
            # Sacar el ``` de cierre si existe
            if lineas and lineas[-1].strip() == "```":
                lineas = lineas[:-1]
            texto_respuesta = "\n".join(lineas).strip()

        hechos = json.loads(texto_respuesta)
        if not isinstance(hechos, list):
            logger.warning("extraer_hechos_candidatos: respuesta no es una lista, se ignora")
            return []

        # Validar estructura básica de cada hecho
        hechos_validos = []
        for hecho in hechos:
            if isinstance(hecho, dict) and "tipo" in hecho and "valor" in hecho:
                # Asegurar campos por defecto
                hecho.setdefault("clave_o_tema", "")
                hecho.setdefault("importancia", 50)
                hechos_validos.append(hecho)
            else:
                logger.debug(f"extraer_hechos_candidatos: hecho mal formado descartado: {hecho}")

        return hechos_validos

    except Exception as e:
        logger.exception(f"Error extrayendo hechos candidatos: {e}")
        return []


# ─── RUTEO DE HECHOS ─────────────────────────────────────────────────────────

def rutear_hecho(hecho: dict, perfil: dict) -> dict:
    """
    Procesa un hecho candidato y actualiza el perfil en memoria según su tipo.
    - Filtra por importancia (>= UMBRAL_IMPORTANCIA).
    - Filtra secretos (ANTES del ruteo, aplica a todos los tipos).
    - Rutea por tipo: perfil_funcional, perfil_vida, proyecto.

    Args:
        hecho: dict con "tipo", "clave_o_tema", "valor", "importancia".
        perfil: dict con el perfil actual (se modifica in-place y se devuelve).

    Returns:
        dict con el perfil actualizado (modificado in-place).
    """
    # ─── Filtro de importancia ────────────────────────────────────────────
    importancia = hecho.get("importancia", 0)
    if importancia < UMBRAL_IMPORTANCIA:
        logger.debug(
            f"Hecho '{hecho.get('tipo', '?')}' con importancia {importancia} "
            f"< umbral {UMBRAL_IMPORTANCIA}, descartado"
        )
        return perfil

    valor = str(hecho.get("valor", "")).strip()
    if not valor:
        return perfil

    # ─── Filtro de exclusión de secretos (ANTES del ruteo) ────────────────
    if _es_secreto(valor):
        logger.info("contenido sensible descartado (no se persiste)")
        return perfil

    tipo = hecho.get("tipo", "")
    clave_o_tema = str(hecho.get("clave_o_tema", "")).strip()

    # ─── Ruteo por tipo ───────────────────────────────────────────────────
    if tipo == "perfil_funcional":
        # Validar que clave_o_tema sea una de las 5 claves del esquema
        if clave_o_tema in ESQUEMA_FUNCIONAL_CLAVES:
            perfil["funcional"][clave_o_tema] = valor
            logger.debug(f"Perfil funcional actualizado: {clave_o_tema} = {valor[:60]}")
        else:
            logger.debug(
                f"Clave '{clave_o_tema}' no está en el esquema funcional, "
                f"se ignora (solo válidas: {ESQUEMA_FUNCIONAL_CLAVES})"
            )

    elif tipo == "perfil_vida":
        # Crear entrada de vida_personal y fusionar
        nueva_entrada = {
            "tema": clave_o_tema,
            "contenido": valor,
            "actualizado": datetime.date.today().strftime("%Y-%m-%d")
        }
        vida_existente = perfil.get("vida_personal", [])
        perfil["vida_personal"] = _fusionar_vida_personal(vida_existente, [nueva_entrada])

    elif tipo == "proyecto":
        # Llamar directo a guardar_recuerdo() de memoria.py
        try:
            from modulos.memoria import guardar_recuerdo
            guardar_recuerdo(
                texto_a_guardar=valor,
                etiqueta_tema="Extracción automática de perfil"
            )
            logger.debug(f"Hecho de proyecto guardado en bóveda: {valor[:60]}")
        except Exception as e:
            logger.exception(f"Error guardando hecho de proyecto en bóveda: {e}")

    else:
        logger.debug(f"Tipo de hecho desconocido: '{tipo}', se ignora")

    return perfil


# ─── ORQUESTADOR ──────────────────────────────────────────────────────────────

def extraer_y_procesar_sesion(ultimos_mensajes: list) -> None:
    """
    Función orquestadora: punto de entrada único tanto para el disparo automático
    como para el botón manual.

    Flujo:
    1. Llama a extraer_hechos_candidatos() para obtener lista de hechos.
    2. Itera cada hecho: filtra por importancia, filtra secretos, rutea.
    3. Guarda el perfil actualizado en disco.
    4. Si excede el tope de consolidación, consolida y guarda de nuevo.

    Args:
        ultimos_mensajes: lista de strings con los mensajes más recientes.
    """
    if not ultimos_mensajes:
        logger.debug("extraer_y_procesar_sesion: sin mensajes, se omite")
        return

    logger.debug(f"📋 Extrayendo hechos de {len(ultimos_mensajes)} mensajes...")

    try:
        # 1. Extraer hechos candidatos (llamada a Gemini)
        hechos = extraer_hechos_candidatos(ultimos_mensajes)

        if not hechos:
            logger.debug("No se encontraron hechos relevantes en esta tanda")
            return

        logger.info(f"📋 {len(hechos)} hecho(s) candidato(s) extraídos")

        # 2. Cargar perfil actual
        perfil = cargar_perfil()

        # 3. Rutear cada hecho (filtros incluidos dentro de rutear_hecho)
        cambios = 0
        for hecho in hechos:
            perfil_antes = json.dumps(perfil, ensure_ascii=False)
            perfil = rutear_hecho(hecho, perfil)
            if json.dumps(perfil, ensure_ascii=False) != perfil_antes:
                cambios += 1

        if cambios == 0:
            logger.debug("Extracción de perfil: sin cambios que persistir")
            return

        # 4. Guardar perfil (la consolidación automática ocurre dentro de guardar_perfil si hace falta)
        guardar_perfil(perfil)
        logger.info(f"📋 Perfil actualizado ({cambios} cambio(s) aplicado(s))")

    except Exception as e:
        logger.exception(f"Error en extraer_y_procesar_sesion: {e}")


# ─── EXTRACCIÓN CON LLM (ANTIGUA, reescribía el perfil entero) ────────────────
# Se mantiene temporalmente por compatibilidad con el bloque OLD en ia.py.
# Será eliminada cuando se remueva ese bloque.

def extraer_hechos_de_sesion(ultimos_mensajes: list, perfil_actual: dict) -> dict:
    """
    [DEPRECADO] Analiza los últimos mensajes de la conversación usando Gemini Flash-Lite
    y devuelve el perfil actualizado. Reemplazado por extraer_hechos_candidatos() + rutear_hecho().

    Args:
        ultimos_mensajes: lista de strings con los mensajes más recientes.
        perfil_actual: dict con el perfil existente.

    Returns:
        dict con el perfil actualizado (ya sanitizado y fusionado).
    """
    if not ultimos_mensajes:
        return _sanitizar_perfil_completo(perfil_actual)

    from modulos.ia import cliente_genai
    from google.genai import types

    hoy = datetime.date.today().strftime("%Y-%m-%d")
    perfil_json = json.dumps(perfil_actual, ensure_ascii=False, indent=2)
    conversacion = "\n".join(str(m) for m in ultimos_mensajes[-50:])

    prompt = (
        "Eres un extractor de perfil de usuario. Tu tarea es analizar la conversación "
        "y el perfil actual, y devolver SOLO un JSON con el perfil actualizado.\n\n"
        "REGLAS:\n"
        "1. El JSON debe tener EXACTAMENTE esta estructura, sin claves extra:\n"
        '   {\n'
        '     "funcional": {\n'
        '       "identidad": "",\n'
        '       "proyecto_actual": "",\n'
        '       "hardware_relevante": "",\n'
        '       "preferencias_comunicacion": "",\n'
        '       "rutina_uso": ""\n'
        '     },\n'
        '     "vida_personal": [\n'
        '       {"tema": "string", "contenido": "string", "actualizado": "YYYY-MM-DD"}\n'
        '     ]\n'
        '   }\n'
        "2. En 'funcional', SOLO podes completar el CONTENIDO de esas 5 claves. "
        "NO agregues claves nuevas.\n"
        "3. En 'vida_personal', cada entrada tiene tema libre (salud, "
        "actividad_fisica, vehiculo, mascotas, etc.). Si encuentras info de un "
        "tema que ya existe, actualiza su contenido. Si es un tema nuevo, agrega "
        "una entrada nueva.\n"
        "4. Si no hay información nueva relevante, devolvé el perfil actual sin cambios.\n"
        "5. Devolvé SOLO el JSON, sin explicaciones ni markdown.\n\n"
        f"Perfil actual:\n{perfil_json}\n\n"
        f"Conversación reciente:\n{conversacion}\n\n"
        "JSON actualizado:"
    )

    try:
        respuesta = cliente_genai.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=2048
            )
        )
        texto_respuesta = respuesta.text.strip()
        # Limpiar posibles delimitadores markdown
        if texto_respuesta.startswith("```"):
            texto_respuesta = texto_respuesta.split("\n", 1)[-1]
        if texto_respuesta.endswith("```"):
            texto_respuesta = texto_respuesta.rsplit("```", 1)[0]
        texto_respuesta = texto_respuesta.strip()

        perfil_nuevo = json.loads(texto_respuesta)
        if not isinstance(perfil_nuevo, dict):
            raise ValueError("Respuesta no es un dict")

    except Exception as e:
        logger.exception(f"Error extrayendo hechos de sesión: {e}")
        # Si falla la IA, devolver perfil actual sin cambios
        return _sanitizar_perfil_completo(perfil_actual)

    # Sanitizar: limpiar claves extra del modelo
    perfil_nuevo = _sanitizar_funcional(perfil_nuevo)

    # Fusionar vida_personal (evitar duplicados)
    vida_actual = perfil_actual.get("vida_personal", [])
    vida_nueva = perfil_nuevo.get("vida_personal", [])
    perfil_nuevo["vida_personal"] = _fusionar_vida_personal(vida_actual, vida_nueva)

    return perfil_nuevo


# ─── CONSOLIDACIÓN ───────────────────────────────────────────────────────────

def consolidar_perfil(perfil: dict) -> dict:
    """
    Reescritura compacta del perfil mediante una segunda llamada a la IA.
    Fusiona redundancias, poda información vieja o contradicha por datos más
    recientes. Máximo ~15 líneas de contenido total tras consolidar.

    Esta función es reutilizable y no está mezclada con la lógica de extracción
    incremental.

    Args:
        perfil: dict con el perfil actual (potencialmente grande).

    Returns:
        dict con el perfil consolidado (más compacto).
    """
    from modulos.ia import cliente_genai
    from google.genai import types

    perfil_json = json.dumps(perfil, ensure_ascii=False, indent=2)
    hoy = datetime.date.today().strftime("%Y-%m-%d")

    prompt = (
        "Eres un consolidado de perfil de usuario. Tu tarea es tomar un perfil "
        "de usuario y reescribirlo de forma MÁS COMPACTA, fusionando redundancias "
        "y podando información vieja o contradicha por datos más recientes.\n\n"
        "REGLAS:\n"
        "1. Mantené la misma estructura JSON exacta.\n"
        '   {\n'
        '     "funcional": { "identidad": "", "proyecto_actual": "", '
        '"hardware_relevante": "", "preferencias_comunicacion": "", "rutina_uso": "" },\n'
        '     "vida_personal": [\n'
        '       {"tema": "string", "contenido": "string", "actualizado": "YYYY-MM-DD"}\n'
        '     ]\n'
        '   }\n'
        "2. Máximo ~15 líneas de contenido total en todo el perfil.\n"
        "3. Si hay información contradictoria, quedate con la más reciente.\n"
        "4. Si hay temas repetidos en vida_personal, fusionalos en una sola entrada.\n"
        "5. Conservá solo lo esencial para que el asistente conozca al usuario.\n"
        "6. Devolvé SOLO el JSON, sin explicaciones ni markdown.\n\n"
        f"Perfil a consolidar:\n{perfil_json}\n\n"
        "JSON consolidado:"
    )

    try:
        respuesta = cliente_genai.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=2048
            )
        )
        texto_respuesta = respuesta.text.strip()
        if texto_respuesta.startswith("```"):
            texto_respuesta = texto_respuesta.split("\n", 1)[-1]
        if texto_respuesta.endswith("```"):
            texto_respuesta = texto_respuesta.rsplit("```", 1)[0]
        texto_respuesta = texto_respuesta.strip()

        perfil_consolidado = json.loads(texto_respuesta)
        if not isinstance(perfil_consolidado, dict):
            raise ValueError("Respuesta no es un dict")

        # Sanitizar
        perfil_consolidado = _sanitizar_funcional(perfil_consolidado)
        return perfil_consolidado

    except Exception as e:
        logger.exception(f"Error consolidando perfil: {e}")
        return _sanitizar_perfil_completo(perfil)


# ─── TEXTO PARA INYECCIÓN EN PROMPTS ─────────────────────────────────────────

def texto_perfil_para_prompt() -> str:
    """
    Convierte el perfil actual en un bloque de texto plano para inyectar en
    los prompts del sistema (obtener_prompt_general, etc.).

    Si el perfil está vacío (todo cadenas vacías y sin vida_personal),
    devuelve cadena vacía.
    """
    perfil = cargar_perfil()
    lineas = []

    funcional = perfil.get("funcional", {})
    tiene_funcional = any(v.strip() for v in funcional.values())
    vida = perfil.get("vida_personal", [])

    if not tiene_funcional and not vida:
        return ""

    lineas.append("[PERFIL DE USUARIO]")

    if tiene_funcional:
        for clave in ESQUEMA_FUNCIONAL_CLAVES:
            valor = funcional.get(clave, "").strip()
            if valor:
                # Formatear nombre legible: "proyecto_actual" → "Proyecto actual"
                nombre_legible = clave.replace("_", " ").capitalize()
                lineas.append(f"- {nombre_legible}: {valor}")

    if vida:
        lineas.append("---")
        for entrada in vida:
            tema = entrada.get("tema", "").strip()
            contenido = entrada.get("contenido", "").strip()
            if tema and contenido:
                lineas.append(f"- {tema}: {contenido}")

    return "\n".join(lineas)