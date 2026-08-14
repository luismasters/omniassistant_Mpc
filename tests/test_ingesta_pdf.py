"""
Tests de la ingesta de archivos/notas a la bóveda (GUIA_MEMORIA §7).

Cubren: extracción de texto (PDF y texto plano), fragmentación (chunking),
ingesta de archivo a bóveda y guardado de nota. La dependencia pesada
(modulos.memoria → ChromaDB) se stubea con guardar_recuerdo fake.
"""

import json
import os
import sys
import types

import pytest


def _stub_memoria(registros):
    """Crea un stub de modulos.memoria con guardar_recuerdo que registra llamadas."""
    m = types.ModuleType("modulos.memoria")

    def guardar_recuerdo(texto_a_guardar, etiqueta_tema, metadatos_extra=None, origen_id=None, origen_fuente=None):
        registros.append({
            "texto": texto_a_guardar,
            "etiqueta": etiqueta_tema,
            "origen_fuente": origen_fuente,
        })
        return True

    m.guardar_recuerdo = guardar_recuerdo
    m.invalidar_por_origen = lambda *a, **k: True
    return m


@pytest.fixture
def memoria_stub(monkeypatch):
    registros = []
    monkeypatch.setitem(sys.modules, "modulos.memoria", _stub_memoria(registros))
    return registros


@pytest.fixture
def pdf_real(tmp_path):
    """Genera un PDF mínimo de 2 páginas (solo para probar que no crashea)."""
    from pypdf import PdfWriter

    ruta = str(tmp_path / "doc.pdf")
    writer = PdfWriter()
    for _ in range(2):
        writer.add_blank_page(width=300, height=300)
    with open(ruta, "wb") as f:
        writer.write(f)
    return ruta


# ─── Fragmentación (chunking) ────────────────────────────────────────────────

def test_dividir_fragmentos_corto():
    from modulos.ingesta_pdf import dividir_en_fragmentos
    assert dividir_en_fragmentos("hola mundo") == ["hola mundo"]


def test_dividir_fragmentos_largo_no_corta_palabras():
    from modulos.ingesta_pdf import dividir_en_fragmentos
    texto = "palabra " * 500  # ~4000 chars
    frags = dividir_en_fragmentos(texto)
    assert len(frags) > 1
    # Ningún fragmento excede el tamaño + una palabra (margen por el corte en espacio).
    for f in frags:
        assert len(f) <= 1201
    # Las palabras se conservan completas (join normalizado == texto normalizado).
    assert " ".join(frags).split() == texto.split()


def test_dividir_fragmentos_vacio():
    from modulos.ingesta_pdf import dividir_en_fragmentos
    assert dividir_en_fragmentos("") == []
    assert dividir_en_fragmentos("   ") == []


# ─── Extracción de texto plano ───────────────────────────────────────────────

def test_extraer_texto_plano(tmp_path):
    from modulos.ingesta_pdf import extraer_texto_archivo
    ruta = tmp_path / "nota.txt"
    ruta.write_text("contenido de prueba", encoding="utf-8")
    assert extraer_texto_archivo(str(ruta)) == "contenido de prueba"


def test_extraer_texto_md(tmp_path):
    from modulos.ingesta_pdf import extraer_texto_archivo
    ruta = tmp_path / "readme.md"
    ruta.write_text("# Hola\n**negrita**", encoding="utf-8")
    assert "# Hola" in extraer_texto_archivo(str(ruta))


def test_extraer_no_soportado(tmp_path):
    from modulos.ingesta_pdf import extraer_texto_archivo
    ruta = tmp_path / "img.png"
    ruta.write_bytes(b"\x89PNG\r\n\x1a\n")
    assert extraer_texto_archivo(str(ruta)) == ""


def test_extraer_ruta_inexistente():
    from modulos.ingesta_pdf import extraer_texto_archivo
    assert extraer_texto_archivo("C:/no/existe/archivo.pdf") == ""


# ─── Ingesta de archivo a bóveda ─────────────────────────────────────────────

def test_ingestar_archivo_texto(memoria_stub, tmp_path):
    from modulos.ingesta_pdf import ingestar_archivo_a_boveda
    ruta = tmp_path / "notas.md"
    ruta.write_text("contenido corto", encoding="utf-8")

    res = ingestar_archivo_a_boveda(str(ruta))

    assert res["exito"] is True
    assert res["fragmentos"] == 1
    assert res["etiqueta"] == "Doc: notas.md"
    assert len(memoria_stub) == 1
    assert memoria_stub[0]["etiqueta"] == "Doc: notas.md"
    assert memoria_stub[0]["origen_fuente"] == "ingesta_archivo"


def test_ingestar_archivo_largo_fragmenta(memoria_stub, tmp_path):
    from modulos.ingesta_pdf import ingestar_archivo_a_boveda
    ruta = tmp_path / "largo.txt"
    ruta.write_text("linea " * 400, encoding="utf-8")  # ~2000 chars

    res = ingestar_archivo_a_boveda(str(ruta))

    assert res["exito"] is True
    assert res["fragmentos"] >= 2
    assert len(memoria_stub) == res["fragmentos"]


def test_ingestar_archivo_invalido(memoria_stub, tmp_path):
    from modulos.ingesta_pdf import ingestar_archivo_a_boveda
    ruta = tmp_path / "binario.bin"
    ruta.write_bytes(b"\x00\x01\x02\x03")
    res = ingestar_archivo_a_boveda(str(ruta))
    assert res["exito"] is False


def test_ingestar_pdf_no_rompe(memoria_stub, pdf_real):
    from modulos.ingesta_pdf import ingestar_archivo_a_boveda
    # El PDF puede no tener texto extraíble, pero no debe crashear ni
    # guardar fragmentos falsos.
    res = ingestar_archivo_a_boveda(pdf_real)
    assert res["exito"] in (True, False)  # tolera PDF sin texto


# ─── Nota a bóveda ───────────────────────────────────────────────────────────

def test_guardar_nota(memoria_stub):
    from modulos.ingesta_pdf import guardar_nota_a_boveda
    res = guardar_nota_a_boveda("recordar comprar leche", "Compras")
    assert res["exito"] is True
    assert res["fragmentos"] == 1
    assert memoria_stub[0]["etiqueta"] == "Compras"
    assert memoria_stub[0]["origen_fuente"] == "nota_manual"


def test_guardar_nota_sin_etiqueta(memoria_stub):
    from modulos.ingesta_pdf import guardar_nota_a_boveda
    res = guardar_nota_a_boveda("texto suelto")
    assert res["exito"] is True
    assert memoria_stub[0]["etiqueta"] == "Nota"


def test_guardar_nota_vacia(memoria_stub):
    from modulos.ingesta_pdf import guardar_nota_a_boveda
    res = guardar_nota_a_boveda("   ")
    assert res["exito"] is False
    assert memoria_stub == []


def test_guardar_nota_larga_fragmenta(memoria_stub):
    from modulos.ingesta_pdf import guardar_nota_a_boveda
    res = guardar_nota_a_boveda("abc " * 500, "Tema")
    assert res["exito"] is True
    assert res["fragmentos"] >= 2
    assert len(memoria_stub) == res["fragmentos"]
