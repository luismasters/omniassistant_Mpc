from modulos.mensajes_web import (
    MARCADOR_SEGUNDA_GENERACION,
    MAX_EVIDENCIA_GUARDADA,
    agregar_evidencia,
    construir_bloque_evidencia_anterior,
    construir_mensajes_segunda_generacion,
)
from google.genai import types


def _contenido(role, texto):
    return types.Content(role=role, parts=[types.Part.from_text(text=texto)])


def _texto(content):
    return "".join(p.text for p in content.parts if hasattr(p, "text") and p.text)


def _textos_modelo(mensajes):
    return [_texto(m) for m in mensajes if m.role == "model"]


def _textos_user(mensajes):
    return [_texto(m) for m in mensajes if m.role == "user"]


EV1 = "[RESULTADOS DE BÚSQUEDA]\nSegundo puesto: B. Fuente: esports.com"
EV2 = "[RESULTADOS DE BÚSQUEDA]\nTercer puesto: no confirmado. Fuente: rankweb.com"


def test_evidencia_persistida_disponible_para_turno_posterior():
    evidencia = []
    evidencia = agregar_evidencia(evidencia, EV1)
    evidencia = agregar_evidencia(evidencia, EV2)

    bloque = construir_bloque_evidencia_anterior(evidencia)

    assert "EVIDENCIA WEB DE CONSULTAS ANTERIORES" in bloque
    assert "esports.com" in bloque
    assert "no confirmado" in bloque


def test_evidencia_no_aparece_como_turno_model():
    evidencia = construir_bloque_evidencia_anterior([EV1])
    mensajes = construir_mensajes_segunda_generacion(
        [_contenido("user", "¿quién ganó?")],
        "¿quién ganó?",
        f"reglas\n{evidencia}\n[RESULTADOS DE BÚSQUEDA]\nAntonelli ganó.",
    )

    for texto in _textos_modelo(mensajes):
        assert "EVIDENCIA WEB" not in texto
        assert "esports.com" not in texto

    assert any("EVIDENCIA WEB" in texto for texto in _textos_user(mensajes))


def test_follow_up_recibe_evidencia_sin_respuesta_anterior_como_evidencia():
    historial = [
        _contenido("user", "¿quién fue segundo?"),
        _contenido("model", "La respuesta final anterior: Antonelli."),
    ]
    evidencia = construir_bloque_evidencia_anterior([EV1])

    mensajes = construir_mensajes_segunda_generacion(
        historial,
        "¿y el tercero?",
        f"reglas\n{evidencia}\n{EV2}",
    )

    # Historial intacto + pregunta + marcador + evidencia: 5 turnos.
    assert [m.role for m in mensajes] == ["user", "model", "user", "model", "user"]

    # La respuesta anterior sigue en el historial como turno 'model'.
    assert any("respuesta final anterior" in t for t in _textos_modelo(mensajes))

    # La respuesta anterior NO se inyecta como evidencia en el turno 'user' final.
    ultimo = _texto(mensajes[-1])
    assert "respuesta final anterior" not in ultimo
    assert "no confirmado" in ultimo


def test_follow_up_segunda_generacion_recibe_historial_pregunta_evidencia_nueva():
    # Escenario del turno 2: se seguía hablando del podio de SF6 y ahora
    # pregunta "¿y el tercero?". La segunda generación debe recibir el
    # historial verificado, la pregunta actual, el marcador neutro y el
    # bloque con evidencia ANTERIOR + RESULTADOS nuevos.
    historial = [
        _contenido("user", "¿Cuál fue el podio de Street Fighter 6?"),
        _contenido("model", "Según las fuentes: oro A, plata B. No pude confirmar el tercer puesto."),
    ]
    evidencia_anterior = construir_bloque_evidencia_anterior([EV1])

    mensajes = construir_mensajes_segunda_generacion(
        historial,
        "¿y el tercero?",
        f"reglas\n{evidencia_anterior}\n[RESULTADOS DE BÚSQUEDA]\nTercer puesto: C.",
    )

    assert [m.role for m in mensajes] == ["user", "model", "user", "model", "user"]

    # El historial se conserva intacto como contexto conversacional.
    assert mensajes[:2] == historial

    # La pregunta actual es el tercer turno 'user'.
    assert "¿y el tercero?" in _texto(mensajes[2])

    # El cuarto turno es el marcador neutro (nunca la respuesta previa).
    assert _texto(mensajes[3]) == MARCADOR_SEGUNDA_GENERACION

    # El último turno agrupa reglas + evidencia anterior + resultados nuevos.
    ultimo = _texto(mensajes[-1])
    assert "EVIDENCIA WEB" in ultimo
    assert "RESULTADOS DE BÚSQUEDA" in ultimo
    assert "Tercer puesto: C." in ultimo


def test_la_respuesta_anterior_no_se_mezcla_con_la_evidencia():
    respuesta_anterior = "Según las fuentes: oro A, segundo B. No pude confirmar el tercer puesto."
    evidencia_anterior = construir_bloque_evidencia_anterior([EV1])

    assert respuesta_anterior not in evidencia_anterior
    assert "EVIDENCIA" in evidencia_anterior


def test_la_evidencia_no_crece_indefinidamente():
    evidencia = []
    for i in range(10):
        evidencia = agregar_evidencia(evidencia, f"evidencia {i}")

    assert len(evidencia) == MAX_EVIDENCIA_GUARDADA == 3
    assert evidencia == ["evidencia 7", "evidencia 8", "evidencia 9"]


def test_bloque_vacio_si_no_hay_evidencia():
    assert construir_bloque_evidencia_anterior([]) == ""
    assert construir_bloque_evidencia_anterior(None) == ""