"""
Módulo de perfil Gamer persistente para Argus.

Mantiene un perfil en JSON (perfil_gamer.json) separado del perfil de usuario
general. Almacena información sobre juegos, personajes, builds, progreso, etc.
CADA ENTRADA se SOBRESCRIBE (no acumula) para evitar saturar el contexto.

Estructura del perfil:
{
    "juego_activo": "nombre_del_juego",
    "juegos": {
        "grim_dawn": {
            "ultima_sesion": "2026-07-23",
            "personaje": "Hechicero nivel 45",
            "build": "Rayo/Elemental",
            ...
        }
    }
}
"""

import json
import os
import re
import threading
import datetime
from modulos.logger import logger

# ─── CONSTANTES ───────────────────────────────────────────────────────────────

RUTA_PERFIL_GAMER = os.path.join(os.path.dirname(os.path.dirname(__file__)), "perfil_gamer.json")

# Los juegos conocidos se detectan automáticamente, no hay lista fija.
# Cada juego tiene sus propios campos dinámicos.

# Lock thread-safe para acceso a disco
_lock_perfil = threading.Lock()


# ─── ESTRUCTURA POR DEFECTO ──────────────────────────────────────────────────

def _perfil_gamer_vacio() -> dict:
    return {
        "juego_activo": "",
        "juegos": {}
    }


# ─── CARGA / GUARDADO (THREAD-SAFE) ─────────────────────────────────────────

def cargar_perfil_gamer() -> dict:
    """
    Lee el perfil gamer desde disco. Si el archivo no existe, está corrupto
    o tiene estructura inválida, devuelve un perfil vacío.
    Thread-safe con _lock_perfil.
    """
    with _lock_perfil:
        if not os.path.exists(RUTA_PERFIL_GAMER):
            logger.info("perfil_gamer.json no encontrado. Creando perfil vacío.")
            perfil = _perfil_gamer_vacio()
            _escribir_perfil_sin_lock(perfil)
            return perfil
        try:
            with open(RUTA_PERFIL_GAMER, "r", encoding="utf-8") as f:
                perfil = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.exception(f"Error leyendo perfil_gamer.json: {e}. Reiniciando perfil.")
            perfil = _perfil_gamer_vacio()
            _escribir_perfil_sin_lock(perfil)
            return perfil

    return _sanitizar_perfil(perfil)


def guardar_perfil_gamer(perfil: dict) -> None:
    """Guarda el perfil gamer en disco de forma thread-safe."""
    perfil = _sanitizar_perfil(perfil)
    with _lock_perfil:
        _escribir_perfil_sin_lock(perfil)


def _escribir_perfil_sin_lock(perfil: dict) -> None:
    """Escribe el perfil a disco. NO es thread-safe — llamar con _lock_perfil."""
    try:
        with open(RUTA_PERFIL_GAMER, "w", encoding="utf-8") as f:
            json.dump(perfil, f, ensure_ascii=False, indent=2)
        logger.debug("Perfil gamer guardado correctamente.")
    except OSError as e:
        logger.exception(f"Error escribiendo perfil_gamer.json: {e}")


# ─── SANITIZACIÓN ────────────────────────────────────────────────────────────

def _sanitizar_perfil(perfil: dict) -> dict:
    """
    Asegura que el perfil tenga la estructura canónica.
    """
    if not isinstance(perfil, dict):
        return _perfil_gamer_vacio()

    juego_activo = perfil.get("juego_activo", "")
    if not isinstance(juego_activo, str):
        juego_activo = ""

    juegos = perfil.get("juegos", {})
    if not isinstance(juegos, dict):
        juegos = {}

    # Sanitizar cada juego: debe ser dict con valores string
    juegos_limpios = {}
    for nombre_juego, datos in juegos.items():
        if isinstance(datos, dict):
            datos_limpios = {}
            for k, v in datos.items():
                if isinstance(v, str):
                    datos_limpios[k] = v
                else:
                    datos_limpios[k] = str(v) if v is not None else ""
            juegos_limpios[nombre_juego] = datos_limpios

    return {"juego_activo": juego_activo, "juegos": juegos_limpios}


# ─── EDICIÓN / OLVIDO POR ID LÓGICO (FASE 2) ─────────────────────────────────

# Espejo de resumen_memoria._CAMPOS_GAMER (mantener idéntico): etiquetas
# visibles de la plantilla de un juego → claves candidatas internas.
CAMPOS_CURADOS = [
    ("Personaje", ["personaje", "personaje_clase", "clase"]),
    ("Nivel", ["nivel", "nivel_actual"]),
    ("Build", ["build", "build_elegida", "build_tipo"]),
    ("Dificultad", ["dificultad"]),
    ("Objetivo", ["objetivo", "objetivo_meta", "objetivo_equipo"]),
    ("Estrategia", ["estrategia"]),
    ("Progreso", ["progreso", "progreso_historico"]),
]


def _slug_estable(texto: str) -> str:
    """Espejo de `resumen_memoria._slug` (mantiene coherencia de ids)."""
    if not texto:
        return "item"
    limpio = re.sub(r"[^a-zA-Z0-9]+", "_", texto.strip().lower()).strip("_")
    return limpio or "item"


def _clave_canonica(etiqueta: str):
    """Devuelve la clave interna canónica de una etiqueta de la plantilla."""
    for etiqueta_curada, claves in CAMPOS_CURADOS:
        if etiqueta_curada == etiqueta:
            return claves[0]
    return None


def _reparsear_ficha(texto: str):
    """
    Reinterpreta el texto editado de un elemento gamer en sus campos
    curados. Formato: "Etiqueta: valor · Etiqueta: valor · ...".

    Devuelve un dict {clave_canonica: valor} o None si el texto no
    respeta la plantilla (caso en el que NUNCA se borran campos: la
    edición de Fase 2 es determinista y sin IA).
    """
    campos = {}
    for parte in texto.split(" · "):
        parte = parte.strip()
        if not parte:
            continue
        if ":" not in parte:
            return None
        etiqueta, _, valor = parte.partition(":")
        clave = _clave_canonica(etiqueta.strip().strip())
        if clave is None or not valor.strip():
            return None
        campos[clave] = valor.strip()
    return campos or None


def _clave_juego_por_slug(perfil: dict, slug: str):
    """Devuelve la clave exacta de 'juegos' cuyo nombre genera el slug
    (o None si hay 0 o más de 1 coincidencia — ambiguo, no se toca nada)."""
    juegos = perfil.get("juegos", {})
    coincidencias = [
        nombre for nombre in juegos.keys()
        if _slug_estable(str(nombre)) == slug
    ]
    if len(coincidencias) == 1:
        return coincidencias[0]
    return None


def _olvidar_en_perfil(perfil: dict, id_elemento: str) -> bool:
    """
    Aplica el olvido sobre un perfil EN MEMORIA (no persiste).

    Es la ÚNICA implementación del mapeo id → mutación del perfil gamer.
    `olvidar_elemento` y cualquier filtro futuro de extracción la reutilizan
    para que ambos mecanismos jamás puedan divergir.

    - 'gamer:juego_activo' → restablece el juego activo a "".
    - 'gamer:<slug_juego>' → elimina la ficha completa del juego; si ese
      juego era el activo, también restablece 'juego_activo' (sin huérfanos).

    Devuelve True si aplicó el cambio; False si el id no pertenece a este
    perfil o el dato no existe / es ambiguo.
    """
    id_ = str(id_elemento or "")
    if not id_.startswith("gamer:"):
        return False
    resto = id_[len("gamer:"):]

    if resto == "juego_activo":
        if not perfil.get("juego_activo"):
            return False
        perfil["juego_activo"] = ""
        return True

    clave = _clave_juego_por_slug(perfil, resto)
    if clave is None:
        return False
    del perfil["juegos"][clave]
    if perfil.get("juego_activo") == clave:
        perfil["juego_activo"] = ""
    return True


def olvidar_elemento(id_elemento: str) -> bool:
    """
    Borra un dato del perfil gamer según su id lógico.

    - 'gamer:juego_activo' → restablece el juego activo a "".
    - 'gamer:<slug_juego>' → elimina la ficha completa del juego; si ese
      juego era el activo, también restablece 'juego_activo' (sin huérfanos).

    Devuelve True si se aplicó el cambio (y se persistió); False si el id
    no pertenece a este perfil o el dato no existe / es ambiguo.
    """
    perfil = cargar_perfil_gamer()
    if not _olvidar_en_perfil(perfil, id_elemento):
        return False
    guardar_perfil_gamer(perfil)
    return True


def editar_elemento(id_elemento: str, texto: str) -> bool:
    """
    Actualiza el contenido de un dato del perfil gamer.

    - 'gamer:juego_activo' → reemplaza el nombre del juego activo.
    - 'gamer:<slug_juego>' → re-renderiza la ficha del juego (ver abajo).

    ESTRATEGIA DE EDICIÓN GAMER SIN IA: el texto editado se interpreta con
    la MISMA plantilla que produce el panel ("Etiqueta: valor · ..."). Solo
    se actualizan los campos que el usuario incluye; los que no se nombran
    quedan intactos. Si el texto NO respeta la plantilla, la edición se
    rechaza (devuelve False) — nunca se corrompen campos ni se inventa data.

    Devuelve True si se aplicó (y se persistió); False en caso contrario.
    """
    texto = (texto or "").strip()
    id_ = str(id_elemento or "")
    if not id_.startswith("gamer:"):
        return False
    resto = id_[len("gamer:"):]

    perfil = cargar_perfil_gamer()

    if resto == "juego_activo":
        if not texto:
            return False
        perfil["juego_activo"] = texto
        guardar_perfil_gamer(perfil)
        return True

    clave = _clave_juego_por_slug(perfil, resto)
    if clave is None:
        return False
    campos = _reparsear_ficha(texto)
    if campos is None:
        return False
    perfil["juegos"][clave] = {**perfil["juegos"][clave], **campos}
    guardar_perfil_gamer(perfil)
    return True


# ─── EXTRACCIÓN CON LLM ──────────────────────────────────────────────────────

def extraer_hechos_gamer(ultimos_mensajes: list) -> list:
    """
    Analiza los últimos mensajes usando Gemini Flash-Lite y extrae información
    relevante del gaming: juegos mencionados, personajes, builds, etc.

    Devuelve una LISTA de hechos gamer. Cada hecho:
    {"juego": "nombre", "campo": "clave", "valor": "string"}

    El último hecho de la lista que tenga "juego_activo" como campo indica
    cuál es el juego activo actual.

    Si no hay nada relevante, devuelve lista vacía [].
    """
    if not ultimos_mensajes:
        return []

    from modulos.ia import cliente_genai
    from google.genai import types

    conversacion = "\n".join([str(m) for m in ultimos_mensajes[-30:]])

    prompt = (
        "Eres un extractor de perfil de gaming. Analizá la conversación "
        "y extraé SOLO información sobre videojuegos, personajes, builds, "
        "progreso, configuraciones, rangos o cualquier dato relacionado "
        "con gaming.\n\n"
        "REGLAS:\n"
        "1. Devolvé una LISTA JSON de hechos. Cada hecho debe tener esta forma:\n"
        '   {"juego": "nombre_del_juego", "campo": "clave_descriptiva", "valor": "string"}\n'
        "2. El primer hecho de la lista DEBE tener campo 'juego_activo' indicando "
        "el juego principal del que se está hablando.\n"
        "   Ejemplo: {\"juego\": \"\", \"campo\": \"juego_activo\", \"valor\": \"Grim Dawn\"}\n"
        "3. Si el usuario menciona un juego, extraé TODA la información relevante "
        "de esa conversación: personaje, build, nivel, dificultad, progreso, "
        "rango, etc. Cada dato como un hecho separado.\n"
        "4. Los campos deben ser descriptivos en español: 'personaje', 'build', "
        "'nivel', 'dificultad', 'progreso', 'rango', 'personaje_principal', "
        "'notas', etc.\n"
        "5. Si habla de un juego que ya existía, incluí SOLO lo NUEVO que se dice "
        "(el sistema se encarga de fusionar).\n"
        "6. Si no hay información relevante sobre gaming, devolvé [] (lista vacía).\n"
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

        # Parseo defensivo
        if texto_respuesta.startswith("```"):
            lineas = texto_respuesta.split("\n")
            if lineas[0].strip().startswith("```"):
                lineas = lineas[1:]
            if lineas and lineas[-1].strip() == "```":
                lineas = lineas[:-1]
            texto_respuesta = "\n".join(lineas).strip()

        hechos = json.loads(texto_respuesta)
        if not isinstance(hechos, list):
            return []

        hechos_validos = []
        for hecho in hechos:
            if isinstance(hecho, dict) and "campo" in hecho and "valor" in hecho:
                hecho.setdefault("juego", "")
                hechos_validos.append(hecho)

        return hechos_validos

    except Exception as e:
        logger.exception(f"Error extrayendo hechos gamer: {e}")
        return []


def rutear_hecho_gamer(hecho: dict, perfil: dict) -> dict:
    """
    Procesa un hecho gamer y actualiza el perfil.

    - Si campo es 'juego_activo': actualiza juego_activo
    - Si tiene juego + campo: actualiza juegos[juego][campo] = valor

    Args:
        hecho: dict con "juego", "campo", "valor".
        perfil: dict con el perfil actual (se modifica in-place y se devuelve).

    Returns:
        dict con el perfil actualizado.
    """
    campo = str(hecho.get("campo", "")).strip()
    valor = str(hecho.get("valor", "")).strip()
    juego = str(hecho.get("juego", "")).strip()

    if not campo or not valor:
        return perfil

    # ─── Filtro de olvidos (tombstones) ──────────────────────────────────
    # Garantía determinista contra la reaparición: si el usuario olvidó este
    # dato desde el panel, la extracción NO puede reintroducirlo. El id
    # candidato usa el MISMO slug que genera el panel (id canónico).
    from modulos.olvidos import esta_olvidado
    if campo == "juego_activo":
        if esta_olvidado("gamer:juego_activo"):
            logger.info("Hecho gamer descartado (dato olvidado): gamer:juego_activo")
            return perfil
    elif juego:
        candidato_id = f"gamer:{_slug_estable(juego)}"
        if esta_olvidado(candidato_id):
            logger.info(f"Hecho gamer descartado (dato olvidado): {candidato_id}")
            return perfil

    # Caso especial: juego_activo
    if campo == "juego_activo":
        perfil["juego_activo"] = valor
        logger.debug(f"Perfil gamer: juego activo actualizado a '{valor}'")
        return perfil

    # Caso normal: dato de un juego específico
    if not juego:
        return perfil

    # Asegurar que el juego existe en el diccionario
    if juego not in perfil["juegos"]:
        perfil["juegos"][juego] = {}

    # Actualizar (sobrescribe, no acumula)
    perfil["juegos"][juego][campo] = valor
    perfil["juegos"][juego]["ultima_sesion"] = datetime.date.today().strftime("%Y-%m-%d")
    logger.debug(f"Perfil gamer: {juego}.{campo} = {valor[:60]}")

    return perfil


# ─── ORQUESTADOR ──────────────────────────────────────────────────────────────

def extraer_y_procesar_sesion_gamer(ultimos_mensajes: list) -> None:
    """
    Función orquestadora para extraer y guardar perfil gamer.
    Similar a extraer_y_procesar_sesion() de perfil_usuario.py pero para gaming.
    """
    if not ultimos_mensajes:
        return

    logger.debug(f"🎮 Extrayendo hechos gamer de {len(ultimos_mensajes)} mensajes...")

    try:
        hechos = extraer_hechos_gamer(ultimos_mensajes)
        if not hechos:
            logger.debug("No se encontraron hechos gamer en esta tanda")
            return

        logger.info(f"🎮 {len(hechos)} hecho(s) gamer candidato(s) extraídos")

        perfil = cargar_perfil_gamer()
        cambios = 0
        for hecho in hechos:
            perfil_antes = json.dumps(perfil, ensure_ascii=False)
            perfil = rutear_hecho_gamer(hecho, perfil)
            if json.dumps(perfil, ensure_ascii=False) != perfil_antes:
                cambios += 1

        if cambios == 0:
            logger.debug("Extracción gamer: sin cambios que persistir")
            return

        guardar_perfil_gamer(perfil)
        logger.info(f"🎮 Perfil gamer actualizado ({cambios} cambio(s) aplicado(s))")

    except Exception as e:
        logger.exception(f"Error en extraer_y_procesar_sesion_gamer: {e}")


# ─── TEXTO PARA INYECCIÓN EN PROMPTS ─────────────────────────────────────────

def texto_perfil_gamer_para_prompt() -> str:
    """
    Convierte el perfil gamer en un bloque de texto plano para inyectar
    en el prompt del sistema del modo Gamer.

    Solo incluye el juego activo actual (para mantener el contexto liviano).
    """
    perfil = cargar_perfil_gamer()
    juego_activo = perfil.get("juego_activo", "")

    if not juego_activo or juego_activo not in perfil.get("juegos", {}):
        # Si hay juegos pero no activo, mostrar el primero
        juegos = perfil.get("juegos", {})
        if juegos:
            juego_activo = list(juegos.keys())[0]
        else:
            return ""

    datos_juego = perfil["juegos"].get(juego_activo, {})
    if not datos_juego:
        return ""

    lineas = [f"[PERFIL GAMER - JUEGO ACTIVO: {juego_activo}]"]
    for campo, valor in datos_juego.items():
        if campo == "ultima_sesion":
            continue  # no mostrar la fecha en el prompt, no es relevante
        nombre_legible = campo.replace("_", " ").capitalize()
        lineas.append(f"- {nombre_legible}: {valor}")

    return "\n".join(lineas)