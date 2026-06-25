# Instrucciones para Búsqueda Web Actualizada

**REGLA OBLIGATORIA:**  
Cuando esta skill esté activa, DEBES usar la función local `buscar_en_internet(consulta)` para obtener información de internet.  
**NO USES `mcp_buscar_en_boveda` ni ninguna herramienta MCP para buscar en internet.** Esa herramienta solo busca en la memoria local, no en la web.

---

## Pasos a seguir

1. **Analiza la consulta** y determina si necesita información reciente (noticias, eventos, precios, lanzamientos, campeonatos, etc.).

2. **Construye la consulta** para DuckDuckGo:
   - **NO uses filtros `after:YYYY-MM-DD` ni `before:YYYY-MM-DD`**. DuckDuckGo no los soporta y arruinan la búsqueda.
   - En cambio, **incluí el año directamente en la consulta** cuando necesites info reciente.
   - Ejemplos correctos:
     - ✅ `"campeón Capcom Pro Tour Street Fighter 6 2025"`
     - ✅ `"cotización dólar blue junio 2026"`
     - ✅ `"lanzamiento GTA 6 fecha 2026"`
     - ❌ `"campeón CPT" after:2025-01-01`  ← esto NO funciona en DuckDuckGo

3. **Ejecuta la búsqueda** emitiendo el comando:
   ```
   buscar: <tu consulta>
   ```
   El sistema ejecutará `buscar_en_internet()` automáticamente con esa consulta.

4. **Analiza los resultados** devueltos. Si aparecen fechas (📅), priorizá los más recientes. Si no hay fechas, evaluá la relevancia por el contenido.

5. **Responde** al usuario con la información encontrada, mencionando la fuente y fecha si están disponibles.

---

## Si no hay resultados útiles

- Indicalo claramente: "No encontré información reciente sobre esto."
- Sugerí al usuario afinar la búsqueda con términos más específicos o un sitio concreto.
- No inventes datos ni uses tu conocimiento interno como si fuera actual.

---

## Recordatorio clave

Tu objetivo es proporcionar información actualizada de la web, **no de tu memoria de entrenamiento**.  
Si la consulta es claramente sobre algo reciente (campeonato, precio, noticia), siempre buscá antes de responder.