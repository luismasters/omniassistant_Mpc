"""
Tests de la semántica de retomar historial persistido (Fase P).

Regla (decisión 12/08/2026): `restaurar_historial_persistido` REEMPLAZA el
contexto si está vacío y ANEXA si ya hay conversación en curso (respetando
MAX_MENSAJES_CONTEXTO). No depende de la persistencia en disco.
"""

from config import EstadoGlobal, MAX_MENSAJES_CONTEXTO


def _estado():
    return EstadoGlobal()


def _historial(n):
    return [{"role": "user", "parts": [f"hist-{i}"]} for i in range(n)]


def test_retomar_con_contexto_vacio_reemplaza():
    e = _estado()
    e.restaurar_historial_persistido(_historial(3))
    assert len(e.contexto_chat) == 3
    assert e.contexto_chat[0]["parts"][0] == "hist-0"


def test_retomar_con_contexto_en_curso_anexa():
    e = _estado()
    e.contexto_chat = [{"role": "user", "parts": ["actual"]}]
    e.restaurar_historial_persistido(_historial(2))
    assert len(e.contexto_chat) == 3
    assert e.contexto_chat[0]["parts"][0] == "actual"
    assert e.contexto_chat[-1]["parts"][0] == "hist-1"


def test_retomar_respeta_max_mensajes():
    e = _estado()
    e.contexto_chat = [{"role": "user", "parts": ["actual"]}]
    e.restaurar_historial_persistido(_historial(MAX_MENSAJES_CONTEXTO))
    # Se recorta a MAX_MENSAJES_CONTEXTO, conservando los más recientes.
    assert len(e.contexto_chat) == MAX_MENSAJES_CONTEXTO
    assert e.contexto_chat[-1]["parts"][0] == f"hist-{MAX_MENSAJES_CONTEXTO - 1}"


def test_retomar_sin_historial_no_rompe():
    e = _estado()
    e.restaurar_historial_persistido([])
    assert e.contexto_chat == []
    e.restaurar_historial_persistido(None)
    assert e.contexto_chat == []
