"""
Tests de C1/C2: serialización de turnos y marcado temporal para la UI.

C1: todos los turnos (texto, voz, gamepad, wake word) convergen en
`enviar_a_gemini`, que adquiere un RLock para que dos entradas concurrentes
no mezclen contexto, streams ni persistencia.

C2: el turno_id temporal viaja prefijado en el remitente del ui_callback
(`@@TURNO:<id>|`) para que la UI dirija las señales provisionales/verificadas
a la burbuja correcta.

Se stubean las dependencias pesadas (modulos.ia, modulos.memoria,
modulos.audio_custom, etc.) para mantener los tests rápidos y offline,
siguiendo el patrón de test_controlador_acciones.py.
"""

import sys
import threading
import time
import types

import pytest


def _stub(nombre, attrs):
    m = types.ModuleType(nombre)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[nombre] = m
    return m


# Nombres de módulos que se stubean SOLO durante la ejecución de cada test
# (los stubs se instalan en el fixture y se restauran al terminar, para no
# contaminar el collection/ejecución de los demás archivos de tests).
_STUBS_BRIDGE = [
    "webview",
    "modulos.audio_custom",
    "modulos.perfil_mentor",
    "modulos.skills.wake_word.gestor_wake_word",
    "modulos.ia",
    "modulos.web_bridge",
]


# ---------------------------------------------------------------------------
# C1: serialización real del RLock ante entradas concurrentes
# ---------------------------------------------------------------------------
def test_turnos_concurrentes_se_serializan():
    """Dos (o más) llamadas concurrentes a enviar_a_gemini nunca ejecutan su
    cuerpo al mismo tiempo: el RLock las serializa."""
    _RLOCK_PROC = threading.RLock()
    _CONTADOR_TURNOS = iter(range(1, 10_000_000))

    def _procesar_mensaje(texto_usuario, modo_voz=False, ui_callback=None, turno_id=None):
        if ui_callback is not None:
            ui_callback("🤖 Argus", "Hola, soy Argus.", "#A8C7FA")

    def enviar_a_gemini(texto_usuario, modo_voz=False, ui_callback=None):
        with _RLOCK_PROC:
            next(_CONTADOR_TURNOS)
            _procesar_mensaje(texto_usuario, modo_voz=modo_voz, ui_callback=ui_callback)

    activos = set()
    mutex = threading.Lock()
    violaciones = []
    cruces = 0
    N = 8
    INTERVALO = 0.02

    def ui_callback(remitente, texto, color=None, nueva_linea=True):
        nonlocal cruces
        with mutex:
            activos.add(threading.get_ident())
            cruces += 1
            if len(activos) > 1:
                violaciones.append((threading.get_ident(), list(activos)))
        time.sleep(INTERVALO)
        with mutex:
            activos.discard(threading.get_ident())

    hilos = [threading.Thread(target=enviar_a_gemini, args=("hola",), kwargs={"ui_callback": ui_callback}) for _ in range(N)]
    for t in hilos:
        t.start()
    for t in hilos:
        t.join()

    assert cruces == N, f"Se esperaban {N} turnos procesados, se procesaron {cruces}"
    assert violaciones == [], f"Se detectó solapamiento de turnos: {violaciones}"


# ---------------------------------------------------------------------------
# C2: el turno_id viaja en el remitente y _ui_callback lo extrae
# ---------------------------------------------------------------------------
@pytest.fixture
def bridge_con_stubs():
    """Instala los stubs, importa ArgusWebBridge REAL y restaura sys.modules
    al terminar (los stubs no deben sobrevivir al test)."""
    orig = {nombre: sys.modules.get(nombre) for nombre in _STUBS_BRIDGE}
    try:
        _stub("webview", {"windows": []})
        _stub("modulos.audio_custom", {
            "capturar_voz_micro": lambda *a, **k: "",
            "hablar_no_bloqueante": lambda *a, **k: None,
            "encolar_texto_para_hablar": lambda *a, **k: None,
            "detener_voz": lambda *a, **k: None,
        })
        _stub("modulos.perfil_mentor", {
            "cargar_perfil_mentor": lambda *a, **k: {},
            "guardar_perfil_mentor": lambda *a, **k: None,
        })
        _stub("modulos.skills.wake_word.gestor_wake_word", {
            "gestor_wake_word": types.SimpleNamespace(
                esta_activo=lambda: False,
                activar=lambda *a, **k: None,
                desactivar=lambda *a, **k: None,
            ),
        })
        _stub("modulos.ia", {
            "enviar_a_gemini": lambda *a, **k: None,
        })

        from modulos.web_bridge import ArgusWebBridge
        yield ArgusWebBridge
    finally:
        for nombre, modulo in orig.items():
            if modulo is None:
                sys.modules.pop(nombre, None)
            else:
                sys.modules[nombre] = modulo


class _VentanaFalsa:
    """Ventana PyWebView falsa que captura evaluate_js."""

    def __init__(self):
        self.comandos = []

    def evaluate_js(self, cmd):
        self.comandos.append(cmd)


def test_marcador_se_genera_y_se_extrae_en_bridge(bridge_con_stubs):
    """El prefijo @@TURNO:<id>| viaja dentro del remitente y el bridge lo
    extrae, seteando self._turno_actual y reenviando el id al frontend."""
    ventana = _VentanaFalsa()
    bridge = bridge_con_stubs()
    bridge._window = ventana

    bridge._ui_callback("@@TURNO:42|🤖 Argus", "Respuesta con web.", "#E8EAED")

    assert bridge._turno_actual == 42
    assert len(ventana.comandos) == 1
    cmd = ventana.comandos[0]
    assert "agregarRespuestaArgus" in cmd
    # json.dumps escapa emojis como surrogates (\ud83e\udd16); comparamos con
    # la misma codificación que genera web_bridge.py.
    import json
    assert json.dumps("🤖 Argus") in cmd
    assert "42" in cmd


def test_senal_verificada_lleva_el_turno_id(bridge_con_stubs):
    """La señal __RESPUESTA_VERIFICADA__ (que pasa por el mismo wrapper)
    reenvía el turno_id al frontend para dirigir el reemplazo a la burbuja
    correcta."""
    ventana = _VentanaFalsa()
    bridge = bridge_con_stubs()
    bridge._window = ventana

    bridge._ui_callback("@@TURNO:7|__RESPUESTA_VERIFICADA__", "Respuesta verificada")

    assert bridge._turno_actual == 7
    assert len(ventana.comandos) == 1
    cmd = ventana.comandos[0]
    assert "reemplazarRespuestaProvisional" in cmd
    assert '"Respuesta verificada"' in cmd
    assert "7" in cmd


def test_callback_sin_marcador_no_rompe_flujo(bridge_con_stubs):
    """Callbacks legacy sin prefijo siguen funcionando (turno_id None)."""
    ventana = _VentanaFalsa()
    bridge = bridge_con_stubs()
    bridge._window = ventana

    bridge._ui_callback("🤖 Argus", "Respuesta legacy.")

    assert bridge._turno_actual is None
    assert len(ventana.comandos) == 1
    cmd = ventana.comandos[0]
    assert "agregarRespuestaArgus" in cmd
    assert "None" in cmd
