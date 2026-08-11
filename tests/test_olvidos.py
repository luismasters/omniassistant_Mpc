"""
Tests del registro persistente de olvidos (tombstones) — modulos/olvidos.py.

Cubren la API del registro (registrar/quitar/consultar), la persistencia en
disco (siempre en tmp_path vía monkeypatch de RUTA_OLVIDOS, nunca en el
olvidos.json real) y las reglas de contrato:
- Solo se aceptan ids con prefijo conocido (funcional:/vida:/mentor:/gamer:).
- La comparación es por igualdad de string determinista (sin fuzzy matching).
- El registro es thread-safe.
"""

import pytest

import modulos.olvidos as olv


@pytest.fixture
def olvidos_tmp(tmp_path, monkeypatch):
    """Apunta RUTA_OLVIDOS a una carpeta temporal para no tocar el archivo real."""
    monkeypatch.setattr(olv, "RUTA_OLVIDOS", str(tmp_path / "olvidos.json"))
    return tmp_path


# ── registrar ────────────────────────────────────────────────────────────────

def test_registrar_y_consultar(olvidos_tmp):
    assert olv.esta_olvidado("vida:salud") is False
    assert olv.registrar_olvido("vida:salud") is True
    assert olv.esta_olvidado("vida:salud") is True


def test_obtener_ids_olvidados(olvidos_tmp):
    olv.registrar_olvido("vida:salud")
    olv.registrar_olvido("mentor:stack_backend")
    assert olv.obtener_ids_olvidados() == {"vida:salud", "mentor:stack_backend"}
    assert olv.obtener_ids_olvidados("vida:") == {"vida:salud"}
    assert olv.obtener_ids_olvidados("mentor:") == {"mentor:stack_backend"}


def test_registrar_duplicado_es_idempotente(olvidos_tmp):
    assert olv.registrar_olvido("funcional:identidad") is True
    assert olv.registrar_olvido("funcional:identidad") is True
    # Solo queda una entrada
    assert olv.obtener_ids_olvidados("funcional:") == {"funcional:identidad"}


# ── quitar ───────────────────────────────────────────────────────────────────

def test_quitar_olvido(olvidos_tmp):
    olv.registrar_olvido("vida:salud")
    assert olv.quitar_olvido("vida:salud") is True
    assert olv.esta_olvidado("vida:salud") is False


def test_quitar_inexistente_devuelve_false(olvidos_tmp):
    assert olv.quitar_olvido("vida:salud") is False


# ── validación de prefijos (contrato) ────────────────────────────────────────

def test_id_sin_prefijo_rechazado(olvidos_tmp):
    assert olv.registrar_olvido("salud") is False
    assert olv.registrar_olvido("") is False
    assert olv.registrar_olvido(None) is False
    assert olv.obtener_ids_olvidados() == set()


def test_id_con_prefijo_desconocido_rechazado(olvidos_tmp):
    assert olv.registrar_olvido("chromadb:xyz") is False
    assert olv.esta_olvidado("chromadb:xyz") is False
    assert olv.obtener_ids_olvidados() == set()


def test_quitar_id_invalido_devuelve_false(olvidos_tmp):
    assert olv.quitar_olvido("boveda:xyz") is False


def test_consultar_id_invalido_devuelve_false(olvidos_tmp):
    assert olv.esta_olvidado("proyecto") is False


# ── igualdad determinista (no fuzzy) ─────────────────────────────────────────

def test_comparacion_es_por_igualdad_exacta(olvidos_tmp):
    # "vida:salud" y "vida:salud_" son ids distintos: no hay fuzzy matching.
    olv.registrar_olvido("vida:salud")
    assert olv.esta_olvidado("vida:salud") is True
    assert olv.esta_olvidado("vida:salud_") is False
    assert olv.esta_olvidado("vida:otra") is False


def test_ids_distintos_no_colisionan(olvidos_tmp):
    olv.registrar_olvido("mentor:stack_backend")
    assert olv.esta_olvidado("mentor:stack_frontend") is False
    assert olv.esta_olvidado("mentor:stack_backend") is True


# ── persistencia en disco ────────────────────────────────────────────────────

def test_persistencia_entre_instancias(olvidos_tmp):
    olv.registrar_olvido("gamer:grim_dawn")
    # Simular reinicio: el archivo queda escrito en tmp_path con la entrada.
    ruta = olvidos_tmp / "olvidos.json"
    assert ruta.exists()
    assert "gamer:grim_dawn" in ruta.read_text(encoding="utf-8")


def test_lectura_mantiene_lo_escrito(olvidos_tmp):
    olv.registrar_olvido("vida:salud")
    registro = olv.leer_registro()
    assert list(registro.keys()) == ["vida:salud"]
    import re
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", list(registro.values())[0])


def test_archivo_corrupto_devuelve_vacio(olvidos_tmp):
    ruta = olvidos_tmp / "olvidos.json"
    ruta.write_text("esto no es json", encoding="utf-8")
    assert olv.leer_registro() == {}
    assert olv.esta_olvidado("vida:salud") is False