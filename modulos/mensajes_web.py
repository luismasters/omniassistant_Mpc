# Construcción de los mensajes de la segunda generación para búsqueda web.
#
# La segunda generación NO debe recibir la primera respuesta del modelo
# (respuesta_ia) como un turno 'model': ese borrador puede contener alucinaciones
# y el objetivo de la fase es que la respuesta final se base SOLO en:
#   - contexto conversacional existente (historial),
#   - la pregunta actual,
#   - las reglas de evidencia,
#   - los resultados reales de la búsqueda web.


# Marcador neutro que reemplaza el turno del modelo eliminado. NO contiene
# ninguna afirmación factual: solo anuncia que hubo una verificación web.
MARCADOR_SEGUNDA_GENERACION = "[Verificación web en curso: la respuesta se basa únicamente en la evidencia de los resultados.]"


def construir_mensajes_segunda_generacion(contenidos_historial, texto_usuario, texto_reglas_y_evidencia):
    """
    Devuelve la lista de `types.Content` para la segunda generación.

    Composición:
        [contenidos_historial] + usuario(actual) + model(marcador neutro) + user(reglas + evidencia)

    `contenidos_historial` debe venir ya convertido por `_convertir_contexto_a_contents`
    en `modulos/ia.py`. Es el único contexto conversacional permitido.
    """
    from google.genai import types

    return list(contenidos_historial) + [
        types.Content(role='user', parts=[types.Part.from_text(text=texto_usuario)]),
        types.Content(role='model', parts=[types.Part.from_text(text=MARCADOR_SEGUNDA_GENERACION)]),
        types.Content(role='user', parts=[types.Part.from_text(text=texto_reglas_y_evidencia)]),
    ]


# =====================================================================
# EVIDENCIA WEB PERSISTIDA ENTRE TURNOS
#
# La evidencia web (resultados/snippets/URLs de una búsqueda) vive en una
# lista SEPARADA del contexto conversacional. Nunca se convierte en un
# turno 'model': siempre viaja etiquetada como EVIDENCIA dentro del mensaje
# 'user' de la segunda generación. Así un follow-up puede volver a verificar
# datos contra fuentes reales sin depender solo de la respuesta anterior.
# =====================================================================

# Límite de entradas de evidencia persistida (rotación FIFO). Acotado para
# que el contexto no crezca indefinidamente.
MAX_EVIDENCIA_GUARDADA = 3


def agregar_evidencia(evidencia_actual, nueva_evidencia, maximo=None):
    """
    Devuelve la lista de evidencia con `nueva_evidencia` agregada al final y
    recortada a los últimos `maximo` elementos (rotación). Es pura: no muta
    la lista de entrada.
    """
    if maximo is None:
        maximo = MAX_EVIDENCIA_GUARDADA
    nueva_lista = list(evidencia_actual) + [nueva_evidencia]
    if len(nueva_lista) > maximo:
        nueva_lista = nueva_lista[-maximo:]
    return nueva_lista


def construir_bloque_evidencia_anterior(entradas):
    """
    Convierte las evidencias de consultas anteriores en un bloque de texto
    explícitamente rotulado como EVIDENCIA externa (nunca como afirmación del
    asistente). Devuelve '' si no hay evidencias.
    """
    if not entradas:
        return ""
    partes = ["[EVIDENCIA WEB DE CONSULTAS ANTERIORES — solo fuentes externas, NO afirmaciones del asistente]"]
    for indice, entrada in enumerate(entradas, start=1):
        partes.append(f"Evidencia {indice} (consulta previa):\n{entrada}")
    return "\n\n".join(partes)


def armar_mensaje_modelo_persistido(respuesta_ia, respuesta_final=""):
    """
    Devuelve el ÚNICO mensaje 'model' que debe persistirse como respuesta del
    turno. Separa conceptualmente:
      - respuesta_ia: borrador provisional de la primera generación.
      - respuesta_final: salida definitiva (segunda generación basada en web).

    Regla de persistencia:
      - Si existe respuesta_final (hubo búsqueda web y la segunda generación
        respondió), esa es la respuesta del turno y se descarta el borrador.
      - Si no hay respuesta_final (turno sin búsqueda, o la segunda generación
        falló/vino vacía), se persiste el borrador como respuesta del turno.
      - Nunca devuelve dos mensajes: el turno queda como un único intercambio
        user: pregunta → model: respuesta.
    """
    return {'role': 'model', 'parts': [respuesta_final or respuesta_ia]}


def decidir_contenido_presentacion(respuesta_ia, respuesta_final):
    """
    Decide cómo debe presentarse la respuesta del turno en la UI:

      - Si hubo segunda generación web y produjo una respuesta definitiva,
        esa respuesta VERIFICADA reemplaza al borrador provisional. El borrador
        no se concatena con la final ni se muestra como respuesta propia.
      - Si no hay respuesta (turno sin búsqueda, o la segunda generación
        falló/vino vacía), el borrador ES la respuesta directa del turno.

    Devuelve (tipo, texto):
      ("verificada", respuesta_final)  → la UI reemplaza el borrador.
      ("directa", respuesta_ia)        → sin verificación web.
    """
    if respuesta_final:
        return ("verificada", respuesta_final)
    return ("directa", respuesta_ia)