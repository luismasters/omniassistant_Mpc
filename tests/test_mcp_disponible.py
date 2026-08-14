# -*- coding: utf-8 -*-
"""
H.3 — Disponibilidad de herramientas MCP según el modelo activo.

En `modulos/ia.py` los tools MCP solo se arman si el modelo activo es Gemini
(`gemini_config.tools = lista_herramientas_mcp`); los modelos DeepSeek/Groq
no los reciben, y una skill activa en el turno también los desactiva. Estos
tests fijan la disponibilidad ESTÁTICA que la UI muestra en el chip "MCP ✓/✗"
exponiendo `mcp_disponible` desde WebBridge. La restricción por skill es por
mensaje (no estática) y se comunica en el tooltip.
"""

import sys
import types

import pytest

from config import EstadoGlobal


def _stub(nombre, attrs):
    m = types.ModuleType(nombre)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[nombre] = m
    return m


_STUBS_BRIDGE = [
    "webview",
    "modulos.audio_custom",
    "modulos.perfil_mentor",
    "modulos.skills.wake_word.gestor_wake_word",
    "modulos.ia",
    "modulos.web_bridge",
]


@pytest.fixture
def bridge_modulo():
    """Stubea las dependencias pesadas y devuelve el módulo web_bridge REAL
    (restaura sys.modules al terminar, sin contaminar otros archivos)."""
    orig = {nombre: sys.modules.get(nombre) for nombre in _STUBS_BRIDGE}
    try:
        _stub("webview", {"windows": []})
        _stub("modulos.audio_custom", {
            "capturar_voz_micro": lambda *a, **k: "",
            "hablar_no_bloqueante": lambda *a, **k: None,
            "encolar_texto_para_hablar": lambda *a, **k: None,
            "detener_voz": lambda *a, **k: None,
        })
        _stub("modulos.perfil_mentor", {
            "cargar_perfil_mentor": lambda *a, **k: {},
            "guardar_perfil_mentor": lambda *a, **k: None,
        })
        _stub("modulos.skills.wake_word.gestor_wake_word", {
            "gestor_wake_word": types.SimpleNamespace(
                esta_activo=lambda: False,
                activar=lambda *a, **k: None,
                desactivar=lambda *a, **k: None,
            ),
        })
        _stub("modulos.ia", {"enviar_a_gemini": lambda *a, **k: None})

        import modulos.web_bridge as wb
        yield wb
    finally:
        for nombre, modulo in orig.items():
            if modulo is None:
                sys.modules.pop(nombre, None)
            else:
                sys.modules[nombre] = modulo


def _con_estado(monkeypatch, wb, **attrs):
    estado = EstadoGlobal()
    for k, v in attrs.items():
        setattr(estado, k, v)
    monkeypatch.setattr(wb, "estado", estado)
    return estado


# ─── modelo_soporta_mcp (lógica estática) ──────────────────────────────────

def test_modelo_soporta_mcp_por_seleccion_y_modo(bridge_modulo):
    wb = bridge_modulo

    assert wb.modelo_soporta_mcp("Gemini 3.1 Flash Lite", "general") is True
    assert wb.modelo_soporta_mcp("Gemini 3.1 Pro (High)", "general") is True
    assert wb.modelo_soporta_mcp("Gemini 3.6 Flash (High)", "general") is True
    assert wb.modelo_soporta_mcp("DeepSeek Reasoner", "general") is False
    assert wb.modelo_soporta_mcp("Groq Llama 3.3 70B", "general") is False
    assert wb.modelo_soporta_mcp("Groq Llama 3.1 8B", "general") is False

    # "Por Defecto"/"Auto" es UNA preferencia GLOBAL (Fase D Punto 2):
    # ya NO resuelve por modo. Default = Gemini → MCP activo en CUALQUIER modo.
    assert wb.modelo_soporta_mcp("Por Defecto", "mentor") is True
    assert wb.modelo_soporta_mcp("Por Defecto", "gamer") is True
    assert wb.modelo_soporta_mcp("Por Defecto", "general") is True


def test_modelo_soporta_mcp_entrada_rara_no_rompe(bridge_modulo):
    wb = bridge_modulo
    assert wb.modelo_soporta_mcp("", "general") is False
    assert wb.modelo_soporta_mcp(None, "general") is False


def test_resolver_default_global_ignora_modo(bridge_modulo, monkeypatch):
    wb = bridge_modulo
    # El default global se lee de config.MODELO_DEFECTO_GLOBAL (env).
    monkeypatch.setattr("config.MODELO_DEFECTO_GLOBAL", "DeepSeek Reasoner")
    assert wb.resolver_modelo_actual("Por Defecto", "mentor") == "DeepSeek Reasoner"
    assert wb.resolver_modelo_actual("Por Defecto", "gamer") == "DeepSeek Reasoner"
    assert wb.resolver_modelo_actual("Por Defecto", "general") == "DeepSeek Reasoner"
    # La selección explícita del usuario SIEMPRE gana.
    assert wb.resolver_modelo_actual("Gemini 3.1 Pro (High)", "mentor") == "Gemini 3.1 Pro (High)"


# ─── Fijar capacidad (pin) — UI opción B ─────────────────────────────────────

def test_capacidad_fijada_por_defecto_none():
    e = EstadoGlobal()
    assert e.obtener_capacidad_fijada() is None


def test_fijar_y_liberar_capacidad():
    e = EstadoGlobal()
    e.fijar_capacidad("mentor")
    assert e.obtener_capacidad_fijada() == "mentor"
    e.fijar_capacidad(None)
    assert e.obtener_capacidad_fijada() is None


def test_bridge_fijar_capacidad_validacion(bridge_modulo, monkeypatch):
    wb = bridge_modulo
    _con_estado(monkeypatch, wb, modo_actual="general", modelo_seleccionado="Por Defecto")
    bridge = wb.ArgusWebBridge()

    res = bridge.fijar_capacidad("mentor")
    assert res["exito"] is True
    assert res["capacidad_fijada"] == "mentor"

    res_invalida = bridge.fijar_capacidad("raro")
    assert res_invalida["exito"] is False

    res_auto = bridge.fijar_capacidad("auto")
    assert res_auto["exito"] is True
    assert res_auto["capacidad_fijada"] is None


# ─── Exposición a la UI ─────────────────────────────────────────────────────

def test_estado_inicial_incluye_mcp_disponible(bridge_modulo, monkeypatch):
    wb = bridge_modulo
    _con_estado(monkeypatch, wb, modo_actual="mentor", modelo_seleccionado="Por Defecto")

    res = wb.ArgusWebBridge().obtener_estado_inicial()

    # Default global = Gemini → MCP activo incluso en modo mentor.
    assert res["mcp_disponible"] is True
    assert res["modelo_real"] == "Gemini 3.5 Flash Lite"


def test_obtener_modelo_real_incluye_mcp(bridge_modulo, monkeypatch):
    wb = bridge_modulo
    _con_estado(monkeypatch, wb, modo_actual="mentor", modelo_seleccionado="Por Defecto")

    res = wb.ArgusWebBridge().obtener_modelo_real()

    assert res["exito"] is True
    assert res["modelo_real"] == "Gemini 3.5 Flash Lite"
    assert res["mcp_disponible"] is True


def test_cambiar_modelo_alerta_mcp_disponible(bridge_modulo, monkeypatch):
    wb = bridge_modulo
    _con_estado(monkeypatch, wb, modo_actual="general", modelo_seleccionado="Por Defecto")

    bridge = wb.ArgusWebBridge()
    res_gemini = bridge.cambiar_modelo_seleccionado("Gemini 3.1 Flash Lite")
    assert res_gemini["exito"] is True
    assert res_gemini["mcp_disponible"] is True

    res_deepseek = bridge.cambiar_modelo_seleccionado("DeepSeek Reasoner")
    assert res_deepseek["exito"] is True
    assert res_deepseek["mcp_disponible"] is False


def test_cambiar_modo_alerta_mcp_disponible(bridge_modulo, monkeypatch):
    wb = bridge_modulo
    _con_estado(monkeypatch, wb, modo_actual="general", modelo_seleccionado="Por Defecto")

    bridge = wb.ArgusWebBridge()
    res_gamer = bridge.cambiar_modo_interfaz("gamer")
    assert res_gamer["exito"] is True
    assert res_gamer["mcp_disponible"] is True

    res_mentor = bridge.cambiar_modo_interfaz("mentor")
    assert res_mentor["exito"] is True
    assert res_mentor["mcp_disponible"] is True


# ─── Botón "Escuchar" (leer texto con voz, sin LLM) ──────────────────────────

def test_leer_texto_con_voz_llama_tts(bridge_modulo, monkeypatch):
    wb = bridge_modulo
    _con_estado(monkeypatch, wb, modo_actual="general", modelo_seleccionado="Por Defecto")

    # web_bridge importó hablar_no_bloqueante en top-level desde el stub de
    # modulos.audio_custom; lo parcheamos en web_bridge para registrar.
    llamadas = []
    monkeypatch.setattr(wb, "hablar_no_bloqueante", lambda t: llamadas.append(t))

    bridge = wb.ArgusWebBridge()
    res = bridge.leer_texto_con_voz("Hola, esto es una respuesta")

    assert res["exito"] is True
    assert llamadas == ["Hola, esto es una respuesta"]


def test_leer_texto_con_voz_vacio_no_llama(bridge_modulo, monkeypatch):
    wb = bridge_modulo
    _con_estado(monkeypatch, wb, modo_actual="general", modelo_seleccionado="Por Defecto")

    llamadas = []
    monkeypatch.setattr(wb, "hablar_no_bloqueante", lambda t: llamadas.append(t))

    bridge = wb.ArgusWebBridge()
    res = bridge.leer_texto_con_voz("   ")

    assert res["exito"] is False
    assert llamadas == []