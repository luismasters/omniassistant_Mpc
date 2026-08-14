"""
Preparación de la memoria persistente de Argus para presentación.

Capa intermedia entre los perfiles persistentes (perfil_usuario,
perfil_mentor, perfil_gamer) y la UI. Convierte las estructuras
internas de cada perfil en secciones listas para presentar, en
lenguaje humano y con id estables.

Reglas:
- Determinista y sin IA: no se generan textos nuevos, solo se
  reorganiza y humaniza información ya existente.
- No inventa datos: si un valor no existe, no se muestra.
- No expone estado técnico (JSON, claves internas, ids de ChromaDB,
  fechas crudas, colecciones).
- Cada elemento expone un id estable para una futura fase "Olvidar".

Este módulo NO importa config, pywebview ni ChromaDB, por lo que es
seguro importarlo y testeable fuera de línea.
"""

import datetime
import re
import unicodedata

from modulos.perfil_usuario import cargar_perfil as _cargar_perfil_usuario
from modulos.perfil_mentor import cargar_perfil_mentor as _cargar_perfil_mentor
from modulos.perfil_gamer import cargar_perfil_gamer as _cargar_perfil_gamer

# Mutadores (Fase 2): resumen_memoria actúa como capa de PRESENTACIÓN/POLÍTICA
# y NUNCA escribe JSON. Solo despacha el id lógico al módulo propietario de
# cada perfil, que es quien maneja locks, sanitización y persistencia.
from modulos.perfil_usuario import olvidar_elemento as _olvidar_usuario
from modulos.perfil_usuario import editar_elemento as _editar_usuario
from modulos.perfil_mentor import olvidar_elemento as _olvidar_mentor
from modulos.perfil_mentor import editar_elemento as _editar_mentor
from modulos.perfil_gamer import olvidar_elemento as _olvidar_gamer
from modulos.perfil_gamer import editar_elemento as _editar_gamer

# Registro de olvidos (tombstones): un dato olvidado queda vedado para la
# extracción/consolidación IA posterior; editar el dato lo desbloquea.
from modulos.olvidos import registrar_olvido as _registrar_olvido
from modulos.olvidos import quitar_olvido as _quitar_olvido

# Prefijos de id → módulo propietario. Base para incorporar ChromaDB en una
# futura fase: alcanza con agregar un prefijo (p.ej. "boveda:") al registro.
RESOLVER_OLVIDAR = {
    "funcional:": _olvidar_usuario,
    "vida:": _olvidar_usuario,
    "mentor:": _olvidar_mentor,
    "gamer:": _olvidar_gamer,
    "boveda:": lambda id_elem: _olvidar_boveda(id_elem),
}

RESOLVER_EDITAR = {
    "funcional:": _editar_usuario,
    "vida:": _editar_usuario,
    "mentor:": _editar_mentor,
    "gamer:": _editar_gamer,
    "boveda:": lambda id_elem, texto: _editar_boveda(id_elem),
}


# Umbral de días para marcar un dato como "reciente"
DIAS_RECIENTE = 7

# Etiquetas humanas para las claves internas del perfil funcional.
ETIQUETAS_FUNCIONAL = {
    "identidad": "Identidad",
    "preferencias_comunicacion": "Preferencias de comunicación",
    "rutina_uso": "Rutina de uso",
    "hardware_relevante": "Hardware relevante",
}

# Orden preferido de secciones en la UI.
ORDEN_SECCIONES = [
    "sobre_vos",
    "preferencias_y_rutina",
    "proyectos",
    "aprendizaje_y_carrera",
    "gaming",
    "memoria",
]

TITULOS_SECCIONES = {
    "sobre_vos": "Sobre vos",
    "preferencias_y_rutina": "Preferencias y rutina",
    "proyectos": "Proyectos",
    "aprendizaje_y_carrera": "Aprendizaje y carrera",
    "gaming": "Gaming",
    "memoria": "Memoria",
}

# Temas de vida_personal que representan rutina/preferencias.
# Formas canónicas SIN tildes: la comparación usa _normalizar() y elimina acentos.
_TEMAS_RUTINA = [
    "suscripcion", "suscripciones", "rutina", "habitos", "logistica",
]

# Temas de vida_personal relacionados con carrera/aprendizaje.
_TEMAS_CARRERA = [
    "objetivos_profesionales", "objetivo_profesional", "objetivos",
    "estudio", "curso", "empleo", "trabajo", "entrevista", "entrevistas",
    "opinion_profesional",
]

# Campos curados del perfil gamer (canonical → claves candidatas).
_CAMPOS_GAMER = [
    ("Personaje", ["personaje", "personaje_clase", "clase"]),
    ("Nivel", ["nivel", "nivel_actual"]),
    ("Build", ["build", "build_elegida", "build_tipo"]),
    ("Dificultad", ["dificultad"]),
    ("Objetivo", ["objetivo", "objetivo_meta", "objetivo_equipo"]),
    ("Estrategia", ["estrategia"]),
    ("Progreso", ["progreso", "progreso_historico"]),
]


def _slug(texto: str) -> str:
    """Normaliza un texto a un slug determinista para usar en ids."""
    if not texto:
        return "item"
    limpio = re.sub(r"[^a-zA-Z0-9]+", "_", texto.strip().lower())
    limpio = limpio.strip("_")
    return limpio or "item"


def _normalizar(texto) -> str:
    """
    Normaliza un tema para comparación/clasificación: sin tildes, en
    minúsculas y con separadores unificados a '_'. No altera la
    representación visible ni los ids (que siguen usando _slug).
    """
    if not isinstance(texto, str):
        return ""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(c)
    )
    return re.sub(r"[^a-zA-Z0-9]+", "_", sin_tildes.strip().lower()).strip("_")


def _humanizar_clave(clave: str) -> str:
    """Convierte snake_case a texto legible."""
    return ETIQUETAS_FUNCIONAL.get(clave, clave.replace("_", " ").capitalize())


def _texto_seguro(valor) -> str:
    """
    Devuelve el texto recortado SOLO si es un str no vacío; en cualquier
    otro caso devuelve "". Evita que None, números u otros tipos terminen
    renderizados como "None" o como texto inventado.
    """
    if isinstance(valor, str):
        return valor.strip()
    return ""


def _fecha_iso(valor):
    """
    Normaliza un valor de fecha a formato ISO (YYYY-MM-DD).
    Acepta "2026-08-08", "2026-08-08 12:09" o fecha ISO completa.
    Devuelve None si no es una fecha válida.
    """
    if not valor or not isinstance(valor, str):
        return None
    texto = valor.strip()
    try:
        parte_fecha = texto.split(" ")[0][:10]
        fecha = datetime.datetime.strptime(parte_fecha, "%Y-%m-%d")
        return fecha.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def _es_reciente(fecha_iso: str) -> bool:
    """Devuelve True si la fecha está dentro del umbral DIAS_RECIENTE (hoy inclusive)."""
    if not fecha_iso:
        return False
    try:
        fecha = datetime.datetime.strptime(fecha_iso, "%Y-%m-%d").date()
        dias = (datetime.date.today() - fecha).days
        return 0 <= dias <= DIAS_RECIENTE
    except (ValueError, TypeError):
        return False


def _elemento(id_, etiqueta, texto, fecha=None, destacado=False, no_editable=False):
    """Construye un elemento con el contrato estable para la UI."""
    fecha_iso = _fecha_iso(fecha)
    return {
        "id": id_,
        "etiqueta": etiqueta,
        "texto": texto,
        "fecha": fecha_iso or None,
        "reciente": _es_reciente(fecha_iso),
        "destacado": destacado,
        "no_editable": no_editable,
    }


def _clasificar_tema_vida(tema: str) -> str:
    """Devuelve la sección a la que pertenece un tema de vida_personal."""
    tema_norm = _normalizar(tema)
    if any(p in tema_norm for p in _TEMAS_RUTINA):
        return "preferencias_y_rutina"
    if any(p in tema_norm for p in _TEMAS_CARRERA):
        return "aprendizaje_y_carrera"
    return "sobre_vos"


def _seccion_vida_personal(entradas) -> list:
    """Convierte la lista vida_personal en elementos por sección."""
    secciones = {k: [] for k in ORDEN_SECCIONES}
    for entrada in entradas or []:
        if not isinstance(entrada, dict):
            continue
        tema = _texto_seguro(entrada.get("tema"))
        contenido = _texto_seguro(entrada.get("contenido"))
        if not tema or not contenido:
            continue
        seccion = _clasificar_tema_vida(tema)
        secciones[seccion].append(_elemento(
            id_=f"vida:{_slug(tema)}",
            etiqueta=tema,
            texto=contenido,
            fecha=entrada.get("actualizado", ""),
        ))
    return secciones


def _seccion_funcional(funcional: dict) -> dict:
    """Agrupa las claves del apartado funcional en secciones."""
    secciones = {k: [] for k in ORDEN_SECCIONES}
    funcional = funcional or {}

    identidad = _texto_seguro(funcional.get("identidad"))
    if identidad:
        secciones["sobre_vos"].append(_elemento(
            id_="funcional:identidad",
            etiqueta="Identidad",
            texto=identidad,
        ))

    for clave, seccion in (
        ("preferencias_comunicacion", "preferencias_y_rutina"),
        ("rutina_uso", "preferencias_y_rutina"),
        ("hardware_relevante", "preferencias_y_rutina"),
    ):
        valor = _texto_seguro(funcional.get(clave))
        if valor:
            secciones[seccion].append(_elemento(
                id_=f"funcional:{clave}",
                etiqueta=_humanizar_clave(clave),
                texto=valor,
            ))

    proyecto_actual = _texto_seguro(funcional.get("proyecto_actual"))
    if proyecto_actual:
        secciones["proyectos"].append(_elemento(
            id_="funcional:proyecto_actual",
            etiqueta="Proyecto actual",
            texto=proyecto_actual,
        ))

    return secciones


def _seccion_mentor(perfil_mentor: dict) -> dict:
    """Convierte el perfil de mentor en la sección 'Aprendizaje y carrera'."""
    secciones = {k: [] for k in ORDEN_SECCIONES}
    perfil_mentor = perfil_mentor or {}
    destino = secciones["aprendizaje_y_carrera"]

    # Stack objetivo
    stack = perfil_mentor.get("stack_objetivo", {}) or {}
    for clave, etiqueta in (
        ("frontend", "Frontend objetivo"),
        ("backend", "Backend objetivo"),
        ("bases_de_datos", "Bases de datos objetivo"),
    ):
        valor = _texto_seguro(stack.get(clave))
        if valor and "pendiente" not in valor.lower():
            destino.append(_elemento(f"mentor:stack_{clave}", etiqueta, valor))

    otras = stack.get("otras_herramientas", [])
    if isinstance(otras, list) and otras:
        valor = " · ".join(_texto_seguro(x) for x in otras if _texto_seguro(x))
        if valor:
            destino.append(_elemento("mentor:stack_otras", "Otras herramientas", valor))

    # Tecnologías
    for clave, etiqueta in (
        ("tecnologias_aprendidas", "Tecnologías aprendidas"),
        ("tecnologias_en_estudio", "En estudio"),
    ):
        lista = perfil_mentor.get(clave, [])
        if isinstance(lista, list) and lista:
            valor = " · ".join(_texto_seguro(x) for x in lista if _texto_seguro(x))
            if valor:
                destino.append(_elemento(f"mentor:{clave}", etiqueta, valor))

    # Último avance
    avance = _texto_seguro(perfil_mentor.get("ultimo_avance_registrado"))
    if avance and avance.lower() != "ninguno":
        destino.append(_elemento("mentor:ultimo_avance", "Último avance", avance))

    # Próximos pasos de la última sesión
    historial = perfil_mentor.get("historial_sesiones", [])
    if isinstance(historial, list) and historial:
        ultima = historial[-1]
        if isinstance(ultima, dict):
            pasos = ultima.get("proximos_pasos", [])
            if isinstance(pasos, list) and pasos:
                texto_pasos = " · ".join(_texto_seguro(p) for p in pasos if _texto_seguro(p))
                if texto_pasos:
                    destino.append(_elemento(
                        id_="mentor:proximos_pasos",
                        etiqueta="Próximos pasos",
                        texto=texto_pasos,
                        fecha=ultima.get("fecha", ""),
                    ))

    # Proyectos de portafolio
    portafolio = perfil_mentor.get("proyectos_de_portafolio", [])
    if isinstance(portafolio, list) and portafolio:
        for proy in portafolio:
            if isinstance(proy, dict):
                nombre = _texto_seguro(proy.get("nombre"))
                desc = _texto_seguro(proy.get("descripcion"))
                if nombre:
                    texto = f"{nombre}: {desc}" if desc else nombre
                    secciones["proyectos"].append(_elemento(
                        id_=f"mentor:proyecto:{_slug(nombre)}",
                        etiqueta="Portafolio",
                        texto=texto,
                    ))

    # Progreso/Mentoría estructurado (Fase 5)
    from modulos.perfil_mentor import _progreso as _progreso_mentor
    prog = _progreso_mentor(perfil_mentor)

    objetivos = prog.get("objetivos", [])
    if isinstance(objetivos, list) and objetivos:
        for o in objetivos:
            if not isinstance(o, dict):
                continue
            titulo = _texto_seguro(o.get("titulo"))
            if not titulo:
                continue
            estado = _texto_seguro(o.get("estado"))
            prioridad = _texto_seguro(o.get("prioridad"))
            proy_asoc = _texto_seguro(o.get("proyecto_asociado"))
            ref = titulo
            extras = [x for x in (estado, f"prioridad {prioridad}" if prioridad else "", proy_asoc) if x]
            if extras:
                ref += " · " + " · ".join(extras)
            destino.append(_elemento(
                id_=f"mentor:progreso_objetivo:{_slug(titulo)}",
                etiqueta="Objetivo",
                texto=ref,
            ))

    pasos = prog.get("proximos_pasos", [])
    if isinstance(pasos, list) and pasos:
        pasos_limpios = [_texto_seguro(p) for p in pasos if _texto_seguro(p)]
        if pasos_limpios:
            destino.append(_elemento(
                id_="mentor:progreso_proximos_pasos",
                etiqueta="Próximos pasos (Progreso)",
                texto=" · ".join(pasos_limpios),
            ))

    dificultades = prog.get("dificultades_activas", [])
    if isinstance(dificultades, list) and dificultades:
        for d in dificultades:
            tema = _texto_seguro(d.get("tema")) if isinstance(d, dict) else ""
            if not tema:
                continue
            occ = (d.get("ocurrencias") or 1) if isinstance(d, dict) else 1
            fecha = _texto_seguro(d.get("ultima_fecha")) if isinstance(d, dict) else ""
            destino.append(_elemento(
                id_=f"mentor:progreso_dificultad:{_slug(tema)}",
                etiqueta="Dificultad activa",
                texto=f"{tema} (×{occ})",
                fecha=fecha,
            ))

    hitos = prog.get("hitos_completados", [])
    if isinstance(hitos, list) and hitos:
        for h in hitos:
            if not isinstance(h, dict):
                continue
            htexto = _texto_seguro(h.get("texto"))
            if not htexto:
                continue
            destino.append(_elemento(
                id_=f"mentor:progreso_hito:{_slug(htexto)}",
                etiqueta="Hito",
                texto=htexto,
                fecha=_texto_seguro(h.get("fecha")) or "",
            ))

    cont = prog.get("continuidad") or {}
    quedamos = _texto_seguro(cont.get("donde_quedamos"))
    if quedamos:
        destino.append(_elemento(
            id_="mentor:progreso_continuidad",
            etiqueta="Continuidad",
            texto=quedamos,
            fecha=_texto_seguro(cont.get("ultima_fecha")) or "",
        ))

    return secciones


def _seccion_gamer(perfil_gamer: dict) -> list:
    """Convierte el perfil gamer en la sección 'Gaming'.

    - Si el juego activo NO tiene ficha: solo aparece el encabezado destacado.
    - Si el juego activo SÍ tiene ficha: aparece UNA sola representación
      (la ficha, destacada). No se duplica el nombre del juego.
    - Fichas de otros juegos: sin destacado, con su fecha (históricas).
    """
    elementos = []
    perfil_gamer = perfil_gamer or {}

    juego_activo = _texto_seguro(perfil_gamer.get("juego_activo"))
    juegos = perfil_gamer.get("juegos", {})
    if not isinstance(juegos, dict):
        juegos = {}

    guardados = {}  # nombre_str -> elemento
    for nombre, datos in juegos.items():
        if not isinstance(datos, dict):
            continue
        nombre_str = _texto_seguro(nombre)
        if not nombre_str:
            continue

        partes = []
        for etiqueta, claves in _CAMPOS_GAMER:
            valor = ""
            for clave in claves:
                v = _texto_seguro(datos.get(clave))
                if v:
                    valor = v
                    break
            if valor:
                partes.append(f"{etiqueta}: {valor}")

        if not partes:
            continue

        ultima_sesion = _texto_seguro(datos.get("ultima_sesion"))
        es_activo = bool(juego_activo) and _slug(nombre_str) == _slug(juego_activo)
        guardados[nombre_str] = {
            "id": f"gamer:{_slug(nombre_str)}",
            "etiqueta": nombre_str,
            "texto": " · ".join(partes),
            "fecha": _fecha_iso(ultima_sesion) or None,
            "es_activo": es_activo,
        }

    # Ficha del juego activo (si existe): única representación, destacada.
    ficha_activa = None
    for nombre_str, datos in guardados.items():
        if datos["es_activo"]:
            ficha_activa = nombre_str
            break

    if juego_activo and ficha_activa is None:
        elementos.append(_elemento(
            id_="gamer:juego_activo",
            etiqueta="Juego activo",
            texto=juego_activo,
            destacado=True,
        ))

    for nombre_str, datos in guardados.items():
        elementos.append(_elemento(
            id_=datos["id"],
            etiqueta=datos["etiqueta"],
            texto=datos["texto"],
            fecha=datos["fecha"],
            destacado=(datos["es_activo"] and nombre_str == ficha_activa),
        ))

    return elementos


def _seccion_memoria() -> list:
    """
    Recuerdos libres de la bóveda de ChromaDB, agrupados por familia
    (`origen_id` `boveda:*`). Import lazy de modulos.memoria para no cargar
    ChromaDB al importar resumen_memoria (offline-safe). Si la bóveda no
    está disponible, devuelve una lista vacía sin romper el panel.
    """
    try:
        from modulos.memoria import listar_recuerdos_boveda
    except Exception:
        return []
    try:
        recuerdos = listar_recuerdos_boveda()
    except Exception:
        return []

    elementos = []
    for r in recuerdos:
        origen_id = r.get("origen_id")
        if not origen_id:
            continue
        elementos.append(_elemento(
            id_=origen_id,
            etiqueta=r.get("etiqueta") or "Memoria",
            texto=r.get("texto") or "",
            fecha=r.get("fecha_guardado"),
            no_editable=True,
        ))
    return elementos


def preparar_secciones() -> dict:
    """
    Construye el dict listo para la UI con la memoria que Argus conoce
    del usuario, organizada en secciones. Las secciones vacías se omiten.
    """
    acoplador = {k: [] for k in ORDEN_SECCIONES}

    perfil_usuario = _cargar_perfil_usuario()
    funcional = (perfil_usuario or {}).get("funcional", {})
    for seccion, elementos in _seccion_funcional(funcional).items():
        acoplador[seccion].extend(elementos)

    vida = (perfil_usuario or {}).get("vida_personal", [])
    for seccion, elementos in _seccion_vida_personal(vida).items():
        acoplador[seccion].extend(elementos)

    perfil_mentor = _cargar_perfil_mentor()
    for seccion, elementos in _seccion_mentor(perfil_mentor).items():
        acoplador[seccion].extend(elementos)

    perfil_gamer = _cargar_perfil_gamer()
    acoplador["gaming"].extend(_seccion_gamer(perfil_gamer))

    acoplador["memoria"].extend(_seccion_memoria())

    secciones = []
    for seccion_id in ORDEN_SECCIONES:
        elementos = acoplador.get(seccion_id, [])
        if not elementos:
            continue
        secciones.append({
            "id": seccion_id,
            "titulo": TITULOS_SECCIONES.get(seccion_id, seccion_id),
            "elementos": elementos,
        })

    return {
        "generado": datetime.datetime.now().isoformat(timespec="seconds"),
        "secciones": secciones,
    }


# ─── FASE 2: OLVIDAR / EDITAR POR ID LÓGICO ──────────────────────────────────
#
# El id lógico del panel identifica el dato de origen. Estas funciones
# resuelven el prefijo (uni-voca, sin IA) y delegan la mutación al módulo
# propietario de cada perfil. resumen_memoria SIGUE siendo presentación:
# no escribe archivos, no conoce locks internos ni estructura de los JSON.

def _olvidar_boveda(id_elemento) -> bool:
    """
    Mutador del namespace `boveda:`. Valida el formato del id de memoria
    libre y delega el borrado físico a invalidar_por_origen() de
    modulos.memoria (lazy import: evita cargar ChromaDB al importar este
    módulo). Devuelve True solo si se borró algo.
    """
    from modulos.olvidos import _id_boveda_valido
    from modulos.memoria import invalidar_por_origen

    id_ = str(id_elemento or "").strip()
    if not _id_boveda_valido(id_):
        return False
    return invalidar_por_origen(id_)


def _editar_boveda(id_elemento, texto) -> bool:
    """
    El namespace `boveda:` no soporta edición en esta fase: la memoria libre
    se borra (olvidar) o se vuelve a guardar como recuerdo nuevo. La edición
    devuelve False sin efecto.
    """
    return False


def _resolver_prefijo(id_elemento) -> str:
    """Devuelve el prefijo "familia:" del id si es conocido; None si no."""
    id_ = str(id_elemento or "")
    for prefijo in RESOLVER_OLVIDAR:
        if id_.startswith(prefijo):
            return prefijo
    return None


def resolver_olvidar(id_elemento) -> dict:
    """
    Despacha el borrado lógico de un dato a su módulo propietario.

    Returns:
        {"exito": bool, "mensaje": str} — mensaje en español listo para la UI.
    """
    prefijo = _resolver_prefijo(id_elemento)
    if prefijo is None:
        return {"exito": False, "mensaje": "El id del dato no es válido."}
    mutador = RESOLVER_OLVIDAR[prefijo]
    try:
        aplicado = mutador(id_elemento)
    except Exception as e:
        return {"exito": False, "mensaje": "Ocurrió un error al olvidar el dato."}
    if not aplicado:
        return {"exito": False, "mensaje": "El dato ya no existe o no se encontró."}
    # SÓLO después de que el perfil fue modificado correctamente se registra
    # el tombstone: el dato queda vedado para extracciones futuras de la IA.
    _registrar_olvido(id_elemento)
    return {"exito": True, "mensaje": "Listo, Argus olvidó este dato."}


def resolver_editar(id_elemento, texto) -> dict:
    """
    Despacha la edición lógica de un dato a su módulo propietario.

    Returns:
        {"exito": bool, "mensaje": str} — mensaje en español listo para la UI.
    """
    prefijo = _resolver_prefijo(id_elemento)
    if prefijo is None:
        return {"exito": False, "mensaje": "El id del dato no es válido."}
    if not texto or not str(texto).strip():
        return {"exito": False, "mensaje": "El dato no puede quedar vacío."}
    mutador = RESOLVER_EDITAR[prefijo]
    try:
        aplicado = mutador(id_elemento, texto)
    except Exception as e:
        return {"exito": False, "mensaje": "Ocurrió un error al editar el dato."}
    if not aplicado:
        return {"exito": False, "mensaje": "El dato ya no existe o no se encontró."}
    # Editar = reintroducir el dato corregido: se quita el tombstone para
    # que la extracción vuelva a poder actualizarlo (o aprenderlo de nuevo).
    _quitar_olvido(id_elemento)
    return {"exito": True, "mensaje": "Listo, Argus actualizó este dato."}