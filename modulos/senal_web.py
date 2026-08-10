# Señal estructurada de decisión web (Arquitectura C+D).
#
# El LLM decide semánticamente si el turno requiere información web y, en ese
# caso, construye una consulta autocontenida. Python solo ejecuta la decisión
# de forma determinística. No hay heurísticas por palabras/longitud/nombres.
#
# Formato de la señal (líneas propias, al final del borrador de la 1ª gen):
#   [WEB: SI]
#   [CONSULTA: <consulta completa y autocontenida>]
#   o simplemente:
#   [WEB: NO]
#
# Compatibilidad durante la transición: si no aparece señal, el pipeline
# actual con `buscar:` sigue funcionando igual.
import re

_PATRON_TAG_SENAL = re.compile(r'\[(?:WEB|CONSULTA)\s*:', re.IGNORECASE)
_PREFIX_SENAL_PARTIAL = ("[WEB", "[CONSULTA")
_PATRON_DECISION = re.compile(r'\[WEB\s*:\s*(SI|NO)\]', re.IGNORECASE)
_PATRON_INICIO_CONSULTA = re.compile(r'^\s*\[CONSULTA\s*:\s*(.+)', re.IGNORECASE)


def _es_fragmento_senal(texto_linea):
    """True si la línea contiene una etiqueta de señal (`[WEB:` o `[CONSULTA:`)."""
    if _PATRON_TAG_SENAL.search(texto_linea):
        return True
    inicio = texto_linea.lstrip()
    return inicio.startswith(_PREFIX_SENAL_PARTIAL)


def _extraer_consulta_de_linea(linea):
    m = _PATRON_INICIO_CONSULTA.match(linea)
    if not m:
        return None
    contenido = m.group(1)
    if contenido.endswith("]"):
        contenido = contenido[:-1]
    contenido = contenido.strip().strip('"\'`').replace('<', '').replace('>', '').strip()
    return contenido or None


def limpiar_respuesta_web(texto):
    """Devuelve el borrador SIN ninguna etiqueta de señal (UI / TTS / persistencia)."""
    if not texto:
        return ""
    lineas = []
    for linea in texto.split("\n"):
        if _es_fragmento_senal(linea):
            continue
        lineas.append(linea)
    return "\n".join(lineas)


def parsear_senal_web(respuesta_ia):
    """
    Parsea la salida de la 1ª generación.

    Retorna dict:
      {'tipo': 'si'|'no'|'ninguna',
       'consulta': str|None,
       'respuesta_limpia': str}
    """
    if not respuesta_ia:
        return {'tipo': 'ninguna', 'consulta': None, 'respuesta_limpia': ""}
    coincidencias = list(_PATRON_DECISION.finditer(respuesta_ia))
    tipo_decision = 'ninguna'
    if coincidencias:
        tipo_decision = coincidencias[-1].group(1).upper()

    consulta = None
    if tipo_decision == 'SI':
        for linea in respuesta_ia.split("\n"):
            consulta = _extraer_consulta_de_linea(linea)
            if consulta:
                break

    respuesta_limpia = limpiar_respuesta_web(respuesta_ia)
    return {
        'tipo': tipo_decision,
        'consulta': consulta,
        'respuesta_limpia': respuesta_limpia,
    }


def fusionar_comando_busqueda(senal_web, comando_legacy):
    """
    Unifica la señal estructurada y el comando `buscar:` legacy en UNA única
    consulta, siguiendo la precedencia de transición:

      1. [WEB: SI] + [CONSULTA]                     -> usa la consulta.
      2. [WEB: SI] sin [CONSULTA] + `buscar:`       -> usa el legacy.
      3. sin señal + `buscar:`                      -> comportamiento actual.
      4. [WEB: NO] sin `buscar:`                    -> no buscar.
      5. [WEB: NO] + `buscar:`                      -> conserva `buscar:` + warning.

    Retorna (comando, warning) donde comando puede ser None.
    """
    tipo = senal_web.get('tipo')
    consulta = senal_web.get('consulta') or None

    if tipo == 'SI':
        if consulta:
            return consulta, None
        if comando_legacy:
            return comando_legacy, "Señal [WEB: SI] sin [CONSULTA]: se usó el comando `buscar:` legacy."
        return None, "Señal [WEB: SI] sin [CONSULTA] ni `buscar:` legacy: búsqueda omitida."

    if tipo == 'NO':
        if comando_legacy:
            return comando_legacy, "Señal [WEB: NO] junto a `buscar:` legacy: se conservó `buscar:` (transición)."
        return None, None

    return comando_legacy, None


class OcultadorStreamWeb:
    """
    Filtra las etiquetas de señal del streaming SIN romper el mecanismo.

    El streaming manda chunks en tiempo real. El mensaje final se muestra con
    línea normal, las etiquetas `[WEB:...]`/`[CONSULTA:...]` se descartan.

    Estrategia: acumula el texto pendiente de la línea en curso; solo deja
    pasar las líneas COMPLETAS que no son etiquetas. La última línea sin
    newline se retiene hasta `finalizar()` y se descarta si es señal.
    Así las señales nunca se muestran, aunque se partan entre chunks
    (ej. `[WEB:` en un chunk y `SI]` en otro).
    """
    def __init__(self):
        self._buffer = ""

    def procesar(self, texto_nuevo):
        """Devuelve SOLO el texto visible de las líneas completas de este chunk."""
        if not texto_nuevo:
            return ""
        self._buffer += texto_nuevo
        salida = []
        while "\n" in self._buffer:
            linea, self._buffer = self._buffer.split("\n", 1)
            if not _es_fragmento_senal(linea):
                salida.append(linea + "\n")
        return "".join(salida)

    def finalizar(self):
        """Termina el último fragmento pendiente (lo emite si no es señal)."""
        resto = self._buffer
        self._buffer = ""
        if not resto:
            return ""
        if _es_fragmento_senal(resto):
            return ""
        return resto


def texto_marcador_tema_web_anterior():
    """
    Marcador semántico inyectado en el contexto de la 1ª generación cuando ya
    existe evidencia web de turnos anteriores. Es instrucción para el LLM
    (no una heurística Python): el modelo decide si el turno continúa el tema.
    """
    return (
        "[TEMA WEB ANTERIOR] En un turno anterior, información reciente se "
        "verificó con fuentes web.\n"
        "Si la pregunta actual ES CONTINUACIÓN DE ESE MISMO TEMA, resolvé la "
        "referencia usando el historial y verificá nuevamente con web "
        "([WEB: SI] + [CONSULTA: <consulta autocontenida>]).\n"
        "Si la pregunta actual introduce un TEMA DIFERENTE, NO heredes esta "
        "obligación y respondé con normalidad.\n"
    )