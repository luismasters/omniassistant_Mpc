# ROADMAP — Argus

> **Este archivo es la ÚNICA fuente de verdad para la planificación del proyecto.**
> Documentos relacionados: `PROJECT_STATE.md` (estado actual, autogenerado por el crawler) y `AUDITORIA_ARQUITECTURA.md` (auditoría histórica del 25/07/2026).

**Versión actual:** v0.5.0 HUD (en camino a v0.6.0)
**Última actualización:** 2026-08-14

---

## 1. Estado actual (resumen)

Argus es un asistente de escritorio de IA para Windows, interfaz web (PyWebView + WebView2), voz (Vosk wake word → Whisper STT → Edge TTS), visión, gamepad multi-mando, memoria persistente (ChromaDB), control del sistema y de audio, y un sistema de Skills extensible. La dirección de producto es que las "personalidades" (General / Mentor / Gamer) evolucionen hacia **capacidades/contextos que Argus activa según lo que el usuario está haciendo** (no modos rígidos): ARGUS = voz + contexto + memoria + progreso + visión + capacidad de actuar.

**Línea de base técnica:** ~12k líneas de Python, frontend web en `gui/`, suite de tests actual (411 tests). Fase P (persistencia durable) y el núcleo de la Fase D (capacidades contextuales) están cerrados; quedan refinamientos de la Fase D y estabilidad (ver §3 y §8).

---

## 2. ✅ Completado

### Infraestructura e interfaz
- [x] Migración a `google-genai` (SDK oficial de Gemini)
- [x] Web HUD con PyWebView + Edge Chromium (`main_web.py` + `gui/`)
- [x] 3 modos de visualización Win32 (Tradicional / Flotante / Fondo de Escritorio con WorkerW)
- [x] Global exception hooks (`sys.excepthook` + `threading.excepthook`)

### Voz y periféricos
- [x] Wake word "argus" con Vosk (gratis, sin API key, continua)
- [x] STT con Whisper (GPU/CPU) y TTS con Edge TTS
- [x] Gamepad en subproceso aislado con fallback XInput nativo (funciona en juegos fullscreen)
- [x] Push-to-talk por teclado (F8) y por mando (L3+R3)

### Skills
- [x] `busqueda_web_actualizada` v1.0 — búsqueda DuckDuckGo priorizando resultados recientes (soluciona la data vieja del modelo)
- [x] `control_audio` v1.0 — volumen maestro, por app, mute y cambio de dispositivo (pycaw)
- [x] `recordatorios` v1.0 — recordatorios temporales con notificación y voz

### Memoria e IA
- [x] Memoria persistente con ChromaDB + caché de embeddings + watchdog de cambios
- [x] Perfiles persistentes de usuario y mentor

### Gestión de memoria — Fase 2 (edición y olvido desde el panel)
Objetivo: el usuario corrige/borra lo que Argus recuerda, sin esperar la siguiente consolidación IA.

- [x] **Edición de elementos:** cada dato del panel tiene botón "editar" que abre un modal con textarea; al guardar, `editar_memoria` persiste el cambio al JSON del perfil y recarga el panel.
- [x] **Olvido/borrado con confirmación:** cada dato tiene botón "olvidar" con modal de confirmación; confirma o cancela desde el propio panel.
- [x] **Dispatcher central en `resumen_memoria.py`:** `resolver_olvidar(id)` y `resolver_editar(id, texto)` validan el prefijo (`funcional:` / `vida:` / `mentor:` / `gamer:`), devuelven `exito` + `mensaje` y delegan la mutación al módulo propietario del prefijo.
- [x] **Mutaciones delegadas a los módulos propietarios de cada perfil:**
  - `perfil_usuario.py` — `olvidar_elemento()` / `editar_elemento()` sobre `funcional` y `vida_personal` (ids estables tipo slug, tildes normalizadas).
  - `perfil_mentor.py` — `olvidar_elemento()` / `editar_elemento()` sobre stack, tecnologías, proyectos, próximos pasos y último avance (olvido reasigna valores por defecto, no deja claves huérfanas).
  - `perfil_gamer.py` — `olvidar_elemento()` / `editar_elemento()` sobre fichas de juego por slug; el olvido de la ficha activa limpia `juego_activo` (sin huérfanos) y rechaza ids ambiguos; la edición de ficha usa plantilla determinista sin IA (`Etiqueta: valor · ...`) y rechaza texto libre.
- [x] **Tests:** 37 tests nuevos en `tests/test_gestion_memoria.py` (offline, sin IA ni ChromaDB; perfiles en carpetas temporales vía monkeypatch). **Suite total: 190 tests pasando.**
- [x] **ChromaDB queda FUERA de esta fase:** las mutaciones persisten solo en los JSON de perfil; no se re-indexaron ni invalidaron hechos de ChromaDB, ni se purgaron datos en el corpus de memoria a largo plazo.

> **⚠️ Limitaciones / riesgos documentados (Fase 2 de gestión de memoria):**
> - **Reaparición de datos por consolidación IA:** borrar/editar un dato en el panel no bloquea a ninguna consolidación futura. Si el LLM vuelve a extraer el mismo hecho en una sesión posterior, puede re-grabarlo y "resucitar" lo olvidado. Falta una lista negra de olvidos (tombstones) que filtre el guardado automático.
> - **Bóveda desincronizada:** `gestor_boveda.py` guarda su propio almacén separado de los perfiles. Un dato olvidado/borrado del panel NO se propaga a la bóveda, así que ahí queda viva una copia desactualizada del dato.

### Gestión de memoria — Fase 3 (bóveda: `origen_id` y ciclo de olvido)
Objetivo: cerrar la deuda de la bóveda desincronizada documentada en la Fase 2 y darle a la memoria libre un `origen_id` invalidable.

- [x] **`origen_id` determinista en la bóveda:** `guardar_recuerdo()` genera un `origen_id` canónico `boveda:memoria_ia:<hash>` (o respeta uno explícito); la familia lógica agrupa los documentos con el mismo origen.
- [x] **Ciclo "Olvidar esto" sobre la bóveda:** `resolver_olvidar("boveda:<origen>")` → `invalidar_por_origen()` borra TODA la familia del documento en ChromaDB y registra el tombstone en `modulos/olvidos.py`. Repetir el olvido del mismo origen es idempotente y no afecta a familias distintas.
- [x] **Tests:** `tests/test_olvido_ciclo_integracion.py` (7 tests, ChromaDB real en tmp, embeddings deterministas, `RUTA_OLVIDOS` en tmp) + `tests/test_integracion_boveda.py` (6 tests). **Suite total: 255 tests pasando.**
- [x] **Panel "Olvidar esto" alcanza la bóveda:** `preparar_secciones()` expone la sección "Memoria" con los recuerdos libres (familia por `origen_id`, `no_editable=True`); el botón "🗑️ Olvidar" existente ya despacha `resolver_olvidar("boveda:")` → `invalidar_por_origen()`.

> **⏳ Pendiente / decisión abierta (Fase 3):**
> - **Protección contra reaparición NO implementada.** `guardar_recuerdo()` no consulta el registro de olvidos ni valida tombstones: re-guardar exactamente el mismo contenido tras un olvido RE-CREA la familia en ChromaDB (test `test_re_guardado_mismo_contenido_tras_olvido_reaparece` fija este comportamiento actual). Falta decidir el mecanismo (p.ej. rechazar en `guardar_recuerdo()` si `esta_olvidado(origen_id)`, y un `quitar_olvido()` como "desolvidar").
> - **Backfill histórico: REALIZADO** (12/08/2026) — ver **Fase 3B** abajo.

### Memoria — Fase 3B (backfill real) y Fase 4 (recuperación automática) — COMPLETADAS y VERIFICADAS

- [x] **Backfill real de los 18 recuerdos legacy EJECUTADO (12/08/2026).** `modulos/backfill_boveda.py` (CLI con `--dry-run` por defecto y `--ejecutar` con backup previo) migró los 18 documentos sin contrato a `origen_id` canónico `boveda:<slug(etiqueta)>:<10hex sha256>` + `origen_fuente=perfil_proyecto` (16 familias resultantes; 1 familia con 3 duplicados físicos). Reutiliza `_generar_origen_id_boveda()` de `memoria.py`; `guardar_recuerdo()`/`invalidar_por_origen()` intactos.
- [x] **Verificación física:** 18/18 con `origen_id`, 18/18 con `origen_fuente=perfil_proyecto`; backup pre-migración completo en `backups/boveda_memoria_20260811_154432/` (snapshot antes de escribir); 2º `--dry-run` → 0 migrables / 18 ya migrados.
- [x] **Tests:** `tests/test_backfill_boveda.py` (12 tests, ChromaDB real en tmp + embeddings deterministas). **Suite total: 285 tests pasando (×2 consecutivos).**
- [x] **Fase 4 — Recuperación automática de memoria integrada.** `modulos/recuperador_memoria.py`: solo recuerdos `boveda:*`, excluye tombstones `olvidos`, umbral `sim = 1 − distancia_l2` ≥ `MEMORIA_SCORE_MIN` (0.45), dedup por `origen_id` con la versión más reciente, orden por score con decay de recencia (`MEMORIA_DECAY_RECENCIA`), tope `MEMORIA_MAX_CARACTERES` (800, incluye cabecera del bloque). Soportado por `buscar_contexto_con_detalle()` y prefetch (`iniciar_busqueda_anticipada`/`obtener_resultado_anticipado_detalle`) en `memoria.py`. Inyectado en `modulos/ia.py` tras el bloque de clima.
- [x] **Validada con datos reales** sobre la bóveda migrada: consultas afines (proyecto actual 0.62–0.65; trabajo actual 0.46–0.59) recuperan y deduplican; consulta ajena (videojuegos) filtrada en sim 0.396. `MEMORIA_SCORE_MIN=0.45` confirmado con datos reales (no recalibrado).

### Calidad (reciente)
- [x] Rotación de logs (10 MB, 5 backups, tolerante a bloqueos en Windows) — `modulos/logger.py`
- [x] Suite de tests con pytest (43 tests: `sistema.py`, `controlador_acciones.py`, `logger.py`)
- [x] `OMNASSISTANT_NO_FILE_LOG=1` para CI/headless

---

## 3. 🚧 Fase 1 — Estabilidad (en curso)

Objetivo: que Argus no se rompa y se pueda mantener.

- [ ] **Ampliar tests** de 43 → 150+:
  - [ ] `modulos/archivos.py` (sandbox y seguridad: `es_ruta_segura`, lectura/escritura en todos los modos)
  - [ ] `modulos/memoria.py` (ChromaDB mockeada)
  - [ ] `modulos/git_bot.py` (lógica de confirmaciones)
  - [ ] `modulos/controlador_acciones.py` (flujo `procesar_acciones_ia` con stubs)
- [ ] **Type hints** en `sistema.py`, `audio_custom.py`, `controlador_acciones.py`
- [x] **Fijar versiones exactas** en `requirements.txt` (todas fijadas a la versión instalada: `pywebview==6.2.1`, `google-genai==2.11.0`, `scipy==1.17.1`, `pytest==9.1.1`)
- [ ] **Retry con backoff exponencial** en llamadas a APIs (`modulos/ia.py`)
- [ ] **Fragmentar** `gui/app.js` y `gui/styles.css` (1200 / 1627 líneas) en módulos

## 4. 🚀 Fase 2 — Producto

Objetivo: pasar de "demo impresionante" a "herramienta que no pierde el trabajo del usuario".

- [x] **Persistencia del contexto de chat** (no perder conversación si la app crashea) — implementada como **Fase P** (ver §8.5.3): JSONL append-only por `context_id` + restauración de prefs/estado de proyecto al arrancar.
- [ ] **Graceful shutdown** (guardar estado, cerrar ChromaDB, detener timers al salir) — parcial: hay flush + `marcar_sesiones_abiertas_como_aborted` al salir (§8.5.3); falta cerrar ChromaDB y detener timers explícitamente.
- [x] **Validación amigable de API keys** (antes `config.py` crasheaba con `ValueError`; ahora degrada con `GEMINI_API_KEY=""` y la IA responde con aviso)
- [x] **Sacar rutas hardcodeadas** (`E:\Mis_Juegos_Yiri`, `c:\users\luis\` en `sistema.py`) → mapeo por máquina en `config.py` (14/08/2026: `config.RUTA_JUEGOS` + `config.ALIASES_USUARIO`, tests en `tests/test_rutas_por_maquina.py`)
- [ ] **Versionado semántico** (`__version__` + `CHANGELOG.md`)
- [ ] **Una sola entrada oficial** (aclarar `main_web.py` vs `main_gui.py` deprecado)

## 5. 🔌 Fase 3 — Skills futuras

| Skill | Prioridad | Estado | Dependencias externas |
|---|---|---|---|
| `monitor_hardware` (temp CPU/GPU real) | 🔴 Alta | ⏳ Pendiente | LibreHardwareMonitor + `wmi` |
| Confirmaciones GUI (modales nativos) | 🟡 Media | ⏳ Pendiente | — |
| Detección de skills por embeddings | 🟡 Media | ⏳ Pendiente | MiniLM (ya en RAM) |
| `clima_tiempo` (wttr.in, sin API key) | 🟡 Media | ⏳ Pendiente | — |
| `steam_integration` | 🟡 Media | ⏳ Pendiente | Steam Web API |
| `portapapeles_inteligente` | 🟡 Media | ⏳ Pendiente | pyperclip |
| `resumen_contenido` (artículos/YouTube) | 🟢 Baja | ⏳ Pendiente | yt-dlp, trafilatura |
| `traductor` | 🟢 Baja | ⏳ Pendiente | — |
| `monitor_procesos` | 🟢 Baja | ⏳ Pendiente | psutil |

> Detalle de cada skill (keywords de activación, arquitectura, archivos): ver apéndice A.

## 6. 🌍 Fase 4 — Multiplataforma (FastAPI + PWA)

Objetivo: acceso a Argus desde celular/tablet en la misma red WiFi.

- **Fase 4a** — Migrar capa de transporte a FastAPI (REST + WebSocket para streaming). El backend (`modulos/*`) no cambia; solo cambia el mecanismo JS→backend (`fetch()` en vez de `pywebview.api`). ~2 días.
- **Fase 4b** — PWA instalable (`manifest.json`, `service-worker.js`, íconos). ~½ día.
- **Fase 4c** — Modo híbrido: PyWebView apunta a `http://localhost:9876`. Opcional.
- **Fase 4d** — Seguridad: token de acceso local / pairing. Opcional.

**Dependencias nuevas:** `fastapi`, `uvicorn[standard]`, `python-multipart`, `websockets`.

**Beneficio clave:** el mismo asistente en PC, celular y tablet, con la misma voz (Whisper server-side) y sin cambios en la lógica de Argus.

---

## 7. 🚀 Siguiente — Fase 5: Progreso/Mentoría

**Objetivo:** evolucionar el "Mentor" (hoy un modo/personalidad rígida con perfil JSON) hacia una **capacidad integrada de PROGRESO / MENTORÍA** de Argus: objetivos, progreso, historial de avances, dificultades recurrentes, próximos pasos, proyectos asociados y continuidad entre sesiones.

**Decisión de producto:** Argus NO es una colección de modos. "General", "Mentoría", "Gaming", etc. son **contextos/capacidades que Argus activa según lo que el usuario está haciendo**, apoyándose en la memoria existente ya implementada (Bóveda, `origen_id`, tombstones, recuperación automática, ranking, deduplicación, límites).

> El detalle completo (auditoría del estado actual de Mentor, partes reutilizables/descartables, arquitectura propuesta, relación con la memoria, flujo de ejemplo, archivos a tocar, tests y orden de implementación) está en el **`INFORME_FASE5_PROGRESO_MENTORIA.md`** (raíz del repo).

**Estado: ✅ CERRADA (núcleo + endurecimiento).** El controlador vive en `modulos/progreso_mentoria.py` (clasificación determinista → `progreso` estructurado en `perfil_mentor.json` + persistencia semántica vía API pública `guardar_recuerdo` con `origen_fuente="mentoria_progreso"` y guard anti-diario `recuerdos_persistidos`). Se dispara al salir del modo Mentor (cambio de modo vía `web_bridge.py` y cierre de app en `main_web.py`) y el bloque PROGRESO/MENTORÍA se inyecta al prompt de mentor desde `perfil_mentor.py`/`resumen_memoria.py` (sección `aprendizaje_y_carrera`, gestionable con olvidar/editar). El modo mentor ya recupera memoria de la Bóveda (Fase 4). **Endurecimiento de cierre (auditoría):** política conservadora anti-pérdida (`avance_significativo` <65 o sin importancia → `hito_completado`/estado; ≥65 → Bóveda, sin duplicar); guard de secretos también en la ruta de estado degradada; guard de sesión `sesion_ya_procesada` (una misma conversación se persiste UNA vez entre cambio de modo y cierre); logs mínimos al rechazar por límites. Tests: `tests/test_progreso_mentoria.py` (31 offline, stubs `modulos.ia`/`modulos.memoria`). Suite completa: 316 verdes.

---

## 8. 🧱 Deuda arquitectónica — Desacoplamiento de modos → capacidades contextuales

> **Auditoría del 12/08/2026 (Skills / MCP / modelos). Estado: DECISIÓN DE PRODUCTO + DEUDA REGISTRADA. NO IMPLEMENTAR todavía.** No migrar los modos, no cambiar la selección de modelos y no crear capas/módulos nuevos para esto hasta que se abra la fase específica (§8.5). Solo se documenta la deuda.

### 8.1 Decisión de producto (explícita)

> Argus **no es una colección de modos/personas**. "General", "Mentoría" y "Gaming" son **contextos/capacidades que Argus puede activar según la actividad del usuario**.

### 8.2 Lo que ya cumple la arquitectura objetivo

- **Skills activan por contenido, no por modo:** `gestor_skills.obtener_skill_relevante()` (gestor_skills.py:47) solo clasifica el texto del mensaje (audio / web / recordatorios) y dispara en cualquier modo.
- **Tools MCP atados a la capacidad del modelo, no a la persona:** `ia.py:716-717` adjunta `lista_herramientas_mcp` solo si `modelo_activo == "gemini"` y no hay skill activa (el modo de la persona no participa de la condición).
- **Capacidades transversales para todos los modos:** recuperación automática de memoria (Fase 4, `ia.py:638`), evidencia web, adjuntos y comandos de ventana/sistema corren igual en general/chat/gamer/mentor.
- **Override de modelo explícito del usuario:** `ia.py:648-667` permite elegir Gemini/DeepSeek/Groq a mano, saliendo del default por modo.

### 8.3 Puntos de fricción (acoplamiento al modo)

#### Punto 1 — System prompt rígido por modo
- **Estado actual:** `ia.py:612-627` elige `obtener_prompt_mentor` / `_gamer` / `_general` con un `if MODO_ACTUAL` duro; `prompts.py` define tres personas completas. Estar en modo "mentor" fuerza la persona mentor aunque el pedido sea de otra actividad.
- **Por qué contradice la arquitectura objetivo:** la persona debería ser **adaptativa a la actividad**, no fijada por un toggle de contexto.
- **Dirección futura recomendada:** **prompt base + bloques contextuales activados por relevancia** (perfil de mentoría, bitácora, perfil del juego, workspace) que entren según el tema detectado o la skill activa — en lugar del switch de persona.

#### Punto 2 — El modelo "Por Defecto" depende del modo (y arrastra las capacidades MCP)
- **Estado actual:** `ia.py:669-676`: con "Por Defecto", mentor → DeepSeek, gamer → Gemini, general → Gemini. El camino DeepSeek/Groq (`ia.py:998-1023`) solo envía `messages`, sin `tools`: **en "Por Defecto" el modo mentor no tiene tools MCP y el modo gamer sí** (el chip `🧩 MCP ✓/✗` del HUD ya lo refleja).
- **Por qué contradice la arquitectura objetivo:** cambiar de contexto **cambia silenciosamente las herramientas disponibles**; la capacidad no debería depender de la persona sino de la actividad/necesidad del turno.
- **Dirección futura recomendada:** **modelo por defecto como preferencia global del usuario** (configuración, no por modo); las tools se atan a la capacidad del modelo elegido, independiente del contexto.

#### Punto 3 — Visión y perfiles parcialmente ligados al modo
- **Estado actual:** `ia.py:601-606` carga `perfil_gamer` solo en modo gamer (en el resto usa el perfil general) y el perfil mentor entra solo por su prompt (`prompts.py:6`); `ia.py:728-732` suma verbos de visión ("compara objetos") únicamente en modo gamer.
- **Por qué contradice la arquitectura objetivo:** el dato de juego o de carrera debería estar disponible si se habla de ese tema en cualquier contexto, no bloqueado por un modo.
- **Dirección futura recomendada:** **perfiles consultados por contexto/tema relevante, no exclusivamente por modo** (detección por embeddings/tema — ver §5 "detección de skills por embeddings"); la Bóveda ya recupera por similitud en cualquier modo (Fase 4) como base.

### 8.4 Direcciones futuras (eje de la evolución)

1. **Prompt base + bloques contextuales activados por relevancia** (en vez del switch de persona).
2. **Modelo por defecto como preferencia global del usuario**, no por modo.
3. **Perfiles consultados por contexto/tema relevante**, no exclusivamente por modo.
4. **Skills y capacidades como mecanismo principal de activación** (hoy ya es por contenido; futura detección por embeddings en §5).

### 8.5 Cierre — futura fase específica

Los 3 puntos de fricción **SÍ deben convertirse en una fase específica de "Desacoplamiento de modos → capacidades contextuales"**, ubicada **DESPUÉS de la persistencia durable del estado de trabajo** (persistencia del chat + graceful shutdown + `_contextos_por_modo` / `evidencia_web` / `snapshot_actual` — pendiente en §4 / Fase 2).

Justificación: el desacoplamiento **reestructura cómo se contienen los contextos** (de buckets por modo a bolsas de contexto/capacidad) y toca `config.estado`. Si ese estado **no está persistido antes**, la migración puede perder conversación/historia. Orden sugerido: `① persistencia durable del estado → ② desacoplamiento de modos → ③ expansiones (FastAPI/PWA)».

### 8.5.1 Auditoría de persistencia durable (12/08/2026) — decisión arquitectónica

> **Alcance: SOLO documentación. No implementar la Fase P todavía.** Ningún cambio de código.

#### Orden aprobado provisionalmente

`Fase P — Persistencia durable → Fase D — Desacoplamiento de modos → expansiones futuras (FastAPI/PWA)`

#### Fase P — Persistencia durable (definición de alcance)

**Debe persistir:**
- **Historial de conversación por contexto** (hoy `_contextos_por_modo` + `contexto_chat`; ver hallazgos: RAM-only).
- **Estado de proyecto / `PROJECT_STATE.md` y su recarga a `snapshot_actual`** al iniciar / al anclar workspace.
- **Preferencias seleccionadas por el usuario**, especialmente `workspace_actual` y `modelo_seleccionado`.

**Debe permanecer volátil:**
- `documento_volatil` (adjuntos: memoria de trabajo, volátil por diseño).
- `pendiente_de_borrado` / `pendiente_de_boveda` / `pendiente_de_git` (confirmaciones en vuelo).
- Estados de acciones en vuelo, `archivo_pendiente_inyeccion` y contadores/transitorios equivalentes (p.ej. `mensajes_desde_ultima_extraccion`).

**`evidencia_web`:** mantenerla **volátil por defecto**. Si en el futuro se persiste el historial por turno, evaluar adjuntarla **al turno** y no como estructura global independiente.

#### Requisitos arquitectónicos de la futura persistencia

1. **No crear una persistencia específica para `general/mentor/gamer`.** El almacenamiento debe usar una **clave de contexto genérica**, preparada para el futuro desacoplamiento de modos (Fase D).
2. **No duplicar la Bóveda ni los perfiles existentes:** la persistencia guarda transcripto/preferencias/estado de proyecto; la memoria semántica sigue viviendo en ChromaDB y los JSON de perfiles.
3. **No persistir estados peligrosos** que puedan ejecutar acciones automáticamente después de un reinicio.
4. Tolerar **cierre normal** y, en la medida razonablemente posible, **recuperación ante cierre anormal** (flush periódico, no solo en `finally`).
5. Definir **límites/rotación** para evitar crecimiento indefinido del historial.
6. **Distinguir claramente historial conversacional** (transcripto retomable) **de memoria semántica** (Bóveda/perfiles).

#### Hallazgos registrados (auditoría SOLO LECTURA del código actual)

- `main_web.py` actualmente **no recarga** el estado de proyecto/snapshot al iniciar ni al anclar workspace: `cargar_snapshot` solo se usa dentro del comando `snapshot:` (controlador_acciones.py:565) y `escanear_proyecto:` escribe `PROJECT_STATE.md` (controlador_acciones.py:818) sin volcarlo a `snapshot_actual`. El radar de cambios (`iniciar_radar_proyecto`) solo corre en `main_gui.py` (deprecado).
- La **extracción de perfiles** ocurre principalmente al **cambiar de modo** (web_bridge.py:436-458) o en **cierre limpio** del modo activo (main_web.py:234-255): un **kill/crash** puede perder el último período de conversación antes de su consolidación, y los contextos inactivos no se extraen al cierre.
- Los **contextos conversacionales son actualmente RAM-only** (`_contextos_por_modo`, `contexto_chat` — config.py:125-131).
- `documento_volatil` **debe seguir siendo volátil por diseño** (es memoria de trabajo de adjuntos).
- `evidencia_web` **no debe convertirse en memoria persistente global** (riesgo de reinyectar fuentes viejas en temas nuevos; es per-turno).

#### Dependencia con la Fase D

La persistencia debe diseñarse **agnóstica a los nombres actuales de los modos**: si la clave de contexto es genérica (slug del contexto/capacidad), la Fase D (desacoplamiento) **no requiere rehacer el almacenamiento** — solo cambia cómo se eligen las claves durante la migración. La Fase P es prerrequisito de la Fase D porque la reestructuración del contenedor de contextos es donde hay más riesgo de pérdida y necesita la red de seguridad ya escrita (ver §8.5).

### 8.5.2 Contrato técnico de la Fase P (diseño SOLO LECTURA, 12/08/2026)

> **Alcance: SOLO DISEÑO. No implementar todavía.** No crear módulos, no tocar `ia.py`/`config.py`/`web_bridge.py`/ChromaDB ni los contratos de memoria/olvido. `turno_id` (C2) intacto.

#### A. Contrato de persistencia

Store append-only de **transcripto conversacional**, aditivo y separado de Bóveda/perfiles. Jerarquía `context_id → sesión → turno → mensaje`, clave genérica `context_id` (nunca `general/mentor/gamer` como schema). Mensajes y `parts` conservan el formato actual. Escritura por **mensaje completado**. Recuperación **solo explícita** con caps. **Olvido NO aplica al transcripto** (H.1: no retroactivo).

#### B. Modelo de datos (JSONL por contexto; una línea = un turno)

```json
{ "store_version": 1,
  "sesiones": [
    { "sesion_id": "ctx-abc-20260812-01", "context_id": "abc",
      "orden": 1, "estado": "open|closed|aborted", "inicio": "...", "fin": "...",
      "turnos": [
        { "turno_id": "ctx-abc-0001", "seq": 1, "ts_ms": 1.7e12,
          "estado": "ok|error|interrumpido", "evidencia": null,
          "mensajes": [ {"role":"user","parts":["..."],"ts_ms":1.7e12},
                        {"role":"model","parts":["..."],"ts_ms":1.7e12} ] } ] } ] }
```

#### C. Flujo de escritura

`RLOCK_CONTEXTO` (mismo lock canónico, no uno nuevo) → append user con `seq` → [stream LLM] → append model con `seq` → commit. Compactación periódica atómica (tmp + `os.replace`).

#### D. Flujo de recuperación

Señal explícita ("dónde quedamos" / botón) → tail última sesión del `context_id` activo → filtrar `system`/marcadores/confirmaciones resueltas → hidratar `contexto_chat` (lock) → prompt normal. **Nunca** carga todo el historial al prompt al iniciar; sin auto-inyección por defecto.

#### E. Política de límites/retención

Activo: `MAX_MENSAJES_CONTEXTO` (sin cambio). Disco: full transcript por contexto ≤ N sesiones o M días (default 7); luego metadata + huella extractable (+ resumen IA opcional, OFF por defecto). Cuota global de bytes + cap por sesión.

#### F. Política de cierre anormal (garantías honestas)

| Evento | Garantía |
|---|---|
| Cierre normal / cambio de modo | Flush **síncrono** + `closed` / rotación de sesión |
| Excepción / fallo LLM en streaming | Turno `error` persistido en el path del catch (no es kill) |
| Reinicio Windows / kill / crash | **Parcial**: append por mensaje completado → al boot se detecta sesión `open/aborted`; el model reply huérfano se marca "(respuesta interrumpida)" pero el user msg queda. No se promete continuar streams |

#### G. Separación persistente/volátil

**Persistente:** transcripto, preferencias, metadata de sesión. **Volátil siempre:** `documento_volatil`, `evidencia_web`, `pendiente_*`, contadores, cachés, prefetch. `snapshot_actual` = derivado (se recarga, no se persiste).

#### H. Compatibilidad con Bóveda

Aditivo, sin re-embed/re-index. La recuperación no consulta Bóveda ni llama `guardar_recuerdo`; tombstones intactos; olvido no retroactivo sobre transcripto.

#### I. Compatibilidad con Fase D

Claves genéricas (solo ids). Rename de `context_id` vía id-map lazy; store intacto ante fusión de contextos; ninguna fila lleva info de persona.

#### J. Matriz de tests (familias)

Escritura (W1-4), lectura (R1-3), recuperación (REC1-4, incl. no auto-inyección y aislamiento), límites (LIM1-4), concurrencia (CON1-3), reinicio (RE1-3), corrupción (COR1-3), duplicados (DUP1-3), cierre anormal (CA1-5), aislamiento de contextos (AISL1-3), Bóveda/olvidos (BOV1-3), Fase D (FD1-3). Todos offline, con store fake inyectable + store real en `tmp_path`; stubs de `modulos.ia`/`modulos.memoria` (patrón `test_controlador_acciones.py`).

#### K. Archivos que HABRÍA que modificar (plan; hoy NO se toca nada)

- **Nuevo módulo futuro:** `modulos/persistencia.py` (store JSONL + preferencias) — **no crear ahora**.
- `config.py`: campos store/preferencias + loader; mapeo transitorio `modo → context_id`.
- `modulos/ia.py`: hooks de append por turno y marcado de parcial en el catch.
- `main_web.py`: arranque (prefs, workspace, load snapshot, recovery opcional) y cierre (flush síncrono).
- `modulos/web_bridge.py`: métodos UI `recuperar_sesion`, `borrar_historial_contexto`, preferencias.
- **No se tocan:** `gestor_skills.py`, `perfil_*`, `gestor_boveda`, ChromaDB, contratos memoria/olvido, `turno_id` C2.

#### L. Riesgos y decisiones pendientes

1. Ubicación del store: fuera del repo (`%LOCALAPPDATA%\ArgusCopilot\conversaciones\`) vs `data/` + `.gitignore` (el repo tiene auto-commits: privacidad). **Decidir.**
2. Re-armado del radar (`iniciar_radar_proyecto`) en `main_web`: feature, no persistencia.
3. Resumen-IA en retención: OFF por defecto (costo de tokens).
4. Trigger de "retomar": palabra clave vs botón UI. **Decidir.**
5. `modelo_seleccionado` como preferencia global anticipa Fase D (Punto 2) — no colisionar.
6. Escritura con `RLOCK_CONTEXTO` para no romper H.2 (modo serializado).
7. Metadata de sesión sensible → truncar/label en UI.

#### Recomendación de almacenamiento (provisional)

**JSONL append-only por `context_id`** (línea = turno, checksum por registro), compactación atómica (tmp + `os.replace`), upsert idempotente por `seq`. Sin SQLite (ChromaDB ya cubre lo semántico; no sumar otro engine). Escrituras sincronizadas con `RLOCK_CONTEXTO`; recuperación solo explícita con caps. Preferencias en `estado_prefs.json` fuera del repo. `PROJECT_STATE.md`/`.cortana/snapshot.json` solo se **cargan**. `turno_id` durable nuevo (UUID/seq) separado de C2.

> **Alternativa abierta (no determinada por el código actual):** si más adelante se quieren consultas/tiempo real o múltiples procesos, **SQLite (WAL)** reemplazaría al JSONL sin cambiar el modelo de datos; la decisión 1 y la de retención de preferencias condicionan cuándo vale la pena.

### 8.5.3 Cierre de la Fase P (MVP implementado — 12/08/2026)

> **Estado: IMPLEMENTADO (MVP) y verificado.** Pasa de "deuda" a "fase cerrada en su núcleo"; quedan refinamientos listados abajo.

**Implementado:**
- **`modulos/persistencia.py` (nuevo):** store JSONL append-only por `context_id` genérico (sesión → turno → mensaje; una línea = un mensaje para durabilidad del msg del usuario antes de la respuesta del LLM), checksum sha256 por registro, dedup por `(context_id, sesion_id, turno_seq, msg_seq)`, escritura dentro de `RLOCK_CONTEXTO`. `recuperar_tail` (caps 25 msg / 2000 chars, excluye marcadores), `purgar_historial`, `borrar_historial`, preferencias atómicas (`prefs.json`), `cargar_estado_proyecto` (solo recarga), `marcar_sesiones_abiertas_como_aborted`, `armar_context_id` (mapeo transitorio modo→context_id). Flags: `OMNASSISTANT_NO_PERSISTENCIA=1`, `ARGUS_PERSISTENCIA_DIR`.
- **Wiring:** `config.py` persiste cada mensaje en `agregar_mensaje_chat` y cierra sesión en `cambiar_modo`; `main_web.py` restaura prefs (workspace/modelo/visualización/modo), recarga `PROJECT_STATE.md`→`snapshot_actual`, re-arma el radar y marca `aborted` al iniciar, flush al cerrar; `web_bridge.py` guarda prefs y expone `recuperar_historial` / `borrar_historial_contexto` / `hay_historial_persistido`; `ia.py` interceptor de frases "dónde quedamos / retomá la conversación"; UI botón ↩️.
- **Decisión "retomar" (12/08/2026):** `restaurar_historial_persistido` **reemplaza** si el contexto está vacío y **anexa** si hay conversación en curso (recorta a `MAX_MENSAJES_CONTEXTO`). No persiste el historial recuperado (solo RAM).
- **Fix de olvido por chat (bug real reportado):** el modelo confirmaba sin ejecutar nada. Se agregó `mcp_olvidar_tema(tema)` (busca en `preparar_secciones`, despacha `resolver_olvidar(id)`, registra tombstone) + instrucción en `prompts.py` (general y gamer) prohibiendo confirmar sin emitir la tool. No retroactivo sobre transcripto (H.1).
- **Tests:** `tests/test_persistencia.py` (24), `tests/test_retomar_historial.py` (4), `tests/test_olvidar_tema.py` (6, subprocesos aislados). Suite total en ese punto: 371. Hoy la suite completa está en 411 pasando. `node --check gui/app.js` OK. Smoke headless OK.

**Refinamientos pendientes de Fase P (no bloqueantes):**
- Prueba manual real con la GUI (`python main_web.py`).
- Revisar si los turnos de confirmaciones del sistema deben persistirse como transcripto (hoy sí se persisten; es transcripto real, coherente con H.1).
- `retomar` por botón pinta historial en la UI; queda a gusto pulir el render.
- El write path persiste cada mensaje vía `agregar_mensaje_chat`; evaluar marcar el partial del modelo en cierre anormal (contrato F §8.5.2, post-MVP).

### 8.6 Restricciones históricas (previas a la apertura de la Fase D)

> Estas restricciones aplicaban **antes** de que la Fase D se abriera y se implementara (ver §8.7). Las del desacoplamiento quedan habilitadas; las de modos/skills/perfiles siguen vigentes para cambios NO relacionados con el desacoplamiento.

- No modificar `modulos/ia.py`, `modulos/gestor_skills.py` ni los perfiles por motivos de desacoplamiento.
- No migrar los modos todavía.
- No crear capas ni módulos nuevos para esto.
- No cambiar la selección de modelos.

### 8.7 Estado de la Fase D — Desacoplamiento de modos → capacidades (12/08/2026)

**Estado: EN PROGRESO (núcleo implementado).** Argus ya **no debe considerarse una colección de modos rígidos**: General / Mentoría / Gaming son **contextos/capacidades** que se activan según la actividad.

**Puntos implementados:**
- **Punto 1 — Prompt base + bloques contextuales: ✅ IMPLEMENTADO.** `modulos/prompts.py` → `obtener_prompt_base()` + `bloque_mentoria()` + `bloque_gaming()` + `construir_contexto_sistema()` (composición única `BASE + bloque`). `obtener_prompt_general/mentor/gamer` quedan como delegaciones (compatibilidad con tests).
- **Punto 2 — Modelo por defecto global: ✅ IMPLEMENTADO.** `config.MODELO_DEFECTO_GLOBAL` (env `ARGUS_MODELO_DEFECTO`); "Auto"/"Por Defecto" ya no depende del modo → el MCP no "parpadea" al cambiar de contexto.
- **Punto 3 — Activación de capacidades por tema: ✅ IMPLEMENTADO.** `detectar_capacidad_por_tema()` (palabras clave conservadoras): en modo general/chat la capacidad mentoría/gaming se activa por el contenido del mensaje; el perfil se elige según la capacidad activa.
- **UI Fase D — Opción A (etiquetas): ✅ IMPLEMENTADA.** Sidebar "Capacidades", header "💬 Argus / Asistente IA con capacidades contextuales", textos sincronizados en `gui/app.js`. Sin cambios de lógica de botones.
- **UI Fase D — Opción B (chips de capacidad auto/fijado): ✅ IMPLEMENTADA.** Chip de capacidad en el header (💬/🎓/🎮) que se actualiza por turno (señal `__CAPACIDAD_ACTIVA__` desde `ia.py`), con **pin** (click = fijar 📌 / liberar ⚡). Backend: `config.capacidad_fijada` + `fijar_capacidad` en bridge; el pin manda siempre sobre modo/tema.

**Estado de puntos/ítems relacionados:**
- **Mentores temáticos (mentoría parametrizada por tema): ⏳ APLAZADOS.** Se deja anotado como evolución futura: desacoplar `progreso_mentoria` de un solo `perfil_mentor.json` hacia un registro de mentores temáticos con avance propio (aprovecha el Punto 3 ya implementado).
- **Refinamiento de activación por embeddings** (reemplazar keywords del Punto 3): pendiente, ligado a la skill "detección de skills por embeddings" (§5).
- **Robustez de la API (Bloque 1): ✅ IMPLEMENTADO.** `_es_error_transitorio_gemini()` (503/429/ResourceExhausted/high demand/timeouts) + `_fallback_deepseek()` reutilizable: ante saturación, el turno continúa con DeepSeek en vez de mostrar "❌ Error en el streaming". Retry con backoff contra el MISMO Gemini: `_gemini_stream_con_retry` (2 intentos, backoff exponencial 0.5/1s, solo si el 503 ocurre ANTES del primer chunk). **Cadena de modelos de reserva (14/08):** `_gemini_stream_con_cadena` + `CADENA_FALLBACK_GEMINI` (3.5-flash-lite ↔ 3.6-flash) — si el **default global** sigue saturado, prueba el modelo de reserva antes de caer a DeepSeek; NO aplica a selecciones explícitas del usuario; si ya se emitió contenido no cambia de modelo (no duplica). Tests: `test_cadena_fallback_*` (4, subprocesos).

**Estado de fases cerradas (no tocar):**
- **Fase P (persistencia durable): CERRADA en su núcleo** (ver §8.5.3).
- **Fase 4 (Bóveda/recuperación automática) y Fase 5 (Progreso/Mentoría): CERRADAS.**
- **C1/C2, H.1 (olvido no retroactivo), H.2 (modo serializado) y H.3 (MCP disponible): CERRADOS.**

**Suite de tests:** 415 passed (76 warnings preexistentes).

**Tanda de estabilidad/UX asentada (14/08/2026):**
- **Modelo por defecto global → `Gemini 3.5 Flash Lite`** (medido: 1.2s vs 24.2s del `3.1-flash-lite` saturado). Fix `gemini-3.1-pro` → `gemini-3.1-pro-preview`; opción `Gemini 3.6 Flash (High)` en la UI (`_modelo_gemini_str` en `modulos/ia.py`).
- **Fix de timeout en `google-genai` 2.11:** `HttpOptions.timeout` es en **milisegundos** (bug de unidades, corregido a `30000`); los read-timeouts se reconocen en `_es_error_transitorio_gemini`.
- **TTS intermitente resuelto:** la voz se ata al **modo de entrada** (`modo_voz`), no a `usaste_mcp`; umbral `_MIN_CHARS_CHUNK_VOZ=30`; el `resto_stream` de `finalizar()` ahora se habla.
- **Botón 🔊 "Escuchar"** en las burbujas de Argus: `web_bridge.leer_texto_con_voz()` (Edge TTS, cero tokens).
- **Restyle visual profesional** (CSS) + cache-busting `?v=2` temporal en `gui/index.html`.
- **Cierre inesperado de la app investigado:** sin tracebacks en el log (cierre externo); se deja como está, sin fix.

---

## 9. Orden de implementación sugerido

```
Primero (impacto inmediato):
  ① Ampliar tests (archivos.py, memoria.py, git_bot.py)
  ② Type hints + rutas hardcodeadas → config.py
  ③ Persistencia del chat + graceful shutdown

Después (estabilidad):
  ④ Retry/backoff en APIs + versiones fijas en requirements
  ⑤ Fragmentar app.js / styles.css

Skills (cuando el core esté estable):
  ⑥ monitor_hardware → confirmaciones GUI → embeddings → clima → resto

Persistencia durable del estado de trabajo (prerrequisito del desacoplamiento, §8.5):
  ⑦ Persistencia del chat + graceful shutdown + estado de trabajo (Fase 2, §4)
  → ⑧ Desacoplamiento de modos → capacidades contextuales (deuda documentada en §8)

Expansión (cuando el producto sea estable):
  ⑨ FastAPI + PWA (Fase 4a → 4d)
```

---

## Apéndice A — Detalle de skills pendientes

### ⏰ `monitor_hardware` — Prioridad ALTA
Temperatura real de CPU/GPU, frecuencias, ventiladores y TDP. `psutil` no lee temperatura de CPU en Windows; requiere LibreHardwareMonitor (proceso externo) exponiendo el namespace WMI `root\LibreHardwareMonitor`. Arquitectura: `hardware_reader.py` → `wmi.WMI(namespace="root\LibreHardwareMonitor")`.

### 🌤️ `clima_tiempo` — Prioridad MEDIA
Clima actual y pronóstico con `wttr.in` (gratuito, sin API key).

### 🎮 `steam_integration` — Prioridad MEDIA
Biblioteca de Steam: horas jugadas, logros, juegos instalados, noticias de parches. Requiere Steam Web API Key.

### 📋 `portapapeles_inteligente` — Prioridad MEDIA
Historial de textos copiados, búsqueda y guardado nombrado de clips.

### 📺 `resumen_contenido` — Prioridad BAJA
Resumir artículos web o transcripciones de YouTube desde una URL (`yt-dlp` + `trafilatura`).

### 💻 `monitor_procesos` — Prioridad BAJA
Listar procesos que más consumen CPU/RAM y finalizar procesos colgados (`psutil`).

### 🌐 `traductor` — Prioridad BAJA
Traducción rápida de frases o fragmentos de código.

---

## Apéndice B — Mejoras técnicas pendientes (deuda)

| # | Problema | Archivo | Impacto |
|---|----------|---------|---------|
| 1 | Cobertura de tests incompleta | `tests/` | Riesgo de regresión |
| 2 | Rutas hardcodeadas de una máquina | `sistema.py` | No portable |

> **Deuda #2 RESUELTA (14/08/2026):** `E:\Mis_Juegos_Yiri` → `config.RUTA_JUEGOS` (env `ARGUS_RUTA_JUEGOS`, ya seteado en el `.env` local) y el hack `c:\users\luis` → `config.ALIASES_USUARIO = {"luis": ""}` (alias genérico a `~` con barra final para no pisar usuarios más largos). Tests: `tests/test_rutas_por_maquina.py` (4).
| 3 | Sin type hints en módulos clave | `sistema.py`, `audio_custom.py`, `controlador_acciones.py` | Mantenimiento difícil |
| 5 | Contexto de chat en memoria (se pierde) | `config.py` | Pérdida de trabajo del usuario |
| 6 | Versiones flotantes | `requirements.txt` | Puede romper |
| 7 | JS/CSS monolíticos | `gui/app.js`, `gui/styles.css` | Difícil de mantener |
| 8 | Sin `__version__` ni CHANGELOG | — | No se trackea la evolución |
| 9 | TTS sin timeout de red | `modulos/audio_custom.py` | Bloqueo sin internet |
