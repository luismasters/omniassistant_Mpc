# Ejemplos de uso de la Skill de Búsqueda Web Actualizada

## Ejemplo 1: Cotización del dólar
**Usuario:** "¿A cuánto está el dólar hoy?"
**Skill activa:** Sí (palabra clave "hoy").
**Acción:** 
  1. Consulta construida: `"cotización dólar" after:2026-06-23`
  2. Resultados de DuckDuckGo (ejemplo): 
     - Título: "Dólar blue hoy: a cuánto cotiza este 23 de junio"
       Fecha: 23/06/2026, Resumen: "El dólar blue sube a $1.450"
     - Título: "Cotización del dólar oficial y MEP"
       Fecha: 22/06/2026, Resumen: "..."
  3. Respuesta: "El dólar blue hoy (23/06/2026) cotiza a $1.450. Fuente: [Título], publicado hoy."

## Ejemplo 2: Lanzamiento de un juego
**Usuario:** "¿Cuándo sale GTA 6?"
**Skill activa:** Sí (tema de lanzamiento).
**Acción:**
  1. Consulta: `"GTA 6 lanzamiento" after:2025-01-01`
  2. Resultados: prioriza los más recientes.
  3. Respuesta: "Según la fuente más reciente (Rockstar Games, 22/06/2026), GTA 6 se lanzará en otoño de 2026."

## Ejemplo 3: Noticias de tecnología
**Usuario:** "¿Qué pasó en IA esta semana?"
**Skill activa:** Sí ("esta semana").
**Acción:**
  1. Consulta: `"IA noticias" week`
  2. Resultados: noticias de la última semana.
  3. Respuesta: resumen de los 3 titulares más relevantes con fechas.

## Ejemplo 4: Información general (sin skill)
**Usuario:** "¿Qué es la inteligencia artificial?"
**Skill activa:** No (tema atemporal).
**Acción:** Busca normalmente sin filtros de fecha.
**Respuesta:** Definición y conceptos clave, sin necesidad de actualidad.