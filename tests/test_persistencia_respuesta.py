from modulos.mensajes_web import armar_mensaje_modelo_persistido


def test_sin_busqueda_web_borrador_es_la_respuesta_del_turno():
    mensaje = armar_mensaje_modelo_persistido("Respuesta del borrador (sin web)")
    assert mensaje == {'role': 'model', 'parts': ["Respuesta del borrador (sin web)"]}


def test_con_segunda_generacion_la_final_es_la_unica_persistida():
    mensaje = armar_mensaje_modelo_persistido(
        "Borrador posiblemente incorrecto.",
        "Respuesta final verificada con fuentes.",
    )
    assert mensaje == {'role': 'model', 'parts': ["Respuesta final verificada con fuentes."]}


def test_el_borrador_no_se_duplica_ni_se_mezcla_en_la_final():
    borrador = "Borrador: el bronce fue C."
    final = "No pude confirmarlo con las fuentes."
    mensaje = armar_mensaje_modelo_persistido(borrador, final)
    assert len(mensaje['parts']) == 1
    assert mensaje['parts'][0] == final
    assert "borrador" not in mensaje['parts'][0]
    assert "C." not in mensaje['parts'][0]


def test_la_final_reemplaza_al_borrador_para_la_persistencia():
    borrador = "Dato inventado: bronce = Antonelli."
    final = "Según las fuentes: el tercer puesto no aparece confirmado."
    mensaje = armar_mensaje_modelo_persistido(borrador, final)
    assert 'parts' in mensaje
    assert mensaje['parts'] == [final]
    assert borrador != mensaje['parts'][0]


def test_fallback_cuando_la_segunda_generacion_falla_o_queda_vacia():
    # Si la segunda generación falla, se conserva el borrador como respuesta del turno.
    assert armar_mensaje_modelo_persistido("Borrador", "") == {'role': 'model', 'parts': ["Borrador"]}
    assert armar_mensaje_modelo_persistido("Borrador", None) == {'role': 'model', 'parts': ["Borrador"]}


def test_respuesta_preliminar_no_domine_cuando_existe_final():
    final = "Dato verificado."
    mensaje = armar_mensaje_modelo_persistido("Dato incorrecto anterior del borrador", final)
    assert mensaje == {'role': 'model', 'parts': [final]}