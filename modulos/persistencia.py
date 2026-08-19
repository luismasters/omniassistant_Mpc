"""
Persistencia durable de la conversación (Fase P — MVP).

Diseño (ROADMAP §8.5.2):
  - Store append-only en JSONL, UN archivo por `context_id` (clave genérica,
    agnóstica a los nombres de modo; la Fase D solo cambia el mapeo).
  - Jerarquía: context_id → sesión → turno (turno_seq) → mensaje.
  - Una línea = un MENSaje (no un turno completo) para que el mensaje del
    usuario quede durable ANTES de que el LLM responda (garantía de cierre
    anormal: kill pierde a lo sumo la respuesta del modelo en vuelo, nunca
    mensajes previos ya escritos). El agrupado por turno se hace por
    `turno_seq` al leer.
  - Checksum sha256 por registro: al leer se descartan registros corruptos.
  - Deduplicación por (context_id, turno_seq, msg_seq) dentro del proceso.
  - Preferencias del usuario en `prefs.json` (workspace/modelo/visualización).
  - `cargar_estado_proyecto` NO persiste copias: solo recarga lo que ya existe
    (PROJECT_STATE.md → .cortana/snapshot.json → "").

Privacidad/seguridad:
  - Ruta por defecto: %LOCALAPPDATA%\\ArgusCopilot\\conversaciones\\ (FUERA
    del repo, evita que los auto-commits suban conversaciones privadas).
  - `OMNASSISTANT_NO_PERSISTENCIA=1` deshabilita TODA escritura/lectura real
    (equivalente a OMNASSISTANT_NO_FILE_LOG; se usa en tests/CI/headless).
  - `ARGUS_PERSISTENCIA_DIR` sobreescribe la ruta base (tests con tmp_path).
  - Escritura atómica para compactación/preferencias (tmp + os.replace).
"""

import hashlib
import json
import os
import threading

# =====================================================================
# CONFIGURACIÓN
# =====================================================================

STORE_VERSION = 1

# Cantidad máxima de mensajes que se recuperan del historial al "retomar".
MAX_MENSAJES_RECUPERACION = 25
# Tope de caracteres del bloque recuperado (evita inflar el contexto).
MAX_RECUPERACION_CARACTERES = 2000
# Sesiones que se conservan por contexto antes de purgar (rotación).
MAX_SESIONES_POR_CONTEXTO = 50

# Mensajes de sistema/marcadores que NO se recuperan al retomar (evita
# contaminar el contexto con confirmaciones o bloques ya resueltos).
_PREFIJO_EXCLUIDO_RECUPERACION = (
    "[SISTEMA]", "[CONTENIDO DE", "[EVIDENCIA", "[RECUERDO", "[PERFIL",
    "[DOCUMENTOS", "[CLIMA", "[ESTADO DEL PROYECTO]", "[WORKSPACE ANCLADO",
    "[SKILL ACTIVADA", "[FIN DE SKILL]", "[PROGRESO",
)

_RLOCK = threading.RLock()
# Sesiones abiertas en memoria por context_id (registro del proceso).
_sesiones_abiertas = {}
# Conjunto de escrituras ya hechas para dedup: {(context_id, turno_seq, msg_seq)}.
_escritos = set()
# Preferencias cacheadas.
_prefs_cache = None


# =====================================================================
# CONFIGURACIÓN DE RUTAS Y HABILITACIÓN
# =====================================================================

def _no_persistencia() -> bool:
    """True si la persistencia está deshabilitada (env para tests/CI/headless)."""
    return os.getenv("OMNASSISTANT_NO_PERSISTENCIA", "") in ("1", "true", "True")


def base_dir() -> str:
    """Carpeta base del store. Override con ARGUS_PERSISTENCIA_DIR."""
    override = os.getenv("ARGUS_PERSISTENCIA_DIR", "")
    if override:
        return os.path.abspath(override)
    local = os.getenv("LOCALAPPDATA", os.path.expanduser("~"))
    return os.path.join(local, "ArgusCopilot", "conversaciones")


def ruta_contexto(context_id: str) -> str:
    return os.path.join(base_dir(), f"{context_id}.jsonl")


def ruta_prefs() -> str:
    return os.path.join(base_dir(), "prefs.json")


def armar_context_id(modo_actual) -> str:
    """
    Mapeo transitorio modo → context_id genérico.

    Hoy devuelve el slug del modo como contexto; la Fase D reemplaza este
    mapeo por contextos/capacidades dinámicas SIN tocar el store.
    """
    slug = str(modo_actual or "general").strip().lower()
    if slug not in ("general", "chat", "mentor", "gamer"):
        return "general"
    if slug == "chat":
        return "general"
    return slug


# =====================================================================
# HELPERS DE ESCRITURA
# =====================================================================

def _canonical(data: dict) -> str:
    """Representación canónica del payload (para checksum y dedup)."""
    return json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)


def _linea_con_checksum(data: dict) -> str:
    """Devuelve una línea JSONL con checksum sha256 del contenido."""
    payload = dict(data)
    payload["sha"] = hashlib.sha256(_canonical(data).encode("utf-8")).hexdigest()
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _escribir_linea(ruta, data: dict) -> bool:
    """Append de una línea con flush inmediato (durabilidad por mensaje)."""
    try:
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        linea = _linea_con_checksum(data) + "\n"
        with open(ruta, "a", encoding="utf-8") as f:
            f.write(linea)
            f.flush()
        return True
    except Exception:
        return False


def _escribir_atomico(ruta, contenido: str) -> bool:
    """Escritura atómica: tmp + os.replace (para compactación/preferencias)."""
    try:
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        tmp = ruta + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(contenido)
            f.flush()
        os.replace(tmp, ruta)
        return True
    except Exception:
        return False


def _leer_registros(context_id: str):
    """
    Lee el JSONL del contexto y devuelve la lista de registros VÁLIDOS
    (checksum OK y json parseable). Los corruptos/truncados se descartan.
    """
    ruta = ruta_contexto(context_id)
    if not os.path.exists(ruta):
        return []
    registros = []
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if not linea:
                    continue
                try:
                    reg = json.loads(linea)
                except json.JSONDecodeError:
                    continue
                sha = reg.pop("sha", None)
                if sha is None:
                    continue
                if hashlib.sha256(_canonical(reg).encode("utf-8")).hexdigest() != sha:
                    continue
                registros.append(reg)
    except Exception:
        return registros
    return registros


# =====================================================================
# SESIONES Y MENSAJES
# =====================================================================

def sesion_actual(context_id: str):
    """Devuelve la sesión abierta en memoria para el contexto (o None)."""
    with _RLOCK:
        return _sesiones_abiertas.get(context_id)


def _nueva_sesion(context_id: str):
    """Abre una sesión nueva para el contexto y la persiste (marcador)."""
    sesion = {
        "tipo": "sesion",
        "context_id": context_id,
        "sesion_id": f"{context_id}-{int(__import__('time').time() * 1000):x}",
        "estado": "open",
        "orden": 0,
    }
    # El número de orden se deriva de las sesiones ya registradas en disco.
    orden = 0
    for reg in _leer_registros(context_id):
        if reg.get("tipo") == "sesion" and reg.get("orden", 0) >= orden:
            orden = int(reg["orden"]) + 1
    sesion["orden"] = orden
    with _RLOCK:
        _sesiones_abiertas[context_id] = sesion
    _escribir_linea(ruta_contexto(context_id), sesion)
    return sesion


def registrar_mensaje(context_id: str, role: str, parts, ts_ms=None) -> bool:
    """
    Persiste un mensaje del historial. Si no hay sesión abierta para el
    contexto, abre una. Es thread-safe y deduplica por
    (context_id, sesion_id, turno_seq, msg_seq). La escritura se hace DENTRO
    del lock para serializar los appends (evita races de archivo en Windows).
    Devuelve False si la persistencia está deshabilitada o falla.
    """
    if _no_persistencia():
        return False
    try:
        context_id = armar_context_id(context_id)
        role = "user" if role == "user" else "model"
        if isinstance(parts, str):
            parts = [parts]
        parts = [p for p in parts if isinstance(p, str)]

        with _RLOCK:
            sesion = _sesiones_abiertas.get(context_id)
            if sesion is None or sesion.get("estado") != "open":
                sesion = _nueva_sesion(context_id)

            turno_seq = sesion.get("_turno_seq", 0)
            msg_seq = 0 if role == "user" else 1
            if role == "user":
                turno_seq += 1
                msg_seq = 0
                sesion["_turno_seq"] = turno_seq
            clave = (context_id, sesion["sesion_id"], turno_seq, msg_seq)
            if clave in _escritos:
                return True
            _escritos.add(clave)

            ts = int(ts_ms) if ts_ms is not None else int(__import__("time").time() * 1000)
            reg = {
                "tipo": "msg",
                "context_id": context_id,
                "sesion_id": sesion["sesion_id"],
                "turno_seq": turno_seq,
                "msg_seq": msg_seq,
                "role": role,
                "parts": parts,
                "ts_ms": ts,
            }
            return _escribir_linea(ruta_contexto(context_id), reg)
    except Exception:
        return False


def cerrar_sesion(context_id: str, estado: str = "closed") -> bool:
    """
    Cierra la sesión abierta del contexto (marcador en disco y limpieza del
    registro en memoria). Idempotente.
    """
    if _no_persistencia():
        return False
    try:
        context_id = armar_context_id(context_id)
        with _RLOCK:
            sesion = _sesiones_abiertas.get(context_id)
            if sesion is None:
                return False
            sesion["estado"] = estado
            if estado == "closed":
                sesion["fin"] = int(__import__("time").time() * 1000)
        ok = _escribir_linea(ruta_contexto(context_id), sesion)
        with _RLOCK:
            if sesion.get("estado") != "open":
                _sesiones_abiertas.pop(context_id, None)
        return ok
    except Exception:
        return False


def marcar_sesiones_abiertas_como_aborted():
    """
    Detecta en disco las sesiones que quedaron abiertas (cierre anormal del
    proceso previo) y las marca como aborted. Devuelve la lista de context_id
    afectados. Se llama al iniciar Argus.
    """
    if _no_persistencia():
        return []
    afectados = []
    base = base_dir()
    if not os.path.isdir(base):
        return []
    for nombre in sorted(os.listdir(base)):
        if not nombre.endswith(".jsonl"):
            continue
        context_id = nombre[: -len(".jsonl")]
        registros = _leer_registros(context_id)
        # La sesión abierta es la última 'sesion' sin marcador posterior closed/aborted.
        sesiones = [r for r in registros if r.get("tipo") == "sesion"]
        if not sesiones:
            continue
        ultima = sesiones[-1]
        if ultima.get("estado") == "open":
            ultima["estado"] = "aborted"
            ultima["fin"] = int(__import__("time").time() * 1000)
            _escribir_linea(ruta_contexto(context_id), ultima)
            afectados.append(context_id)
    return afectados


# =====================================================================
# LECTURA Y RECUPERACIÓN
# =====================================================================

def listar_sesiones(context_id: str):
    """
    Lista las sesiones del contexto (de la más antigua a la más nueva).
    Cada sesión aparece UNA vez (se usa el último registro por sesion_id,
    que lleva el estado final: open/closed/aborted).
    """
    context_id = armar_context_id(context_id)
    por_sesion = {}
    for reg in _leer_registros(context_id):
        if reg.get("tipo") == "sesion" and reg.get("sesion_id"):
            por_sesion[reg["sesion_id"]] = reg
    return [por_sesion[sid] for sid in sorted(por_sesion, key=lambda s: por_sesion[s].get("orden", 0))]


def recuperar_tail(context_id: str, max_mensajes=None, max_caracteres=None) -> list:
    """
    Devuelve la lista de mensajes (role/parts) de la ÚLTIMA sesión del
    contexto, recortada a los últimos `max_mensajes` y `max_caracteres`.
    Excluye mensajes con prefijos de sistema/marcadores. NO escribe nada.
    """
    context_id = armar_context_id(context_id)
    max_mensajes = max_mensajes or MAX_MENSAJES_RECUPERACION
    max_caracteres = max_caracteres or MAX_RECUPERACION_CARACTERES

    sesiones = listar_sesiones(context_id)
    if not sesiones:
        return []
    ultima = sesiones[-1]
    sesion_id = ultima["sesion_id"]

    # Agrupar mensajes por turno y descartar los excluidos.
    mensajes = []
    for reg in _leer_registros(context_id):
        if reg.get("tipo") != "msg" or reg.get("sesion_id") != sesion_id:
            continue
        role = reg.get("role")
        parts = reg.get("parts", [])
        if not parts:
            continue
        texto = parts[0]
        if isinstance(texto, str) and texto.startswith(_PREFIJO_EXCLUIDO_RECUPERACION):
            continue
        mensajes.append({"role": role, "parts": parts, "_seq": (reg.get("turno_seq", 0), reg.get("msg_seq", 0))})

    mensajes.sort(key=lambda m: m["_seq"])

    # Recortar a los últimos `max_mensajes` y respetar el tope de caracteres
    # quedándose con las MÁS RECIENTES (las viejas se descartan primero).
    mensajes = mensajes[-max_mensajes:]
    resultado = []
    total_car = 0
    for m in reversed(mensajes):
        car = sum(len(p) for p in m["parts"] if isinstance(p, str))
        if total_car + car > max_caracteres:
            continue
        total_car += car
        resultado.append({"role": m["role"], "parts": m["parts"]})
    resultado.reverse()
    return resultado


def borrar_historial(context_id: str) -> bool:
    """Borra TODO el historial de un contexto (archivo y sesión en memoria)."""
    if _no_persistencia():
        return False
    try:
        context_id = armar_context_id(context_id)
        with _RLOCK:
            _sesiones_abiertas.pop(context_id, None)
        ruta = ruta_contexto(context_id)
        if os.path.exists(ruta):
            os.remove(ruta)
        return True
    except Exception:
        return False


def purgar_historial(context_id: str, conservar: int = None) -> int:
    """
    Rotación: reescribe el archivo conservando las últimas `conservar`
    sesiones ÚNICAS (por defecto MAX_SESIONES_POR_CONTEXTO). Devuelve cuántas
    sesiones se purgaron. Escritura atómica.
    """
    context_id = armar_context_id(context_id)
    conservar = conservar or MAX_SESIONES_POR_CONTEXTO
    registros = _leer_registros(context_id)

    sesiones = listar_sesiones(context_id)
    if len(sesiones) <= conservar:
        return 0
    conservar_ids = {s["sesion_id"] for s in sesiones[-conservar:]}
    conservados = [r for r in registros if r.get("sesion_id") in conservar_ids]
    contenido = "".join(_linea_con_checksum(r) + "\n" for r in conservados)
    if _escribir_atomico(ruta_contexto(context_id), contenido):
        return len(sesiones) - conservar
    return 0


def purgar_todos_los_contextos(conservar: int = None) -> int:
    """
    Rotación global: purga el historial de TODOS los contextos en disco que
    superen `conservar` sesiones (por defecto MAX_SESIONES_POR_CONTEXTO).
    Devuelve cuántos contextos se purgaron. Best-effort: contextos que fallen
    se ignoran. Se llama al arrancar Argus para mantener el disco acotado.
    """
    if _no_persistencia():
        return 0
    base = base_dir()
    if not os.path.isdir(base):
        return 0
    purgados = 0
    for nombre in sorted(os.listdir(base)):
        if not nombre.endswith(".jsonl"):
            continue
        context_id = nombre[: -len(".jsonl")]
        try:
            if purgar_historial(context_id, conservar=conservar) > 0:
                purgados += 1
        except Exception:
            continue
    return purgados


# =====================================================================
# PREFERENCIAS
# =====================================================================

def cargar_preferencias() -> dict:
    """Carga las preferencias persistentes del usuario (cacheadas)."""
    global _prefs_cache
    if _prefs_cache is not None:
        return dict(_prefs_cache)
    if _no_persistencia():
        return {}
    ruta = ruta_prefs()
    if not os.path.exists(ruta):
        return {}
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            data = json.load(f)
        _prefs_cache = dict(data)
        return dict(data)
    except Exception:
        return {}


def guardar_preferencias(prefs: dict) -> bool:
    """Guarda las preferencias del usuario (escritura atómica)."""
    global _prefs_cache
    if _no_persistencia():
        return False
    try:
        _prefs_cache = dict(prefs)
        ok = _escribir_atomico(ruta_prefs(), json.dumps(prefs, ensure_ascii=False, indent=2))
        return ok
    except Exception:
        return False


# =====================================================================
# ESTADO DE PROYECTO (recarga, NO copia)
# =====================================================================

def cargar_estado_proyecto(workspace) -> str:
    """
    Recarga el estado del proyecto a snapshot_actual desde lo que YA existe
    en el workspace: PROJECT_STATE.md (preferido) → .cortana/snapshot.json →
    "". NO persiste ninguna copia nueva.
    """
    if not workspace:
        return ""
    ruta_state = os.path.join(workspace, "PROJECT_STATE.md")
    if os.path.exists(ruta_state):
        try:
            with open(ruta_state, "r", encoding="utf-8") as f:
                contenido = f.read().strip()
            if contenido:
                return contenido
        except Exception:
            pass
    ruta_snapshot = os.path.join(workspace, ".cortana", "snapshot.json")
    if os.path.exists(ruta_snapshot):
        try:
            with open(ruta_snapshot, "r", encoding="utf-8") as f:
                data = json.load(f)
            return str(data.get("estado", ""))
        except Exception:
            return ""
    return ""


def reiniciar_estado_prueba():
    """Solo para tests: limpia registros en memoria y cachés."""
    global _prefs_cache
    with _RLOCK:
        _sesiones_abiertas.clear()
        _escritos.clear()
    _prefs_cache = None


# =====================================================================
# INTEGRACIÓN CON LA APP
# =====================================================================

def iniciar_radar_persistente(workspace, ui_callback=None):
    """
    Re-arma el watchdog de cambios de archivos (antes solo corría en
    main_gui). Best-effort: si `watchdog` no está disponible, no falla.
    """
    try:
        from modulos.memoria import iniciar_radar_proyecto
        iniciar_radar_proyecto(workspace, ui_callback=ui_callback)
        return True
    except Exception:
        return False


def sesion_abierta_en_disco():
    """
    Reabre en memoria la sesión que quedó como 'open' en disco para el
    contexto actual (si la hay). Devuelve el dict de la sesión o None.
    Útil al iniciar: así los siguientes mensajes se persisten en la MISMA
    sesión que quedó abierta (o se crea una nueva si no hay ninguna).
    """
    from config import estado as _estado
    context_id = armar_context_id(_estado.modo_actual)
    sesiones = listar_sesiones(context_id)
    if not sesiones:
        return None
    ultima = sesiones[-1]
    if ultima.get("estado") == "open":
        with _RLOCK:
            _sesiones_abiertas[context_id] = ultima
        return ultima
    return None
