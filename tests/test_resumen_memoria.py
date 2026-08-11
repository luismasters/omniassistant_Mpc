"""
Tests para modulos.resumen_memoria (panel "Lo que Argus sabe de vos").

Offline: se sustituyen los loaders de perfiles por datos controlados vía
monkeypatch, de modo que NUNCA se leen ni modifican los perfiles reales
(perfil_usuario.json, perfil_mentor.json, perfil_gamer.json).
"""

import datetime

import pytest

from modulos import resumen_memoria as rm

from modulos.perfil_usuario import ESQUEMA_FUNCIONAL_CLAVES


HOY = datetime.date.today()


def _fecha_iso(offset_dias: int) -> str:
    """Fecha ISO desplazada respecto de hoy (offset_dias días)."""
    return (HOY + datetime.timedelta(days=offset_dias)).isoformat()


@pytest.fixture
def sin_perfiles(monkeypatch):
    """Perfiles por defecto: todo vacío (sin tocar disco)."""
    perfil_usuario = {"funcional": {c: "" for c in ESQUEMA_FUNCIONAL_CLAVES}, "vida_personal": []}
    monkeypatch.setattr(rm, "_cargar_perfil_usuario", lambda: perfil_usuario)
    monkeypatch.setattr(rm, "_cargar_perfil_mentor", lambda: {})
    monkeypatch.setattr(rm, "_cargar_perfil_gamer", lambda: {})
    return rm


@pytest.fixture
def con_perfiles(monkeypatch):
    """Permite configurar perfiles controlados por test."""
    def _aplicar(usuario=None, mentor=None, gamer=None):
        perfil_usuario = usuario if usuario is not None else {
            "funcional": {c: "" for c in ESQUEMA_FUNCIONAL_CLAVES}, "vida_personal": []}
        monkeypatch.setattr(rm, "_cargar_perfil_usuario", lambda: perfil_usuario)
        monkeypatch.setattr(rm, "_cargar_perfil_mentor", lambda: (mentor or {}))
        monkeypatch.setattr(rm, "_cargar_perfil_gamer", lambda: (gamer or {}))
        return rm
    _aplicar()
    return _aplicar


# ── 1. Perfiles completamente vacíos ─────────────────────────────────────────

def test_perfiles_vacios_sin_secciones(sin_perfiles):
    res = sin_perfiles.preparar_secciones()
    assert res["secciones"] == []
    assert "exito" not in res


# ── 2. Perfil completo ───────────────────────────────────────────────────────

def test_perfil_completo(con_perfiles):
    con_perfiles(
        usuario={
            "funcional": {
                "identidad": "Luis",
                "proyecto_actual": "OmniAssistant",
                "rutina_uso": "Usa el asistente por la noche",
            },
            "vida_personal": [
                {"tema": "salud", "contenido": "Toma rosuvastatina", "actualizado": _fecha_iso(-3)},
                {"tema": "objetivos_profesionales", "contenido": "Quiere ser dev backend",
                 "actualizado": _fecha_iso(-10)},
                {"tema": "suscripciones", "contenido": "Netflix 14 días", "actualizado": _fecha_iso(-2)},
            ],
        },
        mentor={
            "stack_objetivo": {"frontend": "React", "backend": "Python", "bases_de_datos": "PostgreSQL",
                               "otras_herramientas": ["Docker"]},
            "tecnologias_aprendidas": ["Python", "FastAPI"],
            "tecnologias_en_estudio": ["LangChain"],
            "ultimo_avance_registrado": "Armó un RAG",
            "historial_sesiones": [{"fecha": _fecha_iso(-1), "proximos_pasos": ["Hacer deploy"]}],
            "proyectos_de_portafolio": [{"nombre": "RAG", "descripcion": "Pipeline de RAG"}],
        },
        gamer={
            "juego_activo": "Grim Dawn",
            "juegos": {"Grim Dawn": {"personaje": "Hechicero", "ultima_sesion": _fecha_iso(-1)}},
        },
    )
    res = rm.preparar_secciones()
    ids = [s["id"] for s in res["secciones"]]
    assert ids == ["sobre_vos", "preferencias_y_rutina", "proyectos",
                   "aprendizaje_y_carrera", "gaming"]
    todas = [e["id"] for s in res["secciones"] for e in s["elementos"]]
    assert "funcional:identidad" in todas
    assert "life_salud" not in todas  # sin ids inventados


# ── 3. Omisión de secciones vacías ───────────────────────────────────────────

def test_omision_secciones_vacias(con_perfiles):
    con_perfiles(
        usuario={
            "funcional": {"identidad": "Ana"},
            "vida_personal": [],
        },
        mentor={},
        gamer={},
    )
    res = rm.preparar_secciones()
    assert [s["id"] for s in res["secciones"]] == ["sobre_vos"]
    assert [e["id"] for e in res["secciones"][0]["elementos"]] == ["funcional:identidad"]


# ── 4. Clasificación de vida_personal ────────────────────────────────────────

def test_clasificacion_vida_personal(con_perfiles):
    con_perfiles(
        usuario={
            "funcional": {},
            "vida_personal": [
                {"tema": "familia", "contenido": "Esposa Yuskeli", "actualizado": _fecha_iso(-2)},
                {"tema": "suscripciones", "contenido": "Netflix", "actualizado": _fecha_iso(-2)},
                {"tema": "objetivos_profesionales", "contenido": "Llegar a dev", "actualizado": _fecha_iso(-2)},
            ],
        },
    )
    secc = {s["id"]: s["elementos"] for s in rm.preparar_secciones()["secciones"]}
    assert [e["etiqueta"] for e in secc["sobre_vos"]] == ["familia"]
    assert [e["etiqueta"] for e in secc["preferencias_y_rutina"]] == ["suscripciones"]
    assert [e["etiqueta"] for e in secc["aprendizaje_y_carrera"]] == ["objetivos_profesionales"]


# ── 5. Clasificación con tildes ──────────────────────────────────────────────

@pytest.mark.parametrize("tema,seccion_esperada", [
    ("opinión profesional", "aprendizaje_y_carrera"),
    ("opinion profesional", "aprendizaje_y_carrera"),
    ("habitos", "preferencias_y_rutina"),
    ("hábitos", "preferencias_y_rutina"),
    ("logística", "preferencias_y_rutina"),
    ("logistica", "preferencias_y_rutina"),
    ("objetivos profesionales", "aprendizaje_y_carrera"),
])
def test_clasificacion_tildes(con_perfiles, tema, seccion_esperada):
    con_perfiles(usuario={
        "funcional": {},
        "vida_personal": [{"tema": tema, "contenido": "detalle", "actualizado": _fecha_iso(-2)}],
    })
    secc = {s["id"]: s["elementos"] for s in rm.preparar_secciones()["secciones"]}
    etiquetas = [e["etiqueta"] for e in secc.get(seccion_esperada, [])]
    assert tema in etiquetas


# ── 6. Fallback de temas desconocidos → sobre_vos ────────────────────────────

def test_fallback_temas_desconocidos(con_perfiles):
    con_perfiles(usuario={
        "funcional": {},
        "vida_personal": [
            {"tema": "mascotas", "contenido": "Tiene un perro", "actualizado": _fecha_iso(-2)},
            {"tema": "cocina", "contenido": "Le gusta cocinar", "actualizado": _fecha_iso(-2)},
        ],
    })
    secc = {s["id"]: s["elementos"] for s in rm.preparar_secciones()["secciones"]}
    assert "sobre_vos" in secc
    assert set(e["etiqueta"] for e in secc["sobre_vos"]) == {"mascotas", "cocina"}
    assert "preferencias_y_rutina" not in secc
    assert "aprendizaje_y_carrera" not in secc


# ── 7. IDs deterministas ─────────────────────────────────────────────────────

def test_ids_deterministas(con_perfiles):
    datos = {
        "funcional": {"identidad": "Luis"},
        "vida_personal": [
            {"tema": "salud", "contenido": "Rosuvastatina", "actualizado": _fecha_iso(-1)},
            {"tema": "opinión profesional", "contenido": "La IA cambió el mercado",
             "actualizado": _fecha_iso(-5)},
        ],
    }
    con_perfiles(usuario=datos)
    ids_a = [e["id"] for s in rm.preparar_secciones()["secciones"] for e in s["elementos"]]
    con_perfiles(usuario=datos)
    ids_b = [e["id"] for s in rm.preparar_secciones()["secciones"] for e in s["elementos"]]
    assert ids_a == ids_b
    assert "vida:salud" in ids_a
    # Los ids NO cambian con tildes: _slug no desacentúa (reemplaza por "_").
    assert "vida:opini_n_profesional" in ids_a


# ── 8. Fechas válidas ────────────────────────────────────────────────────────

def test_fechas_validas(con_perfiles):
    assert rm._fecha_iso("2026-08-08") == "2026-08-08"
    assert rm._fecha_iso("2026-08-08 12:09") == "2026-08-08"
    assert rm._fecha_iso("2026-08-08T12:09:00") == "2026-08-08"
    con_perfiles(usuario={
        "funcional": {},
        "vida_personal": [{"tema": "salud", "contenido": "x", "actualizado": "2026-08-08 15:00"}],
    })
    item = rm.preparar_secciones()["secciones"][0]["elementos"][0]
    assert item["fecha"] == "2026-08-08"


# ── 9. Fechas inválidas ──────────────────────────────────────────────────────

def test_fechas_invalidas(con_perfiles):
    assert rm._fecha_iso(None) is None
    assert rm._fecha_iso("") is None
    assert rm._fecha_iso("no es una fecha") is None
    assert rm._fecha_iso("2026/08/08") is None
    assert rm._fecha_iso(123) is None

    con_perfiles(usuario={
        "funcional": {},
        "vida_personal": [{"tema": "salud", "contenido": "x", "actualizado": "fecha inválida"}],
    })
    item = rm.preparar_secciones()["secciones"][0]["elementos"][0]
    assert item["fecha"] is None
    assert item["reciente"] is False


# ── 10-13. Cálculo de reciente (hoy / 7 / 8 / futuro) ────────────────────────

def test_reciente_hoy():
    assert rm._es_reciente(_fecha_iso(0)) is True


def test_reciente_7_dias():
    assert rm._es_reciente(_fecha_iso(-7)) is True


def test_reciente_8_dias():
    assert rm._es_reciente(_fecha_iso(-8)) is False


def test_reciente_fecha_futura():
    assert rm._es_reciente(_fecha_iso(2)) is False
    assert rm._es_reciente(_fecha_iso(30)) is False


def test_reciente_dentro_de_elemento(con_perfiles):
    con_perfiles(usuario={
        "funcional": {},
        "vida_personal": [
            {"tema": "salud", "contenido": "hoy", "actualizado": _fecha_iso(0)},
            {"tema": "deporte", "contenido": "viejo", "actualizado": _fecha_iso(-8)},
        ],
    })
    secc = {s["id"]: s["elementos"] for s in rm.preparar_secciones()["secciones"]}
    por_etiqueta = {e["etiqueta"]: e for e in secc["sobre_vos"]}
    assert por_etiqueta["salud"]["reciente"] is True
    assert por_etiqueta["deporte"]["reciente"] is False


# ── 14. Campos opcionales ────────────────────────────────────────────────────

def test_campos_opcionales(con_perfiles):
    con_perfiles(
        mentor={"stack_objetivo": {}, "tecnologias_aprendidas": [], "historial_sesiones": [],
                "proyectos_de_portafolio": [], "ultimo_avance_registrado": "Ninguno"},
        gamer={"juego_activo": "", "juegos": {}},
    )
    res = rm.preparar_secciones()
    assert "gaming" not in [s["id"] for s in res["secciones"]]
    assert "aprendizaje_y_carrera" not in [s["id"] for s in res["secciones"]]


# ── 15. Juego activo sin ficha ───────────────────────────────────────────────

def test_juego_activo_sin_ficha(con_perfiles):
    con_perfiles(gamer={"juego_activo": "Street Fighter VI", "juegos": {}})
    secc = {s["id"]: s["elementos"] for s in rm.preparar_secciones()["secciones"]}
    gaming = secc["gaming"]
    assert len(gaming) == 1
    assert gaming[0]["id"] == "gamer:juego_activo"
    assert gaming[0]["texto"] == "Street Fighter VI"
    assert gaming[0]["destacado"] is True


# ── 16. Juego activo con ficha: una sola representación ──────────────────────

def test_juego_activo_con_ficha_sin_duplicado(con_perfiles):
    con_perfiles(gamer={
        "juego_activo": "Grim Dawn",
        "juegos": {"Grim Dawn": {"personaje": "Hechicero", "nivel": "45",
                                 "ultima_sesion": _fecha_iso(-1)}},
    })
    secc = {s["id"]: s["elementos"] for s in rm.preparar_secciones()["secciones"]}
    gaming = secc["gaming"]
    assert len(gaming) == 1
    item = gaming[0]
    assert item["id"] == "gamer:grim_dawn"
    assert item["destacado"] is True
    assert item["etiqueta"] == "Grim Dawn"


# ── 17. Ficha histórica de otro juego ────────────────────────────────────────

def test_ficha_historica_otro_juego(con_perfiles):
    con_perfiles(gamer={
        "juego_activo": "Street Fighter VI",
        "juegos": {"Grim Dawn": {"personaje": "Caballero", "ultima_sesion": _fecha_iso(-30)}},
    })
    secc = {s["id"]: s["elementos"] for s in rm.preparar_secciones()["secciones"]}
    gaming = secc["gaming"]
    # Sin ficha del SF6: encabezado destacado + ficha histórica sin destacado.
    assert len(gaming) == 2
    head = gaming[0]
    assert head["id"] == "gamer:juego_activo" and head["destacado"] is True
    hist = gaming[1]
    assert hist["id"] == "gamer:grim_dawn"
    assert hist["destacado"] is False
    assert hist["reciente"] is False


# ── 18. Whitelist de campos gamer ────────────────────────────────────────────

def test_whitelist_campos_gamer(con_perfiles):
    con_perfiles(gamer={
        "juego_activo": "LoL",
        "juegos": {"LoL": {
            "rango": "Oro",           # fuera de whitelist → no debe aparecer
            "notas": "juega los findes",  # fuera de whitelist → no debe aparecer
            "personaje": "main top",
            "nivel": "30",
        }},
    })
    secc = {s["id"]: s["elementos"] for s in rm.preparar_secciones()["secciones"]}
    item = secc["gaming"][0]
    assert "rango" not in item["texto"]
    assert "notas" not in item["texto"]
    assert "Personaje: main top" in item["texto"]
    assert "Nivel: 30" in item["texto"]


# ── 19. Ausencia de datos inventados ─────────────────────────────────────────

def test_ausencia_datos_inventados(con_perfiles):
    con_perfiles(
        usuario={
            "funcional": {"identidad": None, "rutina_uso": 42},
            "vida_personal": [
                {"tema": "", "contenido": "sin tema", "actualizado": _fecha_iso(-1)},
                {"tema": "salud", "contenido": "", "actualizado": _fecha_iso(-1)},
                {"tema": None, "contenido": "tema nulo", "actualizado": _fecha_iso(-1)},
            ],
        },
        mentor={"stack_objetivo": {"frontend": None}},
        gamer={"juego_activo": None, "juegos": {"X": {"personaje": None, "rango": 5}}},
    )
    res = rm.preparar_secciones()
    ids = [e["id"] for s in res["secciones"] for e in s["elementos"]]
    assert ids == []  # nada inventado, nada mostrado como "None"
    assert "None" not in str(res)
    # rutina_uso (int 42) se descarta: no hay ningún elemento ni claves funcionales.
    assert "preferencias_y_rutina" not in [s["id"] for s in res["secciones"]]
    assert "rutina_uso" not in str(res)


def test_sin_exposicion_de_none_en_elementos(con_perfiles):
    con_perfiles(
        usuario={"funcional": {"identidad": "Luis"}},
        gamer={"juego_activo": None, "juegos": {}},
    )
    res = rm.preparar_secciones()
    for s in res["secciones"]:
        for e in s["elementos"]:
            assert e["texto"] != "None"
            assert e["etiqueta"] != "None"
            assert isinstance(e["fecha"], type(None)) or isinstance(e["fecha"], str)


# ── 20. Ausencia de exposición de estructuras internas ───────────────────────

def test_no_exposicion_estructuras_internas(con_perfiles):
    con_perfiles(
        usuario={
            "funcional": {
                "identidad": "Luis",
                "proyecto_actual": "Omni",
                "rutina_uso": "Noche",
                "hardware_relevante": "Doble monitor",
                "preferencias_comunicacion": "Directo",
            },
            "vida_personal": [{"tema": "salud", "contenido": "Detalle", "actualizado": _fecha_iso(-1)}],
        },
        mentor={
            "stack_objetivo": {"frontend": "React"},
            "tecnologias_aprendidas": ["Python"],
            "historial_sesiones": [{"fecha": _fecha_iso(-1), "proximos_pasos": ["x"]}],
        },
        gamer={"juego_activo": "G", "juegos": {"G": {"personaje": "P"}}},
    )
    res = rm.preparar_secciones()
    # Contrato estricto: claves permitidas por nivel.
    assert set(res.keys()) == {"generado", "secciones"}
    for s in res["secciones"]:
        assert set(s.keys()) == {"id", "titulo", "elementos"}
        for e in s["elementos"]:
            assert set(e.keys()) == {"id", "etiqueta", "texto", "fecha", "reciente", "destacado"}
    # No se filtran claves internas de perfiles ni ChromaDB. (Los prefijos
    # "funcional:" / "vida:" son parte del id estable del elemento, no claves crudas.)
    dump = str(res)
    for clave_interna in ("stack_objetivo", "historial_sesiones", "juegos",
                          "proyectos_de_portafolio", "ultima_sesion",
                          "ultimo_avance_registrado", "embedding", "chroma", "snapshot"):
        assert clave_interna not in dump


# ── Texto visible del tema se conserva (sin perder la tilde) ────────────────

def test_tema_visible_preserva_acentos(con_perfiles):
    con_perfiles(usuario={
        "funcional": {},
        "vida_personal": [{"tema": "opinión profesional", "contenido": "Mercado laboral",
                           "actualizado": _fecha_iso(-2)}],
    })
    secc = {s["id"]: s["elementos"] for s in rm.preparar_secciones()["secciones"]}
    item = secc["aprendizaje_y_carrera"][0]
    assert item["etiqueta"] == "opinión profesional"
    assert item["id"] == "vida:opini_n_profesional"  # _slug preserva comportamiento previo