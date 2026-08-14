"""
Tests de la mentoría multitema (Fase 5, multitema tema → sesión → avance).

Cubren:
1. Migración v1 → v2 (registro de temas + espejo legacy del tema activo).
2. API de temas (listar / cambiar / crear / resolver por conversación).
3. Olvido de un tema completo (id `mentor:tema:<slug>`).
4. Procesamiento de eventos scoped por tema (progreso_mentoria).
5. Reescritor de sesión que preserva temas/tema_activo/progreso.

Offline: se stubean modulos.ia y modulos.memoria (dependencias pesadas),
igual que en test_progreso_mentoria / test_controlador_acciones.
"""

import sys
import types
import json
import datetime

import pytest

from modulos import perfil_mentor as pm
from modulos import resumen_memoria as rm
from modulos import progreso_mentoria as pme


def _stub(nombre, attrs):
    m = types.ModuleType(nombre)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[nombre] = m
    return m


class _RespFalsa:
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
        self.llamadas.append((args, kwargs))
        return _RespFalsa(self._respuesta)


class _ClienteFalso:
    def __init__(self, respuesta=""):
        self.models = _ModelosFalsos(respuesta)


_BOVEDA_MOD = _stub("modulos.memoria", {})


def _stub_ia(respuesta_json=""):
    m = types.ModuleType("modulos.ia")
    m.cliente_genai = _ClienteFalso(respuesta_json)
    sys.modules["modulos.ia"] = m
    return m


def _escribir(ruta, datos):
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)


def _leer(ruta):
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


HOY = datetime.date.today().strftime("%Y-%m-%d")


def _perfil_v1():
    """Perfil legado (v1): solo campos de nivel superior."""
    return {
        "stack_objetivo": {
            "frontend": "React",
            "backend": "Python",
            "bases_de_datos": "PostgreSQL",
            "otras_herramientas": ["Docker"],
        },
        "tecnologias_aprendidas": ["Python", "FastAPI"],
        "tecnologias_en_estudio": ["LangChain"],
        "proyectos_de_portafolio": [
            {"nombre": "App Gimn", "descripcion": "App de gimnasio"},
        ],
        "ultimo_avance_registrado": "Armó un RAG",
        "historial_sesiones": [{"fecha": HOY, "proximos_pasos": ["Hacer deploy"]}],
        "claves_de_contexto_faltantes": [],
        "progreso": {"objetivos": [{"titulo": "Aprender FastAPI", "estado": "activo"}]},
    }


@pytest.fixture(autouse=True)
def _stubs_modulos():
    _stub_ia()
    sys.modules["modulos.memoria"] = _BOVEDA_MOD
    yield


@pytest.fixture
def perfil_mentor_tmp(tmp_path, monkeypatch):
    ruta = tmp_path / "perfil_mentor.json"
    monkeypatch.setattr(pm, "RUTA_PERFIL_MENTOR", str(ruta))
    return ruta


# ── 1. Migración v1 → v2 y espejo legacy ────────────────────────────────────

def test_migracion_v1_a_v2_conserva_espejo(perfil_mentor_tmp):
    _escribir(perfil_mentor_tmp, _perfil_v1())
    perfil = pm.cargar_perfil_mentor()
    # Registro de temas creado con el tema de desarrollo como activo.
    assert perfil["meta"]["version"] == 2
    assert perfil["tema_activo"] == pm.SLUG_TEMA_DESARROLLO
    assert isinstance(perfil["temas"], dict)
    assert pm.SLUG_TEMA_DESARROLLO in perfil["temas"]
    # El espejo legacy conserva los datos v1.
    assert perfil["stack_objetivo"]["backend"] == "Python"
    assert perfil["progreso"]["objetivos"][0]["titulo"] == "Aprender FastAPI"
    assert perfil["historial_sesiones"][0]["fecha"] == HOY
    # Y el tema de desarrollo absorbe el estado v1.
    tema = perfil["temas"][pm.SLUG_TEMA_DESARROLLO]
    assert tema["contexto"]["stack_objetivo"]["backend"] == "Python"
    assert tema["progreso"]["objetivos"][0]["titulo"] == "Aprender FastAPI"


def test_guardar_sincroniza_espejo_dentro_del_tema(perfil_mentor_tmp):
    _escribir(perfil_mentor_tmp, _perfil_v1())
    perfil = pm.cargar_perfil_mentor()
    perfil["progreso"]["proximos_pasos"] = ["Hacer deploy"]
    pm.guardar_perfil_mentor(perfil)
    tema = _leer(perfil_mentor_tmp)["temas"][pm.SLUG_TEMA_DESARROLLO]
    assert tema["progreso"]["proximos_pasos"] == ["Hacer deploy"]


def test_cargar_no_reescribe_el_espejo_top_level(perfil_mentor_tmp):
    # `cargar` NO restaura el espejo desde `temas`: conserva lo escrito en
    # el nivel superior (compatibilidad con escrituras top-level previas).
    base = json.loads(json.dumps(pm.ESQUEMA_MENTOR_DEFECTO))
    base["progreso"]["objetivos"] = [{"titulo": "Top-level", "estado": "activo"}]
    _escribir(perfil_mentor_tmp, base)
    perfil = pm.cargar_perfil_mentor()
    assert perfil["progreso"]["objetivos"][0]["titulo"] == "Top-level"


# ── 2. API de temas ─────────────────────────────────────────────────────────

def test_listar_temas_mentoria_devuelve_registro(perfil_mentor_tmp):
    _escribir(perfil_mentor_tmp, _perfil_v1())
    datos = pm.listar_temas_mentoria()
    assert datos["tema_activo"] == pm.SLUG_TEMA_DESARROLLO
    assert len(datos["temas"]) == 1
    t = datos["temas"][0]
    assert t["slug"] == pm.SLUG_TEMA_DESARROLLO
    assert t["activo"] is True
    assert t["n_sesiones"] == 1
    assert t["objetivos_activos"] == 1


def test_crear_tema_nuevo_y_activa(perfil_mentor_tmp):
    res = pm.crear_tema("Música", "Aprender piano")
    assert res["exito"] is True and res["creado"] is True
    perfil = _leer(perfil_mentor_tmp)
    assert perfil["tema_activo"] == res["slug"]
    assert perfil["temas"][res["slug"]]["nombre"] == "Música"
    assert perfil["temas"][res["slug"]]["objetivo_general"] == "Aprender piano"


def test_crear_tema_reutiliza_existente(perfil_mentor_tmp):
    pm.crear_tema("Música")
    res = pm.crear_tema("Música")
    assert res["exito"] is True and res["creado"] is False
    assert len(_leer(perfil_mentor_tmp)["temas"]) == 2


def test_cambiar_tema_activo_inexistente(perfil_mentor_tmp):
    assert pm.cambiar_tema_activo("no_existe") is False


def test_cambiar_tema_activo_restaura_espejo(perfil_mentor_tmp):
    # El tema nuevo queda activo; sus datos se escriben vía el espejo
    # top-level (como hace el LLM / progreso_mentoria).
    pm.crear_tema("Música")
    perfil = pm.cargar_perfil_mentor()
    perfil["progreso"]["objetivos"] = [{"titulo": "Escalas", "estado": "activo"}]
    pm.guardar_perfil_mentor(perfil)
    assert _leer(perfil_mentor_tmp)["temas"]["m_sica"]["progreso"]["objetivos"][0]["titulo"] == "Escalas"

    # Cambiar a otro tema restaura el espejo top-level con ese tema.
    assert pm.cambiar_tema_activo(pm.SLUG_TEMA_DESARROLLO) is True
    perfil2 = pm.cargar_perfil_mentor()
    assert perfil2["progreso"]["objetivos"] == []  # desarrollo no tiene nada
    # Volver a Música recupera su progreso en el espejo.
    assert pm.cambiar_tema_activo("m_sica") is True
    perfil3 = pm.cargar_perfil_mentor()
    assert perfil3["progreso"]["objetivos"][0]["titulo"] == "Escalas"


# ── 3. Olvido de un tema completo ───────────────────────────────────────────

def test_olvidar_tema_completo(perfil_mentor_tmp):
    pm.crear_tema("Inglés")
    assert pm.olvidar_elemento("mentor:tema:ingl_s") is True
    perfil = _leer(perfil_mentor_tmp)
    assert "ingl_s" not in perfil["temas"]
    # El resto de los temas queda intacto.
    assert pm.SLUG_TEMA_DESARROLLO in perfil["temas"]


def test_olvidar_tema_activo_reasigna(perfil_mentor_tmp):
    pm.crear_tema("Inglés")  # queda activo
    assert pm.olvidar_elemento("mentor:tema:ingl_s") is True
    perfil = _leer(perfil_mentor_tmp)
    assert perfil["tema_activo"] == pm.SLUG_TEMA_DESARROLLO
    # El espejo legacy refleja el tema al que se reasignó.
    assert perfil["progreso"]["objetivos"] == []


def test_olvidar_tema_inexistente(perfil_mentor_tmp):
    assert pm.olvidar_elemento("mentor:tema:fantasma") is False


# ── 4. resumen_memoria: sección de temas ────────────────────────────────────

def test_seccion_temas_en_panel(perfil_mentor_tmp):
    pm.crear_tema("Inglés")  # queda activo
    perfil = pm.cargar_perfil_mentor()
    res = rm._seccion_temas(perfil)
    ids = [e["id"] for e in res["temas"]]
    assert "mentor:tema:ingl_s" in ids
    assert f"mentor:tema:{pm.SLUG_TEMA_DESARROLLO}" in ids
    activo = next(e for e in res["temas"] if e["id"] == "mentor:tema:ingl_s")
    assert activo["destacado"] is True


def test_seccion_temas_puede_olvidarse_desde_resumen(perfil_mentor_tmp):
    from modulos import resumen_memoria as _rm
    pm.crear_tema("Inglés")
    res = _rm.resolver_olvidar("mentor:tema:ingl_s")
    assert res.get("exito") is True
    perfil = _leer(perfil_mentor_tmp)
    assert "ingl_s" not in perfil["temas"]


# ── 5. Procesamiento scoped por tema ────────────────────────────────────────

def test_procesar_eventos_scoped_por_tema(perfil_mentor_tmp):
    _escribir(perfil_mentor_tmp, _perfil_v1())
    perfil = pm.cargar_perfil_mentor()
    eventos = [
        {"tipo": "objetivo_creado", "texto": "Tocar una escala completa",
         "importancia": 80, "tema": "Música"},
        {"tipo": "objetivo_creado", "texto": "Deploy del RAG",
         "importancia": 80},
    ]
    pme.procesar_eventos(perfil, eventos)
    pm.guardar_perfil_mentor(perfil)

    guardado = _leer(perfil_mentor_tmp)
    # El evento con `tema` fue al tema de Música (creado en el registro).
    assert "m_sica" in guardado["temas"]
    musica = guardado["temas"]["m_sica"]["progreso"]["objetivos"]
    assert musica[0]["titulo"] == "Tocar una escala completa"
    # El evento sin `tema` fue al tema activo → espejo top-level.
    top = guardado["progreso"]["objetivos"]
    assert top[-1]["titulo"] == "Deploy del RAG"


def test_procesar_eventos_scoped_no_activa_tema_creado(perfil_mentor_tmp):
    _escribir(perfil_mentor_tmp, _perfil_v1())
    perfil = pm.cargar_perfil_mentor()
    pme.procesar_eventos(perfil, [
        {"tipo": "avance_significativo", "texto": "Primera partitura",
         "importancia": 85, "tema": "Música"},
    ])
    pm.guardar_perfil_mentor(perfil)
    guardado = _leer(perfil_mentor_tmp)
    # El tema nuevo se crea en el registro pero NO se activa.
    assert "m_sica" in guardado["temas"]
    assert guardado["tema_activo"] == pm.SLUG_TEMA_DESARROLLO


# ── 6. Reescritor de sesión: preserva temas/tema_activo/progreso ───────────

def test_extraer_sesion_preserva_temas_tema_activo_y_progreso(perfil_mentor_tmp):
    pm.crear_tema("Música")
    # El LLM devuelve un JSON completo sin temas/tema_activo (como haría un
    # modelo ajeno al esquema v2).
    respuesta_llm = json.dumps({
        "stack_objetivo": {"frontend": "React", "backend": "FastAPI",
                           "bases_de_datos": "PostgreSQL", "otras_herramientas": []},
        "tecnologias_aprendidas": ["Python"],
        "tecnologias_en_estudio": [],
        "proyectos_de_portafolio": [],
        "ultimo_avance_registrado": "Refactor del RAG",
        "historial_sesiones": [{"fecha": HOY, "resumen": "Sesión de RAG",
                                "temas": ["RAG"], "proximos_pasos": ["Deploy"]}],
        "claves_de_contexto_faltantes": [],
    })
    _stub_ia(respuesta_llm)
    mensajes = [{"role": "user", "parts": ["hola, retomemos la bitácora"]}]

    pm.extraer_y_procesar_sesion_mentor(mensajes)

    guardado = _leer(perfil_mentor_tmp)
    # El reescritor NO tocó el registro de temas ni el tema activo.
    assert "m_sica" in guardado["temas"]
    assert guardado["tema_activo"] == "m_sica"
    assert guardado["meta"]["version"] == 2
    # El progreso (gestionado por progreso_mentoria) se conserva.
    assert isinstance(guardado["progreso"], dict)
    # El resto de la sesión sí se actualizó.
    assert guardado["ultimo_avance_registrado"] == "Refactor del RAG"
