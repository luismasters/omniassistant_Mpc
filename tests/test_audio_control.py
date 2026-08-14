"""
Pruebas unitarias de auditoría para el módulo control_audio / audio_control.py.
Garantiza que ninguna función provoque cierres de ejecutable, violaciones
de acceso COM o excepciones no capturadas.
"""

import pytest
from unittest.mock import MagicMock, patch

from modulos.skills.control_audio.audio_control import (
    _limpiar_nombre_dispositivo,
    obtener_volumen,
    establecer_volumen,
    subir_volumen,
    bajar_volumen,
    silenciar,
    obtener_volumen_app,
    establecer_volumen_app,
    silenciar_app,
    listar_apps_con_audio,
    listar_dispositivos_audio,
    cambiar_dispositivo_audio,
    _obtener_pids_por_titulo_ventana
)


def test_limpiar_nombre_dispositivo():
    assert _limpiar_nombre_dispositivo('"Altavoces (JBL Go4 Lu)"') == 'Altavoces (JBL Go4 Lu)'
    assert _limpiar_nombre_dispositivo("'Path of Exile 2'") == 'Path of Exile 2'
    assert _limpiar_nombre_dispositivo('  "Discord"  ') == 'Discord'


def test_obtener_volumen_sin_crash():
    resultado = obtener_volumen()
    assert isinstance(resultado, str)
    assert len(resultado) > 0


def test_establecer_volumen_limites():
    res1 = establecer_volumen(150)
    assert isinstance(res1, str)
    res2 = establecer_volumen(-50)
    assert isinstance(res2, str)
    res3 = establecer_volumen(50)
    assert isinstance(res3, str)


def test_subir_bajar_volumen_sin_crash():
    res_subir = subir_volumen(10)
    assert isinstance(res_subir, str)
    res_bajar = bajar_volumen(10)
    assert isinstance(res_bajar, str)


def test_silenciar_maestro_sin_crash():
    res_silenciar = silenciar(True)
    assert isinstance(res_silenciar, str)
    res_activar = silenciar(False)
    assert isinstance(res_activar, str)


def test_obtener_volumen_app_inexistente():
    resultado = obtener_volumen_app("AppFantasma999")
    assert isinstance(resultado, str)
    assert "No encontré" in resultado or "No se pudo" in resultado


def test_establecer_volumen_app_inexistente():
    resultado = establecer_volumen_app("AppFantasma999", 80)
    assert isinstance(resultado, str)
    assert "No encontré" in resultado or "No se pudo" in resultado


def test_silenciar_app_inexistente():
    resultado = silenciar_app("AppFantasma999", True)
    assert isinstance(resultado, str)
    assert "No se encontró" in resultado or "No se pudo" in resultado


def test_listar_apps_con_audio_sin_crash():
    resultado = listar_apps_con_audio()
    assert isinstance(resultado, str)
    assert len(resultado) > 0


def test_listar_dispositivos_audio_sin_crash():
    resultado = listar_dispositivos_audio()
    assert isinstance(resultado, str)
    assert len(resultado) > 0


def test_cambiar_dispositivo_audio_desconocido():
    resultado = cambiar_dispositivo_audio("DispositivoInexistente999")
    assert isinstance(resultado, str)
    assert "No se pudo cambiar" in resultado or "Dispositivo" in resultado


def test_obtener_pids_por_titulo_ventana_sin_crash():
    pids = _obtener_pids_por_titulo_ventana("titulo_que_no_existe_999")
    assert isinstance(pids, set)
