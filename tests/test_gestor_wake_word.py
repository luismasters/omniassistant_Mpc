"""
Pruebas unitarias para el módulo gestor_wake_word y coincidencia de palabra clave.
"""

import os
import sys

def test_gramatica_incluye_ok_argus():
    from modulos.skills.wake_word.gestor_wake_word import GRAMATICA_WAKE_WORD
    assert "ok argus" in GRAMATICA_WAKE_WORD

def test_es_match_wake_word_positivos():
    from modulos.skills.wake_word.gestor_wake_word import _es_match_wake_word
    
    # Coincidencias exactas y fonéticas
    assert _es_match_wake_word("ok argus") is True
    assert _es_match_wake_word("ok argos") is True
    assert _es_match_wake_word("okey argus") is True
    assert _es_match_wake_word("oquei argus") is True
    assert _es_match_wake_word("okey argos") is True
    assert _es_match_wake_word("okargus") is True
    assert _es_match_wake_word("ocargus") is True
    assert _es_match_wake_word("ok argus abre chrome") is True
    assert _es_match_wake_word("okey argus cual es el clima") is True

def test_es_match_wake_word_negativos():
    from modulos.skills.wake_word.gestor_wake_word import _es_match_wake_word
    
    # Frases que no deben detonar
    assert _es_match_wake_word("hola argus") is False
    assert _es_match_wake_word("buenos dias") is False
    assert _es_match_wake_word("corta la musica") is False
    assert _es_match_wake_word("abrir navegador") is False

def test_rms_umbral_voz_config():
    import config
    assert config.RMS_UMBRAL_VOZ == 150
