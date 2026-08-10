from modulos.senal_web import (
    OcultadorStreamWeb,
    fusionar_comando_busqueda,
    limpiar_respuesta_web,
    parsear_senal_web,
    texto_marcador_tema_web_anterior,
)
from modulos.prompts import obtener_prompt_general


# ── Parsea de la señal estructurada ──────────────────────────────────────────

def test_parsea_decision_si_con_consulta():
    senal = parsear_senal_web(
        "El agente de código más usado sigue siendo similar a los anteriores.\n"
        "[WEB: SI]\n[CONSULTA: ranking de agentes de código IA 2026]"
    )
    assert senal['tipo'] == 'SI'
    assert senal['consulta'] == "ranking de agentes de código IA 2026"


def test_parsea_decision_no():
    senal = parsear_senal_web("Es una explicación conceptual.\n[WEB: NO]")
    assert senal['tipo'] == 'NO'
    assert senal['consulta'] is None


def test_ausencia_de_senal_es_ninguna():
    senal = parsear_senal_web("Respuesta normal sin señal alguna.")
    assert senal['tipo'] == 'ninguna'
    assert senal['consulta'] is None


def test_respuesta_limpia_sin_etiquetas():
    senal = parsear_senal_web(
        "Texto visible.\n[WEB: SI]\n[CONSULTA: algo]"
    )
    assert "WEB" not in senal['respuesta_limpia']
    assert "CONSULTA" not in senal['respuesta_limpia']
    assert "Texto visible." in senal['respuesta_limpia']


def test_limpiar_respuesta_aplica_a_salida_de_segunda_generacion():
    # La 2ª generación recibe el mismo contexto de sistema (con el protocolo)
    # y POR ESO puede volver a emitir la señal al final. `limpiar_respuesta_web`
    # es lo que sanea esa salida antes de UI/TTS/persistencia.
    salida_segunda_gen = (
        "Según las fuentes, no pude confirmar el tercer puesto.\n"
        "[WEB: NO]"
    )
    limpia = limpiar_respuesta_web(salida_segunda_gen)
    assert "[WEB" not in limpia
    assert "[CONSULTA" not in limpia
    assert "no pude confirmar el tercer puesto" in limpia


def test_limpiar_no_rompe_salida_con_tema_nuevo_tipo_no():
    salida = "Respuesta normal.\n[WEB: SI]\n[CONSULTA: otro dato]"
    limpia = limpiar_respuesta_web(salida)
    assert limpia == "Respuesta normal."


def test_consulta_autocontenida_sin_cuatros_ni_llaves():
    senal = parsear_senal_web(
        "[WEB: SI]\n[CONSULTA: <quién es el campeón de la Last Chance Qualifier de SF6>]"
    )
    assert senal['consulta'] == "quién es el campeón de la Last Chance Qualifier de SF6"


# ── Fusión con el comando legacy `buscar:` ───────────────────────────────────

def test_si_con_consulta_proporciona_la_consulta():
    comando, warning = fusionar_comando_busqueda(
        {'tipo': 'SI', 'consulta': 'ranking 2026'}, "buscar: ranking 2026"
    )
    assert comando == "ranking 2026"
    assert warning is None


def test_si_sin_consulta_cae_al_legacy():
    comando, warning = fusionar_comando_busqueda(
        {'tipo': 'SI', 'consulta': None}, "buscar: ranking 2026"
    )
    assert comando == "buscar: ranking 2026"
    assert warning is not None


def test_no_sin_legacy_no_busca():
    comando, warning = fusionar_comando_busqueda({'tipo': 'NO', 'consulta': None}, None)
    assert comando is None
    assert warning is None


def test_no_con_legacy_conserva_legacy_transicion():
    comando, warning = fusionar_comando_busqueda(
        {'tipo': 'NO', 'consulta': None}, "buscar: algo"
    )
    assert comando == "buscar: algo"
    assert warning is not None


def test_sin_senal_usa_legacy_como_siempre():
    comando, warning = fusionar_comando_busqueda({'tipo': 'ninguna', 'consulta': None}, "buscar: algo")
    assert comando == "buscar: algo"
    assert warning is None


# ── Ocultador de streaming ───────────────────────────────────────────────────

def test_oculta_senal_partida_entre_chunks():
    ocultador = OcultadorStreamWeb()
    visible = ocultador.procesar("Explicación.\n[WE")
    assert visible == "Explicación.\n"
    visible = ocultador.procesar("B: SI]\n[CONSULTA: consulta]")
    assert visible == ""
    assert ocultador.finalizar() == ""


def test_ocultador_deja_pasar_texto_normal():
    ocultador = OcultadorStreamWeb()
    visible = ocultador.procesar("Hola mundo\n")
    assert visible == "Hola mundo\n"


def test_ocultador_descarta_la_ultima_linea_si_es_senal():
    ocultador = OcultadorStreamWeb()
    visible = ocultador.procesar("Texto.\n[WEB: NI")
    assert visible == "Texto.\n"
    assert ocultador.finalizar() == ""


# ── Marcador de herencia temática ────────────────────────────────────────────

def test_marcador_instruye_obligacion_condicionada():
    texto = texto_marcador_tema_web_anterior()
    assert "TEMA WEB ANTERIOR" in texto
    assert "ES CONTINUACIÓN DE ESE MISMO TEMA" in texto
    assert "NO heredes esta" in texto


# ── Protocolo presente en el prompt general ──────────────────────────────────

def test_prompt_general_incluye_protocolo_web_senal():
    prompt = obtener_prompt_general(
        fecha_hoy="sábado, 8 de agosto de 2026",
        ruta_home=r"C:\Users\luism",
        ventanas_abiertas="",
        texto_workspace="",
        texto_snapshot="",
        texto_doc_volatil="",
    )
    assert "[WEB: SI]" in prompt
    assert "[WEB: NO]" in prompt
    assert "AUTOCONTENIDA" in prompt