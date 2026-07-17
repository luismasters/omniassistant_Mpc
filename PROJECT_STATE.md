# PROJECT_STATE.md — Fuente de la Verdad

## 1. Resumen Ejecutivo

**Argus** es un asistente de IA multimodal integrado al escritorio de Windows, diseñado para operar en tres modos (General, Programador y Planificador) con cambio dinámico de modelo de lenguaje (Gemini Flash para el modo General, DeepSeek Reasoner para modos avanzados). Su núcleo es una **interfaz gráfica en CustomTkinter** con soporte de voz (Edge TTS + Whisper), búsqueda web (DuckDuckGo), control de sistema (ventanas, procesos, audio), gestión de archivos con sandbox de seguridad, memoria persistente vía ChromaDB, control de gamepad (L3+R3 push‑to‑talk), y un sistema extensible de **Skills** (inyección contextual). Está en **fase activa de expansión**, con integración continua de nuevas capacidades (audio, monitoreo de hardware, recordatorios).

## 2. Arquitectura

| Archivo / Módulo | Propósito |
|---|---|
| `config.py` | Cargar variables de entorno, parches para memoria y GPU (Whisper/chromadb), clase `EstadoGlobal` thread‑safe que centraliza el estado de la aplicación (modo, workspace, contexto, archivos en memoria, pendientes de Git/borrado). |
| `main_gui.py` | Interfaz gráfica principal con CustomTkinter: sidebar de modos, área de chat con renderizado de markdown (código, tablas, listas), barra de entrada con placeholder, botones adjuntar/guardar en memoria. Maneja hilos de micrófono, gamepad y callbacks de IA. |
| `modulos/ia.py` | Enrutador universal de mensajes: selecciona modelo (Gemini o DeepSeek), inyecta prompts según modo y skills, maneja streaming de respuesta y voz en paralelo, ejecuta confirmaciones nativas sin juez IA, procesa acciones de archivo/audio/git/sistema. |
| `modulos/prompts.py` | Contiene las plantillas de system prompt para cada modo: `obtener_prompt_general`, `obtener_prompt_programador_unificado`, y el prompt dinámico para la skill de búsqueda web. |
| `modulos/audio_custom.py` | Captura de voz con Whisper (lazy loading), síntesis y reproducción con Edge TTS + pygame, cola de reproducción thread‑safe, limpieza de texto para voz. |
| `modulos/memoria.py` | Capa de persistencia vía ChromaDB: guardar/buscar recuerdos, caché de embeddings con TTL, búsqueda anticipada en hilo paralelo, snapshot de proyecto (JSON), y radar de cambios (watchdog con debounce). |
| `modulos/controlador_acciones.py` | Parsea la salida de la IA para ejecutar acciones de sistema: lectura/escritura/edición de archivos (soporta formatos Markdown y XML), control de audio, comandos Git, snapshot, búsqueda web, creación de carpetas, escaneo de proyecto completo. |
| `modulos/sistema.py` | Gestión de ventanas (Win32 API), radar inteligente de programas (fuzzy matching con thefuzz), ejecución de comandos `abrir:` / `navegar:` / `cerrar:` / `mover:` / `explorar:`, escaneo de hardware con PowerShell, telemetría de PC (CPU%, RAM, GPU temp con nvidia‑smi). |
| `modulos/archivos.py` | Funciones de I/O con sandbox: `leer_contenido_archivo`, `escribir_archivo`, `crear_carpeta`, `eliminar_elemento`, `listar_contenido`, `buscar_archivo_local`. Incluye validación de tamaño, espacio en disco y seguridad de rutas. |
| `modulos/busqueda.py` | Búsqueda en DuckDuckGo vía `ddgs` con retry automático, limpieza de filtros incompatibles (`after:`), y formateo de resultados con fechas. |
| `modulos/vision.py` | Captura de pantalla con PIL + screeninfo; soporte multi‑monitor. |
| `modulos/git_bot.py` | Automatización Git: init, add, commit, pull con rebase, push. Soporta reset de remoto y comandos libres (`git status`, etc.). |
| `modulos/crawler.py` | Recorre un proyecto entero ignorando carpetas no deseadas y concatena el código de archivos `.py`, `.md`, `.json`, `.txt` para generar el `PROJECT_STATE.md`. |
| `modulos/gamepad_control.py` | Lectura de gamepad vía pygame.joystick, detección automática de mapeo L3/R3 (DualSense → 7‑8, Xbox → 8‑9), hilo de escucha aislado del teclado. |
| `modulos/cliente_mcp.py` | Cliente MCP (Model Context Protocol) para ejecución síncrona con timeout de herramientas del servidor `servidor_sistema_mcp.py`. |
| `modulos/servidor_sistema_mcp.py` | Servidor MCP que expone herramientas: `reporte_estado_pc`, `reporte_hardware`, `buscar_en_boveda`, `guardar_en_boveda`, `explorar_ruta`, `leer_documento`. Se comunica vía stdio JSON‑RPC. |
| `modulos/logger.py` | Configura logging a archivo (`logs/omniassistant.log`) y consola con formato estandarizado. |
| `modulos/limpiar.py` | Script standalone para vaciar completamente la base de datos de ChromaDB. |
| `modulos/skills/gestor_skills.py` | Gestor de Skills: carga dinámica de carpetas `modulos/skills/<skill>/`, detecta relevancia por palabras clave y patrones regex, retorna instrucciones para inyectar en el prompt de la IA. |
| `modulos/skills/busqueda_web_actualizada/` | Skill de búsqueda web con prioridad de resultados recientes (instrucciones, ejemplos, metadatos). |
| `modulos/skills/control_audio/` | Skill de control de audio maestro y por aplicación (`audio_control.py` con pycaw), cambio de dispositivo de salida. |
| `config.py` (re‑listado) | Además de lo anterior, define límites de seguridad (tamaño de archivo, contenido, páginas PDF, espacio mínimo), API Keys, y constantes de audio/Whisper. |
| `requirements.txt` | Dependencias del proyecto: chromadb, customtkinter, faster‑whisper, edge‑tts, pygame, psutil, thefuzz, watchdog, etc. |
| `plan_accion_skills_futuro.md` | Roadmap de próximas skills con prioridades y orden de implementación sugerido. |
| `gestor_boveda.py` | Herramienta CLI standalone para listar/borrar/formatear la bóveda de ChromaDB. |
| `mapeo_control_prueba.py` | Script de diagnóstico para identificar índices de botones L3 y R3 en gamepads. |

## 3. Estado Actual

- **Interfaz gráfica completa**: Chat con renderizado de markdown, selección de modo, adjuntar archivos, guardar en memoria, botón de limpiar contexto, modo gaming con gamepad.
- **Voz funcional**: Captura con Whisper (lazy loading, GPU), síntesis con Edge TTS, reproducción con cola thread‑safe y corte por tecla Esc/espacio.
- **Selección de modelo automática**: Gemini 2.5 Flash en modo General, DeepSeek Reasoner en modos Programador/Planificador.
- **Memoria persistente (ChromaDB)**: Guardado y búsqueda de recuerdos con caché de embeddings y pre‑fetch anticipado.
- **Control de sistema**: Abrir/cerrar/mover ventanas, explorar directorios, apagar PC con tiempos, búsqueda inteligente de programas (fuzzy match).
- **Control de audio**: Volumen maestro y por aplicación (pycaw), listado de apps con audio, cambio de dispositivo de salida (requiere módulo AudioDeviceCmdlets para algunos casos).
- **Git integrado**: Push/pull con confirmación nativa, comandos libres, reset de remoto.
- **Gamepad**: Soporte DualSense y Xbox One, combo L3+R3 push‑to‑talk, selector de mando en GUI.
- **Skills operativas**:
  - `busqueda_web_actualizada` v1.0 (detecta consultas temporales, inyecta instrucciones de búsqueda, limpia filtros after/before).
  - `control_audio` v1.0 (detecta comandos de audio, ejecuta funciones via `audio_control.py`).
- **Seguridad**: Sandbox de archivos, confirmaciones nativas (sin gasto de tokens), límites de tamaño/contenido.
- **Logging**: Archivo `logs/omniassistant.log` con rotación potencial.
- **Búsqueda web**: DuckDuckGo con retry y formateo de fechas.
- **Captura de pantalla**: Multi‑monitor, integrada con comandos de voz "capturá la pantalla X".

## 4. Deuda Técnica / Próximos Pasos

### ✅ Completado (Migraciones)
- **Migración a `google.genai`** (nuevo SDK): Migrado de `google.generativeai` deprecado al nuevo SDK `google.genai`. Cliente inicializado en `modulos/ia.py` línea 49 (`genai.Client`). Incluye uso de `google.genai.types` para herramientas nativas.
- **Memoria directa a ChromaDB**: Optimizada para evitar el overhead del servidor MCP en búsqueda/guardado en bóveda. `mcp_buscar_en_boveda()` y `mcp_guardar_en_boveda()` ahora llaman directo a `modulos.memoria` en lugar de `cliente_sistema.ejecutar()`. Latencia reducida de 3-5s a <500ms.

### Urgente
- **Skill `control_audio` — dependencia externa `pycaw`**: Documentar instalación explícita (`pip install pycaw comtypes`). El cambio de dispositivo de salida falla sin el módulo PowerShell `AudioDeviceCmdlets`.

### Alta prioridad
- **Skill `monitor_hardware`**: Falta implementar (pendiente de LibreHardwareMonitor + WMI). Hoy `mcp_estado_pc` no reporta temperatura de CPU en Windows.
- **Skill `recordatorios`**: Código no implementado aún. Plan detallado en `plan_accion_skills_futuro.md`.
- **Confirmaciones GUI**: Reemplazar el mecanismo de confirmación de acciones (borrado, Git) por un popup nativo de CustomTkinter (`CTkDialog`) en lugar del texto en chat con evaluación local.

### Media prioridad
- **Inicio automático de LibreHardwareMonitor**: Al activar la skill de monitoreo, lanzar el proceso en segundo plano.
- **Detección de skills por embeddings**: Reemplazar palabras clave hardcodeadas por similitud semántica con `all‑MiniLM‑L6‑v2` (ya cargado por ChromaDB).
- **Mejorar robustez de Whisper**: Manejar errores de GPU más allá del lazy loading (si se agota VRAM en gaming, Whisper falla silenciosamente).
- **Performance del chat**: La renderización de markdown puede ser lenta con mensajes muy largos. Considerar virtualización o procesamiento en hilo separado.
- **Cobertura de pruebas**: No hay tests unitarios ni de integración. Vulnerable a regresiones.

### Baja prioridad / Futuro
- **Skill `steam_integration`**, `clima_tiempo`, `portapapeles_inteligente`, `resumen_contenido`, `traductor`, `monitor_procesos` — todas en el roadmap.
- **Unificar estado global**: Eliminar `_StateProxy` en `main_gui.py` y usar directamente `config.EstadoGlobal` para evitar duplicidad.
- **Internacionalización**: Actualmente solo español. Podría ampliarse a otros idiomas.
- **Documentación de usuario**: Falta un README.md y guía de instalación.
- **Limpieza de código**: Algunos módulos (`prompts.py`, `controlador_acciones.py`) tienen funciones largas que podrían dividirse. Las instrucciones de `servidor_sistema_mcp.py` son redundantes con la capa directa en `ia.py` (búsqueda en bóveda ya va directo a ChromaDB).