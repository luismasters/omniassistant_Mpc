# Project State — Cortana (OmniAssistant)

## Resumen Ejecutivo

**Cortana** es un asistente de IA multimodal que opera localmente en la PC del usuario. Integra modelos de lenguaje (Gemini Flash, DeepSeek V4) con herramientas del sistema: control de ventanas, sistema de archivos con sandbox, memoria vectorial persistente (ChromaDB), captura de pantalla, voz (Whisper + TTS), búsqueda web, sincronización Git y un servidor MCP para consultas de hardware/estado. La interfaz gráfica está desarrollada con CustomTkinter y proporciona un chat enriquecido con renderizado de Markdown.

El asistente opera en tres modos con prompts y modelos diferenciados, y permite anclar un workspace de proyecto para operaciones seguras de archivos y Git.

## Arquitectura

| Módulo / Archivo                   | Propósito                                                                 |
|------------------------------------|---------------------------------------------------------------------------|
| `config.py`                        | Configuración global: API keys, límites de seguridad, sandbox, parámetros de audio. |
| `main_gui.py`                      | Interfaz gráfica principal (CustomTkinter): chat, sidebar, input, adjuntos, logs. |
| `gestor_boveda.py`                 | Script CLI para listar/borrar la memoria persistente (ChromaDB).         |
| `modulos/ia.py`                    | Motor principal de IA. Enruta solicitudes a Gemini/DeepSeek según el modo, gestiona contexto, comandos de archivos/Git, y parsea respuestas. |
| `modulos/audio.py`                 | Captura de voz (Whisper) y síntesis de voz (pyttsx3).                    |
| `modulos/archivos.py`              | Operaciones seguras de archivos: lectura/escritura/eliminación con validación de rutas dentro del sandbox/workspace. |
| `modulos/sistema.py`               | Control de ventanas (buscar, mover, cerrar), búsqueda de programas/archivos, telemetría de hardware (CPU/RAM/GPU). |
| `modulos/busqueda.py`              | Búsqueda web mediante DuckDuckGo (ddgs).                                 |
| `modulos/vision.py`                | Captura de pantalla (PIL + screeninfo) para envío a Gemini.              |
| `modulos/memoria.py`               | Memoria a largo plazo con ChromaDB: guardado/búsqueda semántica. Snapshots de proyectos en `.cortana/snapshot.json`. |
| `modulos/crawler.py`               | Escanea un proyecto y concatena código para análisis (usa DeepSeek).     |
| `modulos/git_bot.py`               | Sincronización con GitHub: init, commit, push, comandos libre restringidos. |
| `modulos/cliente_mcp.py`           | Cliente asíncrono para el servidor MCP (ejecuta herramientas del sistema). |
| `modulos/prompts.py`               | Prompts separados para cada modo de IA (general, planificador, programador). |
| `modulos/logger.py`                | Configuración de logging a archivo y consola.                            |
| `modulos/servidor_sistema_mcp.py`  | Servidor MCP que expone herramientas (estado PC, hardware, exploración archivos, memoria). |
| `modulos/limpiar.py`               | Utilidad para borrar toda la memoria de ChromaDB.                        |
| `servidor_sistema_mcp.py` (raíz)   | **Duplicado** del servidor MCP en `modulos/`. Debe consolidarse.         |
| `plan.md`                          | Plan de consolidación pendiente (tareas organizadas por fases).          |
| `pruebas/test_nuevo_parser.py`     | Archivo vacío. Sin pruebas unitarias implementadas.                      |
| `pruebas/test_seguridad.txt`       | Nota de prueba (no relevante).                                           |

## Estado Actual

- ✅ **Interfaz gráfica funcional** con chat enriquecido (burbujas, tablas, código, listas) y sidebar de modos.
- ✅ **Tres modos de IA operativos**: General (Gemini Flash), Planificador (DeepSeek V4 Thinking), Programador (DeepSeek V4 Fast).
- ✅ **Cambio entre modos** preserva historial visual pero **no** preserva el contexto completo de IA (CONTEXTO_CHAT no se restaura correctamente).
- ✅ **Anclaje de workspace** con escaneo de estructura y snapshot persistente.
- ✅ **Control de ventanas**: abrir/cerrar/mover programas, búsqueda inteligente de archivos/programas con fuzzy matching.
- ✅ **Editor de archivos seguro**: creación, escritura, reemplazo de bloques con sandbox. El reemplazo usa `str.replace()` que puede fallar si el bloque aparece múltiples veces (riesgo de corrupción).
- ✅ **Memoria a largo plazo** con ChromaDB y búsqueda semántica vía MCP.
- ✅ **Captura de pantalla** y envío a Gemini.
- ✅ **Entrada/salida de voz** con Whisper (model medium) y pyttsx3 (español).
- ✅ **Sincronización Git** con confirmación de seguridad (semáforo).
- ✅ **Crawler de proyectos** y generación de PROJECT_STATE.md mediante DeepSeek.
- ✅ **Servidor MCP** con herramientas de sistema, hardware y exploración de archivos.
- ✅ **Protecciones de seguridad**: verificación de rutas permitidas, límites de contenido, espacio en disco, semáforos para borrado/Git.
- ✅ **Logging profesional** configurado (archivo + consola), pero no se usa consistentemente en todos los módulos (muchos `print()` residuales).

## Deuda Técnica / Próximos Pasos

1. **Duplicación de código**: `servidor_sistema_mcp.py` existe en raíz y en `modulos/`. Debe consolidarse en un solo lugar (probablemente dentro de `modulos/`).
2. **Preservación de contexto al cambiar de modo**: Fase 1.3 del plan no está correctamente implementada. `CONTEXTO_CHAT` no se guarda/restaura con el historial visual, lo que hace que la IA pierda la memoria de la conversación al cambiar de modo.
3. **Seguridad en el reemplazo de bloques**: Usar `re.sub` con límites exactos de líneas en lugar de `str.replace()` para evitar corrupción cuando el bloque buscado aparece más de una vez.
4. **Manejo de errores en la GUI**: Excepciones no capturadas en `callback_ia` y en el motor de micrófono de `main_gui.py`. Falta un mecanismo de reconexión del servidor MCP.
5. **Rendimiento**: La carga de Whisper (model medium) es lenta al inicio. Se recomienda lazy loading o un modelo más pequeño.
6. **Dependencias externas**: Falta un `requirements.txt` congelado. `pywin32`, `screeninfo`, `psutil`, `thefuzz`, `chromadb`, `faster-whisper`, `pyttsx3`, `ddgs`. Algunas tienen requisitos específicos de versión.
7. **Logs inconsistentes**: Muchos `print()` en `ia.py`, `sistema.py`, `audio.py` deberían reemplazarse por `logger.info()`/`logger.error()`.
8. **MCP asíncrono**: El cliente MCP ejecuta `asyncio.run()` cada vez, lo que puede bloquear la UI. Se recomienda un pool persistente de conexiones asíncronas.
9. **Snapshot desactualizado**: El archivo `.cortana/snapshot.json` no se actualiza automáticamente si el usuario edita archivos fuera de Cortana. Falta un watchdog.
10. **Internacionalización**: La interfaz está en español, pero los prompts de sistema tienen mezcla de español e inglés. Unificar todo el idioma.
11. **Pruebas unitarias**: La carpeta `pruebas/` está vacía. No hay tests para `ia.py`, `archivos.py`, `sistema.py`, etc.
12. **GitHub Fix incompleto**: El token no se valida al inicio. Los errores de push no siempre son claros. La lista blanca de comandos Git podría ser más restrictiva.
13. **Lazy loading de Whisper no implementado**: El modelo se carga al importar `audio.py`, ralentizando el arranque.
14. **Comandos de archivos con XML**: Se soportan formatos Markdown (guardar_archivo:, reemplazar_bloque:) y XML (<write_file>, <replace_block>). Esto es redundante y puede causar confusión en los prompts. Unificar a un solo formato.
15. **Crawler dependiente de DeepSeek**: `escanear_proyecto:` usa DeepSeek (planificador) incluso en modo general, lo que puede fallar si no hay API key. Debería tener un fallback.