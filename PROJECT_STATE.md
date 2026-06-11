# PROJECT_STATE.md — Fuente de la Verdad

## Resumen Ejecutivo

**OmniAssistant (Cortana)** es un asistente de IA multimodal integrado en la PC del usuario. Combina modelos de lenguaje (Gemini Flash para el modo general, DeepSeek V4 para planificación/programación) con herramientas locales: control de ventanas, sistema de archivos con sandbox, memoria vectorial persistente (ChromaDB), captura de pantalla, voz (Whisper + pyttsx3), búsqueda web (DuckDuckGo), sincronización Git y un sistema MCP para consultas de hardware/estado del sistema. La interfaz gráfica está construida con CustomTkinter y ofrece un chat enriquecido con renderizado de Markdown (tablas, código, listas). El asistente opera en tres modos con sistemas de prompt y modelos diferenciados, y permite anclar un workspace de proyecto para operaciones de archivos y Git.

## Arquitectura

| Módulo / Archivo                   | Propósito                                                                 |
|------------------------------------|---------------------------------------------------------------------------|
| `config.py`                        | Configuración global: API keys, límites de seguridad, rutas del sandbox, modelo de audio. |
| `main_gui.py`                      | Interfaz gráfica principal. Chat con burbujas (usuario/IA), entrada de texto, adjuntos, sidebar con cambio de modo, logs. |
| `servidor_sistema_mcp.py`          | Servidor MCP que expone herramientas del sistema (estado PC, hardware, memoria, exploración de archivos). |
| `modulos/ia.py`                    | Motor principal de IA. Enruta peticiones a Gemini o DeepSeek según el modo, gestiona el contexto de conversación, los semáforos de seguridad (borrado, Git), y parsea acciones de la respuesta (guardar_archivo, buscar, abrir, etc.). |
| `modulos/audio.py`                 | Captura de voz con micrófono (Whisper) y síntesis de voz (pyttsx3). |
| `modulos/archivos.py`              | Operaciones seguras de archivos: lectura, escritura, creación de carpetas, eliminación con validación de rutas dentro del sandbox/workspace. |
| `modulos/sistema.py`               | Control de ventanas (buscar, mover, cerrar), búsqueda de programas/archivos en disco, ejecución de comandos del sistema, telemetría de hardware y CPU/RAM/GPU. |
| `modulos/busqueda.py`              | Búsqueda web en DuckDuckGo (usando la librería `ddgs`). |
| `modulos/vision.py`                | Captura de pantalla (PIL + screeninfo) para enviar imágenes a Gemini. |
| `modulos/memoria.py`               | Memoria a largo plazo con ChromaDB: guardar, buscar y gestionar recuerdos persistidos. También maneja snapshots de proyectos (`.cortana/snapshot.json`). |
| `modulos/crawler.py`               | Escanea un proyecto local, filtra carpetas innecesarias y concatena el código en un solo texto para análisis. |
| `modulos/git_bot.py`               | Sincronización con GitHub: inicializar repos, commit, push, y ejecución de comandos Git libres. |
| `modulos/cliente_mcp.py`           | Cliente asíncrono para el servidor MCP, usado por `ia.py` para invocar herramientas del sistema. |
| `modulos/limpiar.py`               | Utilidad para borrar toda la memoria de ChromaDB. |
| `modulos/logger.py`                | Configuración de logging a archivo y consola. |
| `gestor_boveda.py`                 | Script independiente para listar/borrar la memoria persistente (CLI). |

## Estado Actual

- ✅ **Interfaz gráfica funcional** con sidebar de modos, entrada de texto, adjuntos, burbujas de usuario y IA, y renderizado de Markdown (tablas, listas, código, negrita/cursiva).
- ✅ **Tres modos de IA operativos**: General (Gemini Flash), Planificador (DeepSeek V4 Thinking), Programador (DeepSeek V4 Fast).
- ✅ **Cambio entre modos** preserva el historial visual y restaura conversaciones anteriores.
- ✅ **Anclaje de workspace** con escaneo de estructura de proyecto y snapshot persistente.
- ✅ **Control de ventanas completo**: abrir programas, cerrar procesos, mover ventanas entre monitores (apoyo multi-monitor).
- ✅ **Búsqueda inteligente de archivos/programas** en disco con fuzzy matching.
- ✅ **Editor de archivos seguro**: creación, escritura, reemplazo de bloques, edición quirúrgica de una línea, con sandbox y límites de tamaño.
- ✅ **Memoria a largo plazo** (ChromaDB) con búsqueda semántica vía MCP.
- ✅ **Captura de pantalla** y envío a Gemini en modo general.
- ✅ **Entrada por voz** con Whisper (modelo medium) y salida de voz con pyttsx3 (español).
- ✅ **Sincronización Git** con confirmación de seguridad (semáforo).
- ✅ **Crawler de proyectos** y generación de `PROJECT_STATE.md` usando DeepSeek.
- ✅ **Servidor MCP** con herramientas de sistema, hardware y exploración de archivos.
- ✅ **Protecciones de seguridad**: rutas permitidas, verificación de espacio, límites de tamaño de contenido, semáforos de confirmación para acciones peligrosas (borrado, Git).

## Deuda Técnica / Próximos Pasos

1. **Duplicación de código**: `servidor_sistema_mcp.py` aparece tanto en la raíz como dentro de `modulos/`. Debe consolidarse en un solo lugar.
2. **Manejo de errores en la GUI**: Algunas excepciones no se capturan en `main_gui.py`, especialmente en `callback_ia` y el motor de micrófono. Falta una estrategia de reconexión del servidor MCP.
3. **Rendimiento**: La inicialización de Whisper (modelo medium) puede ser lenta. Considerar lazy loading o un modelo más pequeño.
4. **Seguridad en la edición de archivos**: El reemplazo de bloques usa `replace(buscar, reemplazar, 1)`, que puede corromper el código si el bloque buscado aparece múltiples veces. Usar `re.sub` con límites de líneas específicas.
5. **Consistencia del historial**: Al cambiar de modo, se guardan los últimos 50 mensajes como historial, pero no se preserva el contexto de sistema (prompts internos). Podría perderse información relevante.
6. **Dependencias externas**: `pywin32`, `screeninfo`, `psutil`, `thefuzz`, `chromadb`, `faster-whisper`, `pyttsx3`, `ddgs`. Algunas tienen requisitos específicos de versión. Falta un `requirements.txt` congelado.
7. **Logs**: El archivo `modulos/logger.py` configura logging, pero no se usa consistentemente en todos los módulos. Muchas funciones aún usan `print()` en lugar de `logger`.
8. **MCP asíncrono**: El cliente MCP se ejecuta con `asyncio.run()` cada vez, lo que puede causar bloqueos de la UI en llamadas frecuentes. Se recomienda un pool persistente de conexiones.
9. **Snapshot**: El archivo `.cortana/snapshot.json` se guarda y carga, pero el contenido puede quedar desactualizado si el usuario edita archivos fuera de Cortana. Falta un mecanismo de detección de cambios.
10. **Internacionalización**: La interfaz está en español, pero los prompts de sistema contienen mezcla de español e inglés. Unificar todo el lenguaje.
11. **Pruebas**: Existe una carpeta `pruebas/` con `test_nuevo_parser.py` vacío. No hay pruebas unitarias para los módulos críticos (`ia.py`, `archivos.py`, `sistema.py`).