# Ejemplos de uso de la Skill de Búsqueda Web Actualizada

## Ejemplo 1: Cotización del dólar
**Usuario:** "¿A cuánto está el dólar hoy?"
**Skill activa:** Sí (palabra clave "hoy").
**Acción:** 
  1. Consulta construida: `"cotización dólar blue junio 2026"` (sin filtros `after:`/`before:`, año en el texto).
  2. Resultados de DuckDuckGo (ejemplo): 
     - Título: "Dólar blue hoy: a cuánto cotiza este 23 de junio"
       Fecha: 23/06/2026, Resumen: "El dólar blue sube a $1.450"
     - Título: "Cotización del dólar oficial y MEP"
       Fecha: 22/06/2026, Resumen: "..."
  3. Respuesta: "El dólar blue hoy (23/06/2026) cotiza a $1.450. Fuente: [Título] ([dominio]), publicado [fecha]."

## Ejemplo 2: Lanzamiento de un juego
**Usuario:** "¿Cuándo sale GTA 6?"
**Skill activa:** Sí (tema de lanzamiento).
**Acción:**
  1. Consulta: `"GTA 6 fecha de lanzamiento 2026"`.
  2. Resultados: prioriza los más recientes y las fuentes oficiales (la propia desarrolladora).
  3. Respuesta: "Según la fuente más reciente (Rockstar Games, [dominio], [fecha]), GTA 6 se lanzará en otoño de 2026."

## Ejemplo 3: Noticias de tecnología
**Usuario:** "¿qué pasó en IA esta semana?"
**Skill activa:** Sí ("esta semana").
**Acción:**
  1. Consulta: `"noticias de IA recientes 2026"`
  2. Resultados: noticias de la última semana.
  3. Respuesta: resumen de los 3 titulares más relevantes con fechas y fuentes.

## Ejemplo 4: Resultado deportivo incompleto (NO completar espacios)
**Usuario:** "¿cómo quedó el podio de Street Fighter 6?"
**Skill activa:** Sí (tema deportivo reciente).
**Acción:**
  1. Consulta: `"podio Street Fighter 6 resultado 2026"`
  2. Los resultados confirman oro y plata, pero ninguna fuente menciona el bronce.
  3. Respuesta correcta:
     - 🥇 Oro: MenaRD (fuente: [dominio], [fecha])
     - 🥈 Plata: A (fuente: [dominio], [fecha])
     - 🥉 Bronce: No pude confirmarlo con las fuentes encontradas.
  4. NO se inventa el tercer puesto.

## Ejemplo 5: Información general (sin skill)
**Usuario:** "¿Qué es la inteligencia artificial?"
**Skill activa:** No (tema atemporal).
**Acción:** Busca normalmente sin filtros de fecha.
**Respuesta:** Definición y conceptos clave, sin necesidad de actualidad.

## Ejemplo 6: Follow-up con consulta autocontenida
**Turno 1 — Usuario:** "¿Cuál fue el podio de Street Fighter 6?"
**Skill activa:** Sí (tema deportivo reciente).
**Acción:**
  1. Consulta: `"podio Street Fighter 6 2026"`.
  2. Búsqueda → segunda generación (con la evidencia y las reglas) → respuesta verificada con fuentes.

**Turno 2 — Usuario:** "¿Y el tercero?"
**Acción:**
  1. La referencia "el tercero" se resuelve usando la conversación anterior: tercer puesto del podio de Street Fighter 6.
  2. Consulta AUTOCONTENIDA emitida: `"tercer puesto del podio de Street Fighter 6 2026"` — NO `"el tercero"`.
  3. La segunda generación recibe la evidencia de la búsqueda anterior más la evidencia nueva, y responde solo con lo que las fuentes confirmen (si ninguna fuente confirma el tercer puesto, dice "No pude confirmarlo con las fuentes encontradas").