"""
Fase D (Punto 1) — Contrato de composición del system prompt:
BASE + bloques contextuales.

`construir_contexto_sistema` es el punto ÚNICO de composición:
- En cualquier contexto SIEMPRE está la base (identidad + reglas transversales).
- El bloque contextual se ANEXA según el contexto activo (mentoría/gaming).
- La base y los bloques son reutilizables/componibles (no personas rígidas).
"""

from modulos.prompts import (
    construir_contexto_sistema,
    obtener_prompt_base,
    bloque_mentoria,
    bloque_gaming,
    detectar_capacidad_por_tema,
)

_ARG = dict(
    fecha_hoy="sábado, 8 de agosto de 2026",
    ruta_home=r"C:\Users\luism",
    ventanas_abiertas="",
    texto_workspace="",
    texto_snapshot="",
    texto_doc_volatil="",
    texto_perfil="",
)


def test_base_siempre_presente_en_cualquier_contexto():
    base = obtener_prompt_base(**_ARG)
    for modo in ("general", "mentor", "gamer"):
        ctx = construir_contexto_sistema(modo, **_ARG)
        assert "tu nombre es: Argus" in ctx
        assert "PROTOCOLO DE VERIFICACIÓN WEB" in ctx
        assert "recordatorio:" in ctx
        assert "mcp_olvidar_tema" in ctx
        assert "EMOTION:" in ctx


def test_mentor_anexa_bloque_mentoria():
    ctx = construir_contexto_sistema("mentor", **_ARG)
    assert "CONTEXTO ACTIVO: MENTORÍA" in ctx
    assert "REGLAS DE MENTORÍA" in ctx
    assert "coaching" in ctx.lower() or "entrevista" in ctx.lower()
    # La base sigue presente junto al bloque (composición, no reemplazo).
    assert "tu nombre es: Argus" in ctx


def test_gamer_anexa_bloque_gaming():
    ctx = construir_contexto_sistema("gamer", **_ARG)
    assert "CONTEXTO ACTIVO: GAMING" in ctx
    assert "GAMING-FIRST" in ctx
    assert "DETECCIÓN AUTOMÁTICA DE JUEGO ACTIVO" in ctx
    assert "tu nombre es: Argus" in ctx


def test_general_solo_base_sin_bloque():
    ctx = construir_contexto_sistema("general", **_ARG)
    assert "CONTEXTO ACTIVO: MENTORÍA" not in ctx
    assert "CONTEXTO ACTIVO: GAMING" not in ctx


def test_bloques_componibles_independientes():
    b_mentor = bloque_mentoria("", "", "")
    b_gamer = bloque_gaming("fecha", "home", "", "", "", "", "")
    assert "MENTORÍA" in b_mentor and "GAMING" in b_gamer
    # Cada bloque define su propio "capacidad activada" (no personas rígidas).
    assert b_mentor.startswith("⚠️ CONTEXTO ACTIVO:")
    assert b_gamer.startswith("⚠️ CONTEXTO ACTIVO:")


def test_obtener_prompt_general_es_la_base():
    assert obtener_prompt_base(**_ARG) == construir_contexto_sistema("general", **_ARG)


# ─── Detección de capacidad por tema (Fase D, Punto 3) ──────────────────────

def test_detectar_capacidad_mentoria_por_tema():
    assert detectar_capacidad_por_tema("quiero aprender a programar") == "mentor"
    assert detectar_capacidad_por_tema("dónde quedamos con el stack") == "mentor"
    assert detectar_capacidad_por_tema("ayudame a preparar mi portafolio") == "mentor"


def test_detectar_capacidad_gaming_por_tema():
    assert detectar_capacidad_por_tema("qué build le conviene a mi personaje") == "gamer"
    assert detectar_capacidad_por_tema("estoy jugando la partida") == "gamer"


def test_detectar_capacidad_general_sin_tema():
    assert detectar_capacidad_por_tema("qué hora es") is None
    assert detectar_capacidad_por_tema("") is None
    assert detectar_capacidad_por_tema(None) is None


def test_detectar_capacidad_ambiguo_no_activa():
    # Señales de mentoría y gaming juntas → no activa (conservador).
    assert detectar_capacidad_por_tema("estudiar y jugar") is None
