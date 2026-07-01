# PROJECT_STATE.md — Fuente de la Verdad

## 1. Resumen Ejecutivo

**Argus** (código interno: OmniAssistant) es un asistente de IA de escritorio para Windows con interfaz gráfica (`customtkinter`), control por voz y gamepad, capaz de interactuar con múltiples modelos de lenguaje (Gemini Flash, DeepSeek Reasoner), gestionar memoria a largo plazo (bóveda vectorial ChromaDB), ejecutar acciones locales (archivos, sistema, Git, audio) y realizar búsquedas web actualizadas. Su propósito es actuar como copiloto integral de productividad, programación y gaming, integrando voz, visión y automatización del sistema.

## 2. Arquitectura

### Módulos principales

| Módulo | Archivo(s) | Propósito |
|---|---|---|
| **Configuración global** | `config.py` | Variables de entorno, API keys, estado global thread-safe (`EstadoGlobal`), límites de seguridad, rutas de sandbox. |
| **Interfaz gráfica** | `main_gui.py` | Aplicación con sidebar, chat, input bar, tabs de logs. Maneja modo gaming, gamepad, envío de mensajes y renderizado Markdown. |
| **Orquestador IA** | `modulos/ia.py` | Enrutador principal: recibe input, selecciona modelo (Gemini / DeepSeek), gestiona streaming, ejecuta herramientas MCP (memoria, sistema, archivos, web) y encola acciones. |
| **Controlador de acciones** | `modulos/controlador_acciones.py` | Parsea la respuesta de la IA, detecta comandos (leer_archivo, guardar_archivo, reemplazar_bloque, audio:, buscar:, github:, etc.) y los ejecuta. |
| **Archivos y sistema** | `modulos/archivos.py`, `modulos/sistema.py` | Operaciones seguras sobre archivos (lectura/escritura/eliminación) con verificación de sandbox; comandos de sistema (abrir, cerrar, mover ventanas, explorar directorios, estado PC). |
| **Memoria persistente** | `modulos/memoria.py` | Bóveda ChromaDB con embeddings `all-MiniLM-L6-v2`. Guardado/búsqueda de recuerdos, snapshots de proyecto, radar watchdog con debounce. |
| **Audio** | `modulos/audio_custom.py` | Síntesis Edge TTS, captura de voz con Whisper (lazy loading), cola de reproducción con Pygame. |
| **Búsqueda web** | `modulos/busqueda.py` | Búsqueda DuckDuckGo con retrys y limpieza de filtros incompatibles. |
| **Git** | `modulos/git_bot.py` | Sincronización Git (init, add, commit, pull, push) y comandos libres. |
| **Gamepad** | `modulos/gamepad_control.py` | Detección de mando vía pygame.joystick, combo L3+R3 push-to-talk sin hooks de teclado (evita conflictos con juegos). |
| **Visión** | `modulos/vision.py` | Captura de pantalla por monitor usando Pillow y screeninfo. |
| **Prompts** | `modulos/prompts.py` | Construcción de system prompts para modos general, programador/planificador. |
| **Gestor de skills** | `modulos/skills/gestor_skills.py` | Detección y activación de skills por palabras clave. |
| **Skills implementadas** | `modulos/skills/busqueda_web_actualizada/`, `modulos/skills/control_audio/` | Búsqueda web actualizada (instrucciones + ejemplos) y control de audio via pycaw (instrucciones + implementación real). |
| **Cliente MCP** | `modulos/cliente_mcp.py` | Puente síncrono para herramientas MCP (estado PC, hardware, bóveda, exploración). |
| **Gestor de bóveda** | `gestor_boveda.py` | CLI para listar, borrar y resetear la bóveda ChromaDB. |
| **Logger** | `modulos/logger.py` | Logging a archivo y consola. |

### Flujo de datos típico

1. Usuario envía input (texto/voz/gamepad).
2. `ia.py` recibe, ejecuta confirmaciones locales (sin IA para borrado/Git), inyecta skills relevantes y envía al modelo correspondiente.
3. Durante streaming, la IA puede invocar herramientas MCP (bóveda, sistema, archivos) o emitir comandos de acción.
4. `controlador_acciones.py` parsea la respuesta y ejecuta las acciones (audio, Git, archivos, búsqueda web).
5. Si hay búsqueda web, se realiza una segunda llamada al modelo para integrar resultados.

## 3. Estado Actual

### Funcionalidades construidas y operativas

| Funcionalidad | Estado | Detalle |
|---|---|---|
| **Chat multimodal** | ✅ Operativo | Entrada texto, voz (F8), gamepad (L3+R3) y adjuntos. Streaming de IA con renderizado Markdown (código, tablas, listas). |
| **Modelos duales** | ✅ Operativo | Gemini Flash (modo general), DeepSeek Reasoner (modo programador/planificador). |
| **Memoria persistente** | ✅ Operativo | ChromaDB con embeddings; guardado/búsqueda directa sin MCP, caché de embeddings, búsqueda anticipada. |
| **Radar watchdog** | ✅ Operativo | Vigilancia de cambios en workspace con debounce de 500 ms; invalida caché de archivos modificados. |
| **Control de audio** | ✅ Operativo | Volumen maestro, volumen por app, silenciar, listar apps. Requiere `pycaw`. |
| **Búsqueda web actualizada** | ✅ Operativo | DuckDuckGo con retry automático; skill activable por palabras clave. |
| **Acciones de sistema** | ✅ Operativo | Abrir/cerrar programas, mover ventanas a monitores, explorar directorios, estado PC (CPU, RAM, GPU). |
| **Git** | ✅ Operativo | Init, add, commit, pull, push; comandos libres. Confirmación nativa sin juez IA. |
| **Control por gamepad** | ✅ Operativo | Combo L3+R3 para push-to-talk; detección automática de mapeo por nombre (DualSense/Xbox). |
| **Adjuntos de archivos** | ✅ Operativo | Carga en contexto volátil con resumen automático. |
| **Snapshot de proyecto** | ✅ Operativo | Guardado/carga de estado del workspace en `.cortana/snapshot.json`. |
| **Modo gaming** | ✅ Operativo | Pausa de micrófono + liberación de VRAM de Whisper. |
| **Gestor de bóveda** | ✅ Operativo | CLI para listar, eliminar o resetear recuerdos. |

### Bugs conocidos / limitaciones

- **Temperatura CPU:** `psutil` no reporta temperatura en Windows; se depende de LibreHardwareMonitor (no implementado aún).
- **Confirmaciones GUI:** Las confirmaciones de borrado/Git se hacen por texto en el chat, no por popup nativo (`CTkDialog`).
- **SDK Gemini deprecado:** Se usa `google.generativeai`; migración a `google.genai` pendiente.
- **Detección de skills:** Por palabras clave hardcodeadas; no usa embeddings semánticos.
- **Historial por modo:** Se guarda en `_historial_por_modo` (solo en UI) pero no persiste entre reinicios.
- **Archivos temporales de audio:** No se limpian en caso de cierre abrupto.

## 4. Deuda Técnica / Próximos Pasos

### Prioridad Alta (impacto diario inmediato)

- **Migración al nuevo SDK de Gemini** (`google.genai`). Urgente: el actual está deprecado.
- **Skills faltantes del roadmap:** `recordatorios` (threading.Timer + notificación), `monitor_hardware` (LibreHardwareMonitor + WMI).
- **Confirmaciones nativas GUI:** Reemplazar el texto de confirmación por popup `CTkDialog` para borrados y Git.

### Prioridad Media (próximas semanas)

- **Detección de skills por embeddings:** Usar el mismo modelo MiniLM de ChromaDB en lugar de palabras clave.
- **Clima/tiempo:** Skill liviana usando `wttr.in`.
- **Steam integration:** Consultar biblioteca y horas vía Steam Web API.
- **Portapapeles inteligente:** Historial de clips con `pyperclip`.

### Prioridad Baja (mejoras y refactors)

- **Unificar estado global:** Eliminar `_AppState` en `main_gui.py` y usar solo `config.EstadoGlobal` con locks.
- **Inicio automático de LibreHardwareMonitor:** Como parte de la skill `monitor_hardware`.
- **Resumen de contenido web/YouTube:** Usar `yt-dlp` y `trafilatura`.
- **Monitoreo de procesos:** Listar/matar procesos con `psutil`.
- **Traductor:** Usar `deep-translator` o llamada directa a DeepSeek.

### Deuda técnica identificada

1. **Duplicación de estado:** `_StateProxy` en UI vs `config.estado` — fuente de potenciales race conditions.
2. **MCP como proceso externo:** Aunque la bóveda ya se accede directo, otras herramientas MCP siguen spawniendo un proceso Python cada vez (latencia ~3s).
3. **Hardcodeo de user path:** `"C:\\Users\\luism"` aparece en `sistema.py`; debería usar `os.path.expanduser("~")`.
4. **Sin tests automatizados:** El proyecto no cuenta con suite de pruebas unitarias ni de integración.
5. **Dependencias sin fijar:** `chromadb==1.5.9` vs versiones posteriores; `pygame` sin versión específica.
6. **Archivos temporales:** Los WAV/MP3 de voz se guardan en `tempfile.gettempdir()` pero no se asegura limpieza si el proceso se mata.

---

*Documento generado por el Arquitecto Principal del proyecto.*  
*Versión: v0.3.1 — Basado en el código completo proporcionado.*