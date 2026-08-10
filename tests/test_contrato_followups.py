import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modulos.prompts import obtener_prompt_general
from modulos.skills.gestor_skills import GestorSkills


def _instrucciones_skill_busqueda():
    return GestorSkills().obtener_instrucciones("busqueda_web_actualizada")


# ── Test 1: la skill instruye consultas autocontenidas para follow-ups ──────

def test_skill_instruye_consulta_autocontenida_para_followups():
    instrucciones = _instrucciones_skill_busqueda()
    assert "AUTOCONTENIDA" in instrucciones
    assert "¿Y el tercero?" in instrucciones
    assert "tercer puesto del podio de Street Fighter 6 2026" in instrucciones


def test_skill_prohibe_consultas_ambiguas():
    instrucciones = _instrucciones_skill_busqueda()
    assert "buscar: el tercero" in instrucciones
    assert "buscar: cuándo fue" in instrucciones


def test_skill_enseña_a_usar_historial_para_resolver_cuando():
    instrucciones = _instrucciones_skill_busqueda()
    assert "fecha del torneo de Street Fighter 6 2026" in instrucciones
    assert "contexto temporal" in instrucciones


# ── Test 2: El prompt general también contiene la instrucción ────────────────

def test_prompt_general_instruye_consulta_autocontenida():
    prompt = obtener_prompt_general(
        fecha_hoy="sábado, 8 de agosto de 2026",
        ruta_home=r"C:\Users\luism",
        ventanas_abiertas="",
        texto_workspace="",
        texto_snapshot="",
        texto_doc_volatil="",
    )
    assert "PREGUNTA DE SEGUIMIENTO" in prompt
    assert "AUTOCONTENIDA" in prompt
    assert "resolver la referencia implícita" in prompt


def test_prompt_general_prohibe_consultas_ambiguas():
    prompt = obtener_prompt_general(
        fecha_hoy="fecha",
        ruta_home="home",
        ventanas_abiertas="",
        texto_workspace="",
        texto_snapshot="",
        texto_doc_volatil="",
    )
    assert "buscar: el tercero" in prompt
    assert "buscar: cuándo fue" in prompt


def test_prompt_general_no_obliga_busqueda_para_explicaciones():
    prompt = obtener_prompt_general(
        fecha_hoy="fecha",
        ruta_home="home",
        ventanas_abiertas="",
        texto_workspace="",
        texto_snapshot="",
        texto_doc_volatil="",
    )
    assert "no busques" in prompt