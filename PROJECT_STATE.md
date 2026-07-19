# PROJECT_STATE.md

## 1. Resumen Ejecutivo
Argus es un asistente de IA multimodal avanzado diseñado para el ecosistema Windows. Su propósito es actuar como un copiloto de escritorio capaz de interactuar con el sistema operativo, gestionar proyectos de software, controlar hardware y mantener una memoria persistente a largo plazo. Se distingue por su capacidad de operar en modos especializados (General, Programador, Planificador) y su integración profunda con voz, visión, gamepad y un perfil de usuario persistente.

## 2. Arquitectura

### Núcleo y Configuración
*   **`config.py`**: Núcleo de configuración, gestión de estado global thread-safe (`EstadoGlobal` con `threading.Lock`) y límites de seguridad. Proporciona métodos seguros para acceso thread-safe a `contexto_chat`, `archivos_en_memoria`, `modelo_seleccionado` y contador para extracción de perfil.
*   **`main_gui.py`**: Interfaz gráfica principal (CustomTkinter) con renderizado de Markdown, selector de modelo activo, padding responsivo, burbujas de chat, soporte de eventos, y un contenedor de rostro interactivo dinámico con un selector segmentado de caras que permite alternar en caliente entre EMO (`EmoBezelFace`) y Argus v2 (`RostroArgus`) preservando el estado de la conversación.
*   **`modulos/rostro_argus.py`**: Implementación nativa de Tkinter.Canvas para el rostro de Argus con transición de suavizado mediante interpolación física y estados expresivos dinámicos (soporta ejecución directa para pruebas).
*   **`gestor_boveda.py`**: Script independiente para gestión de la bóveda vectorial (búsqueda y guardado directo).
*   **`test_emo_face.py`**: Script independiente en la raíz para pruebas y simulación aislada de todas las expresiones del rostro EMO.
*   **`test_argus_face.html`**: Prototipo web interactivo del rostro v2 de Argus con partículas ambientales y panel de emociones.

### Inteligencia Artificial
*   **`modulos/ia.py`**: Enrutador central de IA que gestiona la comunicación con Gemini (SDK `google-genai`), DeepSeek (API compatible OpenAI) y Groq (API compatible OpenAI con soporte de streaming unificado para modelos como Llama y Qwen), con streaming de voz paralelo, herramientas MCP nativas, fallback automático, confirmaciones locales sin juez IA (basadas en palabras clave), e inyección de Skills.
*   **`modulos/prompts.py`**: Generación de prompts de sistema para cada modo (general, programador, planificador), con contexto de perfil de usuario, workspace y documentos volátiles.

### Persistencia y Memoria
*   **`modulos/memoria.py`**: Motor de persistencia basado en ChromaDB con caché de embeddings (`SentenceTransformer all-MiniLM-L6-v2`), búsqueda anticipada (pre-fetch en hilo paralelo), snapshots de proyecto y radar de cambios vía `watchdog` con debounce.
*   **`modulos/perfil_usuario.py`**: Perfil de usuario persistente (JSON) con extracción automática de hechos atómicos vía Gemini Flash-Lite, fusión inteligente de vida personal, filtro de secretos, consolidación automática al superar el umbral de tamaño, y filtro de mensajes técnicos largos para no desperdiciar tokens en extracción.

### Interacción con el Sistema
*   **`modulos/controlador_acciones.py`**: Intérprete de comandos generados por la IA que ejecuta acciones en el sistema: guardado/lectura/edición de archivos (soporta formatos Markdown y XML), reemplazo de bloques con búsqueda exacta y flexible (Regex), control de audio (volumen, dispositivos, apps por separado), operaciones Git, creación de carpetas, escaneo completo de proyectos con crawler, y comandos de sistema (abrir/navegar/cerrar/mover/explorar). Toda mutación de contexto es thread-safe.
*   **`modulos/sistema.py`**: Capa de interacción con Windows (procesos, ventanas, hardware, explorador de directorios, estado del PC).
*   **`modulos/archivos.py`**: Operaciones de archivos con sandbox de seguridad (validación de rutas, truncado por tamaño, detección de binarios).
*   **`modulos/busqueda.py`**: Búsqueda web con APIs de búsqueda.
*   **`modulos/git_bot.py`**: Automatización de flujos de trabajo Git (add/commit/pull/push/reset/comandos libres) con confirmaciones vía chat.

### Audio y Voz
*   **`modulos/audio_custom.py`**: Pipeline completo de voz: Whisper (STL) para transcripción, Edge TTS para síntesis, con gestión de colas, streaming paralelo al streaming de IA, y corte por oraciones.
*   **`modulos/vision.py`**: Captura de pantalla para entrada visual a Gemini.

### Periféricos y Extensibilidad
*   **`modulos/gamepad_control.py`**: Soporte para mandos (gamepad) con detección automática, selector multi-mando, y activación por voz mediante botones físicos (L3+R3). Integración con Modo Gaming que descarga Whisper de VRAM.
*   **`modulos/skills/`**: Sistema modular de capacidades extensibles: `control_audio` (volumen/apps vía pycaw), `busqueda_web_actualizada`, y gestor de skills con detección por palabras clave.

### Infraestructura
*   **`modulos/crawler.py`**: Herramienta de introspección que escanea proyectos y genera `PROJECT_STATE.md` con análisis de arquitectura vía Gemini.
*   **`modulos/servidor_sistema_mcp.py`**: Servidor MCP que expone herramientas del sistema para la IA.
*   **`modulos/cliente_mcp.py`**: Cliente MCP para comunicación con el servidor de sistema.
*   **`modulos/logger.py`**: Sistema de logging estructurado.
*   **`modulos/limpiar.py`**: Utilidad de limpieza de contexto y memoria.

## 3. Estado Actual
*   **Multimodalidad**: Soporte completo de voz (Whisper STT + Edge TTS con sincronización limpia de fin de habla y salida de audio en fallback de contingencia), visión (captura de pantalla, integración PIL con SDK google-genai), entrada por gamepad y **pantalla interactiva dual (EMO / Argus)** con lectura dinámica de sentimientos (etiquetas `[EMOTION: happy/sad/angry]`), confirmaciones visuales de sistema (guiño/wink), alertas en color rojo de fallos (`error`), y acciones inactivas autónomas.
*   **Modelos**: Integración con Gemini 3.1 Flash Lite (SDK `google-genai`), DeepSeek V4 (API compatible OpenAI) y Groq (API compatible OpenAI con soporte para Llama 3.3 70B, Llama 3.1 8B, Qwen 3.6 27B y GPT-OSS 120B). Fallback automático entre modelos ante bloqueos por safety/PII.
*   **Perfil de Usuario**: Sistema de hechos atómicos funcional con extracción automática cada 20 mensajes, extracción manual desde UI, filtro de secretos, fusión sin duplicados y consolidación automática.
*   **Memoria**: Bóveda vectorial (ChromaDB + SentenceTransformer) con búsqueda anticipada, caché de embeddings con TTL, snapshots por proyecto, y radar de cambios con watchdog + debounce.
*   **Thread Safety**: Todas las mutaciones de `contexto_chat` y `archivos_en_memoria` pasan por métodos thread-safe con lock. El parámetro `contar_para_perfil` permite controlar qué mensajes incrementan el contador de extracción de perfil.
*   **Control de Archivos**: Guardado, lectura, edición (1 línea), reemplazo de bloques (exacto y flexible), y creación de carpetas. Soporte dual de sintaxis: Markdown nativo y XML.
*   **Control de Audio**: Gestión completa de volumen maestro, volumen por aplicación, dispositivos de salida, con confirmación por voz del resultado.
*   **Integración Git**: Add/Commit/Pull/Push, reset forzado, comandos libres, todo con confirmación nativa vía chat (sin juez IA).
*   **Interfaz**: GUI responsiva con padding dinámico según ancho de ventana, menú desplegable (CTkOptionMenu) en la barra lateral para selección de modelo en tiempo real (con sincronización con los módulos de IA), renderizado de Markdown (negrita, itálica, código inline, bloques de código con syntax highlighting, tablas, listas, encabezados), burbujas de usuario con ancho máximo dinámico, y botón de copiado en respuestas de IA. Integra en la cabecera de la barra lateral una pantalla interactiva dual con selector segmentado en caliente que permite alternar entre EMO (`EmoBezelFace`) y Argus v2 (`RostroArgus`). Ambos rostros proyectan expresiones vectoriales fluidas en tiempo real, incluyendo animaciones espontáneas inactivas (guiños, bostezos, suspiros y curiosidad) con un fondo negro limpio.
*   **Modo Gaming**: Desactiva micrófono de teclado, descarga Whisper de VRAM, activa gamepad con botón L3+R3 para hablar.
*   **Confirmaciones Locales**: Sistema de confirmación/cancelación de operaciones críticas (borrado, Git, guardado en bóveda) sin llamar a la IA, basado en diccionarios de palabras clave.
*   **Skills**: Sistema de inyección contextual operativo para búsqueda web y control de audio, con detección por palabras clave.
*   **Logging**: Sistema de logs con `logging` y redirección de stdout/stderr a la UI.

## 4. Deuda Técnica / Próximos Pasos
*   **Detección de Skills**: Migrar la detección de skills basada en palabras clave a una basada en embeddings semánticos (usando el modelo `all-MiniLM-L6-v2` ya presente en memoria).
*   **Confirmaciones GUI**: Reemplazar las confirmaciones de texto en el chat por popups nativos (`CTkDialog`) para mejorar la UX y reducir el consumo de tokens.
*   **Monitor de Hardware**: Implementar la skill de monitoreo de temperatura real mediante `LibreHardwareMonitor` y `wmi`.
*   **Recordatorios**: Implementar la skill de gestión de alertas temporales.
*   **Robustez en Audio**: Refinar el manejo de errores en el streaming de voz para evitar bloqueos en caso de latencia de red o microcortes.
*   **Módulos UI**: Extraer `main_gui.py` (~1434 líneas) en submódulos: `ui/chat_widgets.py` (burbujas), `ui/theme.py` (paleta), `ui/markdown_renderer.py` (renderizado).
*   **Refactor ia.py**: `enviar_a_gemini()` (>600 líneas) mezcla enrutamiento, streaming, MCP, voz y acciones. Separar en `core/enrutador.py`, `core/streaming.py`.
*   **Modelo centralizado**: Centralizar el nombre del modelo Gemini (`gemini-3.1-flash-lite`) en `config.py` en vez de hardcodearlo en 9+ lugares.
*   **Confirmaciones por palabra exacta**: `_evaluar_confirmacion_local()` usa `in` (coincidencia parcial), lo que puede causar falsos positivos (ej. "no sé" contiene "sí", "no es necesario" contiene "no"). Migrar a coincidencia de palabras completas con `\b`.
*   **Consolidación MCP/sistema**: Revisar la redundancia entre `modulos/sistema.py` y las herramientas MCP nativas definidas en `ia.py`.
