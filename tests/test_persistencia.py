"""
Tests de modulos.persistencia (Fase P MVP).

Cubren: escritura, lectura, recuperación (tail), límites/rotación,
concurrencia, reinicio/aborted, corrupción, duplicados, aislamiento de
contextos, preferencias y recarga de estado de proyecto. Todo offline, con
ARGUS_PERSISTENCIA_DIR apuntando a tmp_path y persistencia habilitada.
"""

import json
import os
import threading

import pytest

import modulos.persistencia as pers


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Habilita la persistencia en una carpeta temporal y resetea el estado."""
    monkeypatch.delenv("OMNASSISTANT_NO_PERSISTENCIA", raising=False)
    monkeypatch.setenv("ARGUS_PERSISTENCIA_DIR", str(tmp_path))
    pers.reiniciar_estado_prueba()
    yield pers
    pers.reiniciar_estado_prueba()


# ─── Escritura (W) ───────────────────────────────────────────────────────────

def test_registrar_mensaje_escribe_jsonl_valido(store, tmp_path):
    assert store.registrar_mensaje("general", "user", "hola")
    assert store.registrar_mensaje("general", "model", "hola luism")

    ruta = store.ruta_contexto("general")
    assert os.path.exists(ruta)
    lineas = [json.loads(l) for l in open(ruta, encoding="utf-8") if l.strip()]
    tipos = [r["tipo"] for r in lineas]
    assert "sesion" in tipos and "msg" in tipos
    msgs = [r for r in lineas if r["tipo"] == "msg"]
    assert len(msgs) == 2
    assert [m["role"] for m in msgs] == ["user", "model"]
    assert msgs[0]["parts"] == ["hola"]
    assert msgs[1]["turno_seq"] == msgs[0]["turno_seq"]  # mismo turno
    assert msgs[1]["msg_seq"] == 1


def test_registrar_abre_sesion_automatica(store):
    assert store.sesion_actual("gamer") is None
    store.registrar_mensaje("gamer", "user", "hola")
    sesion = store.sesion_actual("gamer")
    assert sesion is not None and sesion["estado"] == "open"
    assert sesion["context_id"] == "gamer"


def test_registrar_acepta_parts_lista(store):
    store.registrar_mensaje("general", "user", ["a", "b"])
    regs = store._leer_registros("general")
    msgs = [r for r in regs if r["tipo"] == "msg"]
    assert msgs[0]["parts"] == ["a", "b"]


# ─── Lectura (R) ─────────────────────────────────────────────────────────────

def test_listar_sesiones_orden(store):
    store.registrar_mensaje("general", "user", "uno")
    store.cerrar_sesion("general")
    store.registrar_mensaje("general", "user", "dos")
    store.cerrar_sesion("general")

    sesiones = store.listar_sesiones("general")
    assert len(sesiones) == 2
    assert sesiones[0]["orden"] < sesiones[1]["orden"]
    assert sesiones[-1]["estado"] == "closed"


# ─── Recuperación (REC) ──────────────────────────────────────────────────────

def test_recuperar_tail_ultima_sesion(store):
    store.registrar_mensaje("general", "user", "viejo")
    store.registrar_mensaje("general", "model", "resp vieja")
    store.cerrar_sesion("general")
    store.registrar_mensaje("general", "user", "nuevo")
    store.registrar_mensaje("general", "model", "resp nueva")

    tail = store.recuperar_tail("general")
    textos = [m["parts"][0] for m in tail]
    assert "viejo" not in textos
    assert "nuevo" in textos and "resp nueva" in textos


def test_recuperar_tail_excluye_marcadores(store):
    store.registrar_mensaje("general", "user", "[SISTEMA] Archivos cargados")
    store.registrar_mensaje("general", "user", "pregunta normal")
    tail = store.recuperar_tail("general")
    textos = [m["parts"][0] for m in tail]
    assert "pregunta normal" in textos
    assert not any(t.startswith("[SISTEMA]") for t in textos)


def test_recuperar_tail_respeta_max_mensajes(store):
    for i in range(30):
        store.registrar_mensaje("general", "user", f"u{i}")
    tail = store.recuperar_tail("general", max_mensajes=10)
    assert len(tail) == 10
    assert tail[0]["parts"][0] == "u20"


def test_recuperar_tail_respeta_max_caracteres(store):
    store.registrar_mensaje("general", "user", "x" * 50)
    store.registrar_mensaje("general", "user", "y" * 50)
    tail = store.recuperar_tail("general", max_mensajes=5, max_caracteres=70)
    assert len(tail) == 1
    assert tail[0]["parts"][0].startswith("y")


def test_recuperar_tail_no_escribe(store, tmp_path):
    store.registrar_mensaje("general", "user", "hola")
    antes = open(store.ruta_contexto("general"), encoding="utf-8").read()
    store.recuperar_tail("general")
    despues = open(store.ruta_contexto("general"), encoding="utf-8").read()
    assert antes == despues


# ─── Límites / rotación (LIM) ────────────────────────────────────────────────

def test_purgar_historial_conserva_ultimas(store):
    for i in range(5):
        store.registrar_mensaje("general", "user", f"s{i}")
        store.cerrar_sesion("general")
    purgadas = store.purgar_historial("general", conservar=2)
    assert purgadas == 3
    sesiones = store.listar_sesiones("general")
    assert len(sesiones) == 2
    # Las sesiones conservadas son las últimas (orden mayor).
    assert [s["orden"] for s in sesiones] == [3, 4]


# ─── Concurrencia (CON) ──────────────────────────────────────────────────────

def test_concurrencia_escritura_no_corrompe(store):
    def escribir(n):
        for i in range(20):
            store.registrar_mensaje("general", "user", f"hilo{n}-{i}")

    hilos = [threading.Thread(target=escribir, args=(n,)) for n in range(4)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    regs = store._leer_registros("general")
    msgs = [r for r in regs if r["tipo"] == "msg"]
    assert len(msgs) == 80
    # Sin duplicados: cada (turno_seq, msg_seq) aparece una sola vez.
    claves = set((m["turno_seq"], m["msg_seq"]) for m in msgs)
    assert len(claves) == 80


# ─── Reinicio / aborted (RE) ─────────────────────────────────────────────────

def test_deteccion_sesion_abierta_marca_aborted(store):
    store.registrar_mensaje("general", "user", "queda abierta")
    # Simula reinicio: nueva instancia (se limpia el registro en memoria).
    store.reiniciar_estado_prueba()
    afectados = store.marcar_sesiones_abiertas_como_aborted()
    assert "general" in afectados
    ultima = store.listar_sesiones("general")[-1]
    assert ultima["estado"] == "aborted"


def test_sesion_cerrada_no_se_marca_aborted(store):
    store.registrar_mensaje("general", "user", "hola")
    store.cerrar_sesion("general")
    store.reiniciar_estado_prueba()
    afectados = store.marcar_sesiones_abiertas_como_aborted()
    assert "general" not in afectados


# ─── Corrupción (COR) ────────────────────────────────────────────────────────

def test_linea_truncada_se_descarta(store, tmp_path):
    store.registrar_mensaje("general", "user", "hola")
    ruta = store.ruta_contexto("general")
    with open(ruta, "a", encoding="utf-8") as f:
        f.write('{"tipo":"msg","parts":["trun')
    regs = store._leer_registros("general")
    assert len(regs) >= 1
    assert all(r["tipo"] in ("sesion", "msg") for r in regs)


def test_checksum_invalido_se_descarta(store, tmp_path):
    store.registrar_mensaje("general", "user", "hola")
    ruta = store.ruta_contexto("general")
    with open(ruta, "a", encoding="utf-8") as f:
        f.write('{"tipo":"msg","parts":["falso"],"sha":"0000"}\n')
    regs = store._leer_registros("general")
    # Ningún registro con checksum inválido sobrevive.
    assert all(r.get("parts") != ["falso"] for r in regs)


# ─── Duplicados (DUP) ────────────────────────────────────────────────────────

def test_reescribir_mismo_turno_no_duplica(store):
    # El dedup es por (context_id, sesion_id, turno_seq, msg_seq): re-persistir
    # el MISMO turno (mismo user + mismo model) no debe duplicar registros.
    store.registrar_mensaje("general", "user", "hola")
    store.registrar_mensaje("general", "model", "respuesta")
    store.registrar_mensaje("general", "model", "respuesta")  # retry del mismo turno
    msgs = [r for r in store._leer_registros("general") if r["tipo"] == "msg"]
    assert len(msgs) == 2


# ─── Aislamiento de contextos (AISL) ─────────────────────────────────────────

def test_aislamiento_entre_contextos(store, tmp_path):
    store.registrar_mensaje("general", "user", "trabajo")
    store.registrar_mensaje("gamer", "user", "partida")
    tail_general = store.recuperar_tail("general")
    tail_gamer = store.recuperar_tail("gamer")
    assert tail_general[0]["parts"][0] == "trabajo"
    assert tail_gamer[0]["parts"][0] == "partida"
    assert os.path.exists(store.ruta_contexto("general"))
    assert os.path.exists(store.ruta_contexto("gamer"))


# ─── Preferencias (PREF) ─────────────────────────────────────────────────────

def test_preferencias_roundtrip(store):
    assert store.guardar_preferencias({"workspace_actual": "C:/repo", "modelo_seleccionado": "Gemini"})
    assert store.cargar_preferencias()["workspace_actual"] == "C:/repo"
    assert store.cargar_preferencias()["modelo_seleccionado"] == "Gemini"


def test_preferencias_atomicas(store, tmp_path):
    store.guardar_preferencias({"a": 1})
    assert not os.path.exists(store.ruta_prefs() + ".tmp")


# ─── Estado de proyecto (PROY) ───────────────────────────────────────────────

def test_cargar_estado_proyecto_desde_project_state(store, tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "PROJECT_STATE.md").write_text("# Estado del proyecto\n", encoding="utf-8")
    assert store.cargar_estado_proyecto(str(ws)).startswith("# Estado del proyecto")


def test_cargar_estado_proyecto_fallback_snapshot(store, tmp_path):
    ws = tmp_path / "ws2"
    cortana = ws / ".cortana"
    cortana.mkdir(parents=True)
    (cortana / "snapshot.json").write_text(json.dumps({"estado": "resumen v1"}), encoding="utf-8")
    assert store.cargar_estado_proyecto(str(ws)) == "resumen v1"


def test_cargar_estado_proyecto_vacio(store, tmp_path):
    ws = tmp_path / "ws3"
    ws.mkdir()
    assert store.cargar_estado_proyecto(str(ws)) == ""
    assert store.cargar_estado_proyecto("") == ""


# ─── Deshabilitación (env) ───────────────────────────────────────────────────

def test_deshabilitada_no_escribe(store, monkeypatch):
    store.registrar_mensaje("general", "user", "hola")
    monkeypatch.setenv("OMNASSISTANT_NO_PERSISTENCIA", "1")
    assert store.registrar_mensaje("general", "user", "nuevo") is False
    assert store.cerrar_sesion("general") is False
    assert store.cargar_preferencias() == {}


# ─── Compatibilidad Fase D (FD) ──────────────────────────────────────────────

def test_context_id_generico_mapea_modos(store):
    assert pers.armar_context_id("chat") == "general"
    assert pers.armar_context_id("mentor") == "mentor"
    assert pers.armar_context_id("gamer") == "gamer"
    assert pers.armar_context_id("raro") == "general"
