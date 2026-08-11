"""
Tests de integración de la fase "Coherencia de la memoria" (tombstones).

Verifican el flujo completo olvidar → extracción bloqueada → editar →
reintroducir → volver a olvidar, usando las mismas rutas temporales y
monkeypatch que el resto de la suite (nunca se tocan perfiles reales).

También cubren la garantía determinista post-IA:
- consolidar_perfil re-aplica _olvidar_en_perfil aunque el modelo reintroduzca
  un dato vedado (se stubea modulos.ia con un cliente_genai falso).
- extraer_y_procesar_sesion_mentor filtra el perfil reconstruido completo.

Ninguna prueba requiere API keys ni ChromaDB real.
"""

import json
import sys
import types
import datetime

import pytest

from modulos import olvidos
from modulos import resumen_memoria as rm
from modulos import perfil_usuario as pu
from modulos import perfil_mentor as pm
from modulos import perfil_gamer as pg


HOY = datetime.date.today().strftime("%Y-%m-%d")


def _escribir(ruta, datos):
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)


def _leer(ruta):
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def _perfil_usuario_inicial():
    return {
        "funcional": {
            "identidad": "Luis",
            "proyecto_actual": "OmniAssistant",
            "hardware_relevante": "",
            "preferencias_comunicacion": "Directo",
            "rutina_uso": "Noche",
        },
        "vida_personal": [
            {"tema": "salud", "contenido": "Toma rosuvastatina", "actualizado": HOY},
        ],
    }


def _perfil_mentor_inicial():
    return {
        "stack_objetivo": {
            "frontend": "React",
            "backend": "Python",
            "bases_de_datos": "PostgreSQL",
            "otras_herramientas": ["Docker"],
        },
        "tecnologias_aprendidas": ["Python"],
        "tecnologias_en_estudio": [],
        "proyectos_de_portafolio": [],
        "ultimo_avance_registrado": "Ninguno",
        "historial_sesiones": [],
        "claves_de_contexto_faltantes": [],
    }


def _perfil_gamer_inicial():
    return {
        "juego_activo": "Grim Dawn",
        "juegos": {
            "Grim Dawn": {"personaje": "Hechicero", "nivel": "45", "ultima_sesion": HOY},
        },
    }


@pytest.fixture
def olvidos_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(olvidos, "RUTA_OLVIDOS", str(tmp_path / "olvidos.json"))
    return tmp_path


@pytest.fixture
def perfil_usuario_tmp(tmp_path, monkeypatch):
    ruta = tmp_path / "perfil_usuario.json"
    monkeypatch.setattr(pu, "RUTA_PERFIL", str(ruta))
    return ruta


@pytest.fixture
def perfil_mentor_tmp(tmp_path, monkeypatch):
    ruta = tmp_path / "perfil_mentor.json"
    monkeypatch.setattr(pm, "RUTA_PERFIL_MENTOR", str(ruta))
    return ruta


@pytest.fixture
def perfil_gamer_tmp(tmp_path, monkeypatch):
    ruta = tmp_path / "perfil_gamer.json"
    monkeypatch.setattr(pg, "RUTA_PERFIL_GAMER", str(ruta))
    return ruta


# ── Stub de modulos.ia (cliente_genai falso) para pruebas post-IA ────────────

class _RespuestaFalsa:
    def __init__(self, texto):
        self._texto = texto

    @property
    def text(self):
        return self._texto


class _ModelosFalsos:
    def __init__(self, respuesta=""):
        self._respuesta = respuesta
        self.llamadas = []

    def generate_content(self, *args, **kwargs):
        self.llamadas.append(kwargs)
        return _RespuestaFalsa(self._respuesta)


class _ClienteFalso:
    def __init__(self, respuesta=""):
        self.models = _ModelosFalsos(respuesta)


def _stub_ia(monkeypatch, respuesta_json):
    """Reemplaza modulos.ia por un módulo falso con cliente_genai stubbeado."""
    cliente = _ClienteFalso(respuesta_json)
    m = types.ModuleType("modulos.ia")
    m.cliente_genai = cliente
    m.respuesta = respuesta_json
    monkeypatch.setitem(sys.modules, "modulos.ia", m)
    return cliente


# ── Flujo completo: olvidar → registrar → editar → reintroducir ─────────────

def test_olvidar_registra_tombstone(perfil_usuario_tmp, olvidos_tmp):
    _escribir(perfil_usuario_tmp, _perfil_usuario_inicial())
    assert olvidos.esta_olvidado("vida:salud") is False
    assert rm.resolver_olvidar("vida:salud")["exito"] is True
    assert olvidos.esta_olvidado("vida:salud") is True
    assert _leer(perfil_usuario_tmp)["vida_personal"] == []


def test_olvidar_fallido_NO_registra_tombstone(perfil_usuario_tmp, olvidos_tmp):
    _escribir(perfil_usuario_tmp, _perfil_usuario_inicial())
    assert rm.resolver_olvidar("vida:deporte")["exito"] is False
    assert olvidos.esta_olvidado("vida:deporte") is False
    assert olvidos.obtener_ids_olvidados() == set()


def test_editar_quita_tombstone(perfil_usuario_tmp, olvidos_tmp):
    _escribir(perfil_usuario_tmp, _perfil_usuario_inicial())
    olvidos.registrar_olvido("vida:salud")
    assert olvidos.esta_olvidado("vida:salud") is True
    assert rm.resolver_editar("vida:salud", "Dejó la medicación")["exito"] is True
    assert olvidos.esta_olvidado("vida:salud") is False
    assert _leer(perfil_usuario_tmp)["vida_personal"][0]["contenido"] == "Dejó la medicación"


def test_editar_fallido_NO_quita_tombstone(perfil_usuario_tmp, olvidos_tmp):
    _escribir(perfil_usuario_tmp, _perfil_usuario_inicial())
    olvidos.registrar_olvido("vida:mascotas")
    assert rm.resolver_editar("vida:mascotas", "Tiene un perro")["exito"] is False
    assert olvidos.esta_olvidado("vida:mascotas") is True


# ── Filtro determinista en la extracción (rutear_hecho) ──────────────────────

def test_rutear_hecho_descarta_vida_olvidada(perfil_usuario_tmp, olvidos_tmp):
    # Perfil con vida_personal VACÍO: el filtro no puede agregar el tema vedado.
    _escribir(perfil_usuario_tmp, {
        "funcional": {clave: "" for clave in pu.ESQUEMA_FUNCIONAL_CLAVES},
        "vida_personal": [],
    })
    olvidos.registrar_olvido("vida:salud")
    perfil = pu.cargar_perfil()
    hecho = {"tipo": "perfil_vida", "clave_o_tema": "salud",
             "valor": "Empezó a correr", "importancia": 80}
    resultado = pu.rutear_hecho(hecho, perfil)
    assert resultado["vida_personal"] == []  # no reintrodujo


def test_rutear_hecho_permite_tema_no_olvidado(perfil_usuario_tmp, olvidos_tmp):
    _escribir(perfil_usuario_tmp, {
        "funcional": {clave: "" for clave in pu.ESQUEMA_FUNCIONAL_CLAVES},
        "vida_personal": [],
    })
    olvidos.registrar_olvido("vida:salud")
    perfil = pu.cargar_perfil()
    hecho = {"tipo": "perfil_vida", "clave_o_tema": "deporte",
             "valor": "Empezó a correr", "importancia": 80}
    resultado = pu.rutear_hecho(hecho, perfil)
    assert resultado["vida_personal"][0]["tema"] == "deporte"


def test_rutear_hecho_descarta_funcional_olvidada(perfil_usuario_tmp, olvidos_tmp):
    _escribir(perfil_usuario_tmp, _perfil_usuario_inicial())
    olvidos.registrar_olvido("funcional:rutina_uso")
    perfil = pu.cargar_perfil()
    hecho = {"tipo": "perfil_funcional", "clave_o_tema": "rutina_uso",
             "valor": "Mañana", "importancia": 80}
    resultado = pu.rutear_hecho(hecho, perfil)
    assert resultado["funcional"]["rutina_uso"] == "Noche"  # sin cambios


def test_rutear_hecho_gamer_descarta_juego_olvidado(perfil_gamer_tmp, olvidos_tmp):
    # El perfil empieza sin el juego: el filtro debe impedir que la IA lo cree.
    _escribir(perfil_gamer_tmp, {"juego_activo": "", "juegos": {}})
    olvidos.registrar_olvido("gamer:grim_dawn")
    perfil = pg.cargar_perfil_gamer()
    hecho = {"juego": "Grim Dawn", "campo": "personaje", "valor": "Caballero"}
    resultado = pg.rutear_hecho_gamer(hecho, perfil)
    assert "Grim Dawn" not in resultado["juegos"]
    assert resultado["juego_activo"] == ""  # el juego olvidado no puede activarse


def test_rutear_hecho_gamer_descarta_juego_activo_olvidado(perfil_gamer_tmp, olvidos_tmp):
    _escribir(perfil_gamer_tmp, _perfil_gamer_inicial())
    olvidos.registrar_olvido("gamer:juego_activo")
    perfil = pg.cargar_perfil_gamer()
    hecho = {"juego": "", "campo": "juego_activo", "valor": "Zelda"}
    resultado = pg.rutear_hecho_gamer(hecho, perfil)
    assert resultado["juego_activo"] == "Grim Dawn"  # sin cambios


def test_extraccion_no_reintroduce_tras_olvidar(perfil_usuario_tmp, olvidos_tmp):
    """Escenario end-to-end: olvidar hoy → la próxima extracción no lo repone."""
    _escribir(perfil_usuario_tmp, _perfil_usuario_inicial())
    rm.resolver_olvidar("vida:salud")
    perfil = pu.cargar_perfil()
    hecho = {"tipo": "perfil_vida", "clave_o_tema": "salud",
             "valor": "Recuerda esto otra vez", "importancia": 90}
    resultado = pu.rutear_hecho(hecho, perfil)
    assert resultado["vida_personal"] == []


def test_editar_y_reintroducir(perfil_usuario_tmp, olvidos_tmp):
    """Tras editar (desbloquear), la extracción vuelve a poder introducir."""
    _escribir(perfil_usuario_tmp, _perfil_usuario_inicial())
    # Tombstone presente (dato vedado) aunque la entrada siga en el perfil.
    olvidos.registrar_olvido("vida:salud")
    # Editar quita el tombstone: el dato deja de estar vedado.
    assert rm.resolver_editar("vida:salud", "Corregido por el usuario")["exito"] is True
    assert olvidos.esta_olvidado("vida:salud") is False
    perfil = pu.cargar_perfil()
    hecho = {"tipo": "perfil_vida", "clave_o_tema": "salud",
             "valor": "Nueva información", "importancia": 80}
    resultado = pu.rutear_hecho(hecho, perfil)
    assert resultado["vida_personal"][0]["contenido"] == "Nueva información"


# ── Garantía determinista post-IA (consolidación) ────────────────────────────

def test_consolidar_no_reintroduce_olvidado(perfil_usuario_tmp, olvidos_tmp, monkeypatch):
    """Aunque el modelo reintroduzca el tema vedado, _olvidar_en_perfil lo elimina."""
    _escribir(perfil_usuario_tmp, _perfil_usuario_inicial())
    olvidos.registrar_olvido("vida:salud")
    olvidos.registrar_olvido("funcional:rutina_uso")

    # El modelo devuelve un perfil que REINTRODUCE los datos olvidados.
    perfil_mal_consolidado = {
        "funcional": {
            "identidad": "Luis", "proyecto_actual": "OmniAssistant",
            "hardware_relevante": "", "preferencias_comunicacion": "Directo",
            "rutina_uso": "Temprano",
        },
        "vida_personal": [
            {"tema": "salud", "contenido": "resucitado", "actualizado": HOY},
            {"tema": "mascotas", "contenido": "Tiene un perro", "actualizado": HOY},
        ],
    }
    _stub_ia(monkeypatch, json.dumps(perfil_mal_consolidado))

    perfil = pu.cargar_perfil()
    resultado = pu.consolidar_perfil(perfil)
    temas = [e["tema"] for e in resultado["vida_personal"]]
    assert "salud" not in temas          # vedado eliminado
    assert "mascotas" in temas           # lo demás se conserva
    assert resultado["funcional"]["rutina_uso"] == ""  # clave vedada vaciada


def test_consolidar_prompt_menciona_bloqueados(perfil_usuario_tmp, olvidos_tmp, monkeypatch):
    """Segunda barrera: el prompt de consolidación anuncia los temas vedados."""
    _escribir(perfil_usuario_tmp, _perfil_usuario_inicial())
    olvidos.registrar_olvido("vida:salud")
    _stub_ia(monkeypatch, json.dumps(_perfil_usuario_inicial()))
    pu.consolidar_perfil(pu.cargar_perfil())
    cliente = sys.modules["modulos.ia"].cliente_genai
    prompt = cliente.models.llamadas[-1]["contents"]
    assert "salud" in prompt
    assert "OLVIDAR" in prompt


# ── Garantía determinista post-IA (mentor, perfil completo) ──────────────────

def test_mentor_extraccion_no_reintroduce_olvidado(perfil_mentor_tmp, olvidos_tmp, monkeypatch):
    """El LLM reconstruye el perfil entero; el filtro post-IA restaura lo vedado."""
    _escribir(perfil_mentor_tmp, _perfil_mentor_inicial())
    olvidos.registrar_olvido("mentor:stack_backend")

    perfil_con_reintroduccion = _perfil_mentor_inicial()
    perfil_con_reintroduccion["stack_objetivo"]["backend"] = "Go"  # reintroducido
    _stub_ia(monkeypatch, json.dumps(perfil_con_reintroduccion))

    mensajes = [{"role": "user", "parts": ["Menciono que uso Go"]}]
    pm.extraer_y_procesar_sesion_mentor(mensajes, workspace_path="")

    perfil_guardado = _leer(perfil_mentor_tmp)
    assert perfil_guardado["stack_objetivo"]["backend"] == "Pendiente de definir"
    assert perfil_guardado["stack_objetivo"]["frontend"] == "React"


def test_mentor_olvidar_todo_el_stack_no_reaparece(perfil_mentor_tmp, olvidos_tmp, monkeypatch):
    _escribir(perfil_mentor_tmp, _perfil_mentor_inicial())
    olvidos.registrar_olvido("mentor:stack_backend")
    olvidos.registrar_olvido("mentor:stack_frontend")

    perfil_con_reintroduccion = _perfil_mentor_inicial()
    perfil_con_reintroduccion["stack_objetivo"]["backend"] = "Go"
    perfil_con_reintroduccion["stack_objetivo"]["frontend"] = "Vue"
    _stub_ia(monkeypatch, json.dumps(perfil_con_reintroduccion))

    mensajes = [{"role": "user", "parts": ["Avanzo con Go y Vue"]}]
    pm.extraer_y_procesar_sesion_mentor(mensajes, workspace_path="")

    perfil_guardado = _leer(perfil_mentor_tmp)
    assert perfil_guardado["stack_objetivo"]["backend"] == "Pendiente de definir"
    assert perfil_guardado["stack_objetivo"]["frontend"] == "Pendiente de definir"


def test_mentor_filtro_respeta_dato_no_olvidado(perfil_mentor_tmp, olvidos_tmp, monkeypatch):
    _escribir(perfil_mentor_tmp, _perfil_mentor_inicial())
    olvidos.registrar_olvido("mentor:stack_backend")

    perfil_con_reintroduccion = _perfil_mentor_inicial()
    perfil_con_reintroduccion["stack_objetivo"]["backend"] = "Go"
    perfil_con_reintroduccion["tecnologias_aprendidas"] = ["Python", "FastAPI"]
    _stub_ia(monkeypatch, json.dumps(perfil_con_reintroduccion))

    mensajes = [{"role": "user", "parts": ["Aprendí FastAPI"]}]
    pm.extraer_y_procesar_sesion_mentor(mensajes, workspace_path="")

    perfil_guardado = _leer(perfil_mentor_tmp)
    assert perfil_guardado["stack_objetivo"]["backend"] == "Pendiente de definir"
    assert perfil_guardado["tecnologias_aprendidas"] == ["Python", "FastAPI"]