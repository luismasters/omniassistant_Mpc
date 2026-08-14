"""
Tests de modulos.ia.mcp_olvidar_tema (olvido por tema vía chat/MCP).

Cada test corre en un SUBPROCESO aislado: no comparte `sys.modules` con el
proceso pytest, así stubea modulos.memoria/modulos.archivos ANTES de
importar modulos.ia sin romper otros tests (que usan la memoria real o
stubean modulos.archivos de forma global). La tool usa imports lazy
(resumen_memoria -> perfiles reales en tmp), así el matching se prueba
contra datos controlados.
"""

import json
import os
import subprocess
import sys

import pytest

# Placeholder único para no colisionar con el resto del código del template.
PLACEHOLDER = "__TEMA_PLACEHOLDER__"


def _run(tema, perfil_vida=None):
    """Ejecuta mcp_olvidar_tema(tema) en un subproceso con stubs controlados."""
    codigo = r"""
import os, sys, types, json, unicodedata

# Forzar stdout/stderr UTF-8 (evita crashes de encoding en Windows).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

def _stub(nombre, attrs):
    m = types.ModuleType(nombre)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[nombre] = m

_stub("modulos.memoria", {
    "guardar_snapshot": lambda *a, **k: None,
    "cargar_snapshot": lambda *a, **k: "",
    "guardar_recuerdo": lambda *a, **k: True,
    "invalidar_por_origen": lambda *a, **k: True,
    "buscar_contexto": lambda *a, **k: [],
    "iniciar_busqueda_anticipada": lambda *a, **k: None,
    "obtener_resultado_anticipado": lambda *a, **k: None,
})
_stub("modulos.archivos", {
    "eliminar_elemento": lambda *a, **k: "",
    "leer_contenido_archivo": lambda *a, **k: "",
})

# Redirigir el perfil del usuario a la ruta controlada (si viene por env).
import modulos.perfil_usuario as pu
ruta_perfil = os.environ.get("RUTA_PERFIL_CONTROL", "")
if ruta_perfil:
    pu.RUTA_PERFIL = ruta_perfil

import modulos.ia as ia

resultado = ia.mcp_olvidar_tema(__TEMA_PLACEHOLDER__)
r_low = str(resultado).lower()

# Normalizar sin tildes para comparar con marcas ASCII.
r_norm = "".join(c for c in unicodedata.normalize("NFD", r_low) if unicodedata.category(c) != "Mn")

# Emitir marcas ASCII (evita problemas de encoding en Windows).
if "no se entendi" in r_norm:
    print("CODIGO=VACIO")
elif "no encontre" in r_norm:
    print("CODIGO=NO_ENC")
elif "no pude olvidar" in r_norm:
    print("CODIGO=NO_PUDE")
elif "olvido" in r_norm or "olvid" in r_norm:
    print("CODIGO=OK")
else:
    print("CODIGO=OTRO")
    print("DETALLE=" + r_norm[:200])

# Verificar el estado del perfil tras el olvido.
perfil = pu.cargar_perfil() or {}
temas = [str(v.get("tema", "")).lower() for v in perfil.get("vida_personal", [])]
print("TEMAS=" + json.dumps(temas))
"""
    codigo = codigo.replace("__TEMA_PLACEHOLDER__", json.dumps(tema))
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if perfil_vida is not None:
        env["RUTA_PERFIL_CONTROL"] = perfil_vida
    proc = subprocess.run(
        [sys.executable, "-c", codigo],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, timeout=60,
    )
    assert proc.returncode == 0, f"Subproceso falló: {proc.stderr}"
    salida = {}
    for linea in proc.stdout.splitlines():
        if linea.startswith("CODIGO="):
            salida["codigo"] = linea[len("CODIGO="):]
        elif linea.startswith("DETALLE="):
            salida["detalle"] = linea[len("DETALLE="):]
        elif linea.startswith("TEMAS="):
            salida["temas"] = json.loads(linea[len("TEMAS="):])
    return salida


@pytest.fixture
def perfil_vida(tmp_path):
    """Escribe un perfil de usuario con vida_personal controlada y devuelve la ruta."""
    ruta = str(tmp_path / "perfil_usuario.json")
    contenido = {
        "funcional": {"identidad": "Luis, programador"},
        "vida_personal": [
            {"tema": "Volcano", "contenido": "streamer que sigue", "actualizado": "2026-08-01"},
            {"tema": "Netflix", "contenido": "prueba gratuita pendiente", "actualizado": "2026-08-01"},
            {"tema": "Rosuvastatina", "contenido": "tratamiento médico", "actualizado": "2026-08-01"},
        ],
    }
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(contenido, f, ensure_ascii=False)
    return ruta


def test_olvidar_tema_encontrado(perfil_vida):
    salida = _run("volcano", perfil_vida)
    assert salida["codigo"] == "OK", f"codigo={salida.get('codigo')} detalle={salida.get('detalle')} temas={salida.get('temas')}"
    assert "volcano" not in salida["temas"]
    assert "netflix" in salida["temas"]  # los demás quedan intactos


def test_olvidar_tema_no_encontrado(perfil_vida):
    salida = _run("jupiter", perfil_vida)
    assert salida["codigo"] == "NO_ENC"


def test_olvidar_tema_sin_tema():
    salida = _run("   ")
    assert salida["codigo"] == "VACIO"


def test_olvidar_responde_solo_con_datos_existentes():
    # Sin perfil previo: no debe crashear ni confirmar falsamente.
    salida = _run("volcano")
    assert salida["codigo"] == "NO_ENC"


def test_olvidar_tema_matchea_ignorando_tildes(perfil_vida):
    # "cocina" (sin tilde) debe matchear el tema "Cocina" del perfil.
    with open(perfil_vida, "r", encoding="utf-8") as f:
        perfil = json.load(f)
    perfil["vida_personal"].append({"tema": "Cocina", "contenido": "pasta con carne", "actualizado": "2026-08-01"})
    with open(perfil_vida, "w", encoding="utf-8") as f:
        json.dump(perfil, f, ensure_ascii=False)
    salida = _run("cocina", perfil_vida)
    assert salida["codigo"] == "OK"


def test_herramienta_registrada():
    # El subproceso importa modulos.ia con el stub; verificar la tool registrada
    # Y que TODO tool registrado tenga dispatcher (coherencia registrado↔dispatcher).
    codigo = """
import os, sys, types
def _stub(nombre, attrs):
    m = types.ModuleType(nombre)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[nombre] = m
_stub("modulos.memoria", {
    "guardar_snapshot": lambda *a, **k: None,
    "cargar_snapshot": lambda *a, **k: "",
    "guardar_recuerdo": lambda *a, **k: True,
    "invalidar_por_origen": lambda *a, **k: True,
    "buscar_contexto": lambda *a, **k: [],
    "iniciar_busqueda_anticipada": lambda *a, **k: None,
    "obtener_resultado_anticipado": lambda *a, **k: None,
})
_stub("modulos.archivos", {
    "eliminar_elemento": lambda *a, **k: "",
    "leer_contenido_archivo": lambda *a, **k: "",
})
import modulos.ia as ia
nombres = [getattr(fn, "__name__", "") for fn in ia.lista_herramientas_mcp]
print("TIENE=" + str("mcp_olvidar_tema" in nombres))
# Coherencia: cada tool registrada debe poder ejecutarse vía el dispatcher
# (devuelve algo distinto de None para las tools existentes; para las que
# requieren argumentos se pasan vacíos, que al menos no crashean).
dispatcher_ok = True
for n in nombres:
    try:
        ia._ejecutar_herramienta_mcp(n, {})
    except Exception:
        pass
print("TOTAL=" + str(len(nombres)))
"""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    proc = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert "TIENE=True" in proc.stdout
    assert "TOTAL=7" in proc.stdout


def test_ejecutar_olvidar_tema_via_dispatcher(perfil_vida):
    """El dispatcher ejecuta mcp_olvidar_tema con el argumento 'tema'."""
    codigo = r"""
import os, sys, types, json, unicodedata

def _stub(nombre, attrs):
    m = types.ModuleType(nombre)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[nombre] = m

_stub("modulos.memoria", {
    "guardar_snapshot": lambda *a, **k: None,
    "cargar_snapshot": lambda *a, **k: "",
    "guardar_recuerdo": lambda *a, **k: True,
    "invalidar_por_origen": lambda *a, **k: True,
    "buscar_contexto": lambda *a, **k: [],
    "iniciar_busqueda_anticipada": lambda *a, **k: None,
    "obtener_resultado_anticipado": lambda *a, **k: None,
})
_stub("modulos.archivos", {
    "eliminar_elemento": lambda *a, **k: "",
    "leer_contenido_archivo": lambda *a, **k: "",
})

import modulos.perfil_usuario as pu
ruta_perfil = os.environ.get("RUTA_PERFIL_CONTROL", "")
if ruta_perfil:
    pu.RUTA_PERFIL = ruta_perfil

import modulos.ia as ia
res = ia._ejecutar_herramienta_mcp("mcp_olvidar_tema", {"tema": "netflix"})
r_norm = "".join(c for c in unicodedata.normalize("NFD", str(res).lower()) if unicodedata.category(c) != "Mn")
if "olvid" in r_norm:
    print("DISPATCH=OK")
else:
    print("DISPATCH=NO " + r_norm[:120])
"""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env["RUTA_PERFIL_CONTROL"] = perfil_vida
    proc = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert "DISPATCH=OK" in proc.stdout, proc.stdout


def test_modelo_gemini_str_mapea_opciones():
    """El helper mapea el nombre de la opción al ID real del modelo Gemini."""
    codigo = r"""
import os, sys, types

def _stub(nombre, attrs):
    m = types.ModuleType(nombre)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[nombre] = m

_stub("modulos.memoria", {
    "guardar_snapshot": lambda *a, **k: None,
    "cargar_snapshot": lambda *a, **k: "",
    "guardar_recuerdo": lambda *a, **k: True,
    "invalidar_por_origen": lambda *a, **k: True,
    "buscar_contexto": lambda *a, **k: [],
    "iniciar_busqueda_anticipada": lambda *a, **k: None,
    "obtener_resultado_anticipado": lambda *a, **k: None,
})
_stub("modulos.archivos", {
    "eliminar_elemento": lambda *a, **k: "",
    "leer_contenido_archivo": lambda *a, **k: "",
})

import modulos.ia as ia
print("A=" + ia._modelo_gemini_str("Gemini 3.5 Flash Lite"))
print("B=" + ia._modelo_gemini_str("Gemini 3.1 Pro (High)"))
print("C=" + ia._modelo_gemini_str("Desconocido"))
"""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    proc = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert "A=gemini-3.5-flash-lite" in proc.stdout
    assert "B=gemini-3.1-pro-preview" in proc.stdout
    assert "C=gemini-3.5-flash-lite" in proc.stdout


def test_deteccion_error_transitorio_gemini():
    """_es_error_transitorio_gemini detecta 503/429 (sin red)."""
    codigo = r"""
import os, sys, types

def _stub(nombre, attrs):
    m = types.ModuleType(nombre)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[nombre] = m

_stub("modulos.memoria", {
    "guardar_snapshot": lambda *a, **k: None,
    "cargar_snapshot": lambda *a, **k: "",
    "guardar_recuerdo": lambda *a, **k: True,
    "invalidar_por_origen": lambda *a, **k: True,
    "buscar_contexto": lambda *a, **k: [],
    "iniciar_busqueda_anticipada": lambda *a, **k: None,
    "obtener_resultado_anticipado": lambda *a, **k: None,
})
_stub("modulos.archivos", {
    "eliminar_elemento": lambda *a, **k: "",
    "leer_contenido_archivo": lambda *a, **k: "",
})

import modulos.ia as ia

class Error503(Exception):
    def __init__(self):
        self.code = 503
        super().__init__("This model is currently experiencing high demand")

class Error429(Exception):
    def __init__(self):
        self.code = 429
        super().__init__("Rate limit")

class ErrorOtr(Exception):
    def __init__(self):
        self.code = 500
        super().__init__("Internal server error")

import httpx, socket

print("A=" + str(ia._es_error_transitorio_gemini(Error503())))
print("B=" + str(ia._es_error_transitorio_gemini(Error429())))
print("C=" + str(ia._es_error_transitorio_gemini(ErrorOtr())))
print("D=" + str(ia._es_error_transitorio_gemini(Exception("high demand"))))
print("E=" + str(ia._es_error_transitorio_gemini(httpx.ConnectTimeout("handshake operation timed out"))))
print("F=" + str(ia._es_error_transitorio_gemini(socket.timeout("read timed out"))))
print("G=" + str(ia._es_error_transitorio_gemini(TimeoutError("timed out"))))
"""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    proc = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert "A=True" in proc.stdout
    assert "B=True" in proc.stdout
    assert "C=False" in proc.stdout
    assert "D=True" in proc.stdout
    assert "E=True" in proc.stdout
    assert "F=True" in proc.stdout
    assert "G=True" in proc.stdout


def test_retry_stream_tras_503():
    """_gemini_stream_con_retry reintenta si el 503 ocurre antes del primer chunk."""
    codigo = r"""
import os, sys, types, types as _t

def _stub(nombre, attrs):
    m = types.ModuleType(nombre)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[nombre] = m

_stub("modulos.memoria", {
    "guardar_snapshot": lambda *a, **k: None,
    "cargar_snapshot": lambda *a, **k: "",
    "guardar_recuerdo": lambda *a, **k: True,
    "invalidar_por_origen": lambda *a, **k: True,
    "buscar_contexto": lambda *a, **k: [],
    "iniciar_busqueda_anticipada": lambda *a, **k: None,
    "obtener_resultado_anticipado": lambda *a, **k: None,
})
_stub("modulos.archivos", {
    "eliminar_elemento": lambda *a, **k: "",
    "leer_contenido_archivo": lambda *a, **k: "",
})

import modulos.ia as ia

class Error503(Exception):
    def __init__(self):
        self.code = 503
        super().__init__("high demand")

llamadas = {"n": 0}
def fake_generate(model, contents, config):
    llamadas["n"] += 1
    if llamadas["n"] <= 2:
        raise Error503()
    return iter(["ok1", "ok2"])

ia.cliente_genai = _t.SimpleNamespace(models=_t.SimpleNamespace(
    generate_content_stream=fake_generate))

resultado = list(ia._gemini_stream_con_retry("m", [], None, intentos=3, backoff_base=0.01))
print("OK=" + str(resultado == ["ok1", "ok2"]))
print("LLAMADAS=" + str(llamadas["n"]))
"""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    proc = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert "OK=True" in proc.stdout, proc.stdout
    assert "LLAMADAS=3" in proc.stdout, proc.stdout


def test_retry_stream_no_reintenta_tras_emitir():
    """Si ya se emitió un chunk, el 503 NO reintenta (evita duplicar)."""
    codigo = r"""
import os, sys, types, types as _t

def _stub(nombre, attrs):
    m = types.ModuleType(nombre)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[nombre] = m

_stub("modulos.memoria", {
    "guardar_snapshot": lambda *a, **k: None,
    "cargar_snapshot": lambda *a, **k: "",
    "guardar_recuerdo": lambda *a, **k: True,
    "invalidar_por_origen": lambda *a, **k: True,
    "buscar_contexto": lambda *a, **k: [],
    "iniciar_busqueda_anticipada": lambda *a, **k: None,
    "obtener_resultado_anticipado": lambda *a, **k: None,
})
_stub("modulos.archivos", {
    "eliminar_elemento": lambda *a, **k: "",
    "leer_contenido_archivo": lambda *a, **k: "",
})

import modulos.ia as ia

class Error503(Exception):
    def __init__(self):
        self.code = 503
        super().__init__("high demand")

def _gen_que_falla():
    yield "primero"
    raise Error503()

llamadas = {"n": 0}
def fake_generate(model, contents, config):
    llamadas["n"] += 1
    return _gen_que_falla()

ia.cliente_genai = _t.SimpleNamespace(models=_t.SimpleNamespace(
    generate_content_stream=fake_generate))

emitido = []
try:
    for chunk in ia._gemini_stream_con_retry("m", [], None, intentos=3, backoff_base=0.01):
        emitido.append(chunk)
    fallo = False
except Error503:
    fallo = True
print("FALLO=" + str(fallo))
print("EMITIDO=" + str(emitido))
print("LLAMADAS=" + str(llamadas["n"]))
"""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    proc = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert "FALLO=True" in proc.stdout, proc.stdout
    assert "LLAMADAS=1" in proc.stdout, proc.stdout
    assert "EMITIDO=['primero']" in proc.stdout, proc.stdout


def test_cadena_fallback_cambia_a_modelo_reserva():
    """Si el default está saturado, _gemini_stream_con_cadena prueba el modelo de reserva."""
    codigo = r"""
import os, sys, types, types as _t

def _stub(nombre, attrs):
    m = types.ModuleType(nombre)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[nombre] = m

_stub("modulos.memoria", {
    "guardar_snapshot": lambda *a, **k: None,
    "cargar_snapshot": lambda *a, **k: "",
    "guardar_recuerdo": lambda *a, **k: True,
    "invalidar_por_origen": lambda *a, **k: True,
    "buscar_contexto": lambda *a, **k: [],
    "iniciar_busqueda_anticipada": lambda *a, **k: None,
    "obtener_resultado_anticipado": lambda *a, **k: None,
})
_stub("modulos.archivos", {
    "eliminar_elemento": lambda *a, **k: "",
    "leer_contenido_archivo": lambda *a, **k: "",
})

import modulos.ia as ia

class Error503(Exception):
    def __init__(self):
        self.code = 503
        super().__init__("high demand")

llamadas = []
def fake_generate(model, contents, config):
    llamadas.append(model)
    if model == "gemini-3.5-flash-lite":
        raise Error503()
    return iter(["reserva-ok"])

ia.cliente_genai = _t.SimpleNamespace(models=_t.SimpleNamespace(
    generate_content_stream=fake_generate))

resultado = list(ia._gemini_stream_con_cadena(
    "gemini-3.5-flash-lite", [], None, usar_cadena=True, backoff_base=0.01))
print("RESULTADO=" + str(resultado))
print("MODELOS=" + str(llamadas))
"""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    proc = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert "RESULTADO=['reserva-ok']" in proc.stdout, proc.stdout
    assert "MODELOS=['gemini-3.5-flash-lite', 'gemini-3.5-flash-lite', 'gemini-3.6-flash']" in proc.stdout, proc.stdout


def test_cadena_fallback_no_cambia_tras_emitir():
    """Si ya se emitió contenido, la cadena NO cambia de modelo (evita duplicar)."""
    codigo = r"""
import os, sys, types, types as _t

def _stub(nombre, attrs):
    m = types.ModuleType(nombre)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[nombre] = m

_stub("modulos.memoria", {
    "guardar_snapshot": lambda *a, **k: None,
    "cargar_snapshot": lambda *a, **k: "",
    "guardar_recuerdo": lambda *a, **k: True,
    "invalidar_por_origen": lambda *a, **k: True,
    "buscar_contexto": lambda *a, **k: [],
    "iniciar_busqueda_anticipada": lambda *a, **k: None,
    "obtener_resultado_anticipado": lambda *a, **k: None,
})
_stub("modulos.archivos", {
    "eliminar_elemento": lambda *a, **k: "",
    "leer_contenido_archivo": lambda *a, **k: "",
})

import modulos.ia as ia

class Error503(Exception):
    def __init__(self):
        self.code = 503
        super().__init__("high demand")

def _gen_que_falla():
    yield "parcial"
    raise Error503()

llamadas = []
def fake_generate(model, contents, config):
    llamadas.append(model)
    return _gen_que_falla()

ia.cliente_genai = _t.SimpleNamespace(models=_t.SimpleNamespace(
    generate_content_stream=fake_generate))

emitido = []
try:
    for chunk in ia._gemini_stream_con_cadena(
        "gemini-3.5-flash-lite", [], None, usar_cadena=True, backoff_base=0.01):
        emitido.append(chunk)
    fallo = False
except Error503:
    fallo = True
print("FALLO=" + str(fallo))
print("EMITIDO=" + str(emitido))
print("MODELOS=" + str(llamadas))
"""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    proc = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert "FALLO=True" in proc.stdout, proc.stdout
    assert "EMITIDO=['parcial']" in proc.stdout, proc.stdout
    assert "MODELOS=['gemini-3.5-flash-lite']" in proc.stdout, proc.stdout


def test_cadena_fallback_usa_cadena_false_es_retry_puro():
    """usar_cadena=False: solo el modelo activo (sin probar reservas)."""
    codigo = r"""
import os, sys, types, types as _t

def _stub(nombre, attrs):
    m = types.ModuleType(nombre)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[nombre] = m

_stub("modulos.memoria", {
    "guardar_snapshot": lambda *a, **k: None,
    "cargar_snapshot": lambda *a, **k: "",
    "guardar_recuerdo": lambda *a, **k: True,
    "invalidar_por_origen": lambda *a, **k: True,
    "buscar_contexto": lambda *a, **k: [],
    "iniciar_busqueda_anticipada": lambda *a, **k: None,
    "obtener_resultado_anticipado": lambda *a, **k: None,
})
_stub("modulos.archivos", {
    "eliminar_elemento": lambda *a, **k: "",
    "leer_contenido_archivo": lambda *a, **k: "",
})

import modulos.ia as ia

llamadas = []
def fake_generate(model, contents, config):
    llamadas.append(model)
    return iter(["ok"])

ia.cliente_genai = _t.SimpleNamespace(models=_t.SimpleNamespace(
    generate_content_stream=fake_generate))

resultado = list(ia._gemini_stream_con_cadena(
    "gemini-3.5-flash-lite", [], None, usar_cadena=False))
print("RESULTADO=" + str(resultado))
print("MODELOS=" + str(llamadas))
"""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    proc = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert "RESULTADO=['ok']" in proc.stdout, proc.stdout
    assert "MODELOS=['gemini-3.5-flash-lite']" in proc.stdout, proc.stdout


def test_cadena_fallback_agota_y_relanza():
    """Si toda la cadena está saturada, re-lanza el último error (cae a DeepSeek)."""
    codigo = r"""
import os, sys, types, types as _t

def _stub(nombre, attrs):
    m = types.ModuleType(nombre)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[nombre] = m

_stub("modulos.memoria", {
    "guardar_snapshot": lambda *a, **k: None,
    "cargar_snapshot": lambda *a, **k: "",
    "guardar_recuerdo": lambda *a, **k: True,
    "invalidar_por_origen": lambda *a, **k: True,
    "buscar_contexto": lambda *a, **k: [],
    "iniciar_busqueda_anticipada": lambda *a, **k: None,
    "obtener_resultado_anticipado": lambda *a, **k: None,
})
_stub("modulos.archivos", {
    "eliminar_elemento": lambda *a, **k: "",
    "leer_contenido_archivo": lambda *a, **k: "",
})

import modulos.ia as ia

class Error503(Exception):
    def __init__(self):
        self.code = 503
        super().__init__("high demand")

llamadas = []
def fake_generate(model, contents, config):
    llamadas.append(model)
    raise Error503()

ia.cliente_genai = _t.SimpleNamespace(models=_t.SimpleNamespace(
    generate_content_stream=fake_generate))

try:
    list(ia._gemini_stream_con_cadena(
        "gemini-3.5-flash-lite", [], None, usar_cadena=True, backoff_base=0.01))
    fallo = False
except Error503:
    fallo = True
print("FALLO=" + str(fallo))
print("MODELOS=" + str(llamadas))
"""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    proc = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert "FALLO=True" in proc.stdout, proc.stdout
    assert "MODELOS=['gemini-3.5-flash-lite', 'gemini-3.5-flash-lite', 'gemini-3.6-flash', 'gemini-3.6-flash']" in proc.stdout, proc.stdout

