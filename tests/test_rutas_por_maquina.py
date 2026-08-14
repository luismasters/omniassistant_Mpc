# -*- coding: utf-8 -*-
"""Rutas por equipo (config.py): RUTA_JUEGOS y ALIASES_USUARIO.

Fijan que las rutas personales que antes estaban hardcodeadas en
modulos/sistema.py ahora viven en config.py y se comportan igual.
"""
import os

import config


def test_radar_incluye_ruta_juegos_configurada(monkeypatch, tmp_path):
    """Si config.RUTA_JUEGOS apunta a una carpeta, el radar la escanea."""
    from modulos import sistema

    carpeta = tmp_path / "juegos_portables"
    carpeta.mkdir()
    (carpeta / "JuegoPortable.lnk").write_text("", encoding="utf-8")

    monkeypatch.setattr(config, "RUTA_JUEGOS", str(carpeta))

    def fake_walk(ruta):
        if str(carpeta) in ruta:
            yield (str(carpeta), [], ["JuegoPortable.lnk"])

    monkeypatch.setattr(sistema.os, "walk", fake_walk)
    monkeypatch.setattr(sistema.os.path, "exists", lambda p: p == str(carpeta))
    monkeypatch.setattr(sistema.process, "extractOne", lambda *a, **k: ("JuegoPortable", 90))

    ruta = sistema.radar_inteligente("JuegoPortable")
    assert ruta == str(carpeta / "JuegoPortable.lnk")


def test_radar_sin_ruta_juegos_no_escanea_carpetas_extra(monkeypatch):
    """Con RUTA_JUEGOS vacía, el radar NO agrega carpetas extra."""
    from modulos import sistema

    monkeypatch.setattr(config, "RUTA_JUEGOS", "")
    escaneadas = []

    def fake_walk(ruta):
        escaneadas.append(ruta)
        yield from ()

    monkeypatch.setattr(sistema.os, "walk", fake_walk)
    monkeypatch.setattr(sistema.os.path, "exists", lambda p: True)
    monkeypatch.setattr(sistema.process, "extractOne", lambda *a, **k: None)

    sistema.radar_inteligente("NoImporta")
    assert escaneadas == [
        os.path.expanduser(r"~\Desktop"),
        r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
        os.path.join(os.path.expanduser("~"), r"AppData\Roaming\Microsoft\Windows\Start Menu\Programs"),
    ]


def test_explorar_aplica_alias_de_usuario(monkeypatch):
    """El alias c:\\users\\luis\\ se reescribe al home real."""
    from modulos import sistema

    monkeypatch.setattr(config, "ALIASES_USUARIO", {"luis": ""})
    monkeypatch.setattr(sistema.os.path, "exists", lambda p: False)

    resultado = sistema.explorar_directorio(r"c:\users\luis\Documentos")
    assert "no existe" in resultado
    assert os.path.expanduser("~").lower() in resultado.lower()


def test_explorar_no_pisa_usuario_mas_largo(monkeypatch):
    """La barra final evita pisar usuarios más largos (ej. luism)."""
    from modulos import sistema

    monkeypatch.setattr(config, "ALIASES_USUARIO", {"luis": ""})
    monkeypatch.setattr(sistema.os.path, "exists", lambda p: False)

    resultado = sistema.explorar_directorio(r"c:\users\luism\Documentos")
    assert r"c:\users\luism\documentos" in resultado.lower()
    assert "no existe" in resultado
