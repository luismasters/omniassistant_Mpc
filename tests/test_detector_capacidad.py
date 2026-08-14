# -*- coding: utf-8 -*-
"""
Fase D (Punto 3, refinamiento) — Detección de capacidad por embeddings.

Contrato ANTIFALSOS POSITIVOS:
- Solo activa si la mejor similitud supera el umbral Y le saca un margen claro
  a la otra capacidad.
- Mensajes neutrales/ambiguos/comandos → None (general).
- Ante cualquier falla del modelo → None (degradación silenciosa).
"""
import sys
import types

import config
from modulos import detector_capacidad as dc


# ─── Lógica pura de decisión (sin modelo) ──────────────────────────────────

def test_decidir_mentor_cuando_supera_umbral_y_margen():
    assert dc._decidir_capacidad_por_scores(0.90, 0.30) == "mentor"


def test_decidir_gamer_cuando_supera_umbral_y_margen():
    assert dc._decidir_capacidad_por_scores(0.30, 0.90) == "gamer"


def test_decidir_none_si_no_alcanza_umbral():
    assert dc._decidir_capacidad_por_scores(0.50, 0.30) is None
    assert dc._decidir_capacidad_por_scores(0.40, 0.40) is None


def test_decidir_none_si_ambiguo_sin_margen():
    # Ambos superan el umbral pero la diferencia es menor al margen → None.
    assert dc._decidir_capacidad_por_scores(0.70, 0.68) is None
    assert dc._decidir_capacidad_por_scores(0.68, 0.70) is None


def test_coseno():
    assert dc._coseno([1, 0], [1, 0]) == 1.0
    assert dc._coseno([1, 0], [0, 1]) == 0.0
    assert dc._coseno([], []) == 0.0
    assert abs(dc._coseno([1, 1], [1, 0]) - (2 ** 0.5) / 2) < 1e-6


# ─── Función completa con stub de modulos.memoria ──────────────────────────

class _FakeModelo:
    """Devuelve embeddings que codifican el caso a probar según el texto."""

    def embed_query(self, textos):
        def vec(t):
            tl = str(t).lower()
            if tl in dc._PROTOTIPOS_MENTORIA:
                return (1.0, 0.0, 0.0)
            if tl in dc._PROTOTIPOS_GAMING:
                return (0.0, 1.0, 0.0)
            if tl.startswith("mentor-win"):
                return (0.9, 0.3, 0.3)
            if tl.startswith("gamer-win"):
                return (0.3, 0.9, 0.3)
            if tl.startswith("ambig"):
                return (0.5, 0.5, 0.0)
            if tl.startswith("neutro"):
                return (0.4, 0.4, 0.4)
            return (0.0, 0.0, 1.0)

        return [vec(t) for t in textos]


def _stub_memoria(monkeypatch):
    """Registra un modulos.memoria falso con el modelo fake (sin cargar nada)."""
    fake = types.ModuleType("modulos.memoria")
    fake.modelo_traductor = _FakeModelo()
    fake._cache_get = lambda k: None
    fake._cache_set = lambda k, v: None
    monkeypatch.setitem(sys.modules, "modulos.memoria", fake)
    monkeypatch.setattr(dc, "_prototipos_cache", None)


def test_detectar_por_embeddings_mentor(monkeypatch):
    _stub_memoria(monkeypatch)
    assert dc.detectar_capacidad_por_embeddings("mentor-win: quiero crecer en IT") == "mentor"


def test_detectar_por_embeddings_gamer(monkeypatch):
    _stub_memoria(monkeypatch)
    assert dc.detectar_capacidad_por_embeddings("gamer-win: dame una guia del juego") == "gamer"


def test_detectar_por_embeddings_ambiguo_none(monkeypatch):
    _stub_memoria(monkeypatch)
    assert dc.detectar_capacidad_por_embeddings("ambig: estudiar y jugar") is None


def test_detectar_por_embeddings_neutro_none(monkeypatch):
    _stub_memoria(monkeypatch)
    assert dc.detectar_capacidad_por_embeddings("neutro: que hora es") is None


def test_detectar_por_embeddings_vacio_none(monkeypatch):
    _stub_memoria(monkeypatch)
    assert dc.detectar_capacidad_por_embeddings("") is None
    assert dc.detectar_capacidad_por_embeddings(None) is None
    assert dc.detectar_capacidad_por_embeddings("   ") is None


def test_detectar_por_embeddings_kill_switch_off(monkeypatch):
    """Con el kill-switch apagado no se toca el modelo (ni el stub)."""
    _stub_memoria(monkeypatch)
    monkeypatch.setattr(config, "ACTIVACION_CAPACIDAD_EMBEDDINGS", False)
    assert dc.detectar_capacidad_por_embeddings("mentor-win: cualquier cosa") is None


def test_detectar_por_embeddings_sin_memoria_degrada_none(monkeypatch):
    """Si modulos.memoria no existe / falla, degrada a None sin crashear."""
    monkeypatch.delitem(sys.modules, "modulos.memoria", raising=False)
    monkeypatch.setattr(config, "ACTIVACION_CAPACIDAD_EMBEDDINGS", True)
    assert dc.detectar_capacidad_por_embeddings("quiero un consejo") is None