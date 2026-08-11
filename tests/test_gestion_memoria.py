"""
Tests Fase 2 — Gestión de memoria de Argus (editar/olvidar datos del panel).

Cubren la capa de política (resumen_memoria.resolver_olvidar / resolver_editar)
y las mutaciones de cada módulo propietario de perfil (perfil_usuario,
perfil_mentor, perfil_gamer), verificando además la persistencia real en disco.

Offline: ninguna llamada a IA ni a ChromaDB. Los perfiles se escriben/leen en
carpetas temporales (monkeypatch de las rutas) para no tocar los JSON reales.
"""

import json
import datetime

import pytest

from modulos import resumen_memoria as rm
from modulos import perfil_usuario as pu
from modulos import perfil_mentor as pm
from modulos import perfil_gamer as pg


def _escribir(ruta, datos):
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)


def _leer(ruta):
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


HOY = datetime.date.today().strftime("%Y-%m-%d")


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
            {"tema": "opinión profesional", "contenido": "La IA cambió el mercado",
             "actualizado": HOY},
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
        "tecnologias_aprendidas": ["Python", "FastAPI"],
        "tecnologias_en_estudio": ["LangChain"],
        "proyectos_de_portafolio": [
            {"nombre": "App Gimn", "descripcion": "App de gimnasio"},
        ],
        "ultimo_avance_registrado": "Armó un RAG",
        "historial_sesiones": [{"fecha": HOY, "proximos_pasos": ["Hacer deploy"]}],
        "claves_de_contexto_faltantes": [],
    }


def _perfil_gamer_inicial():
    return {
        "juego_activo": "Grim Dawn",
        "juegos": {
            "Grim Dawn": {"personaje": "Hechicero", "nivel": "45", "ultima_sesion": HOY},
            "Street Fighter VI": {"personaje": "Ryu", "ultima_sesion": HOY},
        },
    }


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


# ── 1. perfil_usuario: olvidar ───────────────────────────────────────────────

def test_pu_olvidar_funcional(perfil_usuario_tmp):
    _escribir(perfil_usuario_tmp, _perfil_usuario_inicial())
    assert pu.olvidar_elemento("funcional:rutina_uso") is True
    perfil = _leer(perfil_usuario_tmp)
    assert perfil["funcional"]["rutina_uso"] == ""
    assert perfil["funcional"]["identidad"] == "Luis"  # no toca otros


def test_pu_olvidar_vida_por_slug(perfil_usuario_tmp):
    _escribir(perfil_usuario_tmp, _perfil_usuario_inicial())
    # El slug con tilde es vida:opini_n_profesional (id estable del panel).
    assert pu.olvidar_elemento("vida:opini_n_profesional") is True
    perfil = _leer(perfil_usuario_tmp)
    temas = [e["tema"] for e in perfil["vida_personal"]]
    assert "opinión profesional" not in temas
    assert "salud" in temas  # no toca otros


def test_pu_olvidar_vida_inexistente(perfil_usuario_tmp):
    _escribir(perfil_usuario_tmp, _perfil_usuario_inicial())
    perfil_antes = _leer(perfil_usuario_tmp)
    assert pu.olvidar_elemento("vida:deporte") is False
    assert _leer(perfil_usuario_tmp) == perfil_antes


def test_pu_olvidar_clave_funcional_invalida(perfil_usuario_tmp):
    _escribir(perfil_usuario_tmp, _perfil_usuario_inicial())
    perfil_antes = _leer(perfil_usuario_tmp)
    assert pu.olvidar_elemento("funcional:clave_inventada") is False
    assert _leer(perfil_usuario_tmp) == perfil_antes


def test_pu_olvidar_id_ajeno(perfil_usuario_tmp):
    _escribir(perfil_usuario_tmp, _perfil_usuario_inicial())
    perfil_antes = _leer(perfil_usuario_tmp)
    assert pu.olvidar_elemento("mentor:stack_backend") is False
    assert _leer(perfil_usuario_tmp) == perfil_antes


# ── 2. perfil_usuario: editar ────────────────────────────────────────────────

def test_pu_editar_funcional(perfil_usuario_tmp):
    _escribir(perfil_usuario_tmp, _perfil_usuario_inicial())
    assert pu.editar_elemento("funcional:proyecto_actual", "Nuevo Proyecto") is True
    perfil = _leer(perfil_usuario_tmp)
    assert perfil["funcional"]["proyecto_actual"] == "Nuevo Proyecto"


def test_pu_editar_vida_contenido_y_fecha(perfil_usuario_tmp):
    _escribir(perfil_usuario_tmp, _perfil_usuario_inicial())
    assert pu.editar_elemento("vida:salud", "Dejó la rosuvastatina") is True
    perfil = _leer(perfil_usuario_tmp)
    salud = next(e for e in perfil["vida_personal"] if e["tema"] == "salud")
    assert salud["contenido"] == "Dejó la rosuvastatina"
    assert salud["actualizado"] == HOY


def test_pu_editar_inexistente(perfil_usuario_tmp):
    _escribir(perfil_usuario_tmp, _perfil_usuario_inicial())
    assert pu.editar_elemento("vida:mascotas", "Tiene un perro") is False


# ── 3. perfil_mentor: olvidar ────────────────────────────────────────────────

def test_pm_olvidar_stack(perfil_mentor_tmp):
    _escribir(perfil_mentor_tmp, _perfil_mentor_inicial())
    assert pm.olvidar_elemento("mentor:stack_backend") is True
    perfil = _leer(perfil_mentor_tmp)
    assert perfil["stack_objetivo"]["backend"] == "Pendiente de definir"
    assert perfil["stack_objetivo"]["frontend"] == "React"  # no toca otros


def test_pm_olvidar_tecnologias(perfil_mentor_tmp):
    _escribir(perfil_mentor_tmp, _perfil_mentor_inicial())
    assert pm.olvidar_elemento("mentor:tecnologias_aprendidas") is True
    assert _leer(perfil_mentor_tmp)["tecnologias_aprendidas"] == []


def test_pm_olvidar_ultimo_avance(perfil_mentor_tmp):
    _escribir(perfil_mentor_tmp, _perfil_mentor_inicial())
    assert pm.olvidar_elemento("mentor:ultimo_avance") is True
    assert _leer(perfil_mentor_tmp)["ultimo_avance_registrado"] == "Ninguno"


def test_pm_olvidar_proximos_pasos(perfil_mentor_tmp):
    _escribir(perfil_mentor_tmp, _perfil_mentor_inicial())
    assert pm.olvidar_elemento("mentor:proximos_pasos") is True
    perfil = _leer(perfil_mentor_tmp)
    assert perfil["historial_sesiones"][-1]["proximos_pasos"] == []


def test_pm_olvidar_proximos_pasos_sin_historial(perfil_mentor_tmp):
    perfil = _perfil_mentor_inicial()
    perfil["historial_sesiones"] = []
    _escribir(perfil_mentor_tmp, perfil)
    assert pm.olvidar_elemento("mentor:proximos_pasos") is False


def test_pm_olvidar_proyecto(perfil_mentor_tmp):
    _escribir(perfil_mentor_tmp, _perfil_mentor_inicial())
    assert pm.olvidar_elemento("mentor:proyecto:app_gimn") is True
    assert _leer(perfil_mentor_tmp)["proyectos_de_portafolio"] == []


def test_pm_olvidar_proyecto_inexistente(perfil_mentor_tmp):
    _escribir(perfil_mentor_tmp, _perfil_mentor_inicial())
    assert pm.olvidar_elemento("mentor:proyecto:otra_cosa") is False


def test_pm_olvidar_id_ajeno(perfil_mentor_tmp):
    _escribir(perfil_mentor_tmp, _perfil_mentor_inicial())
    assert pm.olvidar_elemento("vida:salud") is False


# ── 4. perfil_mentor: editar ─────────────────────────────────────────────────

def test_pm_editar_stack(perfil_mentor_tmp):
    _escribir(perfil_mentor_tmp, _perfil_mentor_inicial())
    assert pm.editar_elemento("mentor:stack_backend", "Go") is True
    assert _leer(perfil_mentor_tmp)["stack_objetivo"]["backend"] == "Go"


def test_pm_editar_tecnologias_separador(perfil_mentor_tmp):
    _escribir(perfil_mentor_tmp, _perfil_mentor_inicial())
    assert pm.editar_elemento("mentor:tecnologias_aprendidas", "Go · Rust") is True
    assert _leer(perfil_mentor_tmp)["tecnologias_aprendidas"] == ["Go", "Rust"]


def test_pm_editar_proyecto_descripcion(perfil_mentor_tmp):
    _escribir(perfil_mentor_tmp, _perfil_mentor_inicial())
    assert pm.editar_elemento("mentor:proyecto:app_gimn", "App de rutinas") is True
    perfil = _leer(perfil_mentor_tmp)
    assert perfil["proyectos_de_portafolio"][0]["nombre"] == "App Gimn"
    assert perfil["proyectos_de_portafolio"][0]["descripcion"] == "App de rutinas"


def test_pm_editar_proximos_pasos(perfil_mentor_tmp):
    _escribir(perfil_mentor_tmp, _perfil_mentor_inicial())
    assert pm.editar_elemento("mentor:proximos_pasos", "Comprar dominio · Subir app") is True
    perfil = _leer(perfil_mentor_tmp)
    assert perfil["historial_sesiones"][-1]["proximos_pasos"] == ["Comprar dominio", "Subir app"]


# ── 5. perfil_gamer: olvidar ─────────────────────────────────────────────────

def test_pg_olvidar_ficha_y_limpia_activo(perfil_gamer_tmp):
    _escribir(perfil_gamer_tmp, _perfil_gamer_inicial())
    assert pg.olvidar_elemento("gamer:grim_dawn") is True
    perfil = _leer(perfil_gamer_tmp)
    assert "Grim Dawn" not in perfil["juegos"]
    assert perfil["juego_activo"] == ""  # sin huérfanos
    assert "Street Fighter VI" in perfil["juegos"]  # no toca otros


def test_pg_olvidar_ficha_no_activa(perfil_gamer_tmp):
    _escribir(perfil_gamer_tmp, _perfil_gamer_inicial())
    assert pg.olvidar_elemento("gamer:street_fighter_vi") is True
    perfil = _leer(perfil_gamer_tmp)
    assert perfil["juego_activo"] == "Grim Dawn"
    assert "Street Fighter VI" not in perfil["juegos"]


def test_pg_olvidar_juego_activo_solo(perfil_gamer_tmp):
    perfil = _perfil_gamer_inicial()
    perfil["juegos"] = {}
    _escribir(perfil_gamer_tmp, perfil)
    assert pg.olvidar_elemento("gamer:juego_activo") is True
    assert _leer(perfil_gamer_tmp)["juego_activo"] == ""


def test_pg_olvidar_inexistente(perfil_gamer_tmp):
    _escribir(perfil_gamer_tmp, _perfil_gamer_inicial())
    perfil_antes = _leer(perfil_gamer_tmp)
    assert pg.olvidar_elemento("gamer:zelda") is False
    assert _leer(perfil_gamer_tmp) == perfil_antes


def test_pg_olvidar_ficha_ambigua_rechazada(perfil_gamer_tmp):
    # Dos juegos cuyo nombre genera el mismo slug ("a" y "a!") → ambiguo.
    perfil = _perfil_gamer_inicial()
    perfil["juego_activo"] = ""
    perfil["juegos"] = {"a": {"personaje": "x"}, "a!": {"personaje": "y"}}
    _escribir(perfil_gamer_tmp, perfil)
    perfil_antes = _leer(perfil_gamer_tmp)
    assert pg.olvidar_elemento("gamer:a") is False
    assert _leer(perfil_gamer_tmp) == perfil_antes


# ── 6. perfil_gamer: editar (estrategia sin IA, plantilla determinista) ──────

def test_pg_editar_ficha_parcial(perfil_gamer_tmp):
    _escribir(perfil_gamer_tmp, _perfil_gamer_inicial())
    # Solo se actualizan los campos nombrados; 'nivel' queda intacto.
    assert pg.editar_elemento("gamer:grim_dawn", "Personaje: Conjurador") is True
    perfil = _leer(perfil_gamer_tmp)
    ficha = perfil["juegos"]["Grim Dawn"]
    assert ficha["personaje"] == "Conjurador"
    assert ficha["nivel"] == "45"
    assert perfil["juegos"]["Street Fighter VI"]["personaje"] == "Ryu"


def test_pg_editar_ficha_multi_campos(perfil_gamer_tmp):
    _escribir(perfil_gamer_tmp, _perfil_gamer_inicial())
    assert pg.editar_elemento(
        "gamer:grim_dawn",
        "Personaje: Caballero · Nivel: 60 · Build: Tanque · Dificultad: Elite",
    ) is True
    ficha = _leer(perfil_gamer_tmp)["juegos"]["Grim Dawn"]
    assert ficha["personaje"] == "Caballero"
    assert ficha["nivel"] == "60"
    assert ficha["build"] == "Tanque"
    assert ficha["dificultad"] == "Elite"


def test_pg_editar_ficha_plantilla_invalida(perfil_gamer_tmp):
    _escribir(perfil_gamer_tmp, _perfil_gamer_inicial())
    perfil_antes = _leer(perfil_gamer_tmp)
    # Texto libre fuera de la plantilla → se rechaza, no corrompe nada.
    assert pg.editar_elemento("gamer:grim_dawn", "texto libre sin formato") is False
    assert _leer(perfil_gamer_tmp) == perfil_antes


def test_pg_editar_juego_activo(perfil_gamer_tmp):
    perfil = _perfil_gamer_inicial()
    perfil["juegos"] = {}
    _escribir(perfil_gamer_tmp, perfil)
    assert pg.editar_elemento("gamer:juego_activo", "Zelda") is True
    assert _leer(perfil_gamer_tmp)["juego_activo"] == "Zelda"


# ── 7. Capa de política (resumen_memoria) ────────────────────────────────────

def test_resolver_id_invalido():
    assert rm.resolver_olvidar("sarasa")["exito"] is False
    assert rm.resolver_olvidar("")["exito"] is False
    assert rm.resolver_olvidar(None)["exito"] is False
    assert rm.resolver_editar("chrome:algo", "x")["exito"] is False


def test_resolver_editar_texto_vacio():
    assert rm.resolver_editar("funcional:identidad", "   ")["exito"] is False


def test_resolver_olvidar_inexistente(perfil_usuario_tmp):
    # Prefijo válido pero dato ausente → no toca el archivo.
    _escribir(perfil_usuario_tmp, _perfil_usuario_inicial())
    perfil_antes = _leer(perfil_usuario_tmp)
    assert rm.resolver_olvidar("vida:deporte")["exito"] is False
    assert _leer(perfil_usuario_tmp) == perfil_antes


def test_resolver_circulo_vida(perfil_usuario_tmp):
    """Integración: id del panel → borrado real hasta el JSON."""
    _escribir(perfil_usuario_tmp, _perfil_usuario_inicial())
    ids_panel = [
        e["id"] for s in rm.preparar_secciones()["secciones"]
        for e in s["elementos"]
    ]
    assert "vida:salud" in ids_panel
    assert rm.resolver_olvidar("vida:salud")["exito"] is True
    assert rm.resolver_olvidar("vida:salud")["exito"] is False  # idempotente


def test_resolver_editar_funcional(perfil_usuario_tmp):
    _escribir(perfil_usuario_tmp, _perfil_usuario_inicial())
    res = rm.resolver_editar("funcional:identidad", "Luis Alberto")
    assert res["exito"] is True
    assert _leer(perfil_usuario_tmp)["funcional"]["identidad"] == "Luis Alberto"


def test_resolver_olvidar_mentor_y_gamer(perfil_mentor_tmp, perfil_gamer_tmp):
    _escribir(perfil_mentor_tmp, _perfil_mentor_inicial())
    _escribir(perfil_gamer_tmp, _perfil_gamer_inicial())
    assert rm.resolver_olvidar("mentor:stack_backend")["exito"] is True
    assert _leer(perfil_mentor_tmp)["stack_objetivo"]["backend"] == "Pendiente de definir"
    assert rm.resolver_olvidar("gamer:grim_dawn")["exito"] is True
    perfil_g = _leer(perfil_gamer_tmp)
    assert "Grim Dawn" not in perfil_g["juegos"]
    assert perfil_g["juego_activo"] == ""


def test_resolver_no_toca_otros_perfiles(perfil_usuario_tmp, perfil_mentor_tmp):
    _escribir(perfil_usuario_tmp, _perfil_usuario_inicial())
    _escribir(perfil_mentor_tmp, _perfil_mentor_inicial())
    rm.resolver_olvidar("vida:salud")  # borrar en usuario
    assert "Python" in _leer(perfil_mentor_tmp)["tecnologias_aprendidas"]
    assert _leer(perfil_usuario_tmp)["funcional"]["identidad"] == "Luis"


def test_resolver_preparar_despues_de_olvidar(perfil_usuario_tmp, perfil_mentor_tmp, perfil_gamer_tmp):
    """Tras mutaciones el panel sigue siendo válido y refleja la ausencia."""
    _escribir(perfil_usuario_tmp, _perfil_usuario_inicial())
    _escribir(perfil_mentor_tmp, _perfil_mentor_inicial())
    _escribir(perfil_gamer_tmp, _perfil_gamer_inicial())
    assert rm.resolver_olvidar("vida:salud")["exito"] is True
    assert rm.resolver_olvidar("gamer:grim_dawn")["exito"] is True
    ids = [e["id"] for s in rm.preparar_secciones()["secciones"] for e in s["elementos"]]
    assert "vida:salud" not in ids
    assert "gamer:grim_dawn" not in ids
    assert "gamer:juego_activo" not in ids  # se limpió junto con la ficha