from modulos.mensajes_web import decidir_contenido_presentacion


def test_sin_busqueda_el_borrador_es_la_respuesta_directa():
    tipo, texto = decidir_contenido_presentacion("Respuesta del streaming (sin web)", "")
    assert tipo == "directa"
    assert texto == "Respuesta del streaming (sin web)"


def test_con_busqueda_la_respuesta_verificada_reemplaza():
    tipo, texto = decidir_contenido_presentacion(
        "El bronce fue C.", "No pude confirmarlo con las fuentes encontradas."
    )
    assert tipo == "verificada"
    assert texto == "No pude confirmarlo con las fuentes encontradas."


def test_la_final_no_se_concatena_con_el_borrador():
    borrador = "El oro fue A, la plata B y el bronce C..."
    final = "Según las fuentes, no hay confirmación del podio completo."
    _, texto = decidir_contenido_presentacion(borrador, final)
    assert texto == final
    assert "oro fue A" not in texto
    assert "C..." not in texto


def test_si_la_segunda_generacion_queda_vacia_se_mantiene_el_borrador():
    tipo, texto = decidir_contenido_presentacion("Borrador sin verificar", "")
    assert tipo == "directa"
    assert texto == "Borrador sin verificar"
    tipo, texto = decidir_contenido_presentacion("Borrador sin verificar", None)
    assert tipo == "directa"
    assert texto == "Borrador sin verificar"


def test_flujo_normal_con_respuesta_de_una_vuelta_no_requiere_reemplazo():
    # Sin búsqueda web: el streaming existente presenta la respuesta tal cual.
    tipo, texto = decidir_contenido_presentacion("Respuesta normal", "")
    assert tipo == "directa"
    assert "Respuesta normal" in texto