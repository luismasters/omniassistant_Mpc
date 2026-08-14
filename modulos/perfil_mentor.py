import copy
import json
import os
import re
import threading
import datetime
from modulos.logger import logger

# Ruta al archivo de perfil del mentor (raíz del proyecto)
RUTA_PERFIL_MENTOR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "perfil_mentor.json")

_lock_perfil_mentor = threading.Lock()

# ─── MODELO MULTITEMA (tema → sesión → avance) ─────────────────────────────
# El archivo es v2: un registro de TEMAS con `tema_activo`. Los campos legacy
# de nivel superior (stack_objetivo, tecnologias_*, proyectos_de_portafolio,
# progreso, historial_sesiones, ultimo_avance_registrado, claves_*) son un
# ESPEJO del tema activo, mantenido por _sincronizar_tema_activo() en cada
# guardado. No son fuente de verdad: se conservan para no romper el contrato
# histórico (ids `mentor:*`, panel, tests y lectores externos).

SLUG_TEMA_DESARROLLO = "desarrollo_y_carrera"
NOMBRE_TEMA_DESARROLLO = "Desarrollo y carrera tech"

_STACK_OBJETIVO_DEFECTO = {
    "frontend": "Pendiente de definir",
    "backend": "Pendiente de definir",
    "bases_de_datos": "Pendiente de definir",
    "otras_herramientas": [],
}

_PROGRESO_DEFECTO = {
    "objetivos": [],
    "proximos_pasos": [],
    "dificultades_activas": [],
    "hitos_completados": [],
    "continuidad": {"ultimo_tema": "", "ultima_fecha": "", "donde_quedamos": ""},
    "recuerdos_persistidos": [],
}

_CLAVES_CONTEXTO_FALTANTES_DEFECTO = [
    "¿Prefieres enfocarte en desarrollo Frontend, Backend o Fullstack?",
    "¿Qué lenguajes o tecnologías aprendiste en la UTN FRGP y con cuáles te sentiste más cómodo?",
    "¿Tienes en mente alguna idea de proyecto para construir como parte de tu portafolio?",
]


def _tema_default(slug: str) -> dict:
    """Crea un tema de mentoría con su estructura mínima (no persiste)."""
    if slug == SLUG_TEMA_DESARROLLO:
        nombre = NOMBRE_TEMA_DESARROLLO
    else:
        nombre = slug.replace("_", " ").title()
    return {
        "nombre": nombre,
        "objetivo_general": "",
        "contexto": {
            "stack_objetivo": copy.deepcopy(_STACK_OBJETIVO_DEFECTO),
            "tecnologias_aprendidas": [],
            "tecnologias_en_estudio": [],
            "proyectos_de_portafolio": [],
            "claves_de_contexto_faltantes": [],
        },
        "progreso": copy.deepcopy(_PROGRESO_DEFECTO),
        "ultimo_avance_registrado": "Ninguno",
        "historial_sesiones": [],
    }


def _perfil_default() -> dict:
    """Estructura inicial del archivo v2 (copia fresca, sin refs compartidas)."""
    return {
        "meta": {"version": 2},
        "tema_activo": SLUG_TEMA_DESARROLLO,
        "temas": {SLUG_TEMA_DESARROLLO: _tema_default(SLUG_TEMA_DESARROLLO)},
        # Espejo legacy del tema activo:
        "stack_objetivo": copy.deepcopy(_STACK_OBJETIVO_DEFECTO),
        "tecnologias_aprendidas": [],
        "tecnologias_en_estudio": [],
        "proyectos_de_portafolio": [],
        "ultimo_avance_registrado": "Ninguno",
        "historial_sesiones": [],
        "claves_de_contexto_faltantes": list(_CLAVES_CONTEXTO_FALTANTES_DEFECTO),
        "progreso": copy.deepcopy(_PROGRESO_DEFECTO),
    }


ESQUEMA_MENTOR_DEFECTO = _perfil_default()


# ─── MIGRACIÓN v1 → v2 (idempotente) ───────────────────────────────────────

def _migrar_a_v2(perfil: dict) -> dict:
    """Convierte un perfil v1 (solo campos legacy) al modelo multitema v2."""
    if isinstance(perfil.get("temas"), dict) and perfil.get("temas"):
        return perfil
    tema = {
        "nombre": NOMBRE_TEMA_DESARROLLO,
        "objetivo_general": "",
        "contexto": {
            "stack_objetivo": copy.deepcopy(perfil.get("stack_objetivo", _STACK_OBJETIVO_DEFECTO)),
            "tecnologias_aprendidas": perfil.get("tecnologias_aprendidas", []),
            "tecnologias_en_estudio": perfil.get("tecnologias_en_estudio", []),
            "proyectos_de_portafolio": perfil.get("proyectos_de_portafolio", []),
            "claves_de_contexto_faltantes": perfil.get("claves_de_contexto_faltantes", []),
        },
        "progreso": copy.deepcopy(perfil.get("progreso", _PROGRESO_DEFECTO)),
        "ultimo_avance_registrado": perfil.get("ultimo_avance_registrado", "Ninguno"),
        "historial_sesiones": perfil.get("historial_sesiones", []),
    }
    perfil["meta"] = {"version": 2}
    perfil["tema_activo"] = SLUG_TEMA_DESARROLLO
    perfil["temas"] = {SLUG_TEMA_DESARROLLO: tema}
    return perfil


def _asegurar_minimo(perfil: dict) -> dict:
    """Completa claves faltantes (espejo legacy + registro de temas)."""
    for k, v in _perfil_default().items():
        if k not in perfil:
            perfil[k] = copy.deepcopy(v)
    temas = perfil.get("temas")
    if not isinstance(temas, dict) or not temas:
        perfil["temas"] = {SLUG_TEMA_DESARROLLO: _tema_default(SLUG_TEMA_DESARROLLO)}
        perfil["tema_activo"] = SLUG_TEMA_DESARROLLO
    if perfil.get("tema_activo") not in perfil["temas"]:
        perfil["tema_activo"] = next(iter(perfil["temas"]))
    tema = perfil["temas"][perfil["tema_activo"]]
    for clave, default in (
        ("nombre", "Sin nombre"),
        ("objetivo_general", ""),
        ("contexto", {}),
        ("progreso", _PROGRESO_DEFECTO),
        ("ultimo_avance_registrado", "Ninguno"),
        ("historial_sesiones", []),
    ):
        if clave not in tema:
            tema[clave] = copy.deepcopy(default)
    if not isinstance(tema.get("contexto"), dict):
        tema["contexto"] = {}
    return perfil


def _sincronizar_tema_activo(perfil: dict) -> None:
    """
    Vuelca el espejo legacy (nivel superior) dentro del tema activo del
    registro. Se llama en CADA guardado: garantiza que `temas[tema_activo]`
    refleje siempre la copia de trabajo de nivel superior.
    """
    temas = perfil.get("temas")
    if not isinstance(temas, dict) or not temas:
        perfil["temas"] = {SLUG_TEMA_DESARROLLO: _tema_default(SLUG_TEMA_DESARROLLO)}
        temas = perfil["temas"]
    slug = perfil.get("tema_activo", SLUG_TEMA_DESARROLLO)
    if slug not in temas:
        slug = SLUG_TEMA_DESARROLLO
        perfil["tema_activo"] = slug
        temas.setdefault(slug, _tema_default(slug))
    tema = temas[slug]
    ctx = tema.setdefault("contexto", {})
    ctx["stack_objetivo"] = copy.deepcopy(perfil.get("stack_objetivo", _STACK_OBJETIVO_DEFECTO))
    ctx["tecnologias_aprendidas"] = perfil.get("tecnologias_aprendidas", [])
    ctx["tecnologias_en_estudio"] = perfil.get("tecnologias_en_estudio", [])
    ctx["proyectos_de_portafolio"] = perfil.get("proyectos_de_portafolio", [])
    ctx["claves_de_contexto_faltantes"] = perfil.get("claves_de_contexto_faltantes", [])
    tema["progreso"] = copy.deepcopy(perfil.get("progreso", _PROGRESO_DEFECTO))
    tema["ultimo_avance_registrado"] = perfil.get("ultimo_avance_registrado", "Ninguno")
    tema["historial_sesiones"] = perfil.get("historial_sesiones", [])


def _restaurar_mirror(perfil: dict) -> None:
    """Copia el tema activo del registro al espejo legacy de nivel superior."""
    temas = perfil.get("temas")
    if not isinstance(temas, dict):
        return
    slug = perfil.get("tema_activo", SLUG_TEMA_DESARROLLO)
    if slug not in temas:
        return
    tema = temas[slug]
    ctx = tema.get("contexto", {}) or {}
    perfil["stack_objetivo"] = copy.deepcopy(ctx.get("stack_objetivo", _STACK_OBJETIVO_DEFECTO))
    perfil["tecnologias_aprendidas"] = ctx.get("tecnologias_aprendidas", [])
    perfil["tecnologias_en_estudio"] = ctx.get("tecnologias_en_estudio", [])
    perfil["proyectos_de_portafolio"] = ctx.get("proyectos_de_portafolio", [])
    perfil["claves_de_contexto_faltantes"] = ctx.get("claves_de_contexto_faltantes", [])
    perfil["progreso"] = copy.deepcopy(tema.get("progreso", _PROGRESO_DEFECTO))
    perfil["ultimo_avance_registrado"] = tema.get("ultimo_avance_registrado", "Ninguno")
    perfil["historial_sesiones"] = tema.get("historial_sesiones", [])


def _tema_activo_slug(perfil: dict) -> str:
    """Slug del tema activo, con fallback determinista al tema de desarrollo."""
    temas = perfil.get("temas")
    slug = perfil.get("tema_activo", SLUG_TEMA_DESARROLLO)
    if not isinstance(temas, dict) or slug not in temas:
        return SLUG_TEMA_DESARROLLO
    return slug


def obtener_tema(perfil: dict, slug: str = None) -> dict:
    """Devuelve un tema del registro (sin tocar el espejo legacy)."""
    temas = perfil.get("temas")
    if not isinstance(temas, dict):
        return None
    slug = slug or _tema_activo_slug(perfil)
    return temas.get(slug)


def obtener_tema_por_nombre_o_slug(perfil: dict, texto) -> str:
    """Encuentra el slug de un tema por nombre o slug (case-insensitive)."""
    if not texto:
        return None
    low = str(texto).strip().lower()
    temas = perfil.get("temas")
    if not isinstance(temas, dict):
        return None
    for slug, t in temas.items():
        if slug == low or (t.get("nombre") or "").lower() == low:
            return slug
    return None


def cargar_perfil_mentor() -> dict:
    """
    Carga el perfil del mentor desde disco. Thread-safe.
    Migra v1 → v2 si corresponde. Si no existe o está corrupto, crea el default.
    """
    with _lock_perfil_mentor:
        if not os.path.exists(RUTA_PERFIL_MENTOR):
            logger.info("perfil_mentor.json no encontrado. Creando estructura por defecto.")
            _guardar_perfil_mentor_sin_lock(_perfil_default())
            return _perfil_default()
        try:
            with open(RUTA_PERFIL_MENTOR, "r", encoding="utf-8") as f:
                perfil = json.load(f)
            if not isinstance(perfil, dict):
                return _perfil_default()
            perfil = _migrar_a_v2(perfil)
            perfil = _asegurar_minimo(perfil)
            return perfil
        except Exception as e:
            logger.exception(f"Error cargando perfil_mentor.json: {e}")
            return _perfil_default()

def guardar_perfil_mentor(perfil: dict) -> None:
    """Guarda el perfil del mentor en disco. Thread-safe."""
    with _lock_perfil_mentor:
        perfil = _migrar_a_v2(perfil)
        _sincronizar_tema_activo(perfil)
        _guardar_perfil_mentor_sin_lock(perfil)

def _guardar_perfil_mentor_sin_lock(perfil: dict) -> None:
    try:
        with open(RUTA_PERFIL_MENTOR, "w", encoding="utf-8") as f:
            json.dump(perfil, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.exception(f"Error escribiendo perfil_mentor.json: {e}")


# ─── GESTIÓN DE TEMAS (API para GUI y activación) ───────────────────────────

def listar_temas_mentoria() -> dict:
    """Devuelve el registro de temas con su seguimiento (para la GUI)."""
    perfil = cargar_perfil_mentor()
    _sincronizar_tema_activo(perfil)
    activo = _tema_activo_slug(perfil)
    temas = perfil.get("temas")
    if not isinstance(temas, dict):
        temas = {}
    lista = []
    for slug, t in temas.items():
        if not isinstance(t, dict):
            continue
        prog = t.get("progreso", {}) or {}
        cont = prog.get("continuidad", {}) or {}
        objetivos = prog.get("objetivos", [])
        if not isinstance(objetivos, list):
            objetivos = []
        hitos = prog.get("hitos_completados", [])
        if not isinstance(hitos, list):
            hitos = []
        lista.append({
            "slug": slug,
            "nombre": t.get("nombre", slug),
            "objetivo_general": t.get("objetivo_general", ""),
            "activo": slug == activo,
            "ultima_fecha": cont.get("ultima_fecha", ""),
            "donde_quedamos": cont.get("donde_quedamos", ""),
            "objetivos_activos": sum(
                1 for o in objetivos
                if isinstance(o, dict) and o.get("estado") == "activo"
            ),
            "hitos": len(hitos),
            "ultimo_avance": t.get("ultimo_avance_registrado", ""),
            "n_sesiones": len(t.get("historial_sesiones", []) or []),
        })
    return {"tema_activo": activo, "temas": lista}


def cambiar_tema_activo(slug: str) -> bool:
    """Cambia el tema activo (persiste). Devuelve False si no existe."""
    perfil = cargar_perfil_mentor()
    temas = perfil.get("temas")
    if not isinstance(temas, dict) or slug not in temas:
        return False
    if slug == _tema_activo_slug(perfil):
        return True
    _sincronizar_tema_activo(perfil)
    perfil["tema_activo"] = slug
    _restaurar_mirror(perfil)
    guardar_perfil_mentor(perfil)
    return True


def crear_tema(nombre: str, objetivo_general: str = "") -> dict:
    """
    Crea un tema nuevo (o selecciona uno existente con el mismo slug) y lo
    deja como tema activo. Persiste. Devuelve {exito, slug, nombre, creado}.
    """
    nombre = (nombre or "").strip()
    if not nombre:
        return {"exito": False, "error": "El nombre del tema está vacío."}
    slug = _slug_estable(nombre)
    perfil = cargar_perfil_mentor()
    temas = perfil.setdefault("temas", {})
    if not isinstance(temas, dict):
        temas = {}
        perfil["temas"] = temas
    if slug in temas:
        perfil["tema_activo"] = slug
        _restaurar_mirror(perfil)
        guardar_perfil_mentor(perfil)
        return {"exito": True, "slug": slug, "nombre": temas[slug].get("nombre", nombre), "creado": False}
    _sincronizar_tema_activo(perfil)
    nuevo = _tema_default(slug)
    nuevo["nombre"] = nombre
    nuevo["objetivo_general"] = (objetivo_general or "").strip()
    temas[slug] = nuevo
    perfil["tema_activo"] = slug
    _restaurar_mirror(perfil)
    guardar_perfil_mentor(perfil)
    return {"exito": True, "slug": slug, "nombre": nombre, "creado": True}


# Patrones de lenguaje para crear/cambiar de tema desde la conversación.
# El auto-creado queda restringido a señales EXPLÍCITAS ("tema:", "nuevo
# tema", "crear tema", "empecemos") para evitar activaciones no deseadas;
# mencionar un tema existente solo lo selecciona.
_PATRON_CREAR_TEMA = re.compile(
    r"(?:tema\s*:|nuevo tema|crear\s*(?:el\s+)?tema|cre[áa]\s+(?:el\s+)?tema|"
    r"empecemos\s+(?:con|un)\s+|empezar\s+(?:el\s+)?tema|abr[íi]\s+un\s+tema)\s+"
    r"([A-Za-zÁÉÍÓÚáéíóúñÑ][A-Za-z0-9ÁÉÍÓÚáéíóúñÑ\s\-]{2,})",
    re.IGNORECASE,
)


def _nombre_tema(slug: str) -> str:
    perfil = cargar_perfil_mentor()
    t = obtener_tema(perfil, slug)
    return t.get("nombre", slug) if t else slug


def resolver_tema_mentoria(texto) -> dict:
    """
    Decide el tema de mentoría para un mensaje del usuario.

    - Señal explícita de creación ("tema: X", "nuevo tema X", "crear tema X",
      "empecemos con X") → crea y activa.
    - Mención de un tema existente por su nombre → lo activa.
    - Sin señal → mantiene el tema activo actual.

    Persiste SOLO cuando hay un cambio (evita escrituras por turno).
    Devuelve {"slug", "nombre", "cambio": bool, "creado": bool}.
    """
    if not texto or not str(texto).strip():
        slug = _tema_activo_slug(cargar_perfil_mentor())
        return {"slug": slug, "nombre": _nombre_tema(slug), "cambio": False, "creado": False}
    perfil = cargar_perfil_mentor()
    low = str(texto).lower()
    m = _PATRON_CREAR_TEMA.search(low)
    if m:
        nombre = m.group(1).strip()
        slug = _slug_estable(nombre)
        temas = perfil.get("temas")
        if not isinstance(temas, dict) or slug not in temas:
            res = crear_tema(nombre)
            return {"slug": slug, "nombre": res.get("nombre", nombre), "cambio": True, "creado": res.get("creado", False)}
        if cambiar_tema_activo(slug):
            return {"slug": slug, "nombre": _nombre_tema(slug), "cambio": True, "creado": False}
    else:
        temas = perfil.get("temas")
        if isinstance(temas, dict):
            for s, t in temas.items():
                nombre_t = (t.get("nombre") or s).lower()
                if nombre_t and len(nombre_t) >= 3 and nombre_t in low:
                    if cambiar_tema_activo(s):
                        return {"slug": s, "nombre": t.get("nombre", s), "cambio": True, "creado": False}
                    break
    slug = _tema_activo_slug(perfil)
    return {"slug": slug, "nombre": _nombre_tema(slug), "cambio": False, "creado": False}


# ─── EDICIÓN / OLVIDO POR ID LÓGICO (FASE 2) ─────────────────────────────────

def _slug_estable(texto: str) -> str:
    """Espejo de `resumen_memoria._slug` (mantiene coherencia de ids).

    Verificar SIEMPRE: los ids lógicos de los elementos del panel se generan
    con resumen_memoria._slug; esta copia debe quedar idéntica para poder
    localizar el dato original por su id.
    """
    if not texto:
        return "item"
    limpio = re.sub(r"[^a-zA-Z0-9]+", "_", texto.strip().lower()).strip("_")
    return limpio or "item"


def _progreso(perfil: dict) -> dict:
    """Acceso seguro al bloque 'progreso' del perfil mentor (no persiste)."""
    import copy
    p = perfil.get("progreso")
    if not isinstance(p, dict):
        p = {}
    base = ESQUEMA_MENTOR_DEFECTO["progreso"]
    result = dict(p)
    for k, v in base.items():
        result.setdefault(k, copy.deepcopy(v))
    return result


def _indices_progreso_objetivos_por_slug(perfil: dict, slug: str) -> list:
    """Índices de objetivos cuyo 'titulo' tiene el slug dado."""
    objetivos = _progreso(perfil).get("objetivos", [])
    if not isinstance(objetivos, list):
        return []
    return [
        i for i, o in enumerate(objetivos)
        if isinstance(o, dict) and _slug_estable(str(o.get("titulo", ""))) == slug
    ]


def _indices_progreso_dificultades_por_slug(perfil: dict, slug: str) -> list:
    """Índices de dificultades activas cuyo 'tema' tiene el slug dado."""
    difs = _progreso(perfil).get("dificultades_activas", [])
    if not isinstance(difs, list):
        return []
    return [
        i for i, d in enumerate(difs)
        if isinstance(d, dict) and _slug_estable(str(d.get("tema", ""))) == slug
    ]


def _indices_progreso_hitos_por_slug(perfil: dict, slug: str) -> list:
    """Índices de hitos cuyo 'texto' tiene el slug dado."""
    hitos = _progreso(perfil).get("hitos_completados", [])
    if not isinstance(hitos, list):
        return []
    return [
        i for i, h in enumerate(hitos)
        if isinstance(h, dict) and _slug_estable(str(h.get("texto", ""))) == slug
    ]


def _dividir_lista_segun(texto: str, separador: str = " · ") -> list:
    """Divide un texto plano de edición en elementos de lista determinista."""
    if not texto.strip():
        return []
    return [parte.strip() for parte in texto.split(separador) if parte.strip()]


def _indices_proyectos_por_slug(perfil: dict, slug: str) -> list:
    """Índices de proyectos de portafolio cuyo 'nombre' tiene el slug dado."""
    proyectos = perfil.get("proyectos_de_portafolio", [])
    if not isinstance(proyectos, list):
        return []
    return [
        i for i, p in enumerate(proyectos)
        if isinstance(p, dict) and _slug_estable(str(p.get("nombre", ""))) == slug
    ]


def _olvidar_en_perfil(perfil: dict, id_elemento: str) -> bool:
    """
    Aplica el olvido sobre un perfil EN MEMORIA (no persiste).

    Es la ÚNICA implementación del mapeo id → mutación del perfil mentor.
    `olvidar_elemento` y el filtro post-IA de extracción de sesión usan esta
    misma función para que ambos mecanismos jamás puedan divergir.

    - 'mentor:stack_<clave>' → restablece el valor por defecto del esquema.
    - 'mentor:stack_otras' → limpia la lista de otras herramientas.
    - 'mentor:tecnologias_aprendidas' / 'mentor:tecnologias_en_estudio'
      → limpia la lista.
    - 'mentor:ultimo_avance' → restablece "Ninguno".
    - 'mentor:proximos_pasos' → vacía los próximos pasos de la última sesión.
    - 'mentor:proyecto:<slug>' → elimina el proyecto (solo si hay UNA
      coincidencia de slug; si hay varias o ninguna, no toca nada).

    Devuelve True si aplicó el cambio; False si el id no pertenece a este
    perfil o el dato no existe / es ambiguo.
    """
    id_ = str(id_elemento or "")
    if not id_.startswith("mentor:"):
        return False
    resto = id_[len("mentor:"):]

    if resto.startswith("tema:"):
        slug = resto[len("tema:"):]
        temas = perfil.get("temas")
        if not isinstance(temas, dict) or slug not in temas:
            return False
        del temas[slug]
        if _tema_activo_slug(perfil) == slug:
            if temas:
                perfil["tema_activo"] = next(iter(temas))
            else:
                perfil["tema_activo"] = SLUG_TEMA_DESARROLLO
                temas[SLUG_TEMA_DESARROLLO] = _tema_default(SLUG_TEMA_DESARROLLO)
            _restaurar_mirror(perfil)
        return True

    if resto.startswith("proyecto:"):
        slug = resto[len("proyecto:"):]
        indices = _indices_proyectos_por_slug(perfil, slug)
        if len(indices) != 1:
            return False
        del perfil["proyectos_de_portafolio"][indices[0]]
        return True

    if resto == "stack_otras":
        perfil.setdefault("stack_objetivo", {})["otras_herramientas"] = []
        return True

    if resto == "stack_frontend" or resto == "stack_backend" or resto == "stack_bases_de_datos":
        clave = resto[len("stack_"):]
        perfil.setdefault("stack_objetivo", {})[clave] = ESQUEMA_MENTOR_DEFECTO["stack_objetivo"][clave]
        return True

    if resto == "tecnologias_aprendidas" or resto == "tecnologias_en_estudio":
        perfil[resto] = []
        return True

    if resto == "ultimo_avance":
        perfil["ultimo_avance_registrado"] = "Ninguno"
        return True

    if resto == "proximos_pasos":
        historial = perfil.get("historial_sesiones", [])
        if isinstance(historial, list) and historial and isinstance(historial[-1], dict):
            historial[-1]["proximos_pasos"] = []
            return True
        return False

    if resto.startswith("progreso_objetivo:"):
        slug = resto[len("progreso_objetivo:"):]
        indices = _indices_progreso_objetivos_por_slug(perfil, slug)
        if len(indices) != 1:
            return False
        del perfil["progreso"]["objetivos"][indices[0]]
        return True

    if resto.startswith("progreso_dificultad:"):
        slug = resto[len("progreso_dificultad:"):]
        indices = _indices_progreso_dificultades_por_slug(perfil, slug)
        if len(indices) != 1:
            return False
        del perfil["progreso"]["dificultades_activas"][indices[0]]
        return True

    if resto.startswith("progreso_hito:"):
        slug = resto[len("progreso_hito:"):]
        indices = _indices_progreso_hitos_por_slug(perfil, slug)
        if len(indices) != 1:
            return False
        del perfil["progreso"]["hitos_completados"][indices[0]]
        return True

    if resto == "progreso_proximos_pasos":
        perfil.setdefault("progreso", {})["proximos_pasos"] = []
        return True

    if resto == "progreso_continuidad":
        perfil.setdefault("progreso", {})["continuidad"] = {
            "ultimo_tema": "", "ultima_fecha": "", "donde_quedamos": ""
        }
        return True

    return False


def olvidar_elemento(id_elemento: str) -> bool:
    """
    Borra un dato del perfil del mentor según su id lógico.

    - 'mentor:stack_<clave>' → restablece el valor por defecto del esquema.
    - 'mentor:stack_otras' → limpia la lista de otras herramientas.
    - 'mentor:tecnologias_aprendidas' / 'mentor:tecnologias_en_estudio'
      → limpia la lista.
    - 'mentor:ultimo_avance' → restablece "Ninguno".
    - 'mentor:proximos_pasos' → vacía los próximos pasos de la última sesión.
    - 'mentor:proyecto:<slug>' → elimina el proyecto (solo si hay UNA
      coincidencia de slug; si hay varias o ninguna, no toca nada).

    Devuelve True si se aplicó el cambio (y se persistió); False si el id
    no pertenece a este perfil o el dato no existe / es ambiguo.
    """
    perfil = cargar_perfil_mentor()
    if not _olvidar_en_perfil(perfil, id_elemento):
        return False
    guardar_perfil_mentor(perfil)
    return True


def editar_elemento(id_elemento: str, texto: str) -> bool:
    """
    Actualiza el contenido de un dato del perfil del mentor.

    - 'mentor:stack_<clave>' → reemplaza el valor escalar.
    - 'mentor:stack_otras' / tecnologías / próximos_pasos → reemplaza la
      lista reinterpretando el texto editado (split por " · ").
    - 'mentor:ultimo_avance' → reemplaza el texto.
    - 'mentor:proyecto:<slug>' → reemplaza la descripción del proyecto
      (el nombre se conserva).

    Devuelve True si se aplicó (y se persistió); False si el id no
    pertenece a este perfil o el dato no existe / es ambiguo.
    """
    texto = (texto or "").strip()
    id_ = str(id_elemento or "")
    if not id_.startswith("mentor:"):
        return False
    resto = id_[len("mentor:"):]

    if resto.startswith("proyecto:"):
        slug = resto[len("proyecto:"):]
        perfil = cargar_perfil_mentor()
        indices = _indices_proyectos_por_slug(perfil, slug)
        if len(indices) != 1:
            return False
        perfil["proyectos_de_portafolio"][indices[0]]["descripcion"] = texto
        guardar_perfil_mentor(perfil)
        return True

    if resto == "stack_otras":
        perfil = cargar_perfil_mentor()
        perfil.setdefault("stack_objetivo", {})["otras_herramientas"] = _dividir_lista_segun(texto)
        guardar_perfil_mentor(perfil)
        return True

    if resto == "stack_frontend" or resto == "stack_backend" or resto == "stack_bases_de_datos":
        clave = resto[len("stack_"):]
        perfil = cargar_perfil_mentor()
        perfil.setdefault("stack_objetivo", {})[clave] = texto
        guardar_perfil_mentor(perfil)
        return True

    if resto == "tecnologias_aprendidas" or resto == "tecnologias_en_estudio":
        perfil = cargar_perfil_mentor()
        perfil[resto] = _dividir_lista_segun(texto)
        guardar_perfil_mentor(perfil)
        return True

    if resto == "ultimo_avance":
        perfil = cargar_perfil_mentor()
        perfil["ultimo_avance_registrado"] = texto
        guardar_perfil_mentor(perfil)
        return True

    if resto == "proximos_pasos":
        perfil = cargar_perfil_mentor()
        historial = perfil.get("historial_sesiones", [])
        if isinstance(historial, list) and historial and isinstance(historial[-1], dict):
            historial[-1]["proximos_pasos"] = _dividir_lista_segun(texto)
            guardar_perfil_mentor(perfil)
            return True
        return False

    if resto == "progreso_proximos_pasos":
        perfil = cargar_perfil_mentor()
        perfil.setdefault("progreso", {})["proximos_pasos"] = _dividir_lista_segun(texto)
        guardar_perfil_mentor(perfil)
        return True

    if resto.startswith("progreso_objetivo:"):
        slug = resto[len("progreso_objetivo:"):]
        perfil = cargar_perfil_mentor()
        indices = _indices_progreso_objetivos_por_slug(perfil, slug)
        if len(indices) != 1:
            return False
        perfil["progreso"]["objetivos"][indices[0]]["titulo"] = texto
        guardar_perfil_mentor(perfil)
        return True

    if resto.startswith("progreso_dificultad:"):
        slug = resto[len("progreso_dificultad:"):]
        perfil = cargar_perfil_mentor()
        indices = _indices_progreso_dificultades_por_slug(perfil, slug)
        if len(indices) != 1:
            return False
        perfil["progreso"]["dificultades_activas"][indices[0]]["tema"] = texto
        guardar_perfil_mentor(perfil)
        return True

    if resto.startswith("progreso_hito:"):
        slug = resto[len("progreso_hito:"):]
        perfil = cargar_perfil_mentor()
        indices = _indices_progreso_hitos_por_slug(perfil, slug)
        if len(indices) != 1:
            return False
        perfil["progreso"]["hitos_completados"][indices[0]]["texto"] = texto
        guardar_perfil_mentor(perfil)
        return True

    return False


def obtener_bitacora_workspace(workspace_path: str = "") -> str:
    """
    Busca si existe BITACORA_MENTOR.md o bitacora.md en el workspace anclado.
    Si existe, retorna las últimas entradas (máx 1200 caracteres) para economía de tokens.
    """
    if not workspace_path or not os.path.exists(workspace_path):
        return ""
    
    nombres_posibles = ["BITACORA_MENTOR.md", "bitacora_mentor.md", "BITACORA.md", "bitacora.md"]
    for nombre in nombres_posibles:
        ruta_file = os.path.join(workspace_path, nombre)
        if os.path.isfile(ruta_file):
            try:
                with open(ruta_file, "r", encoding="utf-8") as f:
                    contenido = f.read().strip()
                if contenido:
                    if len(contenido) > 1200:
                        contenido = "... [recortado por economía de tokens]\n" + contenido[-1200:]
                    return f"[BITÁCORA ANCLADA AL WORKSPACE ({nombre})]:\n{contenido}\n"
            except Exception as e:
                logger.warning(f"Error leyendo bitácora del workspace {ruta_file}: {e}")
    return ""

def _texto_progreso_para_prompt(p: dict) -> str:
    """Formatea el bloque de Progreso/Mentoría estructurado para el prompt."""
    prog = _progreso(p)
    lineas = []

    objetivos = prog.get("objetivos", [])
    if isinstance(objetivos, list) and objetivos:
        partes = []
        for o in objetivos:
            if isinstance(o, dict) and str(o.get("titulo", "")).strip():
                estado = str(o.get("estado", "")).strip()
                prioridad = str(o.get("prioridad", "")).strip()
                proy = str(o.get("proyecto_asociado", "")).strip()
                ref = o["titulo"]
                if estado:
                    ref += f" [{estado}]"
                if prioridad:
                    ref += f" (prioridad {prioridad})"
                if proy:
                    ref += f" · proyecto: {proy}"
                partes.append(ref)
        if partes:
            lineas.append(f"- OBJETIVOS: {', '.join(partes)}")

    pasos = prog.get("proximos_pasos", [])
    if isinstance(pasos, list) and pasos:
        pasos_limpios = [str(x).strip() for x in pasos if str(x).strip()]
        if pasos_limpios:
            lineas.append("- PRÓXIMOS PASOS: " + " · ".join(pasos_limpios))

    difs = prog.get("dificultades_activas", [])
    if isinstance(difs, list) and difs:
        partes = []
        for d in difs:
            if isinstance(d, dict) and str(d.get("tema", "")).strip():
                partes.append(f"{d['tema']} (×{d.get('ocurrencias', 1)})")
        if partes:
            lineas.append("- DIFICULTADES ACTIVAS: " + ", ".join(partes))

    hitos = prog.get("hitos_completados", [])
    if isinstance(hitos, list) and hitos:
        partes = []
        for h in hitos:
            if isinstance(h, dict) and str(h.get("texto", "")).strip():
                partes.append(h["texto"])
        if partes:
            lineas.append("- HITOS COMPLETADOS: " + " · ".join(partes))

    cont = prog.get("continuidad") or {}
    quedamos = str(cont.get("donde_quedamos", "")).strip()
    if quedamos:
        lineas.append(f"- CONTINUIDAD (dónde quedamos la última sesión): {quedamos}")

    if not lineas:
        return ""
    return "\n[PROGRESO Y MENTORÍA (estructurado)]:\n" + "\n".join(lineas) + "\n"


def texto_perfil_mentor_para_prompt(workspace_path: str = "") -> str:
    """
    Formatea el perfil del mentor en formato Markdown para inyectar en el prompt.
    Optimizado para economía de tokens.
    """
    p = cargar_perfil_mentor()
    
    stack = p.get("stack_objetivo", {})
    frontend = stack.get("frontend", "Pendiente")
    backend = stack.get("backend", "Pendiente")
    db = stack.get("bases_de_datos", "Pendiente")
    otras = ", ".join(stack.get("otras_herramientas", [])) or "Ninguna"
    
    aprendidas = ", ".join(p.get("tecnologias_aprendidas", [])) or "Ninguna"
    estudio = ", ".join(p.get("tecnologias_en_estudio", [])) or "Ninguna"
    
    proyectos_str = ""
    for proj in p.get("proyectos_de_portafolio", []):
        if isinstance(proj, dict):
            nombre_p = proj.get("nombre", "Proyecto")
            desc_p = proj.get("descripcion", "")
            proyectos_str += f"- **{nombre_p}**: {desc_p}\n"
        else:
            proyectos_str += f"- {proj}\n"
    if not proyectos_str:
        proyectos_str = "- Ninguno registrado aún\n"
        
    preguntas_str = ""
    for preg in p.get("claves_de_contexto_faltantes", []):
        preguntas_str += f"- {preg}\n"
    if not preguntas_str:
        preguntas_str = "- Todo el contexto básico completado\n"
        
    avance = p.get("ultimo_avance_registrado", "Ninguno")
    
    historial = p.get("historial_sesiones", [])
    historial_str = ""
    if historial:
        for s in historial[-3:]:
            fecha = s.get("fecha", "Reciente")
            res = s.get("resumen", "")
            pasos = ", ".join(s.get("proximos_pasos", [])) if isinstance(s.get("proximos_pasos"), list) else s.get("proximos_pasos", "")
            historial_str += f"  * [{fecha}] Resumen: {res}"
            if pasos:
                historial_str += f" | Próximos pasos: {pasos}"
            historial_str += "\n"
    else:
        historial_str = f"  * Único avance guardado: {avance}\n"

    texto_bitacora_ws = obtener_bitacora_workspace(workspace_path)

    # Tema activo: el espejo legacy (nivel superior) ya refleja al tema activo;
    # sumamos su nombre y objetivo general para el encabezado del prompt.
    slug_tema = _tema_activo_slug(p)
    tema = obtener_tema(p, slug_tema) or {}
    nombre_tema = tema.get("nombre", slug_tema)
    objetivo_tema = str(tema.get("objetivo_general", "") or "").strip()

    texto = (
        "[PERFIL DEL TEMA ACTIVO DE MENTORÍA]:\n"
        f"- TEMA ACTIVO: {nombre_tema}\n"
        + (f"- OBJETIVO GENERAL DEL TEMA: {objetivo_tema}\n" if objetivo_tema else "")
        + "Este es el estado del tema y la bitácora de sesiones de Luis. "
        "YA TIENES ESTA INFORMACIÓN EN CONTEXTO, no necesitas realizar lecturas de archivos de bitácora al iniciar.\n"
        "- STACK OBJETIVO:\n"
        f"  * Frontend: {frontend}\n"
        f"  * Backend: {backend}\n"
        f"  * Bases de Datos: {db}\n"
        f"  * Otras herramientas: {otras}\n"
        f"- Tecnologías Aprendidas/Conocidas: {aprendidas}\n"
        f"- Tecnologías en Estudio Actual: {estudio}\n"
        f"- Proyectos de Portafolio Planificados/En curso:\n{proyectos_str}"
        f"- HISTORIAL DE ÚLTIMAS SESIONES Y AVANCES:\n{historial_str}"
        f"- Claves de contexto faltantes (Si es oportuno y fluye con la charla, hazle una de estas preguntas para completar su perfil):\n"
        f"{preguntas_str}"
    )
    if texto_bitacora_ws:
        texto += f"\n{texto_bitacora_ws}"

    texto += _texto_progreso_para_prompt(p)

    return texto

def extraer_y_procesar_sesion_mentor(ultimos_mensajes: list, workspace_path: str = "") -> None:
    """
    Extrae hechos tecnológicos y actualiza perfil_mentor.json (y BITACORA_MENTOR.md si hay workspace)
    usando Gemini Flash Lite con estricta economía de tokens.
    """
    if not ultimos_mensajes:
        return
        
    mensajes_relevantes = ultimos_mensajes[-14:]
    conversacion = ""
    for msg in mensajes_relevantes:
        role = msg.get("role", "user")
        parts = msg.get("parts", [])
        text = ""
        for part in parts:
            if isinstance(part, str):
                text += part
            elif isinstance(part, dict) and "text" in part:
                text += part["text"]
        if len(text) > 500:
            text = text[:500] + "... [truncado]"
        conversacion += f"{role.upper()}: {text}\n"

    if not conversacion.strip():
        return

    from modulos.ia import cliente_genai
    from google.genai import types

    perfil_actual = cargar_perfil_mentor()
    fecha_hoy = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    prompt = (
        "Analiza la siguiente conversación reciente entre Luis (el estudiante) y su Mentor Tecnológico (Argus).\n"
        "Tu tarea es extraer actualizaciones para su perfil de mentoría y devolver el perfil_mentor.json actualizado.\n\n"
        f"Perfil actual de mentoría:\n{json.dumps(perfil_actual, ensure_ascii=False, indent=2)}\n\n"
        "INSTRUCCIONES DE ACTUALIZACIÓN:\n"
        "1. Revisa si Luis menciona nuevas tecnologías que aprendió o que quiere aprender. Agrégalas a 'tecnologias_aprendidas' o 'tecnologias_en_estudio'.\n"
        "2. Revisa si Luis responde a alguna de las 'claves_de_contexto_faltantes'. Si es así, actualiza los campos correspondientes y ELIMINA esa pregunta de la lista.\n"
        "3. Revisa si definieron o avanzaron en algún proyecto de portafolio y actualiza 'proyectos_de_portafolio'.\n"
        "4. En 'ultimo_avance_registrado', guarda un resumen de 1 sola frase con el logro principal de la sesión.\n"
        "5. En 'historial_sesiones', agrega un nuevo objeto: "
        f'{{"fecha": "{fecha_hoy}", "resumen": "resumen breve de lo trabajado", "temas": ["tema1", "tema2"], "proximos_pasos": ["paso1", "paso2"]}}. '
        "MANTÉN MÁXIMO 5 SESIONES en 'historial_sesiones' (elimina la más antigua si supera 5).\n"
        "6. Devuelve el JSON completo con las modificaciones integradas.\n"
        "7. IMPORTANTE: No inventes información. Si no hubo avances significativos, actualiza la lista con un resumen sucinto.\n"
        "8. Responde ÚNICAMENTE con el objeto JSON limpio. No uses formato de markdown (sin ```json) ni explicaciones.\n\n"
        f"Conversación reciente:\n{conversacion}\n\n"
        "JSON Actualizado:"
    )
    
    try:
        respuesta = cliente_genai.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=1500
            )
        )
        texto = respuesta.text.strip()
        
        # Despojar markdown si viniera
        if texto.startswith("```"):
            lineas = texto.split("\n")
            if lineas[0].strip().startswith("```"):
                lineas = lineas[1:]
            if lineas and lineas[-1].strip() == "```":
                lineas = lineas[:-1]
            texto = "\n".join(lineas).strip()
            
        nuevo_perfil = json.loads(texto)
        if isinstance(nuevo_perfil, dict):
            # Validar que no se pierdan claves principales
            for k in ESQUEMA_MENTOR_DEFECTO.keys():
                if k not in nuevo_perfil:
                    nuevo_perfil[k] = perfil_actual.get(k, ESQUEMA_MENTOR_DEFECTO[k])

            # El registro de temas y la selección de tema activo NO los decide
            # el LLM: se conservan del perfil previo (el LLM solo actualiza el
            # espejo legacy del TEMA ACTIVO en el nivel superior).
            nuevo_perfil["temas"] = perfil_actual.get("temas", {})
            nuevo_perfil["meta"] = perfil_actual.get("meta", {"version": 2})
            nuevo_perfil["tema_activo"] = perfil_actual.get("tema_activo", SLUG_TEMA_DESARROLLO)

            # `progreso` es gestionado por modulos/progreso_mentoria.py (Fase 5):
            # este reescritor completo NO debe reescribirlo. Se conserva tal cual
            # estaba en el perfil anterior (evita que el LLM lo pise o lo invente).
            nuevo_perfil["progreso"] = _progreso(perfil_actual)

            # Limitar historial a 5 entradas máx
            if "historial_sesiones" in nuevo_perfil and isinstance(nuevo_perfil["historial_sesiones"], list):
                nuevo_perfil["historial_sesiones"] = nuevo_perfil["historial_sesiones"][-5:]

            # GARANTÍA DETERMINISTA (filtro post-IA): el LLM reconstruye el
            # perfil COMPLETO, así que puede reintroducir datos olvidados.
            # Se re-aplica el mismo olvido que usaría olvidar_elemento() antes
            # de persistir. El prompt jamás es la única barrera.
            from modulos.olvidos import obtener_ids_olvidados
            for id_bloqueado in obtener_ids_olvidados("mentor:"):
                _olvidar_en_perfil(nuevo_perfil, id_bloqueado)

            guardar_perfil_mentor(nuevo_perfil)
            logger.info("✅ perfil_mentor.json actualizado con éxito tras la sesión.")

            # Si hay workspace activo, actualizar también BITACORA_MENTOR.md en esa carpeta
            if not workspace_path:
                import config as _cfg
                workspace_path = getattr(_cfg.estado, "workspace_actual", "")

            if workspace_path and os.path.exists(workspace_path):
                try:
                    ruta_bitacora = os.path.join(workspace_path, "BITACORA_MENTOR.md")
                    historial = nuevo_perfil.get("historial_sesiones", [])
                    ultima = historial[-1] if historial else None
                    if ultima:
                        resumen = ultima.get("resumen", "")
                        temas = ", ".join(ultima.get("temas", [])) if isinstance(ultima.get("temas"), list) else ultima.get("temas", "")
                        pasos = ", ".join(ultima.get("proximos_pasos", [])) if isinstance(ultima.get("proximos_pasos"), list) else ultima.get("proximos_pasos", "")
                        
                        linea_nueva = f"\n### Sesión {fecha_hoy}\n- **Resumen:** {resumen}\n- **Temas tratados:** {temas}\n- **Próximos pasos:** {pasos}\n"
                        
                        if not os.path.exists(ruta_bitacora):
                            with open(ruta_bitacora, "w", encoding="utf-8") as f:
                                f.write(f"# Bitácora de Mentoría — Argus Copilot\n{linea_nueva}")
                        else:
                            with open(ruta_bitacora, "a", encoding="utf-8") as f:
                                f.write(linea_nueva)
                        logger.info(f"✅ BITACORA_MENTOR.md actualizada en workspace: {ruta_bitacora}")
                except Exception as e_ws:
                    logger.warning(f"Error escribiendo BITACORA_MENTOR.md en workspace: {e_ws}")
    except Exception as e:
        logger.exception(f"Error procesando sesión del mentor: {e}")

