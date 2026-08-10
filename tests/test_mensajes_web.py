from google.genai import types

from modulos.mensajes_web import (
    MARCADOR_SEGUNDA_GENERACION,
    construir_mensajes_segunda_generacion,
)


def _contenido(role, texto):
    return types.Content(role=role, parts=[types.Part.from_text(text=texto)])


def test_no_se_inyecta_respuesta_anterior_como_turno_model():
    historial = [
        _contenido('user', '¿quién obtuvo el bronce en SF6?'),
        _contenido('model', 'El bronce fue C.'),
    ]
    mensajes = construir_mensajes_segunda_generacion(
        historial,
        '¿quién obtuvo el bronce en SF6?',
        '[REGLAS] No uses tu respuesta previa.\n[RESULTADOS DE BÚSQUEDA]\nNo se encontró evidencia.',
    )

    assert [m.role for m in mensajes] == ['user', 'model', 'user', 'model', 'user']

    turnos_model_inyectados = [m for m in mensajes[len(historial):] if m.role == 'model']
    assert len(turnos_model_inyectados) == 1
    texto_modelo = "".join(p.text for p in turnos_model_inyectados[0].parts)
    assert texto_modelo == MARCADOR_SEGUNDA_GENERACION
    assert 'bronce' not in texto_modelo


def test_el_historial_se_conserva_y_es_el_unico_contexto_conversacional():
    historial = [
        _contenido('user', '¿qué es la Unión Europea?'),
        _contenido('model', 'Es una unión de países europeos.'),
    ]
    mensajes = construir_mensajes_segunda_generacion(historial, '¿y el bronce?', 'reglas\nresultados')

    assert mensajes[:2] == historial

    ultimo = mensajes[-1]
    assert ultimo.role == 'user'
    assert 'resultados' in "".join(p.text for p in ultimo.parts)


def test_nunca_recibe_respuesta_anterior_como_argumento():
    # La API interna de la función no acepta la respuesta previa del primer
    # modelo: solo historial, pregunta actual y reglas+evidencia.
    import inspect

    params = list(inspect.signature(construir_mensajes_segunda_generacion).parameters)
    assert params == ['contenidos_historial', 'texto_usuario', 'texto_reglas_y_evidencia']