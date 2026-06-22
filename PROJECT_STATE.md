He completado el análisis arquitectónico del proyecto. A continuación te presento el **PROJECT_STATE.md** generado, que servirá como la única fuente de verdad para futuras planificaciones.

---

# PROJECT_STATE.md

## 1. Resumen Ejecutivo

**Argus** es un asistente de IA de escritorio con interfaz gráfica (CustomTkinter) que integra:
- Múltiples modelos de lenguaje (Gemini Flash, DeepSeek Reasoner)
- Entrada/Salida de voz (Whisper + Edge TTS)
- Control del sistema operativo Windows
- Gestión de archivos con sandbox
- Memoria persistente (ChromaDB vectorial)
- Búsqueda web
- Control de versiones Git
- Capacidades de visión

Su propósito es servir como un copiloto local avanzado, capaz de mantener contexto prolongado, ejecutar acciones en el sistema y memorizar información a largo plazo.

## 2. Arquitectura

### Módulos principales

| Archivo | Rol | Dependencias |
|---------|-----|--------------|
| `config.py` | Singleton de estado global (`EstadoGlobal`), variables de entorno, parches. | dotenv, threading |
| `modulos/logger.py` | Sistema de logging centralizado a archivo y consola. | logging |
| `modulos/archivos.py` | Sandbox de archivos: lectura/escritura/eliminación con validación de rutas, tamaño, espacio. | config, pathlib |
| `modulos/sistema.py` | Control de ventanas, procesos, búsqueda de programas, exploración FS. | win32gui, psutil, thefuzz |
| `modulos/vision.py` | Captura de pantalla multipantalla con PIL + screeninfo. | PIL, screeninfo |
| `modulos/busqueda.py` | Búsqueda web usando DuckDuckGo. | ddgs |
| `modulos/memoria.py` | Bóveda RAG (ChromaDB + SentenceTransformer). Watchdog (radar de cambios). | chromadb, watchdog |
| `modulos/audio_custom.py` | Captura de micrófono (Whisper), síntesis de voz (Edge TTS), reproducción con cola. | faster-whisper, sounddevice, edge-tts, pygame |
| `modulos/cliente_mcp.py` | Cliente MCP para servidor interno de sistema. | mcp |
| `modulos/servidor_sistema_mcp.py` | Servidor MCP que expone funciones de sistema/memoria. | mcp |
| `modulos/prompts.py` | Generadores de prompts por modo. | (ninguno) |
| `modulos/ia.py` | Orquestador principal: enruta a Gemini o DeepSeek según modo, procesa streaming, intercepta adjuntos, confirmaciones, ejecuta herramientas MCP. | genai, openai, todos los módulos anteriores |
| `modulos/controlador_acciones.py` | Parseo de comandos en respuestas de IA y ejecución (archivos, git, sistema). | ia, archivos, sistema, memoria |
| `modulos/git_bot.py` | Operaciones Git (init, add, commit, pull, push). | gitpython |
| `modulos/crawler.py` | Escaneo de proyecto completo (excluye .git, venv, etc). | (ninguno) |
| `main_gui.py` | Interfaz gráfica: sidebar, área de chat con burbujas markdown, input bar, adjuntos, micrófono. | customtkinter, keyboard, todos los módulos |
| `gestor_boveda.py` | Herramienta CLI para listar/borrar/formatear la bóveda. | chromadb |
| `a.py` | Script de descarga forzada de modelo Whisper. | faster-whisper |

### Flujo de datos

1. Usuario escribe/habla → `main_gui.py` captura y llama a `enviar_a_gemini` (hilo).
2. `ia.py` decide modelo según `config.estado.modo_actual` (Gemini para general, DeepSeek para programador/planificador).
3. Durante generación, se pasan chunks a `callback_ia` que actualiza burbuja (`AIBubble.append_text`).
4. Al finalizar, `controlador_acciones.py` parsea la respuesta en busca de comandos estructurados.
5. Las acciones se ejecutan (leer/escribir archivos, control sistema, git, etc.) y se retroalimentan al contexto.
6. El estado se mantiene en `EstadoGlobal` (thread-safe) y la memoria persistente en ChromaDB.

## 3. Estado Actual

### Funcionalidades operativas

- [x] **Chat multimodal**: texto, voz (captura con Whisper, síntesis con Edge TTS streaming).
- [x] **Dos modos de IA**: General (Gemini Flash) y Programador (DeepSeek Reasoner). Cambio con sidebar.
- [x] **Sandbox de archivos**: lectura/escritura/eliminación con validación de ruta segura, tamaño, espacio.
- [x] **Bóveda RAG**: guardado/búsqueda de recuerdos con embeddings.
- [x] **Control del sistema**: abrir/cerrar/mover ventanas, explorar carpetas, búsqueda de programas con fuzzy matching.
- [x] **Control Git**: init, add, commit, pull, push con confirmación del usuario.
- [x] **Visión**: captura de pantalla específica (monitor 1 o 2) o todas.
- [x] **Búsqueda web**: DuckDuckGo con enriquecimiento de respuesta IA.
- [x] **Streaming de voz**: síntesis por fragmentos mientras la IA genera texto.
- [x] **Adjuntos**: carga de archivos al contexto volátil (no a bóveda).
- [x] **Radar de cambios**: Watchdog que invalida caché de archivos al modificar.
- [x] **Gestor CLI de bóveda**: listar, eliminar, hard reset.

## 4. Deuda Técnica y Próximos Pasos

### 🔴 Crítico - Seguridad y Robustez

1. **`config.py`**: `EstadoGlobal` tiene atributos públicos sin protección de concurrencia. El acceso directo (ej. `estado.contexto_chat.append(...)`) es inseguro. Migrar completamente a métodos y eliminar acceso directo desde `controlador_acciones.py` y `ia.py`.
2. **`modulos/ia.py`**: Manejo de excepciones deficiente en streaming. Agregar `try/except` y llamada a `ui_callback` en `finally`.
3. **`modulos/controlador_acciones.py`**: Normalizar rutas y verificar permiso de workspace antes de operaciones de archivos.
4. **`modulos/sistema.py`**: Limitar `radar_inteligente` a rutas seguras configuradas.
5. **Validación de tamaño**: Verificar tamaño en disco antes de leer archivos.

### 🟡 Medio - Mantenibilidad y Rendimiento

6. **Duplicación de estado**: Eliminar `_AppState` en `main_gui.py` y usar exclusivamente `config.estado`.
7. **Prompts duplicados**: Eliminar funciones deprecated en `prompts.py`.
8. **Lazy loading de Whisper**: Unificar con script de descarga.
9. **Manejo de errores en adjuntos**: Agregar try/except en `cargar_adjuntos_en_contexto`.
10. **Dependencias**: Separar core de opcionales, versiones mínimas en requirements.

### 🟢 Bajo - Limpieza y UX

11. **Logs duplicados**: Integrar `LogRedirector` en sistema de logging.
12. **Interfaz**: Mejorar comportamiento del `_welcome_label`.
13. **Eliminar `modulos/limpiar.py`**: Archivo huérfano.
14. **`pruebas/`**: Migrar a `tests/` con contenido real.

### 📌 Recomendaciones Estratégicas

- **Migrar a comunicación asíncrona** entre hilos y UI usando `queue.Queue`.
- **Separar audio** en módulos independientes.
- **Centralizar confirmaciones** en máquina de estados.
- **Mejorar búsqueda en bóveda** combinando múltiples resultados con puntuación.

---

Este documento debe actualizarse después de cada ciclo de planificación. La prioridad inmediata es resolver los puntos **🔴 Crítico** (1-5) para evitar fallos en producción. Luego atacar los **🟡 Medio** (6-10) para mejorar mantenibilidad. Los **🟢 Bajo** (11-14) pueden delegarse a tareas de limpieza en sprints futuros.

Como Arquitecto Principal, recomiendo comenzar con el punto **#1**: la unificación del estado y la eliminación de accesos directos a atributos públicos de `EstadoGlobal`.

Si lo deseas, puedo profundizar en cualquiera de estos puntos o generar un plan de acción detallado para el siguiente sprint.