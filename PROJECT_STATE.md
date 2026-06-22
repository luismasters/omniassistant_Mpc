# PROJECT_STATE.md — Fuente de la Verdad del Proyecto Argus

---

## 1. Resumen Ejecutivo

**Argus** es un asistente de inteligencia artificial de escritorio integrado al sistema operativo Windows. Actúa como un copiloto conversacional capaz de interactuar mediante texto y voz, leer/escribir archivos locales, controlar ventanas y programas, gestionar un repositorio local de memoria vectorial (ChromaDB), realizar búsquedas web, y programar con ayuda de modelos avanzados (Gemini Flash Lite y DeepSeek Reasoner). El proyecto está orientado a desarrolladores y usuarios avanzados, ofreciendo modos especializados (General, Programador/Planificador) con acceso seguro al sistema de archivos mediante un sandbox dinámico.

---

## 2. Arquitectura y Módulos Principales

### 2.1. Estructura de Archivos

| Ruta | Propósito |
|---|---|
| `main_gui.py` | Punto de entrada principal. Interfaz gráfica con CustomTkinter, manejo de burbujas de chat, entrada de texto, botones de adjuntar/guardar, pestaña de logs y cambio de modo. Renderizado de Markdown extendido (código, tablas, listas) en las burbujas de IA. |
| `config.py` | Configuración global: API keys, límites de seguridad, parámetros de Whisper, clase EstadoGlobal thread-safe que centraliza el estado de la sesión (modo, workspace, contexto, archivos en memoria, etc.). |
| `gestor_boveda.py` | Herramienta CLI para listar, eliminar documentos o hacer hard reset de la base de datos vectorial (ChromaDB). |
| `requirements.txt` | Dependencias externas del proyecto. |
| `modulos/archivos.py` | Funciones seguras de lectura/escritura/eliminación/creación de archivos y carpetas, con validación de sandbox, límites de tamaño y espacio en disco. |
| `modulos/audio_custom.py` | Captura de voz con micrófono mediante `sounddevice` y transcripción con `faster-whisper`. Síntesis de voz con `edge-tts` y reproducción asíncrona con `pygame`. |
| `modulos/busqueda.py` | Búsqueda web real mediante DuckDuckGo (`ddgs`), devuelve resultados textuales. |
| `modulos/cliente_mcp.py` | Cliente asíncrono para el servidor MCP local (`modulos/servidor_sistema_mcp.py`). Permite ejecutar herramientas del servidor desde el flujo principal. |
| `modulos/controlador_acciones.py` | Intérprete y ejecutor de comandos generados por la IA (guardar_archivo, reemplazar_bloque, leer_archivo, buscar, github, etc.). Contiene lógica de reemplazo flexible (regex) y protección de sandbox. |
| `modulos/crawler.py` | Recorre un proyecto para extraer el código completo de todos los archivos fuente (`.py`, `.md`, `.json`, `.txt`), omitiendo carpetas no relevantes. |
| `modulos/git_bot.py` | Integración con GitPython: init, add, commit, pull (con rebase) y push. Soporte para reset remoto y comandos libres. |
| `modulos/ia.py` | **Enrutador principal de inteligencia artificial**. Maneja la lógica de envío a Gemini o DeepSeek según el modo, procesamiento de MCP, streaming de voz, interceptación de comandos adjuntos, y confirmaciones de seguridad (borrado, git). |
| `modulos/limpiar.py` | Script para vaciar completamente la colección ChromaDB. |
| `modulos/logger.py` | Configuración centralizada de logging: archivo `logs/omniassistant.log` y salida a consola. |
| `modulos/memoria.py` | **Capa de persistencia vectorial**: conexión a ChromaDB, guardado/búsqueda de recuerdos por embeddings (`all-MiniLM-L6-v2`), snapshot del proyecto (archivo JSON) y watchdog que detecta cambios en el workspace y limpia la caché correspondiente. |
| `modulos/prompts.py` | Fábrica de prompts según el modo: general, programador (dos versiones, la actual unificada), planificador (deprecado). |
| `modulos/servidor_sistema_mcp.py` | Servidor MCP basado en `FastMCP` que expone herramientas: estado de PC, hardware, búsqueda/guardado en bóveda, exploración de directorios y lectura de archivos. |
| `modulos/sistema.py` | **Control del sistema Windows**: búsqueda inteligente de programas (radar con fuzzy matching), apertura/cierre de ventanas, movimiento entre monitores, exploración de carpetas, obtención de ventanas activas, telemetría (CPU, RAM, GPU). |
| `modulos/vision.py` | Captura de pantalla de monitores específicos usando `PIL.ImageGrab` y `screeninfo`. |
| `a.py` | Script auxiliar que fuerza la descarga del modelo Whisper "medium" en CPU para que quede en caché. |

### 2.2. Flujo de Datos Principal

```
Usuario (texto/voz) → main_gui.py → ia.py (enrutador)
  ├─ Si modo general: Gemini Flash Lite + MCP (opcional) + búsqueda web (si aplica)
  └─ Si modo programador/planificador: DeepSeek Reasoner (stream)
Luego → controlador_acciones.py (parsea comandos de la respuesta)
  ├─ Acciones de archivos → archivos.py
  ├─ Acciones de sistema → sistema.py
  ├─ Acciones Git → git_bot.py
  ├─ Acciones de memoria → memoria.py (guardado en bóveda)
  └─ Acciones web → busqueda.py (si se detecta "buscar:")
```

---

## 3. Estado Actual

### 3.1. Funcionalidades Completas y Operativas

- **Chat conversacional** con renderizado de Markdown extendido (código coloreado, tablas, listas, texto en negrita/cursiva/monospace).
- **Modo General**: usa Gemini Flash Lite, acceso completo a archivos sin restricción de sandbox, control de ventanas (abrir/cerrar/mover), búsqueda web, captura de pantalla.
- **Modo Programador/Planificador**: usa DeepSeek Reasoner, sandbox restrictivo al workspace seleccionado, comandos directos de lectura/escritura/reemplazo de archivos, generación de snapshot, escaneo y análisis del proyecto (crawler → DeepSeek → PROJECT_STATE.md).
- **Memoria a largo plazo (Bóveda)**: ChromaDB con embeddings, posibilidad de guardar/recuperar recuerdos mediante MCP o comandos explícitos.
- **Interacción por voz**: captura con micrófono (tecla F8), transcripción con Whisper, síntesis con Edge TTS (voz española latina) y reproducción en streaming.
- **Watchdog de cambios en el workspace**: detecta modificaciones en los archivos y limpia automáticamente la caché obsoleta del contexto.
- **Integración Git**: inicialización, commit, pull con rebase, push, comandos personalizados.
- **Seguridad de archivos**: sandbox por modo, verificación de espacio en disco, límite de tamaño, confirmación de eliminación vía modelo juez.
- **MCP (Model Context Protocol)**: servidor local que expone estado del sistema, hardware, memoria y sistema de archivos al LLM.
- **Logging centralizado** con rotación a archivo y consola.
- **Interfaz adaptable** con CustomTkinter (tema oscuro, pestañas, scroll, botones de acción rápida).

### 3.2. Funcionalidades Parciales o con Advertencias

- **Modo Planificador**: deprecado, redirige al modo Programador. El prompt "planificador" existe pero no se usa activamente.
- **Captura de pantalla**: funciona, pero la imagen no se pasa directamente al modelo (solo se usa en mensajes adjuntos genéricos). La integración con Gemini para análisis visual no está implementada (no se envía como parte multimodal).
- **Búsqueda web**: solo en modo general, la respuesta secundaria reemplaza a la primera generación (podría duplicar contenido si la búsqueda falla).
- **Tecla de voz F8**: puede causar conflictos si el teclado tiene otras funciones asignadas; no hay GUI para reasignar.

---

## 4. Deuda Técnica y Próximos Pasos

### 4.1. Deuda Técnica Identificada

1. **Duplicación de estado**: Existe `EstadoGlobal` en `config.py` y también `_AppState` en `main_gui.py` (clase singleton). Ambos mantienen información similar (modo, workspace, contexto, memoria de archivos). Esto puede ocasionar inconsistencias. Se recomienda unificar en un solo gestor de estado.

2. **Manejo de errores en streaming**: En `ia.py`, los bloques `try/except` dentro de los bucles de streaming para Gemini y DeepSeek son generales y capturan excepciones amplias. Sería mejor diferenciar entre errores recuperables (timeout de red) y fatales.

3. **Renderizado de Markdown**: La lógica en `AIBubble` es pesada y manual. Podría simplificarse usando una librería como `rich` o `mistune` para convertir a widgets tkinter.

4. **Confirmaciones de seguridad**: El uso de un modelo "juez" (Gemini Flash Lite) para decidir si el usuario confirmó un borrado o una operación Git es frágil. Depende del prompt y puede fallar si el usuario responde de manera ambigua. Mejor usar botones de confirmación en la GUI.

5. **Dependencias pesadas**: `chromadb` y `faster-whisper` (con modelo "medium") se cargan por completo incluso si no se usan (por ejemplo, en modo solo texto). Se podría implementar lazy loading más agresivo.

6. **Manejo de la sesión de voz**: `pygame` mezcla la reproducción de audio en el mismo hilo que el resto de la GUI. Si hay muchos fragmentos, puede generar latencia. Mejor usar un thread separado con cola (ya está implementado de forma básica pero con algunas condiciones de carrera en `hablar_no_bloqueante`).

7. **Código muerto**: `a.py` es un script que ya no es necesario porque el modelo se descarga bajo demanda. `pruebas/test_nuevo_parser.py` está vacío.

8. **Protección contra inyección de comandos**: En `controlador_acciones.py`, los comandos extraídos de la respuesta de la IA se ejecutan directamente. Aunque hay validación de rutas, un LLM malicioso o con alucinaciones podría generar comandos peligrosos. Falta un filtro de verbos permitidos y sanitización de argumentos.

### 4.2. Próximos Pasos Recomendados

| Prioridad | Tarea |
|---|---|
| **Crítica** | Unificar estado en un solo gestor thread-safe (fusionar `EstadoGlobal` y `_AppState`). |
| **Alta** | Reemplazar confirmaciones de seguridad (borrado, git) por botones en la GUI en lugar del juez LLM. |
| **Alta** | Agregar una pantalla de configuración (tecla de voz, modelo Whisper, API keys) dentro de la aplicación. |
| **Media** | Implementar lazy loading para ChromaDB y Whisper (iniciar solo cuando se use voz o memoria). |
| **Media** | Mejorar el renderizado de Markdown usando una librería externa (p.ej., `tkinterhtml` o `markdown` + `tkinter.Text` más limpio). |
| **Media** | Agregar soporte multimodal real: enviar capturas de pantalla a Gemini como imágenes en la generación. |
| **Baja** | Crear un asistente de configuración inicial (first-run wizard) para seleccionar workspace y API keys. |
| **Baja** | Refactorizar `sistema.py` para separar la captura de monitores, el radar de programas y el comando `abrir:` en sub-módulos. |
| **Baja** | Escribir tests unitarios para `controlador_acciones.py` (especialmente `_dividir_comandos` y `_validar_ruta`). |
| **Baja** | Eliminar los scripts obsoletos (`a.py`, `pruebas/test_nuevo_parser.py`) y mover `limpiar.py` a herramientas CLI. |

---

**Nota final**: El proyecto tiene una arquitectura sólida y modular, con buenas prácticas de seguridad y manejo de hilos. Sin embargo, la duplicación de estado y la falta de confirmaciones visuales son los principales puntos de mejora para garantizar la robustez y experiencia de usuario.