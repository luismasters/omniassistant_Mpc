# INFORME DE FASE 5 — Progreso / Mentoría

Fecha: 2026-08-11
Fases 3B (backfill real de la Bóveda) y 4 (recuperación automática) cerradas y verificadas.
Este documento es **auditoría + propuesta, sin implementación**. Nada de esto está aplicado.

---

## A. Estado actual de Mentor

Mentor existe hoy como **modo rígido**, no como capacidad integrada.

### Selección y estado
- `config.estado.modo_actual` ∈ `{general, mentor, gamer}`; los contextos de chat viven en `_contextos_por_modo` (`config.py:231` `cambiar_modo`). En `gamer`/`mentor` el workspace queda anclado (`cambiar_workspace`, `cambiar_snapshot`, config.py:264-269).
- La UI lo cambia con `pyApi.cambiar_modo_interfaz('mentor')` (`gui/app.js`); botón `btnModeMentor` (`gui/index.html:88-91`), tema `theme-mentor` y `#mentor-hud` en el avatar (`gui/avatar_anime.js`).

### Perfil de mentoría
- Datos en `perfil_mentor.json` (raíz), lógica en `modulos/perfil_mentor.py` (acceso thread-safe, `_lock`).
- Esquema actual (`ESQUEMA_MENTOR_DEFECTO`): `stack_objetivo` (frontend/backend/bases_de_datos/otras_herramientas), `tecnologias_aprendidas`, `tecnologias_en_estudio`, `proyectos_de_portafolio`, `ultimo_avance_registrado`, `historial_sesiones`, `claves_de_contexto_faltantes`.
- Contenido real (perfil_mentor.json): frontend `React (nociones)`, backend `Pendiente de definir`, bases `PostgreSQL + SQLModel`, otras herramientas (ChromaDB, LangChain, Docker, GitHub Actions, Pytest, CrewAI, Groq, Aider, Claude Code); 20 tecnologías aprendidas, 11 en estudio, 2 proyectos de portafolio.
- Funciones de mutación: `olvidar_elemento` (línea 160), `editar_elemento` (183), ambas con slugs estables (`_slug_estable`, 69) espejo de `resumen_memoria._slug`; mapeo id→mutación (104-108).

### Integración en el router
- `modulos/ia.py:50` importa `obtener_prompt_mentor`; en `ia.py:588-589` y `ia.py:646`, si `MODO_ACTUAL == "mentor"` el sistema usa `obtener_prompt_mentor(texto_workspace, texto_snapshot, texto_doc_volatil, texto_perfil)` (`modulos/prompts.py`, prompt fijo "Mentor Tecnológico de Luis…", sin modelo de progreso).
- El prefetch de memoria es solo `general`/`chat`/`gamer` (`ia.py:555-556`); en modo mentor **no** se recupera bóveda automáticamente.

### Persistencia de sesión
- Al salir del modo (`web_bridge.cambiar_modo_interfaz`, 395-420) o al cerrar la app (`main_web.py:238-241`): `extraer_y_procesar_sesion_mentor(mensajes, workspace_actual)` → reescribe `perfil_mentor.json` y una bitácora en el workspace.
- Olvidos: `olvidos.py::PREFIJOS_VALIDOS = ("funcional:", "vida:", "mentor:", "gamer:", "boveda:")`; `esta_olvidado`/`obtener_ids_olvidados` (149/159).

### Presentación
- `resumen_memoria.py:_seccion_mentor` (268) transforma el perfil en la sección `aprendizaje_y_carrera` del panel (ids `mentor:stack_*`, `mentor:tecnologias_*`, `mentor:ultimo_avance`, próximos pasos de la última sesión en 307+).

### Qué NO existe (gaps)
- No hay modelo de **objetivos** con estado/prioridad/fecha.
- No hay **progreso** medible por objetivo (solo `ultimo_avance_registrado` + `historial_sesiones`).
- No hay **dificultades recurrentes** persistentes ni **próximos pasos** de la sesión como dato reutilizable fuera de la bitácora.
- No hay **continuidad** real entre sesiones: la mentoría no lee la Bóveda (que ya tiene 16 recuerdos de perfil_proyecto, incl. "MentoríasLuis").
- La mentoría solo se dispara por modo manual; no por contexto/necesidad.

---

## B. Piezas reutilizables (sin reinventar)

1. `perfil_mentor.py`: persistencia thread-safe, `olvidar_elemento`/`editar_elemento` con ids canónicos estables, `_slug_estable` espejo, patrón "mapeo id→mutación". Éste es EL patrón de mutación admisible.
2. `_slug_estable`/espejos en `perfil_usuario.py:134-140` y `perfil_gamer.py` — mismo mecanismo de ids.
3. `resumen_memoria._seccion_mentor` → hoy produce `aprendizaje_y_carrera`; base para secciones de progreso/objetivos.
4. `olvidos.py` tombstones por prefijo → extender/reusar para ids de progreso.
5. El pipeline de extracción de sesión de `perfil_usuario.py` (`extraer_y_procesar_sesion` de 582; ruteo de hechos 533-577; filtros de importancia/secretos/tombstones 496-531) como plantilla para extraer "avances" — más maduro que reescribir todo el perfil.
6. Bóveda + `recuperador_memoria.py` (Fase 4): ranking temporal, dedup por `origen_id`, tombstones, tope 800 c/h → lista para dar "continuidad/dónde quedamos".
7. `resumen_memoria.listar_recuerdos_boveda`/`preparar_secciones` (428/447) para mezclar memoria episódica en el panel.
8. `snapshot:`, `iniciar_radar_proyecto`, `crawler.extraer_codigo_proyecto` para contexto de proyecto activo.
9. `block de memoria en ia.py:617` ya inyecta bóveda tras el clima — extensible a mentoría.

---

## C. Qué desaparece / deja de ser "modo"

Dentro del espíritu del roadmap (personalidades → **capacidades/contextos**):

- Que la mentoría **no dependa de `modo_actual == "mentor"`** para activarse: pasa a ser una *capacidad* que Argus puede convocar (por intención del usuario, por contexto del problema, o por pedido explícito).
- Desaparece el **modo manual obligatorio** como única puerta de entrada (el botón puede seguir seleccionando "modo mentor" como *modo visible*, pero la capacidad debe funcionar también en general si Argus detecta trabajo de aprendizaje/proyecto).
- Desaparece el **prompt fijo** "Eres el Mentor Tecnológico…" como único artefacto: pasa a ser un *bloque PROGRESO/MENTORÍA* ensamblado desde estructura de progreso + memoria + workspace, activo cuando la capacidad está invitada.
- El prefiltro de memoria por modo (`ia.py:555`) deja de excluir a la mentoría: la recuperación automática debe poder responder a un objetivo/avance.

No desaparecen como dato: `perfil_mentor.json`, `olvidos`, `aprendizaje_y_carrera`; se **evolucionan**.

---

## D. Nueva arquitectura (propuesta)

### D1. Núcleo: entidad "avance/progreso"
Añadir a `perfil_mentor.py` (o a un nuevo `modulos/progreso.py` que lo reúse) un modelo estructurado mínimo:

```
objetivos: [{ id, titulo, estado (activo|pausado|logrado|abandonado),
              prioridad, categoria (proyecto|habilidad|carrera),
              proyecto_asociado?, creado, actualizado }]
progreso_por_objetivo: { objetivo_id: { avances_acumulados, ultimo_avance_fecha } }
dificultades_recurrentes: [ { tema, ocurrencias, ultima_fecha, ejemplo_id_recuerdo? } ]
proximos_pasos: [ ... ] (próximos pasos sugeridos tras la última sesión)
continuidad: { ultimo_tema, ultima_fecha, donde_quedamos }
```

Se agrega sin romper el esquema actual: se mantienen `stack_objetivo`, `tecnologias_*`, `proyectos_de_portafolio` como *objetivos* en `estado=activo`.

### D2. Activación por contexto (no solo modo)
- Nueva señal en el prompt del router (mismo patrón `[WEB: SI]/[WEB: NO]`): `[MENTORIA: SI]` = Argus detecta que la conversación necesita programación/entrenamiento/avance de proyecto. Python solo ensambla.
- Cuando `[MENTORIA: SI]` **o** modo mentor **o** comando explícito (`/objetivos`, `¿qué sigue?`, etc.) → inyectar el bloque "PROGRESO Y MENTORÍA" construido en `prompts.py`.

### D3. Bloque de contexto "PROGRESO Y MENTORÍA"
Ensamblado en `prompts.py` a partir de:
- `perfil_mentor` (objetivos, stack, dificultades, próximos pasos, continuidad).
- Memoria recuperada por `recuperador_memoria` (avances previos, proyecto actual, recuerdos perfil_proyecto incl. "MentoríasLuis").
- Workspace/snapshot si el modo/workspace está activo.

### D4. Escritura de avances
- Al cierre de sesión con contenido de mentoría (cualquier modo): extraer con el pipeline tipo `perfil_usuario` (importancia/tombstones), volcando:
  - a JSON: objetivos/progreso/dificultades/próximos pasos/continuidad;
  - opcionalmente a Bóveda: un recuerdo de tipo avance (`origen_fuente="avance_mentoria"`) para recuperación episódica — ver riesgo K5 (requiere aprobación).

### D5. Presentación
- `resumen_memoria` gana secciones: `progreso_y_objetivos`, `dificultades_recurrentes`, `continuidad`. Reusa `_slug`/espejos; editar/olvidar igual que hoy.

---

## E. Relación con la memoria

- **Lectura**: la mentoría DEBE leer la Bóveda (Fase 4) — hoy no lo hace en modo mentor. Inyectar recuerdo "dónde quedamos" + avances previos.
- **Escritura**: los avances de mentoría van primero a JSON (decisión de planificación), y opcionalmente un *recuerdo* a Bóveda (memoria episódica) — sin tocar `guardar_recuerdo` internals; usar el API público de `memoria.py` o el ruteo de `perfil_usuario`.
- **Tombstones**: `mentor:*` sigue marcando mutaciones del perfil; si se crean ids de "recuerdo de avance" se usan los `boveda:*` ya filtrables.
- **No duplicar**: JSON = planificación/estructura; Bóveda = episodios recuperables; bitácora del workspace = narrativa opcional no fuente.
- `config.estado` se muta por sus métodos locked (nunca asignación directa).

---

## F. Datos estructurados vs Bóveda

| Dato | Lugar | Por qué |
|---|---|---|
| Objetivos, stack objetivo, tecnologías aprendidas/en estudio | `perfil_mentor.json` | Esquema consultado por prompt y panel; editable/olvidable |
| Progreso por objetivo, dificultades recurrentes, próximos pasos, continuidad | `perfil_mentor.json` (+ `resumen_memoria`) | Igual que arriba; requiere lectura exacta y ordenada |
| Historias/avances episódicos ("el 12/08 terminó el CRUD en FastAPI") | Bóveda (`origen_fuente="avance_mentoria"` o existente `perfil_proyecto`) | Recuperación por similitud/rango; ya hay 16 recuerdos así |
| Bitácora narrativa | workspace | Apoyo humano; no fuente para Argus |

Regla: lo que la prompt necesita leer **determinísticamente** = JSON; lo que se **recupera por similitud** = Bóveda. Nada de duplicar el mismo texto en ambos.

---

## G. Ejemplo de flujo

1. Usuario escribe en modo general o mentor: *"no avanza el deploy, el backend de FastAPI no levanta"*.
2. Argus (router) pone `[MENTORIA: SI]`.
3. Se ensambla el bloque PROGRESO: objetivo `backend FastAPI` (activo, prioridad alta), dificultad recurrente `deploy`, próximos pasos de la última sesión, continuidad (última sesión 07/08), + recuerdos de la Bóveda (proyecto RAG, "desplegar usando Streamlit Cloud", MentoríasLuis).
4. Argus responde como mentor **sin haber cambiado de modo**; la pantalla puede resaltar el hud con "mentoría activa".
5. Al cerrar la sesión: pipeline de extracción; `perfil_mentor.json` actualiza dificultades/progreso/próximos pasos/continuidad; si hay aprobación K5, guarda un recuerdo de avance.
6. En `resumen_memoria`/panel: secciones `progreso_y_objetivos` y `dificultades_recurrentes`.

---

## H. Archivos a modificar

1. `modulos/perfil_mentor.py`: modelo de objetivos/progreso/dificultades/próximos pasos/continuidad; extracción y merge de avances.
2. `modulos/prompts.py`: bloque "PROGRESO Y MENTORÍA"; `obtener_prompt_mentor` reubicable/adaptable.
3. `modulos/ia.py`: señal `[MENTORIA: SI]`; habilitar recuperación automática en mentoría; inyección del bloque.
4. `modulos/resumen_memoria.py`: nuevas secciones de progreso/variables; `_seccion_mentor` ampliada.
5. `modulos/web_bridge.py`: disparar extracción de avance también fuera del modo mentor; APIs nuevas de panel si aplican.
6. `config.py`: si hace falta portar flags (p.ej. `estado.mentoria_activa`) como métodos locked; **no** se cambian parámetros de memoria existentes.
7. `gui/` (`index.html`, `app.js`, `avatar_anime.js`): secciones del panel de progreso y señalización visual "mentoría activa".
8. `main_web.py`: cierre de sesión según la nueva lógica (sin romper el actual).

---

## I. Archivos que NO debo tocar

- `modulos/memoria.py` (guardar_recuerdo, bóveda núcleo).
- `modulos/recuperador_memoria.py` (podría leerse más, no reescribirse).
- `modulos/backfill_boveda.py` y la **bóveda real** (`modulos/boveda_memoria`) + `backups/`.
- Los 5 parámetros `MEMORIA_*` de `config.py` (57-60).
- `modulos/olnidos.py` lógica central (quizá solo ampliar `PREFIJOS_VALIDOS` con `progreso:` si se decide).
- `modulos/ia.py` prefetch/streaming existente (solo agregar capacidad).
- `main_gui.py` (deprecado), `modulos/senal_web.py`, `modulos/mensajes_web.py`, `modulos/skills/`.
- `tests/` existentes (nuevos tests se agregan, no se rompen).

---

## J. Tests necesarios (offline, stub de memoria/ia/perfil_usuario como `test_controlador_acciones.py`)

1. Extracción de avance: sesión de ejemplo → `perfil_mentor.json` gana objetivo/progreso/dificultad/continuidad; filtrando hechos con importancia < umbral y olvidados.
2. Activación por contexto: con `[MENTORIA: SI]` el bloque se inyecta; sin señal y modo general, no.
3. Ninguna llamada real a Bóveda en los tests de extracción (stub de `modulos.memoria`).
4. `_slug`/ids: espejos cliente/perfil_ids estables para `progreso:*`.
5. Resumen: secciones nuevas aparecen/desaparecen según perfil vacío vs completo.
6. Regresión de las 285 actuales (todo verde).

---

## K. Riesgos / decisiones que requieren aprobación

1. **Activación automática (`[MENTORIA: SI]`)**: riesgo de sobre/Sub detección; hay que calibrar con ejemplos reales antes de prometerla (inicial: solo bajo demanda o modo mentor).
2. **Costo y alcance del análisis de sesión por turno**: hoy se analiza al cierre; propongo el mismo ritmo (evita latencia en streaming).
3. **Migración de `perfil_mentor.json` actual** a nuevo esquema: es migración de datos (no de Bóveda) — requiere su propia prueba y verificación de que no se pierde stack/tecnologías.
4. **Nuevo prefijo `progreso:`** en `olvidos`: cambio acotado; revisar compat con tombstones existentes.
5. **Escribir avances a la Bóveda** (D4, K5): la regla actual es **no tocar la Bóveda sin autorización**. Requiere aprobación explícita y decisión de origen_fuente (¿`avance_mentoria` nuevo o reusar `perfil_proyecto`?).
6. **Contenido del bloque en la prompt**: tamaño/orden (token budget) debe validarse frente a `MEMORIA_MAX_CARACTERES=800`.
7. **Compatibilidad con `historial_sesiones` y bitácora** existentes: si se reemplaza por estructura de progreso, hay que migrar/aprovechar lo ya guardado.
8. **UI**: no es objetivo de Fase 5 rediseñar; solo paneles informativos mínimos.

---

## L. Orden exacto de implementación (una vez aprobado)

1. Extender el esquema de `perfil_mentor.py` (objetivos/progreso/dificultades/próximos pasos/continuidad) + migrar `perfil_mentor.json`; tests de merge/estabilidad de ids.
2. Pipeline de extracción de avances (patrón `perfil_usuario`) al cierre de sesión, también fuera del modo mentor; tests de extracción.
3. Bloque "PROGRESO Y MENTORÍA" en `prompts.py` + inyección cuando modo mentor o `[MENTORIA: SI]`; `resumen_memoria` nuevas secciones; tests.
4. (Si se aprueba K5) guardar recuerdo de avance a Bóveda con API pública y `origen_fuente` decidido.
5. Panel/UI mínima de progreso en `gui/`.
6. Suite completa 285 + nuevas en verde; informe de verificación como en Fases 3B/4.
7. Actualizar `ROADMAP.md` y `git` solo si el usuario lo pide.