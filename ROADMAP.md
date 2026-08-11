# ROADMAP — Argus

> **Este archivo es la ÚNICA fuente de verdad para la planificación del proyecto.**
> Documentos relacionados: `PROJECT_STATE.md` (estado actual, autogenerado por el crawler) y `AUDITORIA_ARQUITECTURA.md` (auditoría histórica del 25/07/2026).

**Versión actual:** v0.5.0 HUD (en camino a v0.6.0)
**Última actualización:** 2026-08-10

---

## 1. Estado actual (resumen)

Argus es un asistente de escritorio de IA para Windows con 3 personalidades (General / Mentor / Gamer), interfaz web (PyWebView + WebView2), voz (Vosk wake word → Whisper STT → Edge TTS), visión, gamepad multi-mando, memoria persistente (ChromaDB), control del sistema y de audio, y un sistema de Skills extensible.

**Línea de base técnica:** ~12k líneas de Python, frontend web en `gui/`, suite de tests actual (263 tests).

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

### Gestión de memoria — Fase 3 (bóveda: `origen_id`, ciclo de olvido y anti-reaparición)
Objetivo: cerrar las dos deudas documentadas de la Fase 2 — la reaparición de datos por consolidación IA y la bóveda desincronizada.

- [x] **`origen_id` determinista en la bóveda:** `guardar_recuerdo()` genera un `origen_id` canónico `boveda:memoria_ia:<hash>` (o respeta uno explícito); la familia lógica agrupa los documentos con el mismo origen.
- [x] **Backfill histórico (`modulos/backfill_boveda.py`):** migra los documentos existentes de la bóveda a `origen_id` (18/18 migrados, 16 `origen_id` únicos, 0 ambiguos). Backup previo en `backups/boveda_memoria_20260810_151540`; `--dry-run` no escribe.
- [x] **Ciclo "Olvidar esto" sobre la bóveda:** `resolver_olvidar("boveda:<origen>")` → `invalidar_por_origen()` borra TODA la familia del documento en ChromaDB y registra el tombstone en `modulos/olvidos.py`. Repetir el olvido del mismo origen es idempotente y no afecta a familias distintas.
- [x] **Protección contra reaparición:** `guardar_recuerdo()` consulta `esta_olvidado(origen_id)` (lazy) y rechaza re-guardar una familia tombstoned; `quitar_olvido()` actúa como "desolvidar" y rehabilita la familia.
- [x] **Tests:** `tests/test_olvido_ciclo_integracion.py` (7 tests, ChromaDB real en tmp, embeddings deterministas, `RUTA_OLVIDOS` en tmp) + `tests/test_backfill_boveda.py` (11 tests) + `tests/test_integracion_boveda.py` (6 tests). **Suite total: 263 tests pasando.**

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
- [ ] **Fijar versiones exactas** en `requirements.txt` (hoy hay varias con `>=`)
- [ ] **Retry con backoff exponencial** en llamadas a APIs (`modulos/ia.py`)
- [ ] **Fragmentar** `gui/app.js` y `gui/styles.css` (1200 / 1627 líneas) en módulos

## 4. 🚀 Fase 2 — Producto

Objetivo: pasar de "demo impresionante" a "herramienta que no pierde el trabajo del usuario".

- [ ] **Persistencia del contexto de chat** (no perder conversación si la app crashea)
- [ ] **Graceful shutdown** (guardar estado, cerrar ChromaDB, detener timers al salir)
- [ ] **Validación amigable de API keys** (hoy `config.py` crashea con `ValueError` si falta `GEMINI_API_KEY`)
- [ ] **Sacar rutas hardcodeadas** (`E:\Mis_Juegos_Yiri`, `c:\users\luis\` en `sistema.py`) → mapeo por máquina en `config.py`
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

## 7. Orden de implementación sugerido

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

Expansión (cuando el producto sea estable):
  ⑦ FastAPI + PWA (Fase 4a → 4d)
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
| 3 | Sin type hints en módulos clave | `sistema.py`, `audio_custom.py`, `controlador_acciones.py` | Mantenimiento difícil |
| 4 | `config.py` crashea sin API key | `config.py` | Arranque frágil |
| 5 | Contexto de chat en memoria (se pierde) | `config.py` | Pérdida de trabajo del usuario |
| 6 | Versiones flotantes | `requirements.txt` | Puede romper |
| 7 | JS/CSS monolíticos | `gui/app.js`, `gui/styles.css` | Difícil de mantener |
| 8 | Sin `__version__` ni CHANGELOG | — | No se trackea la evolución |
| 9 | TTS sin timeout de red | `modulos/audio_custom.py` | Bloqueo sin internet |
