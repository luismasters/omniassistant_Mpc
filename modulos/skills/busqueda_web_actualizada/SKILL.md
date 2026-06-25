# Skill: Búsqueda Web Actualizada

**Descripción:**  
Permite a Argus buscar información en internet con prioridad en resultados recientes, filtrando por fecha y validando la antigüedad de las fuentes. Esta skill asegura que la información proporcionada sea lo más actualizada posible, especialmente para noticias, eventos, precios y tendencias.

**Cuándo usar esta Skill:**  
- Cuando el usuario pregunte sobre noticias, eventos, precios, lanzamientos, o cualquier tema que requiera información actualizada.
- Cuando el usuario especifique fechas (ej. "este año", "2025", "últimos 6 meses").
- Cuando el usuario exprese dudas sobre la actualidad de la información (ej. "¿esto sigue vigente?").
- Cuando la pregunta contenga palabras como: actual, hoy, reciente, último, nueva, 2026, noticias, cotización, precio, lanzamiento, estreno, cambio, novedad, tendencia.

**Contexto requerido:**  
- La fecha actual (se obtiene automáticamente del sistema).
- La consulta de búsqueda que quiere hacer el usuario.

**Herramientas que usa:**  
- `buscar_en_internet(consulta)` (existente en modulos/busqueda.py)
- Análisis de fechas en los resultados (post-procesamiento).

**Versión:** 1.0
**Autor:** Luis
**Fecha de creación:** 2026-06-23