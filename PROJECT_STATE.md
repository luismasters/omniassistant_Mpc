# PROJECT_STATE.md

## 1. Resumen Ejecutivo
Argus es un asistente de IA multimodal avanzado diseñado para el ecosistema Windows. Su propósito es actuar como un copiloto de escritorio capaz de interactuar con el sistema operativo, gestionar proyectos de software, controlar hardware y mantener una memoria persistente a largo plazo. Se distingue por su arquitectura dual de interfaz (GUI nativa con CustomTkinter y Web HUD flotante/escritorio basado en PyWebView + Edge Chromium WebView2), sus tres modos especializados (**General**, **Mentor Tecnológico** y **Gamer**) con 3 modos de visualización (Tradicional, Widget Flotante y Fondo de Escritorio anclado a WorkerW vía Win32), e integración profunda con voz, visión, gamepad multi-mando y perfil de usuario/mentor persistente.

## 2. Arquitectura

### Núcleo y Configuración
*   **`config.py`**: Núcleo de configuración, gestión de estado global thread-safe (`EstadoGlobal` con `threading.Lock`) y límites de seguridad.
*   **`main_gui.py`**: Interfaz gráfica principal (CustomTkinter) con renderizado de Markdown, selector de modelo activo y soporte de eventos.
*   **`main_web.py`**: Punto de entrada Web HUD (PyWebView + Edge Chromium). Carga la interfaz web moderna en `gui/` con soporte para temas neón dinámicos.
*   **`gestor_boveda.py`**: Script independiente para gestión de la bóveda vectorial.
*   **`test_emo_face.py`**: Prototipo autónomo para simulación del rostro EMO.
*   **`mapeo_control_prueba.py`**: Utilidad de diagnóstico de mandos.

### Interfaz y Modos de Visualización Win32
*   **`modulos/ui_manager.py`**: Gestor de modos de visualización (Strategy Pattern).
*   **`modulos/win32_desktop.py`**: Integración Win32 API (ctypes) para WorkerW, reparenting y DPI Awareness.
*   **`modulos/web_bridge.py`**: Puente bidireccional thread-safe entre JavaScript y Python (PyWebView API).

### Inteligencia Artificial
*   **`modulos/ia.py`**: Enrutador central de IA (Gemini SDK, DeepSeek, Groq). Implementa streaming, herramientas MCP, fallback automático y confirmaciones locales.
*   **`modulos/prompts.py`**: Generación de prompts de sistema para cada modo.

### Persistencia y Memoria
*   **`modulos/memoria.py`**: Motor de persistencia (ChromaDB) con caché de embeddings, búsqueda anticipada y watchdog de cambios.
*   **`modulos/perfil_usuario.py`**: Perfil persistente con extracción automática de hechos atómicos.
*   **`modulos/perfil_mentor.py`**: Gestor persistente del perfil del mentor (stack, proyectos, avances).

### Interacción con el Sistema y Periféricos
*   **`modulos/controlador_acciones.py`**: Intérprete de comandos de IA (archivos, audio, Git, sistema).
*   **`modulos/sistema.py`**: Capa de interacción con Windows (procesos, ventanas, hardware).
*   **`modulos/gamepad_control.py` / `gamepad_service.py`**: Gestor de mandos de juego con subproceso aislado y fallback XInput nativo.
*   **`modulos/audio_custom.py`**: Pipeline de voz (Whisper + Edge TTS).
*   **`modulos/vision.py`**: Captura de pantalla multi-monitor.

### Skills y Extensibilidad
*   **`modulos/skills/gestor_skills.py`**: Gestor de inyección contextual de Skills.
*   **`modulos/skills/busqueda_web_actualizada/`**: Skill de búsqueda web (DuckDuckGo).
*   **`modulos/skills/control_audio/`**: Skill de control de audio (pycaw).

## 3. Estado Actual
*   **Multimodalidad**: Soporte completo de voz, visión, gamepad (XInput/Pygame) y rostros interactivos (EMO/Argus v2) a 60 FPS.
*   **Interfaces**: GUI Desktop (CustomTkinter) y Web HUD (PyWebView) con sincronización en tiempo real.
*   **Modos de Operación**: General, Mentor Tecnológico y Gamer (con optimización de VRAM).
*   **Persistencia**: Bóveda vectorial ChromaDB, perfiles de usuario y mentor en JSON.
*   **Skills Operativas**: `busqueda_web_actualizada` (v1.0) y `control_audio` (v1.0).

## 4. Deuda Técnica / Próximos Pasos

### Deuda Técnica
*   **Tests Automatizados**: La carpeta `tests/` está vacía. Riesgo alto de regresión.
*   **Logging**: Falta rotación de logs (`RotatingFileHandler`), riesgo de llenado de disco.
*   **Rate Limiting**: Falta backoff exponencial en llamadas a APIs de IA.
*   **JS/CSS Monolíticos**: `app.js` y `styles.css` superan las 1000 líneas, dificultando el mantenimiento.
*   **Type Hints**: Ausencia de type hints en módulos críticos (`sistema.py`, `audio_custom.py`).

### Próximos Pasos
*   **Fase 2 (Testing)**: Configurar `pytest` y crear tests unitarios para `sistema.py` y `controlador_acciones.py`.
*   **Fase 3 (Calidad)**: Fragmentar archivos JS/CSS y añadir type hints.
*   **Fase 4 (Features)**: Implementar skill `recordatorios` y `monitor_hardware` (LibreHardwareMonitor).
*   **Fase 5 (Despliegue)**: Empaquetado con PyInstaller e instalador MSI.
*   **Expansión**: Migración a FastAPI para acceso multiplataforma (PWA).