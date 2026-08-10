import re
from urllib.parse import urlparse

FALLO_SIN_RESULTADOS = "No se encontraron resultados relevantes en la web."
FALLO_ERROR_CONEXION = "No se encontraron resultados debido a un error de conexión."


def _extraer_dominio(url: str) -> str:
    """Devuelve el dominio de una URL (ej. 'www.example.com') o vacío si no se puede parsear."""
    if not url:
        return ""
    try:
        netloc = urlparse(url).netloc
        return netloc if netloc else url
    except Exception:
        return url


def _formatear_resultado(r: dict, indice: int) -> str:
    """
    Formatea un resultado de DuckDuckGo incluyendo: número, fecha, título,
    dominio, URL y snippet. NO descarta URL ni dominio.
    """
    titulo = (r.get('title') or 'Sin título').strip()
    resumen = (r.get('body', r.get('snippet', 'Sin resumen')) or 'Sin resumen').strip()
    url = (r.get('href') or '').strip()
    fecha = r.get('date', r.get('published', r.get('date_utc', ''))) or ''

    dominio = _extraer_dominio(url)

    cabecera = f"[{indice}] 📅 {fecha} | {titulo}" if fecha else f"[{indice}] 📄 {titulo}"
    linea_fuente = f"🌐 Fuente: {dominio}" + (f" — {url}" if url else " (sin URL)")
    return f"{cabecera}\n{linea_fuente}\n{resumen}\n"


def buscar_en_internet(consulta: str, reciente: bool = False) -> str:
    """
    Busca en DuckDuckGo y devuelve un string con resultados: número, fecha,
    título, dominio, URL y resumen.

    Args:
        consulta:  Término de búsqueda. NO incluir filtros tipo 'after:YYYY-MM-DD'
                   (no son soportados por DuckDuckGo). Para info reciente, usar
                   el parámetro `reciente=True` o incluir el año en la consulta.
        reciente:  Si True, limita los resultados al último año usando el parámetro
                   nativo de DDGS (timelimit='y'). Por defecto False.

    Returns:
        String con los resultados formateados, o un mensaje de error/sin resultados.
    """
    # Limpiar filtros de fecha tipo Google que rompen la búsqueda en DuckDuckGo
    consulta_limpia = re.sub(r'\bafter:\d{4}-\d{2}-\d{2}\b', '', consulta).strip()
    consulta_limpia = re.sub(r'\bbefore:\d{4}-\d{2}-\d{2}\b', '', consulta_limpia).strip()
    consulta_limpia = re.sub(r'\s+', ' ', consulta_limpia).strip()

    print(f"🌐 [INTERNET REAL] Buscando: '{consulta_limpia}' (reciente={reciente})...")

    try:
        from ddgs import DDGS
    except ImportError:
        return "Error: Falta instalar la librería ddgs. Ejecutá: pip install ddgs"

    def _ejecutar_busqueda(ddgs, query: str, timelimit=None, max_results: int = 6) -> list:
        """Intenta la búsqueda y devuelve lista de resultados o lista vacía."""
        try:
            kwargs = {"max_results": max_results}
            if timelimit:
                kwargs["timelimit"] = timelimit
            return list(ddgs.text(query, **kwargs))
        except Exception as e:
            print(f"⚠️ Error en búsqueda DDGS: {e}")
            return []

    try:
        with DDGS() as ddgs:
            # ── Intento 1: con filtro de tiempo si se pidió info reciente ──────
            timelimit = 'y' if reciente else None
            results = _ejecutar_busqueda(ddgs, consulta_limpia, timelimit=timelimit)

            # ── Intento 2 (retry): sin filtro de tiempo si no hubo resultados ──
            if not results and reciente:
                print("🔄 Sin resultados con filtro anual, reintentando sin límite de tiempo...")
                results = _ejecutar_busqueda(ddgs, consulta_limpia, timelimit=None)

            # ── Intento 3 (retry): consulta simplificada (primeras 4 palabras) ─
            if not results:
                palabras = consulta_limpia.split()
                if len(palabras) > 4:
                    consulta_simple = " ".join(palabras[:4])
                    print(f"🔄 Reintentando con consulta simplificada: '{consulta_simple}'...")
                    results = _ejecutar_busqueda(ddgs, consulta_simple, timelimit=timelimit)

            if results:
                resultados_formateados = [
                    _formatear_resultado(r, i + 1) for i, r in enumerate(results)
                ]
                return "\n".join(resultados_formateados)

            return FALLO_SIN_RESULTADOS

    except Exception as e:
        print(f"⚠️ Error interno en DuckDuckGo Search: {e}")
        return FALLO_ERROR_CONEXION