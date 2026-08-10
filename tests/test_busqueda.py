from modulos.busqueda import _formatear_resultado, _extraer_dominio


# ── _extraer_dominio ─────────────────────────────────────────────────────

def test_extraer_dominio_url_comun():
    assert _extraer_dominio("https://www.example.com/art/123") == "www.example.com"


def test_extraer_dominio_subdominio():
    assert _extraer_dominio("https://news.mydomain.org/x") == "news.mydomain.org"


def test_extraer_dominio_vacio():
    assert _extraer_dominio("") == ""


def test_extraer_dominio_url_invalida_no_rompe():
    assert _extraer_dominio("no-es-una-url") == "no-es-una-url"


# ── _formatear_resultado ─────────────────────────────────────────────────

def test_resultado_incluye_numero_fecha_titulo_dominio_url_y_snippet():
    r = {
        "title": "Dólar blue hoy, 23 de junio",
        "href": "https://www.ejemplo.com/nota/1",
        "body": "El dólar blue sube a $1.450.",
        "date": "2026-06-23",
    }
    out = _formatear_resultado(r, 1)
    assert "[1]" in out
    assert "2026-06-23" in out
    assert "Dólar blue hoy" in out
    assert "www.ejemplo.com" in out
    assert "https://www.ejemplo.com/nota/1" in out
    assert "El dólar blue sube a $1.450." in out
    assert "📅" in out


def test_resultado_sin_url_avisa_y_rompe():
    r = {"title": "Título solo", "body": "Resumen", "date": ""}
    out = _formatear_resultado(r, 2)
    assert "[2]" in out
    assert "sin URL" in out
    assert "Resumen" in out
    assert "📄" in out
    assert "📅" not in out


def test_resultado_sin_fecha_no_crashea():
    r = {"title": "Título", "body": "Resumen"}
    out = _formatear_resultado(r, 3)
    assert out.startswith("[3]")
    assert "📄" in out