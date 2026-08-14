"""
Controlador de persistencia de Progreso/Mentoría (Fase 5).

Separa el estado estructurado (perfil_mentor.json → clave `progreso`) de la
memoria semántica (Bóveda, vía guardar_recuerdo con origen_fuente constante),
con reglas deterministas de clasificación. El LLM propone eventos candidatos,
pero la decisión de "qué es estado / qué es recuerdo / qué se descarta" la toma
este módulo con umbrales fijos (el LLM NUNCA escribe a la Bóveda por su cuenta).

Regla de persistencia (K5):
- La Bóveda NO es un diario: solo eventos semánticos con importancia alta y
  tipo en el allowlist se escriben como recuerdos (origen_fuente='mentoria_progreso').
- Un mismo evento semántico se persiste UNA sola vez (guard de sha256 en
  `progreso["recuerdos_persistidos"]`).
- Estado estructurado: objetivos, próximos pasos, dificultades activas, hitos
  completados y continuidad. Se REUTILIZAN las claves ya existentes del perfil
  (stack_objetivo, tecnologias_*, proyectos_de_portafolio, ultimo_avance_registrado)
  sin duplicarlas.

No importa ChromaDB ni modulos.ia al cargar (imports lazies dentro de funciones).
"""

import datetime
import hashlib
import json
import re
import threading

from modulos.logger import logger

# ─── CONTRATO DE PERSISTENCIA ────────────────────────────────────────────────

# Origen consistente para TODOS los recuerdos de mentoría en la Bóveda. Permite
# identificarlos por origen_fuente y olvidarlos con el mecanismo existente
# (olvidos → invalidar_por_origen / recuperador_memoria → esta_olvidado).
ORIGEN_FUENTE_MENTORIA = "mentoria_progreso"
ETIQUETA_BOVEDA = "Progreso_Mentoria"

# Tipos SEMÁNTICOS: SOLO estos pueden ir a la Bóveda (allowlist determinista).
TIPOS_SEMANTICOS = {
    "avance_significativo",
    "decision_importante",
    "aprendizaje_relevante",
    "dificultad_recurrente",
    "contexto_proyecto",
}

# Tipos ESTRUCTURADOS: actualizan perfil_mentor.json → `progreso`.
TIPOS_ESTADO = {
    "objetivo_creado",
    "objetivo_actualizado",
    "objetivo_logrado",
    "objetivo_abandonado",
    "proximo_paso",
    "dificultad",
    "hito_completado",
    "continuidad",
}

TIPOS_VALIDOS = TIPOS_SEMANTICOS | TIPOS_ESTADO

# Umbrales de importancia (el extractor devuelve 0-100; el control decide).
UMBRAL_IMPORTANCIA_ESTADO = 50
UMBRAL_IMPORTANCIA_BOVEDA = 65

# Límites del estado estructurado.
MAX_OBJETIVOS = 12
MAX_PROXIMOS_PASOS = 8
MAX_DIFICULTADES = 10
MAX_HITOS = 15

# Tamaño máximo de texto de un recuerdo persistido (economía + no-duplicación).
MAX_CARACTERES_BOVEDA = 600

# Patrón simple anti-secretos/credenciales (ídem perfil_usuario).
_PATRON_SECRETO = re.compile(
    r"(contraseña|password|api.?key|token|pin|sk-[a-zA-Z0-9]{20,}|"
    r"[A-Za-z0-9]{20,})",
    re.IGNORECASE,
)

# Determinación de estado para objetivos a partir del tipo de evento.
_ESTADO_POR_TIPO_OBJETIVO = {
    "objetivo_creado": "activo",
    "objetivo_actualizado": "activo",
    "objetivo_logrado": "completado",
    "objetivo_abandonado": "abandonado",
}


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def _es_secreto(texto: str) -> bool:
    """Devuelve True si el texto parece contener credenciales o tokens."""
    if not isinstance(texto, str):
        return False
    return bool(_PATRON_SECRETO.search(texto))


def _normalizar_texto(texto: str) -> str:
    """Normaliza para deduplicación: strip + colapsa whitespace."""
    return " ".join(str(texto or "").split())


def _sha_texto(texto: str) -> str:
    return hashlib.sha256(_normalizar_texto(texto).encode("utf-8")).hexdigest()


def _slug_estable(texto) -> str:
    """Espejo de perfil_mentor._slug_estable (coherencia de ids del panel)."""
    if not texto:
        return "item"
    limpio = re.sub(r"[^a-zA-Z0-9]+", "_", str(texto).strip().lower()).strip("_")
    return limpio or "item"


def _imputar_importancia(evento) -> int:
    try:
        valor = int(evento.get("importancia") or 0)
    except (TypeError, ValueError):
        valor = 0
    return max(0, min(100, valor))


def _estado_progreso_vacio() -> dict:
    return {
        "objetivos": [],
        "proximos_pasos": [],
        "dificultades_activas": [],
        "hitos_completados": [],
        "continuidad": {"ultimo_tema": "", "ultima_fecha": "", "donde_quedamos": ""},
        "recuerdos_persistidos": [],
    }


# ─── CLASIFICACIÓN (CONTROL DETERMINISTA; el LLM NO decide) ─────────────────

def clasificar_evento(evento: dict) -> str:
    """
    Devuelve el destino de un evento candidato:
      - "estado"       → solo perfil_mentor.json (estructurado).
      - "boveda"       → solo recuerdo semántico en la Bóveda.
      - "ambos"        → estado estructurado + recuerdo semántico.
      - "descartable"  → no se persiste nada.

    El allowlist de tipos y los umbrales están fijos en este módulo: el LLM
    puede etiquetar mal o inflar importancia, pero su libertad termina acá.
    """
    if not isinstance(evento, dict):
        return "descartable"
    tipo = str(evento.get("tipo") or "").strip()
    texto = str(evento.get("texto") or "").strip()
    if not tipo or not texto or tipo not in TIPOS_VALIDOS:
        return "descartable"
    importancia = _imputar_importancia(evento)

    if tipo in TIPOS_SEMANTICOS:
        if tipo == "dificultad_recurrente":
            # Dificultad recurrente: es memoria semántica SOLO si es relevante;
            # en cualquier caso se refleja en el estado (dificultades activas).
            if importancia >= UMBRAL_IMPORTANCIA_BOVEDA:
                return "ambos"
            if importancia >= UMBRAL_IMPORTANCIA_ESTADO:
                return "estado"
            return "descartable"
        # Política conservadora (auditoría Fase 5): un avance significativo
        # NUNCA se pierde. Por encima del umbral va a la Bóveda; por debajo
        # (o sin importancia válida → imputada 0) cae al estado como hito.
        # El resto de tipos semánticos conserva su semántica original.
        if tipo == "avance_significativo":
            if importancia >= UMBRAL_IMPORTANCIA_BOVEDA:
                return "boveda"
            return "estado"
        if importancia >= UMBRAL_IMPORTANCIA_BOVEDA:
            return "boveda"
        return "descartable"

    # Tipos de estado: solo requieren el umbral de estado.
    if importancia >= UMBRAL_IMPORTANCIA_ESTADO:
        return "estado"
    return "descartable"


# ─── APLICACIÓN AL ESTADO ESTRUCTURADO ───────────────────────────────────────

def _resolver_contenedor_tema(perfil: dict, evento: dict):
    """
    Devuelve (contenedor, nombre_tema) para un evento.

    El contenedor es el dict que posee la clave 'progreso' a actualizar:
      - Tema activo → el PERFIL completo (espejo legacy de nivel superior);
      - Otro tema (evento con campo `tema`) → el dict del tema en el registro.
    Si el evento nombra un tema que aún no existe, se crea en el registro
    (sin activarlo) para que "empezar un tema por conversación" funcione.
    """
    from modulos.perfil_mentor import _tema_activo_slug, obtener_tema

    nombre_evento = str(evento.get("tema") or "").strip()
    if nombre_evento:
        temas = perfil.get("temas")
        if isinstance(temas, dict):
            slug = _slug_estable(nombre_evento)
            for s, t in temas.items():
                if s == slug or (t.get("nombre") or "").lower() == nombre_evento.lower():
                    slug = s
                    break
            if slug in temas:
                return temas[slug], temas[slug].get("nombre", slug)
            nuevo = {
                "nombre": nombre_evento,
                "objetivo_general": "",
                "contexto": {},
                "progreso": _estado_progreso_vacio(),
                "ultimo_avance_registrado": "Ninguno",
                "historial_sesiones": [],
            }
            temas[slug] = nuevo
            return nuevo, nombre_evento
    slug = _tema_activo_slug(perfil)
    tema = obtener_tema(perfil, slug)
    return perfil, (tema.get("nombre", slug) if tema else slug)


def _aplicar_estado(contenedor: dict, evento: dict) -> bool:
    """Actualiza contenedor["progreso"] en memoria. Devuelve True si hubo cambio."""
    prog = contenedor.setdefault("progreso", {})
    for clave, default in _estado_progreso_vacio().items():
        prog.setdefault(clave, default)

    tipo = str(evento.get("tipo") or "").strip()
    texto = str(evento.get("texto") or "").strip()
    hoy = datetime.date.today().strftime("%Y-%m-%d")

    # ── Objetivos (creado/actualizado/logrado/abandonado) ──
    if tipo in _ESTADO_POR_TIPO_OBJETIVO:
        titulo = str(evento.get("titulo") or texto).strip()
        if not titulo:
            return False
        slug = _slug_estable(titulo)
        objetivos = prog["objetivos"]
        idx = next((i for i, o in enumerate(objetivos)
                    if isinstance(o, dict) and _slug_estable(o.get("titulo", "")) == slug), None)
        es_nuevo = idx is None
        if es_nuevo:
            if len(objetivos) >= MAX_OBJETIVOS:
                logger.warning(f"Límite de objetivos alcanzado (máx {MAX_OBJETIVOS}); objetivo no aplicado: {titulo[:80]}")
                return False
            idx = len(objetivos)
            objetivos.append({
                "titulo": titulo,
                "estado": _ESTADO_POR_TIPO_OBJETIVO[tipo],
                "prioridad": str(evento.get("prioridad") or "media").strip(),
                "proyecto_asociado": str(evento.get("proyecto_asociado") or "").strip(),
                "fecha_creacion": hoy,
                "fecha_actualizacion": hoy,
            })
        else:
            objetivos[idx]["estado"] = _ESTADO_POR_TIPO_OBJETIVO[tipo]
            objetivos[idx]["fecha_actualizacion"] = hoy
            if evento.get("proyecto_asociado"):
                objetivos[idx]["proyecto_asociado"] = str(evento["proyecto_asociado"]).strip()
            if evento.get("prioridad"):
                objetivos[idx]["prioridad"] = str(evento["prioridad"]).strip()
        return True

    # ── Próximos pasos ──
    if tipo == "proximo_paso":
        pasos = prog["proximos_pasos"]
        if any(_slug_estable(p) == _slug_estable(texto) for p in pasos):
            return False  # ya existe (no duplicar dentro del estado)
        if len(pasos) >= MAX_PROXIMOS_PASOS:
            logger.warning(f"Límite de próximos pasos alcanzado (máx {MAX_PROXIMOS_PASOS}); paso no aplicado: {texto[:80]}")
            return False
        pasos.append(texto)
        return True

    # ── Dificultades activas (dificultad o dificultad_recurrente) ──
    if tipo in ("dificultad", "dificultad_recurrente"):
        tema = texto
        slug = _slug_estable(tema)
        difs = prog["dificultades_activas"]
        idx = next((i for i, d in enumerate(difs)
                    if isinstance(d, dict) and _slug_estable(d.get("tema", "")) == slug), None)
        if idx is None:
            if len(difs) >= MAX_DIFICULTADES:
                logger.warning(f"Límite de dificultades activas alcanzado (máx {MAX_DIFICULTADES}); dificultad no aplicada: {tema[:80]}")
                return False
            difs.append({"tema": tema, "ocurrencias": 1, "ultima_fecha": hoy})
        else:
            difs[idx]["ocurrencias"] = int(difs[idx].get("ocurrencias") or 0) + 1
            difs[idx]["ultima_fecha"] = hoy
        return True

    # ── Hitos completados (hito_completado o avance_significativo degradado a estado) ──
    if tipo in ("hito_completado", "avance_significativo"):
        # Un avance degradado a estado NUNCA arrastra información sensible:
        # la ruta nueva (avance→hito) comparte el mismo guard de secretos que
        # la Bóveda para no crear una vía de persistencia de credenciales.
        if tipo == "avance_significativo" and _es_secreto(texto):
            logger.info(f"avance_significativo con contenido sensible omitido del estado: {texto[:80]}")
            return False
        hitos = prog["hitos_completados"]
        if any(h.get("texto") == texto for h in hitos if isinstance(h, dict)):
            return False
        if len(hitos) >= MAX_HITOS:
            logger.warning(f"Límite de hitos completados alcanzado (máx {MAX_HITOS}); hito no aplicado: {texto[:80]}")
            return False
        hitos.append({"texto": texto, "fecha": hoy})
        return True

    # ── Continuidad (dónde quedamos) ──
    if tipo == "continuidad":
        prev = prog["continuidad"]
        nuevo = {**(prev or {}), "ultimo_tema": texto, "ultima_fecha": hoy, "donde_quedamos": texto}
        if prev == nuevo:
            return False
        prog["continuidad"] = nuevo
        return True

    return False


# ─── PERSISTENCIA SEMÁNTICA (Bóveda) ─────────────────────────────────────────

def _persistir_boveda(contenedor: dict, evento: dict, tema_nombre: str = "") -> bool:
    """
    Convierte un evento semántico en recuerdo de la Bóveda SOLO si:
      - el tipo está en el allowlist semántico;
      - la importancia supera el umbral semántico;
      - no es un secreto;
      - NO se persistió antes (guard sha256 → Bóveda no es un diario).
    Reutiliza el API público guardar_recuerdo() (contrato boveda:*), sin
    tocar la arquitectura de la bóveda. origen_fuente es CONSTANTE para que
    todos los recuerdos de mentoría sean identificables en conjunto; el tema
    viaja en metadatos para poder filtrar por tema si hace falta.
    """
    tipo = str(evento.get("tipo") or "").strip()
    if tipo not in TIPOS_SEMANTICOS:
        return False
    if _imputar_importancia(evento) < UMBRAL_IMPORTANCIA_BOVEDA:
        return False

    texto = " ".join(str(evento.get("texto") or "").split())
    if not texto or _es_secreto(texto):
        return False
    if len(texto) > MAX_CARACTERES_BOVEDA:
        texto = texto[:MAX_CARACTERES_BOVEDA].rstrip() + "…"

    # Guard anti-duplicación: el mismo (sha de texto) ya persistido → no repetir.
    sha = _sha_texto(texto)
    prog = contenedor.setdefault("progreso", {})
    for clave, default in _estado_progreso_vacio().items():
        prog.setdefault(clave, default)
    persistidos = prog["recuerdos_persistidos"]
    if sha in persistidos:
        logger.debug("Evento semántico ya persistido antes, se omite (no diario).")
        return False

    try:
        from modulos.memoria import guardar_recuerdo
        metadatos = {"tipo_relacionado": tipo}
        if tema_nombre:
            metadatos["tema_relacionado"] = tema_nombre
        exito = guardar_recuerdo(
            texto_a_guardar=texto,
            etiqueta_tema=ETIQUETA_BOVEDA,
            metadatos_extra=metadatos,
            origen_fuente=ORIGEN_FUENTE_MENTORIA,
        )
    except Exception as e:
        logger.exception(f"No se pudo persistir recuerdo semántico de mentoría: {e}")
        return False

    if exito:
        persistidos.append(sha)
        if len(persistidos) > 200:
            del persistidos[:-200]
        logger.info(f"🧠 Recuerdo semántico persistido (mentoria_progreso): {texto[:80]}...")
    return bool(exito)


# ─── ORQUESTACIÓN ────────────────────────────────────────────────────────────

# Guard anti-duplicación de procesamiento de sesión (P4): una MISMA sesión de
# mentoría solo se examina/persiste UNA vez, ya sea que el disparo venga del
# cambio de modo o del cierre de la aplicación. Se compara una huella sha256
# de los mensajes: si el contexto no cambió, la segunda llamada es no-op.
_session_lock = threading.Lock()
_session_fingerprint = None


def _huella_sesion(ultimos_mensajes: list) -> str:
    """Fingerprint estable del contexto de conversación (para deduplicar)."""
    return hashlib.sha256(
        json.dumps(ultimos_mensajes or [], ensure_ascii=False, default=str, sort_keys=True).encode("utf-8")
    ).hexdigest()


def sesion_ya_procesada(ultimos_mensajes: list) -> bool:
    """
    Marca (y consulta) si la sesión actual ya fue procesada.

    - Primera vez con esta huella: devuelve False y queda registrada.
    - Misma sesión de nuevo (mensajes idénticos): devuelve True (no re-examinar).
    - Sesión nueva (mensajes distintos): devuelve False (se procesa).
    Thread-safe.
    """
    global _session_fingerprint
    huella = _huella_sesion(ultimos_mensajes)
    with _session_lock:
        if _session_fingerprint == huella:
            logger.debug("Sesión de mentoría ya procesada (misma conversación); se omite la re-persistencia.")
            return True
        _session_fingerprint = huella
        return False


def _serializar(perfil: dict) -> str:
    return json.dumps(perfil, ensure_ascii=False, default=str)


def procesar_eventos(perfil: dict, eventos: list) -> dict:
    """Clasifica y aplica una lista de eventos. No persiste por sí mismo."""
    stats = {"estado": 0, "recuerdos_boveda": 0, "descartados": 0, "cambios_perfil": 0}
    if not eventos:
        return stats
    for evento in eventos:
        clasif = clasificar_evento(evento)
        if clasif == "descartable":
            stats["descartados"] += 1
            continue
        contenedor, tema_nombre = _resolver_contenedor_tema(perfil, evento)
        if contenedor is None:
            stats["descartados"] += 1
            continue
        antes = _serializar(perfil)
        if clasif in ("estado", "ambos"):
            stats["estado"] += 1
            _aplicar_estado(contenedor, evento)
        if clasif in ("boveda", "ambos"):
            if _persistir_boveda(contenedor, evento, tema_nombre):
                stats["recuerdos_boveda"] += 1
        if _serializar(perfil) != antes:
            stats["cambios_perfil"] += 1
    return stats


def extraer_eventos_progreso(ultimos_mensajes: list) -> list:
    """
    Extrae eventos de progreso de mentoría con un LLM (Gemini Flash-Lite).

    Devuelve una lista de dicts: {"tipo", "texto", "importancia", ...}.
    Solo son admitidos los tipos de TIPOS_VALIDOS; la clasificación de destino
    la hace luego clasificar_evento() (este módulo), no el LLM.

    Parseo defensivo: falla silencioso y devuelve [] (nada se persiste).
    """
    if not ultimos_mensajes:
        return []

    from modulos.ia import cliente_genai
    from google.genai import types

    mensajes_relevantes = ultimos_mensajes[-14:]
    conversacion = ""
    for msg in mensajes_relevantes:
        role = str(getattr(msg, "get", lambda k, d=None: msg.get(k, d))("role", "user"))
        parts = msg.get("parts", []) if isinstance(msg, dict) else []
        texto_msg = ""
        for part in parts:
            if isinstance(part, str):
                texto_msg += part
            elif isinstance(part, dict) and "text" in part:
                texto_msg += part["text"]
        if len(texto_msg) > 500:
            texto_msg = texto_msg[:500] + "... [truncado]"
        if texto_msg.strip():
            conversacion += f"{role.upper()}: {texto_msg}\n"

    if not conversacion.strip():
        return []

    tipos_estado = ", ".join(sorted(TIPOS_ESTADO))
    tipos_semanticos = ", ".join(sorted(TIPOS_SEMANTICOS))

    prompt = (
        "Analizá la conversación reciente entre Luis (estudiante) y Argus (su Mentor).\n"
        "Extraé SOLO eventos de progreso de mentoría. Cada evento es un objeto JSON:\n"
        '  {"tipo": "<tipo>", "texto": "descripción breve", "importancia": 0-100,\n'
        '   "titulo": "...", "prioridad": "alta|media|baja", "proyecto_asociado": "...",\n'
        '   "tema": "nombre del tema de mentoría, p.ej. Desarrollo y carrera tech, Música, Inglés"}\n\n'
        "El campo 'tema' es OBLIGATORIO en cada evento: identifica el tema de mentoría al que "
        "pertenece el avance (no inventes temas nuevos salvo que la conversación claramente se "
        "mueva a otro ámbito; en ese caso usá ese nombre).\n\n"
        "TIPOS DE ESTADO (actualizan el progreso estructurado del tema):\n"
        f"  {tipos_estado}\n"
        "  - objetivo_*: 'titulo' es el nombre del objetivo; prioridad/proyecto_asociado opcionales.\n"
        "  - proximo_paso / dificultad / hito_completado / continuidad: 'texto' con lo concreto.\n\n"
        "TIPOS SEMÁNTICOS (avances y decisiones con valor de continuidad futura):\n"
        f"  {tipos_semanticos}\n"
        "  - avance_significativo: logro concreto de la sesión.\n"
        "  - decision_importante / aprendizaje_relevante / contexto_proyecto.\n\n"
        "REGLAS:\n"
        "1. Importancia 0-100: <40 trivial, 40-64 útil, >=65 muy relevante.\n"
        "2. NO inventes. Si no hay nada nuevo y concreto, devolvé [] (lista vacía).\n"
        "3. NO informes contenido sensible ni credenciales.\n"
        "4. Devolvé SOLO el JSON (lista), sin markdown ni explicaciones.\n\n"
        f"Conversación reciente:\n{conversacion}\n\n"
        "Lista JSON de eventos:"
    )

    try:
        respuesta = cliente_genai.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=2048,
            ),
        )
        texto_respuesta = respuesta.text.strip()
        if texto_respuesta.startswith("```"):
            lineas = texto_respuesta.split("\n")
            if lineas[0].strip().startswith("```"):
                lineas = lineas[1:]
            if lineas and lineas[-1].strip() == "```":
                lineas = lineas[:-1]
            texto_respuesta = "\n".join(lineas).strip()

        eventos = json.loads(texto_respuesta)
        if not isinstance(eventos, list):
            return []
        validos = []
        for ev in eventos:
            if not isinstance(ev, dict):
                continue
            tipo = str(ev.get("tipo") or "").strip()
            texto = str(ev.get("texto") or "").strip()
            if tipo in TIPOS_VALIDOS and texto:
                ev.setdefault("importancia", 50)
                validos.append(ev)
        return validos
    except Exception as e:
        logger.exception(f"Error extrayendo eventos de progreso: {e}")
        return []


def procesar_sesion_progreso(ultimos_mensajes: list) -> dict:
    """
    Orquestador: extrae eventos → clasifica → aplica estado → persiste recuerdo
    semántico. Carga/guarda perfil_mentor.json. Nunca toca la bóveda por sí
    mismo salvo vía guardar_recuerdo (API pública, contrato boveda:*).

    La deduplicación de procesamiento de la MISMA sesión NO es responsabilidad
    de esta función (los disparos de cambio de modo y cierre usan
    sesion_ya_procesada antes de invocar esta ruta + el reescritor de perfil).
    """
    if not ultimos_mensajes:
        return {"estado": 0, "recuerdos_boveda": 0, "descartados": 0, "cambios_perfil": 0}
    try:
        eventos = extraer_eventos_progreso(ultimos_mensajes)
        if not eventos:
            return {"estado": 0, "recuerdos_boveda": 0, "descartados": 0, "cambios_perfil": 0}

        from modulos.perfil_mentor import cargar_perfil_mentor, guardar_perfil_mentor

        perfil = cargar_perfil_mentor()
        stats = procesar_eventos(perfil, eventos)
        if stats["cambios_perfil"] or stats["recuerdos_boveda"]:
            guardar_perfil_mentor(perfil)
            logger.info(f"✅ Progreso/Mentoría guardado: {stats['estado']} evento(s) de estado, "
                        f"{stats['recuerdos_boveda']} recuerdo(s) semántico(s).")
        return stats
    except Exception as e:
        logger.exception(f"Error procesando sesión de progreso: {e}")
        return {"estado": 0, "recuerdos_boveda": 0, "descartados": 0, "cambios_perfil": 0}