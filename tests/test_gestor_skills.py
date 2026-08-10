import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modulos.skills.gestor_skills import GestorSkills


def _web_activa(consulta):
    res = GestorSkills().obtener_skill_relevante(consulta)
    return res[0] if res else None


# ── Casos positivos: consultas que deben activar la skill web ─────────────

def test_evento_factual_con_anio():
    assert _web_activa("¿cuál es el resultado de Street Fighter 6 2026?") == "busqueda_web_actualizada"


def test_followup_podio():
    assert _web_activa("¿y cómo quedó el podio?") == "busqueda_web_actualizada"


def test_followup_corto_bronce():
    assert _web_activa("¿y el bronce?") == "busqueda_web_actualizada"


def test_followup_corto_medalla():
    assert _web_activa("y la medalla?") == "busqueda_web_actualizada"


def test_followup_quien_tercero():
    assert _web_activa("¿quién quedó tercero?") == "busqueda_web_actualizada"


def test_followup_quien_primero():
    assert _web_activa("¿quién quedó primero?") == "busqueda_web_actualizada"


def test_followup_quien_ganador():
    assert _web_activa("¿quién ganó?") == "busqueda_web_actualizada"


def test_followup_cual_fue_el_resultado():
    assert _web_activa("¿cuál fue el resultado?") == "busqueda_web_actualizada"


def test_followup_marcador():
    assert _web_activa("¿qué marcador hubo?") == "busqueda_web_actualizada"


def test_followup_medalla_oro():
    assert _web_activa("¿quién obtuvo la medalla de oro?") == "busqueda_web_actualizada"


def test_busca_informacion_actualizada():
    assert _web_activa("busca información actualizada, está mal") == "busqueda_web_actualizada"


# ── Casos negativos (NO deben activar búsqueda web) ─────────────────────

def test_no_activa_tema_atemporal():
    assert _web_activa("¿podés explicar qué es una lista enlazada?") is None


def test_no_activa_consulta_larga_con_bronce_metal():
    assert _web_activa("contame la historia del uso del bronce en la antigüedad") is None


def test_no_activa_consulta_internet_NO_necesaria():
    assert _web_activa("abrís el explorador de archivos") is None