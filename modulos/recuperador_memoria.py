"""
Recuperador automático de memoria a largo plazo (Fase 4).

Toma el resultado de la bóveda (ChromaDB) CON metadata y lo convierte en un
bloque de contexto listo para inyectar al prompt de sistema:

  - Solo recuerdos con `origen_id` que arranque en `boveda:*` (memoria libre
    invalidable por olvido; los espejos con ids de panel quedan fuera).
  - Excluye los recuerdos olvidados (modulos.olvidos.esta_olvidado).
  - Aplica el umbral de similitud: `sim = 1 - distancia_l2` >= MEMORIA_SCORE_MIN.
  - Deduplica por origen_id quedándose con la versión más reciente.
  - Ordena por un score suave (similitud − decay × antigüedad) y toma TOP_K.
  - Recorta el bloque total a MEMORIA_MAX_CARACTERES.

Devuelve "" si no hay nada lo bastante relevante (el prompt queda intacto).

Los imports pesados (modulos.memoria) se hacen dentro de las funciones para
que importar este módulo sea barato y testeable fuera de línea con stubs.
"""

import datetime

import config


def _similitud(distancia):
    """Transforma la distancia l2 de ChromaDB en similitud (1 - distancia)."""
    if distancia is None:
        return 0.0
    try:
        return 1.0 - float(distancia)
    except (TypeError, ValueError):
        return 0.0


def _antiguedad_dias(fecha_guardado):
    """
    Días transcurridos desde la fecha de guardado (formato '%Y-%m-%d %H:%M:%S').
    Devuelve 0 si no se puede interpretar (memorias sin fecha no penalizan).
    """
    if not fecha_guardado:
        return 0
    try:
        fecha = datetime.datetime.strptime(str(fecha_guardado)[:19], "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return 0
    return max(0.0, (datetime.datetime.now() - fecha).total_seconds() / 86400.0)


def recuperar_memorias(consulta, cantidad_maxima=None):
    """
    Recupera y filtra las memorias relevantes para la consulta.

    Devuelve una lista de dicts (hasta cantidad_maxima, por defecto
    MEMORIA_TOP_K) con la forma de buscar_contexto_con_detalle() más:
      - "similitud": 1 - distancia l2
      - "score": similitud − MEMORIA_DECAY_RECENCIA × antigüedad (para ordenar)
    Ordenadas por score descendente.
    """
    from modulos.memoria import obtener_resultado_anticipado_detalle
    from modulos import olvidos

    detalle = obtener_resultado_anticipado_detalle(consulta) or []
    cantidad_maxima = cantidad_maxima or config.MEMORIA_TOP_K

    por_origen = {}
    for r in detalle:
        origen = str(r.get("origen_id") or "").strip()
        if not origen.startswith("boveda:"):
            continue
        if olvidos.esta_olvidado(origen):
            continue
        similitud = _similitud(r.get("distancia"))
        if similitud < config.MEMORIA_SCORE_MIN:
            continue

        candidato = dict(r, similitud=similitud)
        actual = por_origen.get(origen)
        if actual is None:
            por_origen[origen] = candidato
            continue

        # Deduplicar por familia: gana la versión más reciente; en empate,
        # la de mayor similitud.
        fecha_c = candidato.get("fecha_guardado") or ""
        fecha_a = actual.get("fecha_guardado") or ""
        if fecha_c > fecha_a or (fecha_c == fecha_a and similitud > actual["similitud"]):
            por_origen[origen] = candidato

    memorias = list(por_origen.values())
    for m in memorias:
        m["score"] = m["similitud"] - config.MEMORIA_DECAY_RECENCIA * _antiguedad_dias(
            m.get("fecha_guardado")
        )
    memorias.sort(key=lambda m: m["score"], reverse=True)
    return memorias[:cantidad_maxima]


def bloque_memoria_para_contexto(consulta):
    """
    Devuelve el bloque de contexto con las memorias recuperadas, o "" si no
    hay nada relevante. El bloque se recorta a MEMORIA_MAX_CARACTERES.
    """
    memorias = recuperar_memorias(consulta)
    if not memorias:
        return ""

    cabecera_bloque = "[MEMORIA A LARGO PLAZO (bóveda, recuperada automáticamente)]:"
    presupuesto = max(0, config.MEMORIA_MAX_CARACTERES - len(cabecera_bloque) - 1)

    lineas = []
    total = 0
    for m in memorias:
        doc = (m.get("documento") or "").strip()
        if not doc:
            continue
        cabecera = "### Recuerdo de la bóveda"
        if m.get("etiqueta"):
            cabecera += f" [etiqueta: {m['etiqueta']}]"
        if m.get("fecha_guardado"):
            cabecera += f" (guardado: {m['fecha_guardado']})"
        bloque_entrada = f"{cabecera}\n{doc}"

        restante = presupuesto - total
        if restante <= 0:
            break
        if len(bloque_entrada) > restante:
            # Cortar duramente la entrada (puede cortar la cabecera si el
            # presupuesto ya está casi agotado, pero nunca lo excede).
            bloque_entrada = bloque_entrada[: max(0, restante - 1)] + "…"

        lineas.append(bloque_entrada)
        total += len(bloque_entrada)

    return f"{cabecera_bloque}\n" + "\n\n".join(lineas)
