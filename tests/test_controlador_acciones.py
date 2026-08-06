import logging
import os
import sys
import types

# ---------------------------------------------------------------------------
# Las dependencias pesadas (modulos.ia -> modulos.memoria -> descarga del modelo
# SentenceTransformer desde HuggingFace) se stubean para que los tests sean
# rápidos, offline y deterministas. Se mantienen los módulos REALES de
# modulos.sistema y modulos.logger (offline y rápidos; logger queda en modo
# NullHandler gracias a OMNASSISTANT_NO_FILE_LOG=1 de conftest).
# ---------------------------------------------------------------------------
def _stub(nombre, attrs):
    m = types.ModuleType(nombre)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[nombre] = m
    return m


_stub("modulos.ia", {})
_stub("modulos.archivos", {
    "crear_carpeta": lambda ruta: "creado",
    "escribir_archivo": lambda ruta, contenido: "Archivo guardado correctamente",
    "leer_contenido_archivo": lambda ruta: "contenido",
    "es_ruta_segura": lambda ruta: True,
})
_stub("modulos.memoria", {
    "guardar_snapshot": lambda *a, **k: None,
    "cargar_snapshot": lambda *a, **k: "",
})

import modulos.controlador_acciones as ca


# --- _dividir_comandos ---------------------------------------------------
def test_dividir_comandos_single():
    assert ca._dividir_comandos("abrir: chrome") == ["abrir: chrome"]


def test_dividir_comandos_multiples():
    lineas = ca._dividir_comandos("abrir: chrome navegar: youtube")
    assert lineas == ["abrir: chrome", "navegar: youtube"]


def test_dividir_comandos_limpia_conjuncion():
    assert ca._dividir_comandos("abrir: chrome y") == ["abrir: chrome"]


def test_dividir_comandos_limpia_conjuncion_2():
    assert ca._dividir_comandos("abrir: chrome e") == ["abrir: chrome"]


def test_dividir_comandos_sin_verbos():
    assert ca._dividir_comandos("hola que tal") == ["hola que tal"]


# --- _normalizar_ruta ----------------------------------------------------
def test_normalizar_ruta_relativa():
    ws = r"C:\proyecto"
    assert ca._normalizar_ruta("src/app.py", ws) == os.path.join(r"C:\proyecto", "src", "app.py")


def test_normalizar_ruta_absoluta():
    assert ca._normalizar_ruta(r"C:\docs\a.txt", None) == r"C:\docs\a.txt"


def test_normalizar_ruta_limpia_caracteres():
    assert ca._normalizar_ruta(r"`C:\docs\a*.txt`", None) == r"C:\docs\a.txt"


def test_normalizar_ruta_vacia():
    assert ca._normalizar_ruta("", None) is None


# --- _validar_ruta -------------------------------------------------------
def test_validar_ruta_vacia():
    valida, _ = ca._validar_ruta("", "ws", "general")
    assert valida is False


def test_validar_ruta_modo_general():
    valida, ruta = ca._validar_ruta(r"C:\cualquier\cosa", None, "general")
    assert valida is True
    assert ruta == r"C:\cualquier\cosa"


def test_validar_ruta_dentro_workspace():
    valida, _ = ca._validar_ruta(r"C:\proyecto\archivo.txt", r"C:\proyecto", "mentor")
    assert valida is True


def test_validar_ruta_fuera_workspace():
    valida, msg = ca._validar_ruta(r"C:\otra\cosa.txt", r"C:\proyecto", "mentor")
    assert valida is False
    assert "fuera del workspace" in msg


# --- _frasear_resultado_audio_para_voz -----------------------------------
def test_frasear_resultado_audio_strips_emojis():
    assert ca._frasear_resultado_audio_para_voz("✅ Audio maestro silenciado") == "Listo, silencié el audio"


def test_frasear_resultado_audio_primera_linea():
    resultado = ca._frasear_resultado_audio_para_voz(
        "🔊 Volumen maestro establecido al 50%\nInstrucciones técnicas de instalación..."
    )
    assert resultado == "Listo, volumen al 50%"


def test_frasear_resultado_audio_otro_reemplazo():
    assert ca._frasear_resultado_audio_para_voz("Dispositivo de audio cambiado") == "Listo, cambié el dispositivo de audio"


def test_frasear_resultado_audio_sin_reemplazo():
    assert ca._frasear_resultado_audio_para_voz("Algo inesperado") == "Algo inesperado"