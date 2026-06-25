# PROJECT_STATE.md — Argus (Personal AI Assistant)

## 1. Resumen Ejecutivo

Argus es un asistente de IA de escritorio integrado en Windows, que combina procesamiento de lenguaje natural (Gemini/DeepSeek), control del sistema (abrir programas, mover ventanas, ejecutar comandos), búsqueda web (DuckDuckGo), captura de pantalla, memoria vectorial a largo plazo (ChromaDB), control por voz (Edge TTS + Whisper) y un sistema de plugins (Skills). Su propósito es servir como interfaz conversacional para productividad, programación y gestión del entorno del usuario.

## 2. Arquitectura

### Módulos principales y responsabilidad de cada archivo

| Archivo | Función |
|---------|---------|
| `config.py` | Variables globales, API keys, límites de seguridad, estado global thread-safe (`EstadoGlobal`). |
| `main_gui.py` | Interfaz gráfica con CustomTkinter: sidebar, chat burbujas, input bar, pestaña de logs. |
| `gestor_boveda.py` | CLI para administrar la memoria vectorial (listar/borrar/formatear colecciones ChromaDB). |
| `modulos/ia.py` | Enrutador principal de IA: decide modelo (Gemini/DeepSeek), maneja streaming, acciones, skills y contexto. |
| `modulos/controlador_acciones.py` | Parsea comandos de la IA (guardar_archivo, reemplazar_bloque, buscar web, git, etc.) y ejecuta modificaciones seguras. |
| `modulos/archivos.py` | Operaciones seguras de archivos: leer, escribir, eliminar, listar, validar rutas (sandbox). |
| `modulos/sistema.py` | Control del sistema Windows: abrir programas con radar inteligente, mover ventanas, cerrar procesos, explorar directorios, obtener hardware. |
| `modulos/audio_custom.py` | Síntesis de voz (Edge TTS), reproducción con pygame, cola de chunks, captura de micrófono (Whisper). |
| `modulos/vision.py` | Captura de pantalla con PIL, soporte multimonitor. |
| `modulos/memoria.py` | Memoria vectorial ChromaDB (guardar/recuperar recuerdos), snapshot del proyecto, watchdog (radar de cambios). |
| `modulos/busqueda.py` | Búsqueda web real con DuckDuckGo (ddgs). |
| `modulos/crawler.py` | Extrae código completo del proyecto (sin .git, venv) para análisis con DeepSeek. |
| `modulos/git_bot.py` | Integración Git (init/add/commit/pull/push) con GitPython. |
| `modulos/cliente_mcp.py` | Cliente asíncrono para el servidor MCP (`modulos/servidor_sistema_mcp.py`). |
| `modulos/servidor_sistema_mcp.py` | Servidor MCP que expone herramientas: estado PC, hardware, búsqueda/guardado en bóveda, explorar/leer archivos. |
| `modulos/prompts.py` | Generación de prompts según el modo (general, programador unificado). |
| `modulos/logger.py` | Configuración centralizada de logging con archivo y consola. |
| `modulos/skills/gestor_skills.py` | Carga skills desde subcarpetas (`SKILL.md`, `instructions.md`, `ejemplos.md`) y detecta relevancia por palabras clave. |
| `modulos/skills/busqueda_web_actualizada/` | Skill de ejemplo: búsqueda web con filtros de fecha, prioriza resultados recientes. |

### Flujo de datos

1. Usuario escribe/habla → `main_gui` captura entrada.
2. `ia.py` recibe texto, determina modo (general → Gemini; programador/planificador → DeepSeek), inyecta prompt + skills + contexto.
3. Durante streaming, la IA puede emitir comandos de acción (XML o `verbo: objetivo`).
4. `controlador_acciones.py` parsea y ejecuta (escribir archivos, buscar web, git, etc.) usando funciones seguras de `archivos.py`, `sistema.py`, `busqueda.py`.
5. Las acciones son confirmadas por el usuario (borrados, git) mediante juez IA en `ia.py`.
6. La respuesta final se muestra en burbujas AI y se puede leer en voz alta.

## 3. Estado Actual

### Funcionalidades operativas

- ✅ **Chat multimodal** (texto, voz, adjuntos, captura de pantalla).
- ✅ **Dos modos de IA**: Gemini (general) y DeepSeek Reasoner (programación/planificación).
- ✅ **Edición segura de archivos**: leer, escribir, reemplazar bloques, crear carpetas, todo con sandbox.
- ✅ **Control del sistema**: abrir programas (radar inteligente), mover ventanas entre monitores, cerrar procesos, explorar carpetas.
- ✅ **Búsqueda web real** con DuckDuckGo.
- ✅ **Memoria a largo plazo** (ChromaDB): guardar/recuperar recuerdos, snapshots de proyecto.
- ✅ **Radar de cambios** (watchdog) que invalida caché al modificar archivos.
- ✅ **Sistema de Skills extensible** (carga dinámica desde subcarpetas).
- ✅ **Streaming de voz** con Edge TTS y reproducción paralela.
- ✅ **Captura de pantalla** multimonitor.
- ✅ **Git**: sync completo (init/add/commit/pull/push) y comandos libres (previa confirmación).
- ✅ **Crawler** para escanear todo el proyecto y generar `PROJECT_STATE.md` automáticamente.
- ✅ **Interfaz gráfica** con temas oscuros, burbujas de usuario/IA, resaltado de código, tablas, botón de copia.
- ✅ **Logs** en pestaña dedicada y archivo `logs/omniassistant.log`.
- ✅ **Thread-safety** en estado global (`EstadoGlobal` con locks).

## 4. Deuda Técnica / Próximos Pasos

### 🔴 Crítico
- **Compatibilidad ChromaDB/Protocol Buffers**: El parche `os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"` puede degradar rendimiento. Migrar a ChromaDB 2.x o usar implementación nativa.
- **Gestión de errores en `main_gui.py`**: La burbuja AI no tiene un mecanismo robusto de cleanup si el streaming falla (puede quedar `_streaming = True` y no finalizar). Implementar `__del__` o manejo de excepciones en el callback.
- **Dependencia de `pywin32`**: Solo funciona en Windows; no hay abstracción multiplataforma.

### 🟡 Importante
- **Doble definición de estados**: Existe `config.EstadoGlobal` (thread-safe con locks) y `_AppState` en `main_gui.py` (singleton sin locks). Refactorizar para usar solo la instancia de `config.estado`.
- **Skills**: Solo hay una skill de ejemplo. Completar al menos 2-3 skills funcionales y agregar detección de relevancia más inteligente (ej. embeddings).
- **Crawler**: Ignora archivos `.env` (bien), pero no filtra archivos binarios; podría incluir imágenes/PDFs.
- **Confirmaciones de UI**: El juez IA (Gemini) es lento y susceptible a errores. Reemplazar con confirmaciones explícitas del usuario en la GUI (popup Sí/No).
- **Memoria volátil vs. bóveda**: Hay dos mecanismos de carga de archivos (adjuntos → contexto volátil, guardar en memoria → bóveda). Unificarlos con una interfaz clara.

### 🟢 Mejora Continua
- **Límites de tokens**: En `controlador_acciones.py` hay truncado manual de 80k caracteres. Usar conteo de tokens real o chunking automático.
- **Reemplazo de bloque flexible**: La lógica de Regex es frágil. Mejor usar diff (ej. difflib) o soporte de búsqueda semántica.
- **Sonidos de inicio/fin**: Actualmente solo beep en captura. Agregar sonidos para inicio de streaming, error, tarea completada.
- **Documentación**: El proyecto carece de documentación inline (docstrings). Agregar docstrings a todas las funciones principales.
- **Tests**: No hay test suite. Agregar pruebas unitarias para `archivos.py`, `sistema.py`, `controlador_acciones.py`.