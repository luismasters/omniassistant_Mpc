# GUIA_MEMORIA.md

Guía de la memoria de Argus: cómo funciona y cómo sacarle provecho.

Si querés el detalle de implementación (contratos, tests que los fijan), este documento
resume la arquitectura real del código; para profundizar mira `modulos/memoria.py`,
`modulos/recuperador_memoria.py`, `modulos/resumen_memoria.py`, `modulos/perfil_usuario.py`
y `ARQUITECTURA_VERIFICACION_WEB.md`.

---

## 1. La idea en una imagen

Pensá la memoria de Argus como dos lugares separados, igual que tu cabeza:

- **La conversación de ahora** (memoria de trabajo): como la "memoria RAM" de una PC. Vive
  mientras la app está abierta, y se pierde si se cierra. Ahí está lo que se dijo en la charla
  actual. Máximo 25 mensajes por turno (se recorta lo más viejo).
- **La bóveda y los perfiles** (memoria a largo plazo): como el "disco". Quedan guardados en
  archivos del proyecto y sobreviven a reinicios. Ahí está todo lo que Argus "aprende" de vos
  y de tus proyectos.

Todo es **local**: no sale a ningún servidor externo. Los datos viven en archivos JSON y en
una base de datos vectorial `ChromaDB` dentro del repo.

---

## 2. Las capas de memoria

| Capa | Qué guarda | Dónde vive | Sobrevive al reinicio |
|------|------------|------------|----------------------|
| Contexto conversacional | Los mensajes del chat actual | `config.estado.contexto_chat` (RAM), aislado por modo | No |
| Bóveda (memoria libre) | Recuerdos sueltos con embeddings | `modulos/boveda_memoria/` (ChromaDB) | Sí |
| Perfiles | Quién sos vos, tu aprendizaje, tu juego | `perfil_*.json` en la raíz + ChromaDB | Sí |
| Memoria de proyecto | Estado de tus archivos/código | `PROJECT_STATE.md`, `documento_volatil`, watchdog | Sí (regenerable) |
| Evidencia web | Snippets de búsquedas recientes | `config.estado.evidencia_web` (RAM), máx 3, FIFO | No |
| Olvidos | Tombstones: qué NO recordar | `olvidos.json` | Sí |

### 2.1 Contexto conversacional (corto plazo)

- Cada modo (general, mentor, gamer) mantiene **su propia** conversación en memoria:
  `_contextos_por_modo`. Cambiás de modo → arrancás "fresco" aunque cambies de vuelta después.
- El contexto de chat **no se persiste en disco**: al cerrar la app se pierde. Los perfiles se
  extraen de él ANTES de perderlo (ver 2.3).
- Es seguro pedirle "olvidate de esta conversación" / "uniformar contexto": se borra la RAM sin
  tocar bóveda ni perfiles.

### 2.2 Bóveda: la memoria a largo plazo con embeddings

- Es una base **vectorial** ChromaDB (carpeta `modulos/boveda_memoria/`, colección
  `contexto_general`) que usa el modelo de embeddings `all-MiniLM-L6-v2`.
- Cada recuerdo se guarda como texto con su vector. El "vector" es una representación numérica
  del significado: permite buscar **por sentido**, no por palabra exacta.
- **Cómo se guarda** (dos caminos):
  - **Explícito, por vos:** cuando le decís *"acordate de que..."*, *"guardá esto..."* o
    *"no te olvides que..."*, el modelo llama `mcp_guardar_en_boveda` y guarda el dato con
    etiqueta `Memoria_IA`.
  - **Automático, por el sistema:** la extracción pasiva de perfil (ver 2.3) guarda datos
    relevantes con etiquetas temáticas mientras conversás, sin que el modelo lo decida en vivo.
- **Cómo se recupera:**
  - **Búsqueda explícita:** si preguntás algo, el modelo puede usar `mcp_buscar_en_boveda` para
    consultar la bóveda.
  - **Recuperación automática (Fase 4):** en `modulos/recuperador_memoria.py`. Cada mensaje,
    antes de responder, se calcula qué recuerdos de la bóveda son relevantes para lo que decís y
    se inyectan al prompt del sistema. Filtra por similitud (`sim = 1 - distancia` >= umbral
    `MEMORIA_SCORE_MIN`), **excluye lo olvidado**, deduplica por id, ordena por relevancia y
    antigüedad, y recorta el bloque a un máximo de caracteres. Si nada supera el umbral, no se
    inyecta nada.
- Para inspeccionarla a mano hay un CLI: `python gestor_boveda.py`.

> Nota técnica: el modelo de embeddings se descarga de internet la **primera** vez que se usa
> (por eso los tests no importan `modulos.memoria` directamente: lo stubean para no depender de
> la red).

### 2.3 Perfiles: la "imagen de largo plazo" de vos y tus proyectos

- Archivos `perfil_usuario.json` (identidad, proyecto actual, hardware, preferencias, rutina),
  `perfil_mentor.json` (objetivo de aprendizaje, stack, historial de sesiones) y
  `perfil_gamer.json` (juego activo, personaje, nivel, build).
- **Se extraen con IA pasivamente** (`extraer_y_procesar_sesion`): se dispara en puntos
  clave — al cambiar de modo, al cerrar la app, manualmente desde la UI, y en la versión GUI
  también cada 20 mensajes (`UMBRAL_MENSAJES_EXTRACCION = 20`).
- Filtros de calidad antes de guardar:
  - Importancia alta: se descarta lo trivial (umbral `UMBRAL_IMPORTANCIA = 60`).
  - **Se filtran secretos** (contraseñas, claves …): no deberían quedar en el perfil.
  - **Respeta olvidos:** lo olvidado nunca vuelve a extraerse (filtros `esta_olvidado`).
  - Si el perfil crece mucho (> 2000 caracteres) se consolida/compacta antes de escribir.
- **Mentoría:** al terminar una sesión de mentor también se guarda progreso
  (`modulos/progreso_mentoria.py`) en ChromaDB con la etiqueta `Progreso_Mentoria`, para que el
  mentor recuerde dónde quedaste (temas, dudas, siguientes pasos).

### 2.4 Memoria de proyecto (tu código/archivos)

- Cuando trabajás sobre el proyecto, Argus vigila los archivos (watchdog/RADAR) y toma
  **snapshots** del estado: qué archivos hay, qué cambiaron, en qué se está laburando.
- Ese estado se vuelca en `PROJECT_STATE.md` y en el `documento_volatil`, y los archivos clave se
  inyectan a la conversación como bloques `[CONTENIDO DE '<ruta>']`.
- `PROJECT_STATE.md` se genera solo (`escanear_proyecto:`): **no se edita a mano**. Es la
  "memoria de que está pasando con el repo".

### 2.5 Evidencia web

- Los resultados de las búsquedas web verificadas se guardan como *evidencia* (snippets): Argus
  los cita y responde con base. Se mantienen los **últimos 3**, en memoria (FIFO). Detalle en
  `ARQUITECTURA_VERIFICACION_WEB.md`.

---

## 3. El ciclo completo de un mensaje

1. Llega tu mensaje. Primero se intenta **búsqueda anticipada** en la bóveda (si el tema encaja).
2. Se arma el contexto: conversación del modo (últimos 25 mensajes) + **recuerdos relevantes de
   la bóveda** (recuperación automática) + perfil del modo + bloques `[CONTENIDO DE ...]` si hay
   archivos + evidencia web de ser necesario.
3. El modelo responde. Si pediste recordar algo, guarda en la bóveda. Si preguntaste algo que
   tiene que mirar en la bóveda, la consulta, etc.
4. Periodicamente y en puntos clave (cambio de modo, cierre, manual) se **extrae el aprendizaje**
   a los perfiles / a la bóveda.

### Guardar (resumen)
- Vos pedís ✅ → `mcp_guardar_en_boveda` (etiqueta `Memoria_IA`).
- Lo mencionás al pasar 💭 → la **extracción pasiva** decide (no el modelo en vivo).

### Olvidar (resumen)
- "olvidá: <tema>" → `resolver_olvidar()` registra un **tombstone** en `olvidos.json` e invalida
  el perfil y los recuerdos bóveda vinculados.
- **Contrato clave:** el olvido **NO es retroactivo** sobre la conversación activa. Si algo ya se
  dijo/habló, queda en el registro del chat tal cual; el olvido evita que reaparezca **en el
  futuro** vía recuperación/extracción/consolidación. No se purga el contexto por coincidencia
  textual: esa relación no existe y sería imprecisa. (Tests: `tests/test_contrato_olvido_no_retroactivo.py`.)

---

## 4. Dónde está cada cosa (mapa de archivos)

| Qué | Ruta |
|-----|------|
| Bóveda vectorial | `modulos/boveda_memoria/` |
| Perfil general | `perfil_usuario.json` (raíz) |
| Perfil mentor | `perfil_mentor.json` (raíz) |
| Perfil gamer | `perfil_gamer.json` (raíz) |
| Tombstones de olvido | `olvidos.json` (raíz) |
| Estado de proyecto (autogenerado) | `PROJECT_STATE.md` (raíz) |
| Contexto conversacional | RAM (`config.estado.contexto_chat`, por modo) |
| CLI de inspección | `python gestor_boveda.py` |

---

## 5. Tips prácticos de uso

1. **Para que NO se te olvide nada importante, pedilo explícito:** "acordate de que mi
   presupuesto final es 15.000", "guardá esto en la bóveda". El guardado automático existe, pero
   el explícito manda.
2. **Repetí los datos clave:** si algo es realmente importante, decilo más de una vez en la
   sesión. La extracción pasiva suma contexto y aumenta la chance de que caiga en el perfil.
3. **Chequeá qué recuerda:** preguntale "¿qué sabés de mí?", "¿te acordás de <tema>?". Sirve
   también para notar si la bóveda quedó desactualizada.
4. **No confundas limpiar contexto con olvidar:** "limpiá el contexto" borra la charla de ahora
   (RAM) sin tocar lo aprendido. "olvidá: X" afecta el largo plazo. Exactamente lo mismo que en
   tu cabeza.
5. **El olvido mira al futuro:** si en esta misma conversación se habló de X y le decís
   "olvidá X", lo ya escrito queda en el chat; solo se evita que X reaparezca de ahora en más.
   Si querés "arrancar limpio del todo", cambiá de modo o limpiá el contexto.
6. **Usá los modos a propósito:** mentor ↔ gamer ↔ general tienen conversaciones aisladas y
   perfiles propios. Para estudiar un lenguaje usá mentor; para tu partida, gamer. Así no se
   mezclan los recuerdos.
7. **Cerrá la app por las vías normales:** al cambiar de modo o cerrar, Argus corre la
   extracción de la sesión. Si matás el proceso (o se cuelga), esa charla puede no llegar a los
   perfiles. Si te quedaste no extraído, cerrás bien y listo.
8. **No guardes contraseñas ni secretos:** hay un filtro automático, pero no es infalible. La
   memoria es local, pero aun así: saludable que no existan.
9. **Para que conozca tu proyecto, laburá con la sesión de archivos activa:** así toma snapshots
   y arma `PROJECT_STATE.md`. Si algo quedó viejo en ese estado, regeneralo con `escanear_proyecto:`.
10. **Revisá la bóveda de vez en cuando:** con `python gestor_boveda.py` ves qué guardó y podés
    limpiar lo que sobra; después podés "olvidá" temas que ya no sirven para que no ensucien las
    respuestas.

---

## 6. Limitaciones honestas

- **El contexto activo es RAM y se pierde al cerrar.** Todo lo que NO llegó a extraerse
  (importancia baja, secretos descartados, o sesión cerrada de golpe) se pierde por diseño.
- **La similitud por embeddings no es infalible:** "se parece el sentido" no siempre es
  "es lo correcto". El umbral es conservador (`MEMORIA_SCORE_MIN` es un umbral, no un número
  calibrado) y la recuperación se autocorrige con uso.
- **La bóveda y los perfiles no se comparten con la nube:** son locales del repo. Si borrás la
  carpeta `boveda_memoria/` o los `perfil_*.json`, Argus pierde ese historial.
- **La "memoria por archivos" depende del watchdog/snapshot:** si un archivo cambia muy seguido o
  el estado es enorme, el mismo proyecto es el que decide cuánto entra. `PROJECT_STATE.md` es un
  resumen, no un volcado total del repo.

---

## 7. Trabajo pendiente (anotado, SIN implementar)

> Registro de lo acordado en la sesión del 11/08/2026. Aún no se tocó código; esto quedó
> asentado para tener la hoja de ruta clara.

### 7.1 Contexto / diagnóstico

- Antes existía un flujo `procesar_archivo_adjunto` que, previa confirmación del usuario,
  **guardaba el archivo adjuntado en la bóveda** por fragmentos de 1500 chars con etiqueta
  `Doc: <nombre>` (`for chunk in chunks: guardar_recuerdo(...)`).
- Ese flujo **fue reemplazado** en el commit `d92ed3e` (21‑jun‑2026, refactor hacia `main_web.py`):
  ahora `cargar_adjuntos_en_contexto` solo inyecta el adjunto a `config.estado.documento_volatil`
  ("SIEMPRE A CONTEXTO VOLÁTIL"), **sin persistir a la bóveda**. Se eliminó también
  `config.estado.archivo_pendiente_inyeccion` en ese cambio.
- Ni antes ni ahora se leyeron **PDFs binarios**: `leer_contenido_archivo` solo soporta texto
  UTF‑8; no hay PyPDF/PyMuPDF en el repo y `MAX_PDF_PAGES = 100` (config.py:36) está definido
  pero sin uso.

### 7.2 Solución acordada (pendiente de implementar)

Objetivo: poder indexar **archivos grandes en la bóveda sin gastar tokens de contexto** y
guardar **notas por orden** (de tamaño moderado). El costo de indexar es local
(embeddings `all-MiniLM-L6-v2`) y la recuperación solo trae `TOP_K` fragmentos a contexto.

Entradas nuevas (en la sección **Memoria** de la sidebar, que ya tiene `btnMemoria` →
`modalMemoria` y los métodos `obtener_panel_memoria` / `olvidar_memoria` / `editar_memoria`):

1. **"Adjuntar archivo grande a bóveda"** — para los que NO deben tocar el contexto:
   - file picker → extracción (`pypdf` si es PDF, texto plano si no) → chunking
     (~1000‑1500 chars, respetando `MAX_PDF_PAGES`) → `guardar_recuerdo(chunk,
     etiqueta_tema="Doc: <nombre>.pdf")` por fragmento.
   - **Nunca** escribe `documento_volatil` ni el contexto conversacional.
2. **"Guardar nota por orden"** — no tan extenso:
   - textarea + etiqueta opcional → un fragmento a la bóveda con la etiqueta elegida.
   - Complementa a `mcp_guardar_en_boveda` (chat: "guardá esto en la bóveda").

### 7.3 Roles propuestos (para mantener ambos adjuntos)

| Vía | Dónde | Comportamiento | Caso de uso |
|-----|-------|----------------|-------------|
| Botón clip actual | `gui/app.js` | Sólo contexto volátil (`documento_volatil`) | "Habláme de esto ahora, olvidate mañana" |
| Tool nueva de bóveda | Sidebar → Memoria | Bóveda persistente, sin contexto | "Guardáme esto para siempre sin gastar tokens" |

### 7.4 Cómo se implementaría (referencia para cuando se haga)

- `modulos/ingesta_pdf.py` (nuevo): extracción + chunking + `guardar_recuerdo`.
- `modulos/web_bridge.py`: métodos `procesar_adjunto_boveda(ruta)` y
  `guardar_nota_boveda(texto, etiqueta)` expuestos a JS (patrón de `pyApi` existente).
- `gui/index.html` + `gui/app.js`: entrada en el modal de Memoria + feedback de progreso
  (cantidad de fragmentos).
- Elegir extremo del chunking: límite de tamaño, etiqueta automática (`Doc:`) vs manual, y si se
  genera un resumen del PDF con Gemini (opcional, no es core).
- Tests con stubs de `modulos.memoria` (patrón de `test_controlador_acciones.py`).