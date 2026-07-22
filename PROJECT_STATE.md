# PROJECT_STATE.md

## 1. Resumen Ejecutivo
Argus es un asistente de IA multimodal avanzado diseñado para el ecosistema Windows. Su propósito es actuar como un copiloto de escritorio capaz de interactuar con el sistema operativo, gestionar proyectos de software, controlar hardware y mantener una memoria persistente a largo plazo. Se distingue por su arquitectura dual de interfaz (GUI nativa con CustomTkinter y Web HUD flotante/escritorio basado en PyWebView + Edge Chromium WebView2), sus tres modos especializados (**General**, **Mentor Tecnológico** y **Gamer**) con 3 modos de visualización (Tradicional, Widget Flotante y Fondo de Escritorio anclado a WorkerW vía Win32), e integración profunda con voz, visión, gamepad multi-mando y perfil de usuario/mentor persistente.

## 2. Arquitectura

### Núcleo y Configuración
*   **`config.py`**: Núcleo de configuración, gestión de estado global thread-safe (`EstadoGlobal` con `threading.Lock`) y límites de seguridad. Proporciona métodos seguros para acceso thread-safe a `contexto_chat`, `archivos_en_memoria`, `modelo_seleccionado` y contador para extracción de perfil.
*   **`main_gui.py`**: Interfaz gráfica principal (CustomTkinter) con renderizado de Markdown, selector de modelo activo, padding responsivo, burbujas de chat, soporte de eventos, y la cabecera interactiva dual con selector en caliente entre EMO (`EmoBezelFace`) y Argus v2 (`RostroArgus`).
*   **`main_web.py`**: Punto de entrada al Web HUD basado en PyWebView (Edge Chromium WebView2). Carga la interfaz web moderna en `gui/` (`index.html`, `app.js`, `emo_face.js` a 60 FPS, `styles.css`) con soporte para temas neón dinámicos, atajo global F8 y push-to-talk vía gamepad.
*   **`gestor_boveda.py`**: Script independiente para gestión de la bóveda vectorial (búsqueda y guardado directo).
*   **`test_emo_face.py`**: Script independiente en la raíz para pruebas y simulación aislada de todas las expresiones del rostro EMO.
*   **`mapeo_control_prueba.py`**: Utilidad de diagnóstico y mapeo de mandos en la raíz.

### Interfaz y Modos de Visualización Win32
*   **`modulos/ui_manager.py`**: Gestor de modos de visualización utilizando el patrón Strategy (`IWindowHost`). Implementa `TraditionalWindowHost` (ventana estándar), `FloatingWidgetHost` (widget flotante sin bordes) y `DesktopModeHost` (modo fondo de pantalla).
*   **`modulos/win32_desktop.py`**: Integración Win32 API mediante `ctypes` (64-bit). Permite desovar ventanas `WorkerW` para reparenting de la GUI de Argus al escritorio (estilo Wallpaper Engine / Rainmeter), ocultar la ventana en la barra de tareas (`WS_EX_TOOLWINDOW`), y gestionar resoluciones multi-monitor con DPI Awareness.
*   **`modulos/web_bridge.py`**: Puente de comunicación bidireccional thread-safe entre JavaScript y Python (`window.pywebview.api`). Expone métodos como `enviar_mensaje`, `cambiar_modo_interfaz`, `iniciar_escucha_voz`, `seleccionar_perfil_mentor`, `cambiar_modelo_seleccionado` y resuelve dinámicamente el modelo activo (`resolver_modelo_actual`).

### Inteligencia Artificial
*   **`modulos/ia.py`**: Enrutador central de IA que gestiona la comunicación con Gemini (SDK `google-genai`), DeepSeek (API compatible OpenAI) y Groq (API compatible OpenAI con soporte de streaming unificado para Llama 3.3 70B, Llama 3.1 8B, Qwen 3.6 27B y GPT-OSS 120B). Implementa streaming de voz paralelo, herramientas MCP nativas, fallback automático, confirmaciones locales sin juez IA (basadas en palabras clave), e inyección contextual de Skills.
*   **`modulos/prompts.py`**: Generación de prompts de sistema para cada modo (General, Mentor, Gamer), con contexto de perfil de usuario, perfil de mentor, workspace y documentos volátiles.

### Persistencia y Memoria
*   **`modulos/memoria.py`**: Motor de persistencia basado en ChromaDB con caché de embeddings (`SentenceTransformer all-MiniLM-L6-v2`), búsqueda anticipada (pre-fetch en hilo paralelo), snapshots de proyecto y radar de cambios vía `watchdog` con debounce.
*   **`modulos/perfil_usuario.py`**: Perfil de usuario persistente (`perfil_usuario.json`) con extracción automática de hechos atómicos vía Gemini Flash-Lite, fusión inteligente, filtro de secretos y consolidación automática.
*   **`modulos/perfil_mentor.py`**: Gestor persistente del perfil del mentor (`perfil_mentor.json`). Mantiene el stack objetivo del usuario, tecnologías en estudio/aprendidas, proyectos de portafolio y preguntas de diagnóstico.

### Interacción con el Sistema y Periféricos
*   **`modulos/controlador_acciones.py`**: Intérprete de comandos de la IA que ejecuta acciones en el sistema: guardado/lectura/edición de archivos (Markdown y XML), reemplazo de bloques por Regex, control de audio maestro y por app, operaciones Git, creación de carpetas, escaneo con crawler y comandos de sistema.
*   **`modulos/sistema.py`**: Capa de interacción con Windows (procesos, ventanas, hardware, explorador de directorios, estado del PC).
*   **`modulos/archivos.py`**: Operaciones de archivos con sandbox de seguridad (validación de rutas, truncado por tamaño, detección de binarios).
*   **`modulos/busqueda.py`**: Búsqueda web en DuckDuckGo.
*   **`modulos/git_bot.py`**: Automatización de flujos de trabajo Git (add/commit/pull/push/reset/comandos libres) con confirmaciones vía chat.
*   **`modulos/gamepad_control.py`**: Gestor de mandos de juego que conecta los eventos de gamepad con la interfaz.
*   **`modulos/gamepad_service.py`**: Servicio independiente en subproceso para lectura continua de mandos (Xbox / DualSense).
*   **`modulos/xinput_reader.py`**: Lector XInput nativo (ctypes Win32) utilizado como fallback cuando juegos en primer plano capturan Pygame/SDL, garantizando el funcionamiento de la combinación L3+R3.
*   **`modulos/gamepad_inputs.py`**: Definiciones y mapeos de botones para diferentes controladores.

### Audio y Voz
*   **`modulos/audio_custom.py`**: Pipeline completo de voz: Whisper (faster-whisper GPU/CPU) para transcripción STT, Edge TTS para síntesis hablada con colas thread-safe y corte por oraciones o teclas.
*   **`modulos/vision.py`**: Captura de pantalla multi-monitor para análisis visual con Gemini.

### Skills y Extensibilidad
*   **`modulos/skills/gestor_skills.py`**: Gestor de inyección contextual de Skills.
*   **`modulos/skills/busqueda_web_actualizada/`**: Skill de búsqueda web en DuckDuckGo priorizando información reciente (v1.0 Operativa).
*   **`modulos/skills/control_audio/`**: Skill de control de audio (`audio_control.py`, pycaw) para volumen maestro, volumen por app, mute/unmute y cambio de dispositivos de salida (v1.0 Operativa).

### Infraestructura
*   **`modulos/crawler.py`**: Herramienta de introspección que escanea proyectos y genera `PROJECT_STATE.md` con análisis de arquitectura vía Gemini.
*   **`modulos/servidor_sistema_mcp.py`**: Servidor MCP que expone herramientas del sistema para la IA.
*   **`modulos/cliente_mcp.py`**: Cliente MCP para comunicación con el servidor de sistema.
*   **`modulos/logger.py`**: Sistema de logging estructurado.
*   **`modulos/limpiar.py`**: Utilidad de limpieza de contexto y memoria.

## 4. Estado Actual
*   **Multimodalidad**: Soporte completo de voz (Whisper STT + Edge TTS), visión (captura de pantalla multi-monitor), entrada por gamepad (XInput / Pygame), y renderizado dual de rostros interactivos en 2D SVG/Canvas a 60 FPS (EMO y Argus v2) con lectura de emociones (`[EMOTION: happy/sad/angry]`), animaciones inactivas espontáneas y temas cromáticos por modo.
*   **Interfaces**: 
    - **GUI Desktop (CustomTkinter)**: Chat responsivo con Markdown, selector de modelos, menú de temas y soporte para 3 modos de visualización Win32 (`ui_manager.py`).
    - **Web HUD (PyWebView + WebView2)**: Interfaz web flotante/escritorio acelerada por GPU, con temas neón dinámicos, puente bidireccional Python-JS (`web_bridge.py`) y sincronización en tiempo real.
*   **Modos de Operación**:
    - **General**: Asistente cotidiano (Gemini 3.1 Flash Lite por defecto).
    - **Mentor Tecnológico**: Asesoría de stack, portafolio y preguntas de diagnóstico (`perfil_mentor.py`, DeepSeek Reasoner por defecto).
    - **Gamer**: Respuesta ultra rápida para juegos (Groq Llama 3.1 8B por defecto, F8 desactivado, push-to-talk por gamepad L3+R3).
*   **Perfil de Usuario y Mentor**: Extracción automática de hechos atómicos cada 20 mensajes y perfil del mentor sincronizado en JSON.
*   **Skills Operativas**:
    - `busqueda_web_actualizada` (v1.0)
    - `control_audio` (v1.0 con pycaw)
*   **Memoria y Thread Safety**: Bóveda vectorial ChromaDB con caché de embeddings y watchdog de cambios. Mutaciones de estado protegidas con `threading.Lock` en `config.EstadoGlobal`.

## 4. Deuda Técnica / Próximos Pasos

### Logros Recientes ✅
*   [x] Migración completa a `google-genai` (nuevo SDK oficial).
*   [x] Desarrollo del Web HUD nativo en PyWebView con Edge Chromium WebView2 (`main_web.py` + `web_bridge.py` + `gui/`).
*   [x] Implementación de la Skill `control_audio` (volumen maestro y por aplicación).
*   [x] Implementación de arquitectura Win32 Wallpaper Engine / Reparenting a `WorkerW` (`win32_desktop.py` y `ui_manager.py`).
*   [x] Subproceso de Gamepad con fallback a XInput nativo para captura continua durante juegos (`gamepad_service.py` + `xinput_reader.py`).

### Próximas Prioridades 🔄
*   [ ] **Skill `monitor_hardware`**: Monitoreo de temperatura real CPU/GPU mediante `LibreHardwareMonitor` y `wmi`.
*   [ ] **Skill `recordatorios`**: Gestión de alertas temporales con notificaciones de Windows y voz.
*   [ ] **Detección de Skills por Embeddings**: Migrar la detección de palabras clave en `gestor_skills.py` a similitud semántica con `all-MiniLM-L6-v2`.
*   [ ] **Confirmaciones GUI**: Reemplazar confirmaciones de texto en chat por diálogos popups nativos (`CTkDialog` / Modales Web) para ahorrar tokens y mejorar UX.
*   [ ] **Coincidencia de Palabras Exactas en Confirmaciones**: Refinar `_evaluar_confirmacion_local()` con regex `\b` para evitar falsos positivos.
*   [ ] **Población del Suite de Tests**: Crear tests unitarios e integrales estructurados dentro de la carpeta `tests/`.
