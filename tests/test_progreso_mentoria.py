"""
Tests de Fase 5 — Persistencia de Progreso/Mentoría (K5).

Cubren:
1. Clasificación determinista de eventos (estado / bóveda / ambos / descartable).
2. Aplicación al estado estructurado (perfil_mentor.json → clave 'progreso').
3. Persistencia semántica a la Bóveda con contratos reutilizados
   (guardar_recuerdo, origen_fuente='mentoria_progreso') y guard anti-diario.
4. Extracción de eventos (parseo defensivo, sin API keys: cliente_genai fake).
5. Integración con perfil_mentor (olvidar/editar ids del bloque progreso) y
   resumen_memoria (nuevos elementos en aprendizaje_y_carrera).

Offline: se stubean modulos.ia y modulos.memoria (ver test_controlador_acciones).
Ninguna prueba toca la bóveda ni los perfiles reales.
"""

import sys
import types
import json
import datetime

import pytest

from modulos import perfil_mentor as pm
from modulos import resumen_memoria as rm
from modulos import progreso_mentoria as pme


# ── Stubs (modulos.ia y modulos.memoria son dependencias pesadas) ───────────

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


_llamadas_boveda = []
_BOVEDA_MOD = _stub("modulos.memoria", {})


def _stub_boveda():
    """Instala el stub de modulos.memoria con guardar_recuerdo lógico."""
    def guardar_recuerdo(texto_a_guardar, etiqueta_tema, metadatos_extra=None,
                         origen_id=None, origen_fuente=None, **kwargs):
        _llamadas_boveda.append({
            "texto": texto_a_guardar,
            "etiqueta": etiqueta_tema,
            "origen_fuente": origen_fuente,
        })
        return True
    _BOVEDA_MOD.guardar_recuerdo = guardar_recuerdo
    # Reafirmar en sys.modules: otros test files (test_memoria, test_backfill...)
    # hacen pop()/reimport de modulos.memoria; el stub debe seguir vigente aquí.
    sys.modules["modulos.memoria"] = _BOVEDA_MOD


def _stub_ia(respuesta_json=""):
    cliente = _ClienteFalso(respuesta_json)
    m = types.ModuleType("modulos.ia")
    m.cliente_genai = cliente
    sys.modules["modulos.ia"] = m
    return cliente


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def perfil_mentor_tmp(tmp_path, monkeypatch):
    ruta = tmp_path / "perfil_mentor.json"
    monkeypatch.setattr(pm, "RUTA_PERFIL_MENTOR", str(ruta))
    return ruta


@pytest.fixture
def boveda_stub(monkeypatch):
    _llamadas_boveda.clear()
    _stub_boveda()
    return _llamadas_boveda


# ── 1. Clasificación determinista ───────────────────────────────────────────

def test_clasificar_evento_semantico_boveda():
    ev = {"tipo": "avance_significativo", "texto": "Terminó el CRUD en FastAPI", "importancia": 80}
    assert pme.clasificar_evento(ev) == "boveda"


def test_clasificar_evento_semantico_bajo_descarta():
    ev = {"tipo": "aprendizaje_relevante", "texto": "Vio un tutorial de Docker", "importancia": 30}
    assert pme.clasificar_evento(ev) == "descartable"


def test_clasificar_evento_estado():
    ev = {"tipo": "proximo_paso", "texto": "Hacer deploy", "importancia": 70}
    assert pme.clasificar_evento(ev) == "estado"


def test_clasificar_evento_objetivo():
    ev = {"tipo": "objetivo_creado", "texto": "Aprender FastAPI", "importancia": 70}
    assert pme.clasificar_evento(ev) == "estado"


def test_clasificar_evento_dificultad_recurrente():
    ev = {"tipo": "dificultad_recurrente", "texto": "Problemas con el puerto", "importancia": 80}
    assert pme.clasificar_evento(ev) == "ambos"


def test_clasificar_evento_dificultad_recurrente_baja():
    ev = {"tipo": "dificultad_recurrente", "texto": "Problemas con el puerto", "importancia": 55}
    assert pme.clasificar_evento(ev) == "estado"


def test_clasificar_evento_desconocido():
    ev = {"tipo": "lo_que_quiera", "texto": "Invención", "importancia": 100}
    assert pme.clasificar_evento(ev) == "descartable"


def test_clasificar_evento_tipo_bueno_sin_texto():
    ev = {"tipo": "avance_significativo", "texto": "", "importancia": 100}
    assert pme.clasificar_evento(ev) == "descartable"


# ── 2-3. Procesamiento (estado + bóveda, anti-diario) ───────────────────────

def test_procesar_eventos_estado_y_boveda(perfil_mentor_tmp, boveda_stub):
    _escribir(perfil_mentor_tmp, _perfil_base())
    perfil = pm.cargar_perfil_mentor()
    eventos = [
        {"tipo": "objetivo_creado", "texto": "Aprender FastAPI", "importancia": 80},
        {"tipo": "proximo_paso", "texto": "Hacer deploy", "importancia": 70},
        {"tipo": "dificultad", "texto": "Puerto ocupado", "importancia": 55},
        {"tipo": "hito_completado", "texto": "Primer endpoint", "importancia": 60},
        {"tipo": "avance_significativo", "texto": "Terminó el CRUD con SQLModel", "importancia": 85},
        {"tipo": "decision_importante", "texto": "Elegir PostgreSQL como motor", "importancia": 75},
        {"tipo": "informativo", "texto": "Charla casual", "importancia": 90},
    ]
    stats = pme.procesar_eventos(perfil, eventos)

    assert stats["estado"] == 4          # objetivo, próximo paso, dificultad, hito
    assert stats["recuerdos_boveda"] == 2  # avance + decisión
    assert stats["descartados"] == 1     # informativo
    assert stats["cambios_perfil"] >= 1

    prog = perfil["progreso"]
    assert len(prog["objetivos"]) == 1
    assert prog["objetivos"][0]["titulo"] == "Aprender FastAPI"
    assert prog["objetivos"][0]["estado"] == "activo"
    assert "Hacer deploy" in prog["proximos_pasos"]
    assert prog["dificultades_activas"][0]["tema"] == "Puerto ocupado"
    assert prog["hitos_completados"][0]["texto"] == "Primer endpoint"

    # La bóveda recibió 2 recuerdos con el origen de mentoría constante.
    assert len(_llamadas_boveda) == 2
    assert all(c["origen_fuente"] == "mentoria_progreso" for c in _llamadas_boveda)


def test_no_duplica_recuerdo_semantico(perfil_mentor_tmp, boveda_stub):
    _escribir(perfil_mentor_tmp, _perfil_base())
    perfil = pm.cargar_perfil_mentor()
    evento = {"tipo": "avance_significativo", "texto": "Terminó el CRUD completo", "importancia": 90}
    stats1 = pme.procesar_eventos(perfil, [evento])
    # Se persiste el perfil con el guard (recuerdos_persistidos)
    pm.guardar_perfil_mentor(perfil)
    assert stats1["recuerdos_boveda"] == 1

    perfil2 = pm.cargar_perfil_mentor()
    stats2 = pme.procesar_eventos(perfil2, [evento])
    assert stats2["recuerdos_boveda"] == 0
    assert len(_llamadas_boveda) == 1  # el diario no crece


def test_procesar_eventos_estado_objetivo_upsert(perfil_mentor_tmp, boveda_stub):
    _escribir(perfil_mentor_tmp, _perfil_base())
    perfil = pm.cargar_perfil_mentor()
    pme.procesar_eventos(perfil, [
        {"tipo": "objetivo_creado", "texto": "Aprender FastAPI", "importancia": 80},
        {"tipo": "objetivo_logrado", "texto": "Aprender FastAPI", "importancia": 90},
    ])
    assert len(perfil["progreso"]["objetivos"]) == 1
    assert perfil["progreso"]["objetivos"][0]["estado"] == "completado"


def test_procesar_eventos_continuidad(perfil_mentor_tmp, boveda_stub):
    _escribir(perfil_mentor_tmp, _perfil_base())
    perfil = pm.cargar_perfil_mentor()
    pme.procesar_eventos(perfil, [
        {"tipo": "continuidad", "texto": "Quedamos en armar el esquema SQL", "importancia": 65},
    ])
    cont = perfil["progreso"]["continuidad"]
    assert cont["donde_quedamos"] == "Quedamos en armar el esquema SQL"


# ── 4. Extracción de eventos (cliente fake) ─────────────────────────────────

def test_extraer_eventos_progreso_parsea_lista(perfil_mentor_tmp, boveda_stub):
    _stub_ia(json.dumps([
        {"tipo": "objetivo_creado", "texto": "Aprender React", "importancia": 80},
        {"tipo": "desconocido", "texto": "Basura que inventa el LLM", "importancia": 99},
    ]))
    eventos = pme.extraer_eventos_progreso([{"role": "user", "parts": ["Hola, quiero aprender React"]}])
    assert len(eventos) == 1
    assert eventos[0]["tipo"] == "objetivo_creado"


def test_extraer_eventos_progreso_sin_mensajes():
    assert pme.extraer_eventos_progreso([]) == []


def test_extraer_eventos_progreso_no_lista(perfil_mentor_tmp, boveda_stub):
    _stub_ia("no soy json")
    eventos = pme.extraer_eventos_progreso([{"role": "user", "parts": ["mensaje"]}])
    assert eventos == []


# ── 5. Integración perfil_mentor: olvidar/editar ids del progreso ───────────

def _perfil_base():
    base = json.loads(json.dumps(pm.ESQUEMA_MENTOR_DEFECTO))
    base["progreso"]["objetivos"] = [
        {"titulo": "Aprender FastAPI", "estado": "activo", "prioridad": "alta",
         "proyecto_asociado": "", "fecha_creacion": "2026-08-11", "fecha_actualizacion": "2026-08-11"}
    ]
    base["progreso"]["dificultades_activas"] = [
        {"tema": "Puerto ocupado", "ocurrencias": 3, "ultima_fecha": "2026-08-11"}
    ]
    base["progreso"]["hitos_completados"] = [{"texto": "Primer endpoint", "fecha": "2026-08-11"}]
    base["progreso"]["proximos_pasos"] = ["Hacer deploy"]
    base["progreso"]["continuidad"] = {"ultimo_tema": "SQL", "ultima_fecha": "2026-08-11",
                                       "donde_quedamos": "Quedamos en el esquema"}
    return base


def _escribir(ruta, datos):
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)


def _leer(ruta):
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def test_pm_olvidar_objetivo_progreso(perfil_mentor_tmp):
    _escribir(perfil_mentor_tmp, _perfil_base())
    assert pm.olvidar_elemento("mentor:progreso_objetivo:aprender_fastapi") is True
    perfil = _leer(perfil_mentor_tmp)
    assert perfil["progreso"]["objetivos"] == []


def test_pm_olvidar_proximos_pasos_progreso(perfil_mentor_tmp):
    _escribir(perfil_mentor_tmp, _perfil_base())
    assert pm.olvidar_elemento("mentor:progreso_proximos_pasos") is True
    assert _leer(perfil_mentor_tmp)["progreso"]["proximos_pasos"] == []


def test_pm_editar_objetivo_progreso(perfil_mentor_tmp):
    _escribir(perfil_mentor_tmp, _perfil_base())
    assert pm.editar_elemento("mentor:progreso_objetivo:aprender_fastapi", "Aprender FastAPI y Pydantic") is True
    perfil = _leer(perfil_mentor_tmp)
    assert perfil["progreso"]["objetivos"][0]["titulo"] == "Aprender FastAPI y Pydantic"


def test_pm_editar_dificultad_progreso(perfil_mentor_tmp):
    _escribir(perfil_mentor_tmp, _perfil_base())
    assert pm.editar_elemento("mentor:progreso_dificultad:puerto_ocupado", "Puerto ocupado por Docker") is True
    perfil = _leer(perfil_mentor_tmp)
    assert perfil["progreso"]["dificultades_activas"][0]["tema"] == "Puerto ocupado por Docker"


# ── resumen_memoria: nuevos elementos en aprendizaje_y_carrera ──────────────

def test_resumen_mentor_incluye_progreso(monkeypatch):
    reg = pm.cargar_perfil_mentor()
    progreso_bas = _perfil_base()["progreso"]
    perfil_mentor = dict(reg, progreso=progreso_bas)
    secciones = {k: [] for k in rm.ORDEN_SECCIONES}
    res = rm._seccion_mentor(perfil_mentor)
    ids = [e["id"] for e in res["aprendizaje_y_carrera"]]
    assert "mentor:progreso_objetivo:aprender_fastapi" in ids
    assert "mentor:progreso_proximos_pasos" in ids
    assert "mentor:progreso_dificultad:puerto_ocupado" in ids
    assert "mentor:progreso_hito:primer_endpoint" in ids
    assert "mentor:progreso_continuidad" in ids


# ── procesar_sesion_progreso: orquestador con perfil real en disco ──────────

def test_procesar_sesion_progreso_en_disco(perfil_mentor_tmp, boveda_stub):
    _escribir(perfil_mentor_tmp, _perfil_base())
    _stub_ia(json.dumps([
        {"tipo": "avance_significativo", "texto": "Completó el módulo de autenticación", "importancia": 88}
    ]))
    stats = pme.procesar_sesion_progreso([{"role": "user", "parts": ["Avancé en auth"]}])
    assert stats["recuerdos_boveda"] == 1
    perfil = _leer(perfil_mentor_tmp)
    assert len(perfil["progreso"]["recuerdos_persistidos"]) == 1
    # El avance no borra la continuidad previa (solo 'continuidad' la actualiza).
    assert perfil["progreso"]["continuidad"]["donde_quedamos"] == "Quedamos en el esquema"


# ── Cierre de Fase 5: P1 — ningún avance significativo se pierde ────────────

@pytest.fixture
def olvidos_tmp(tmp_path, monkeypatch):
    """Redirige olvidos.json a un archivo temporal (sin tocar el real)."""
    from modulos import olvidos as olv
    ruta = tmp_path / "olvidos.json"
    monkeypatch.setattr(olv, "RUTA_OLVIDOS", str(ruta))
    return ruta


def test_avance_significativo_64_se_conserva(perfil_mentor_tmp, boveda_stub):
    _escribir(perfil_mentor_tmp, _perfil_base())
    perfil = pm.cargar_perfil_mentor()
    stats = pme.procesar_eventos(perfil, [
        {"tipo": "avance_significativo", "texto": "Deploy exitoso en Streamlit Cloud", "importancia": 64}
    ])
    assert stats["descartados"] == 0
    assert stats["estado"] == 1
    assert stats["recuerdos_boveda"] == 0
    assert "Deploy exitoso en Streamlit Cloud" in [h["texto"] for h in perfil["progreso"]["hitos_completados"]]
    assert _llamadas_boveda == []


def test_avance_significativo_50_se_conserva(perfil_mentor_tmp, boveda_stub):
    _escribir(perfil_mentor_tmp, _perfil_base())
    perfil = pm.cargar_perfil_mentor()
    stats = pme.procesar_eventos(perfil, [
        {"tipo": "avance_significativo", "texto": "Corrigió el bug del registro", "importancia": 50}
    ])
    assert stats["descartados"] == 0
    assert stats["estado"] == 1
    assert "Corrigió el bug del registro" in [h["texto"] for h in perfil["progreso"]["hitos_completados"]]


def test_avance_significativo_sin_importancia_se_conserva(perfil_mentor_tmp, boveda_stub):
    _escribir(perfil_mentor_tmp, _perfil_base())
    perfil = pm.cargar_perfil_mentor()
    evento = {"tipo": "avance_significativo", "texto": "Terminé el módulo de autenticación"}
    assert pme.clasificar_evento(evento) == "estado"  # sin importancia → imputada 0 → estado
    stats = pme.procesar_eventos(perfil, [evento])
    assert stats["descartados"] == 0
    assert stats["estado"] == 1
    assert "Terminé el módulo de autenticación" in [h["texto"] for h in perfil["progreso"]["hitos_completados"]]
    assert _llamadas_boveda == []


def test_evento_realmente_descartable_se_descarta(boveda_stub):
    perfil = {}
    stats = pme.procesar_eventos(perfil, [
        {"tipo": "informativo", "texto": "Charla casual", "importancia": 90},
        {"tipo": "aprendizaje_relevante", "texto": "Vio un video de Docker", "importancia": 30},
    ])
    assert stats["descartados"] == 2
    assert stats["estado"] == 0
    assert stats["recuerdos_boveda"] == 0
    assert _llamadas_boveda == []


def test_avance_no_se_duplica_en_estado_y_boveda(perfil_mentor_tmp, boveda_stub):
    _escribir(perfil_mentor_tmp, _perfil_base())
    # Alto → SOLO Bóveda (no se refleja como hito).
    perfil = pm.cargar_perfil_mentor()
    stats = pme.procesar_eventos(perfil, [
        {"tipo": "avance_significativo", "texto": "Terminó el CRUD completo", "importancia": 90}
    ])
    assert stats["recuerdos_boveda"] == 1
    assert stats["estado"] == 0
    # Alto → NO se refleja como hito (no se duplica).
    assert "Terminó el CRUD completo" not in [h["texto"] for h in perfil["progreso"]["hitos_completados"]]
    # Medio → SOLO estado (no se duplica en la Bóveda).
    perfil2 = pm.cargar_perfil_mentor()
    stats2 = pme.procesar_eventos(perfil2, [
        {"tipo": "avance_significativo", "texto": "Corrigió el bug del deploy", "importancia": 60}
    ])
    assert stats2["recuerdos_boveda"] == 0
    assert stats2["estado"] == 1
    assert "Corrigió el bug del deploy" in [h["texto"] for h in perfil2["progreso"]["hitos_completados"]]


# ── Cierre de Fase 5: P2 — un progreso olvidado no reaparece ─────────────────

def test_olvido_progreso_no_reintroducido_por_reescriptor(perfil_mentor_tmp, boveda_stub, olvidos_tmp):
    _escribir(perfil_mentor_tmp, _perfil_base())
    # El usuario olvida el objetivo desde el panel (borrado + tombstone).
    assert rm.resolver_olvidar("mentor:progreso_objetivo:aprender_fastapi")["exito"] is True
    assert _leer(perfil_mentor_tmp)["progreso"]["objetivos"] == []
    from modulos import olvidos as olv
    assert "mentor:progreso_objetivo:aprender_fastapi" in olv.obtener_ids_olvidados("mentor:")
    # El LLM (fake) "reintroduce" el objetivo en su devolución de perfil completo.
    resp = _perfil_base()
    resp["ultimo_avance_registrado"] = "Seguimos con FastAPI"
    _stub_ia(json.dumps(resp))
    pm.extraer_y_procesar_sesion_mentor([{"role": "user", "parts": ["Hola, seguimos con FastAPI"]}])
    perfil = _leer(perfil_mentor_tmp)
    assert perfil["progreso"]["objetivos"] == []  # no reaparece
    assert perfil["ultimo_avance_registrado"] == "Seguimos con FastAPI"  # la sesión sí se persistió


# ── Cierre de Fase 5: P3 — secretos nunca se persisten ───────────────────────

def test_es_secreto_detecta_credenciales():
    assert pme._es_secreto("Mi contraseña es SuperSecreta123") is True
    assert pme._es_secreto("la api key es sk-abcdefghijklmnopqrstuvwx") is True
    assert pme._es_secreto("el token de acceso es z9x8c7v6b5n4m3a2s1d0f") is True


def test_es_secreto_texto_normal():
    assert pme._es_secreto("Terminé el CRUD con SQLModel, FastAPI y lo desplegué en Streamlit Cloud") is False


def test_avance_secreto_no_se_persiste(perfil_mentor_tmp, boveda_stub):
    _escribir(perfil_mentor_tmp, _perfil_base())
    # Importancia alta → cae a Bóveda, pero el guard de secretos lo bloquea.
    perfil = pm.cargar_perfil_mentor()
    stats = pme.procesar_eventos(perfil, [
        {"tipo": "avance_significativo", "texto": "Cambié la contraseña del server", "importancia": 90}
    ])
    assert stats["recuerdos_boveda"] == 0
    assert _llamadas_boveda == []
    # Importancia media → ruta de estado; el guard de la ruta nueva lo bloquea.
    perfil2 = pm.cargar_perfil_mentor()
    stats2 = pme.procesar_eventos(perfil2, [
        {"tipo": "avance_significativo", "texto": "contraseña nueva guardada", "importancia": 60}
    ])
    assert perfil2["progreso"]["hitos_completados"][-1]["texto"] != "contraseña nueva guardada"
    assert "contraseña nueva guardada" not in [h["texto"] for h in perfil2["progreso"]["hitos_completados"]]


# ── Cierre de Fase 5: P4 — una misma sesión se persiste UNA sola vez ─────────

def test_sesion_ya_procesada_dedupe():
    msgs = [{"role": "user", "parts": ["hola"]}]
    assert pme.sesion_ya_procesada(msgs) is False
    assert pme.sesion_ya_procesada(msgs) is True   # misma conversación → no re-examinar
    assert pme.sesion_ya_procesada([{"role": "user", "parts": ["otra cosa"]}]) is False