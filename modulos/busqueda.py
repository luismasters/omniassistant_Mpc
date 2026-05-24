def buscar_en_internet(consulta):
    """Busca en DuckDuckGo y devuelve un string con los resultados."""
    print(f"🌐 [INTERNET REAL] Buscando información sobre: '{consulta}'...")
    try:
        from ddgs import DDGS
        resultados_texto = []
        with DDGS() as ddgs:
            resultados = ddgs.text(consulta, max_results=3)
            
            if resultados:
                for r in resultados:
                    titulo = r.get('title', 'Sin título')
                    resumen = r.get('body', r.get('snippet', 'Sin resumen'))
                    resultados_texto.append(f"Título: {titulo}\nResumen: {resumen}\n")
        
        if resultados_texto:
            return "\n".join(resultados_texto)
        return "No se encontraron resultados relevantes en la web."
        
    except ImportError:
        return "Error: Falta instalar la librería ddgs. Ejecutá: pip install ddgs"
    except Exception as e:
        print(f"⚠️ Error interno en DuckDuckGo Search: {e}")
        return "No se encontraron resultados debido a un error de conexión."