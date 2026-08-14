"""
Tests del recuperador automático de memoria (Fase 4).

Se stubea `modulos.memoria` (pesado: descarga el SentenceTransformer al
importar) con una versión que devuelve el detalle de la bóveda a pedido.
Se usa el módulo REAL de `modulos.olvidos` apuntando a un archivo temporal,
igual que hacen los tests de olvidos existentes.

Offline y rápido: no hay red, ni API keys, ni ChromaDB real.
"""

import sys
import types

import pytest

import modulos.recuperador_memoria as rm


@pytest.fixture
def detalle_boveda_stub(monkeypatch):
    """
    Inyecta en sys.modules un `modulos.memoria` falso cuyo detalle se puede
    configurar por test. Devuelve una función `configurar(detalle)`.
    """
    modulo = types.ModuleType("modulos.memoria")
    modulo._resultado_detalle = []

    def _obtener_detalle(consulta):
        return modulo._resultado_detalle

    modulo.obtener_resultado_anticipado_detalle = _obtener_detalle
    monkeypatch.setitem(sys.modules, "modulos.memoria", modulo)

    def _configurar(detalle):
        modulo._resultado_detalle = detalle

    yield _configurar
    monkeypatch.delitem(sys.modules, "modulos.memoria", raising=False)


@pytest.fixture
def olvidos_tmp(tmp_path, monkeypatch):
    from modulos import olvidos

    monkeypatch.setattr(olvidos, "RUTA_OLVIDOS", str(tmp_path / "olvidos.json"))
    return olvidos


# ─── Helpers ────────────────────────────────────────────────────────────────

_ID_BOVEDA = "boveda:memoria_ia:488f6c7c78"
_ID_BOVEDA_2 = "boveda:memoria_ia:aabbccddee"


def _recuerdo(
    texto,
    distancia,
    origen_id=_ID_BOVEDA,
    etiqueta="Memoria_IA",
    fecha="2025-01-01 12:00:00",
    origen_fuente="memoria_manual",
):
    return {
        "documento": texto,
        "origen_id": origen_id,
        "origen_fuente": origen_fuente,
        "etiqueta": etiqueta,
        "fecha_guardado": fecha,
        "distancia": distancia,
    }


# ─── recuperar_memorias: filtros ─────────────────────────────────────────────

def test_recuperar_memorias_solo_boveda(detalle_boveda_stub):
    detalle = [
        _recuerdo("Recuerdo libre", 0.47),
        _recuerdo("Espejo de panel", 0.40, origen_id="vida:salud"),
    ]
    detalle_boveda_stub(detalle)

    memorias = rm.recuperar_memorias("algo")
    assert [m["origen_id"] for m in memorias] == [_ID_BOVEDA]


def test_recuperar_memorias_excluye_olvidadas(detalle_boveda_stub, olvidos_tmp):
    olvidos_tmp.registrar_olvido(_ID_BOVEDA)
    detalle = [
        _recuerdo("Recuerdo olvidado", 0.47, origen_id=_ID_BOVEDA),
        _recuerdo("Recuerdo vigente", 0.47, origen_id=_ID_BOVEDA_2),
    ]
    detalle_boveda_stub(detalle)

    memorias = rm.recuperar_memorias("algo")
    assert [m["origen_id"] for m in memorias] == [_ID_BOVEDA_2]


def test_recuperar_memorias_filtra_por_umbral_similitud(detalle_boveda_stub):
    detalle = [
        _recuerdo("Relevante (sim 0.53)", 0.47),
        _recuerdo("Irrelevante (sim 0.40)", 0.60),
    ]
    detalle_boveda_stub(detalle)

    memorias = rm.recuperar_memorias("algo")
    assert len(memorias) == 1
    assert memorias[0]["documento"] == "Relevante (sim 0.53)"


def test_recuperar_memorias_sin_distancia_no_pasa_umbral(detalle_boveda_stub):
    detalle = [_recuerdo("Sin distancia", None)]
    detalle_boveda_stub(detalle)

    assert rm.recuperar_memorias("algo") == []


def test_recuperar_memorias_sin_resultados_devuelve_vacio(detalle_boveda_stub):
    detalle_boveda_stub([])
    assert rm.recuperar_memorias("algo") == []


# ─── recuperar_memorias: dedup, orden y tope ─────────────────────────────────

def test_recuperar_memorias_deduplica_por_origen_id_quedando_reciente(detalle_boveda_stub):
    detalle = [
        _recuerdo("Versión vieja", 0.47, origen_id=_ID_BOVEDA, fecha="2024-01-01 12:00:00"),
        _recuerdo("Versión nueva", 0.47, origen_id=_ID_BOVEDA, fecha="2025-01-01 12:00:00"),
    ]
    detalle_boveda_stub(detalle)

    memorias = rm.recuperar_memorias("algo")
    assert len(memorias) == 1
    assert memorias[0]["documento"] == "Versión nueva"


def test_recuperar_memorias_ordena_por_similitud(detalle_boveda_stub):
    detalle = [
        _recuerdo("Menos parecido", 0.48, origen_id=_ID_BOVEDA, fecha="2025-01-01 12:00:00"),
        _recuerdo("Más parecido", 0.45, origen_id=_ID_BOVEDA_2, fecha="2025-01-01 12:00:00"),
    ]
    detalle_boveda_stub(detalle)

    memorias = rm.recuperar_memorias("algo")
    assert [m["documento"] for m in memorias] == ["Más parecido", "Menos parecido"]


def test_recuperar_memorias_respeta_cantidad_maxima(detalle_boveda_stub):
    detalle = [
        _recuerdo("Uno", 0.47, origen_id=_ID_BOVEDA),
        _recuerdo("Dos", 0.47, origen_id=_ID_BOVEDA_2),
    ]
    detalle_boveda_stub(detalle)

    memorias = rm.recuperar_memorias("algo", cantidad_maxima=1)
    assert len(memorias) == 1


# ─── bloque_memoria_para_contexto ───────────────────────────────────────────

def test_bloque_vacio_devuelve_cadena_vacia(detalle_boveda_stub):
    detalle_boveda_stub([])
    assert rm.bloque_memoria_para_contexto("algo") == ""


def test_bloque_incluye_cabecera_y_documento(detalle_boveda_stub):
    detalle_boveda_stub([_recuerdo("El usuario usa FastAPI", 0.47)])
    bloque = rm.bloque_memoria_para_contexto("framework")

    assert "MEMORIA A LARGO PLAZO" in bloque
    assert "El usuario usa FastAPI" in bloque
    assert "[etiqueta: Memoria_IA]" in bloque


def test_bloque_respeta_tope_de_caracteres(detalle_boveda_stub):
    import config

    texto_largo = "x" * 5000
    detalle_boveda_stub([_recuerdo(texto_largo, 0.47)])

    bloque = rm.bloque_memoria_para_contexto("algo")
    assert len(bloque) <= config.MEMORIA_MAX_CARACTERES
    assert bloque.endswith("…")  # quedó recortado


def test_bloque_excluye_olvidadas_en_presentacion(detalle_boveda_stub, olvidos_tmp):
    olvidos_tmp.registrar_olvido(_ID_BOVEDA)
    detalle = [
        _recuerdo("Este no debe aparecer", 0.47, origen_id=_ID_BOVEDA),
        _recuerdo("Este sí", 0.47, origen_id=_ID_BOVEDA_2),
    ]
    detalle_boveda_stub(detalle)

    bloque = rm.bloque_memoria_para_contexto("algo")
    assert "Este no debe aparecer" not in bloque
    assert "Este sí" in bloque
