import re


def buscar_en_internet(consulta: str, reciente: bool = False) -> str:
    """
    Busca en DuckDuckGo y devuelve un string con resultados y fechas si están disponibles.

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

    def _formatear_resultado(r: dict) -> str:
        titulo = r.get('title', 'Sin título')
        resumen = r.get('body', r.get('snippet', 'Sin resumen'))
        fecha = r.get('date', r.get('published', r.get('date_utc', '')))
        if fecha:
            return f"📅 {fecha} | {titulo}\n{resumen}\n"
        return f"📄 {titulo}\n{resumen}\n"

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
                resultados_formateados = [_formatear_resultado(r) for r in results]
                return "".join(resultados_formateados)

            return "No se encontraron resultados relevantes en la web."

    except Exception as e:
        print(f"⚠️ Error interno en DuckDuckGo Search: {e}")
        return "No se encontraron resultados debido a un error de conexión."