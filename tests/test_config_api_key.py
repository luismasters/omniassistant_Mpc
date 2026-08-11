"""
Tests para la validación amigable de GEMINI_API_KEY en config.py.

Contrato (deuda del ROADMAP): importar `config` SIN GEMINI_API_KEY no debe
crashear (antes lanzaba ValueError). La app degrada: GEMINI_API_KEY queda "" y
la IA responde con un aviso (ver modulos.ia.enviar_a_gemini).

Estos tests importan `config` REAL en un proceso limpio, stubeando solo el
entorno (os.environ) y las dependencias pesadas que config arrastraría si
estuvieran importadas. Offline y sin red.
"""

import importlib
import os
import sys

import pytest


@pytest.fixture
def config_limpio(monkeypatch):
    """Expulsa config (y dependencias arrastradas) de los cachés de import."""
    for nombre in ("config", "modulos.mensajes_web", "modulos.logger"):
        sys.modules.pop(nombre, None)
    # Forzar entorno controlado: sin GEMINI_API_KEY. load_dotenv() NO
    # sobreescribe una variable ya definida, aunque sea vacía.
    monkeypatch.setenv("GEMINI_API_KEY", "")
    yield
    for nombre in ("config", "modulos.mensajes_web", "modulos.logger"):
        sys.modules.pop(nombre, None)


def test_config_sin_key_no_crashea_y_degrada(config_limpio):
    """Sin GEMINI_API_KEY: importar config NO lanza y queda con key vacía."""
    module = importlib.import_module("config")
    assert module.GEMINI_API_KEY == ""
    assert module.TIENE_API_GEMINI is False


def test_config_con_key_expuesta(config_limpio, monkeypatch):
    """Con GEMINI_API_KEY: importar config la conserva y activa el flag."""
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")
    module = importlib.import_module("config")
    assert module.GEMINI_API_KEY == "clave-de-prueba"
    assert module.TIENE_API_GEMINI is True