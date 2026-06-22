# PROJECT_STATE.md — Fuente de la Verdad

## 1. Resumen Ejecutivo

**Argus** es un asistente de IA de escritorio para Windows, diseñado para actuar como copiloto inteligente en tareas de programación, administración del sistema, búsqueda de información y control de la PC. Integra modelos de lenguaje (Gemini Flash, DeepSeek Reasoner), reconocimiento y síntesis de voz (Whisper, Edge TTS), memoria persistente (ChromaDB), operaciones Git, búsqueda web, captura de pantalla, manipulación segura de archivos y un sistema de herramientas MCP para acceder a recursos locales. Su interfaz gráfica está construida con CustomTkinter, con soporte multimodo (General, Programador) y streaming en tiempo real.

## 2. Arquitectura

| Archivo / Módulo | Función principal |
|---|---|
| `a.py` | Utilidad única para descargar forzadamente el modelo Whisper "medium" a caché |
| `config.py` | Configuración central: API keys, límites, estado global singleton `estado` |
| `gestor_boveda.py` | CLI independiente para gestionar (listar/borrar/formatear) la memoria ChromaDB |
| `main_gui.py` | Interfaz gráfica principal (Chat + Logs), manejo de entrada, streaming, barras laterales |
| `modulos/archivos.py` | Lectura/escritura/eliminación segura con sandbox, validación de rutas y espacio |
| `modulos/audio_custom.py` | Captura de voz (Whisper) y síntesis de voz (Edge TTS) con cola y reproducción asíncrona |
| `modulos/busqueda.py` | Búsqueda en internet vía DuckDuckGo (ddgs) |
| `modulos/cliente_mcp.py` | Cliente síncrono para el servidor MCP local |
| `modulos/controlador_acciones.py` | Parser de comandos de acción extraídos de las respuestas de la IA (leer, guardar, reemplazar, sistema, git) |
| `modulos/crawler.py` | Extracción recursiva del código de un proyecto (ignora .git, venv, etc.) para análisis masivo |
| `modulos/git_bot.py` | Operaciones Git: init, add, commit, pull (rebase), push, comandos libres |
| `modulos/ia.py` | Orquestador central: enruta mensajes al modelo correcto, maneja MCP, streaming, intercepta intenciones |
| `modulos/limpiar.py` | Utilidad mínima para vaciar toda la bóveda de memoria |
| `modulos/logger.py` | Configuración de logging (archivo + consola) |
| `modulos/memoria.py` | Conexión a ChromaDB persistente, funciones de guardado/búsqueda vectorial, snapshot local, watchdog (radar) |
| `modulos/prompts.py` | Definición de los prompts del sistema para cada modo (General, Programador, Planificador -deprecado) |
| `modulos/servidor_sistema_mcp.py` | Servidor MCP que expone herramientas: estado PC, hardware, explorar ruta, leer documento, memoria |
| `modulos/sistema.py` | Comandos reales del SO: abrir/cerrar/mover ventanas, explorar carpetas, radar de programas, hardware, estado |
| `modulos/vision.py` | Captura de pantalla con soporte multimonitor |
| `plan.md` | Plan de acción para la solución de problemas Git (ya implementada en git_bot.py) |
| `requirements.txt` | Dependencias Python del proyecto |

## 3. Estado Actual (Funcionalidades operativas)

- ✅ **Chat multimodal**: Gemini Flash (general) y DeepSeek Reasoner (programador/planificador) con streaming de texto y voz.
- ✅ **Reconocimiento de voz**: Whisper (medium) en GPU con VAD, activado por tecla F8.
- ✅ **Síntesis de voz**: Edge TTS (voz Jorge, pitch/rate ajustables) con reproducción en segundo plano.
- ✅ **Memoria persistente**: ChromaDB con embeddings (all-MiniLM-L6-v2) para búsqueda semántica.
- ✅ **Memoria volátil y adjuntos**: Carga de archivos en contexto (volátil) sin pregunta, con resumen automático.
- ✅ **Snapshots y radar**: Guardado de estructura del proyecto y watchdog que invalida caché al modificar archivos.
- ✅ **Gestión de archivos segura**: Sandbox inteligente (modo general permite cualquier ruta, modo proyecto restringe al workspace).
- ✅ **Operaciones Git**: Push, pull con rebase, commit automático, manejo de remotos, detección de cambios.
- ✅ **Búsqueda web**: DuckDuckGo integrada (fallback para información en tiempo real).
- ✅ **Control del sistema**: Abrir/cerrar/mover programas, explorar carpetas, apagado programado.
- ✅ **Captura de pantalla**: Captura por monitor (soporte multi) con envío a Gemini.
- ✅ **Herramientas MCP**: Estado PC, hardware, busqueda/guardado en bóveda, exploración de rutas, lectura de documentos.
- ✅ **Interfaz gráfica**: CustomTkinter con tema oscuro, burbujas de usuario e IA, resaltado de sintaxis (código), tablas Markdown, botones de copia.
- ✅ **Gestor de bóveda independiente**: Script CLI para listar/borrar/formatear la memoria.
- ✅ **Crawler de proyectos**: Extrae todo el código de un proyecto y lo envía a DeepSeek para generar PROJECT_STATE.md automáticamente.

## 4. Deuda Técnica / Próximos Pasos

### 4.1 Problemas detectados

- **Estado global frágil**: `config.estado` es un singleton mutable accedido desde múltiples hilos (GUI, micrófono, watchdog). No hay locks, riesgo de condiciones de carrera.
- **Inicialización perezosa de Whisper**: Se carga bajo demanda, pero el primer uso puede congelar la UI brevemente (≈2-3s en GPU).
- **Gestión de errores incompleta**:
  - `servidor_sistema_mcp.py` redirige stdout/stderr a `os.devnull`, ocultando errores del servidor.
  - Algunos `except:` genéricos en `ia.py` y `controlador_acciones.py` pueden enmascarar fallos.
- **Modelos deprecados**: `obtener_prompt_planificador` y `obtener_prompt_programador` (prompts.py) ya no se usan (se usa el unificado), pero permanecen en el código.
- **Dependencias pesadas**: Faster-Whisper (modelo medium ≈1.5 GB), ChromaDB con sentence-transformers, DeepSeek API → el primer arranque descarga múltiples modelos o requiere conexión.
- **Radar (watchdog) sin límite**: Si el proyecto tiene muchos archivos, el evento `on_modified` puede dispararse con alta frecuencia, causando reinicios innecesarios de caché.
- **Manejo de monitores**: El mapeo en `_mapear_monitor` invierte 1↔2; según comentarios, el monitor 1 es el izquierdo, pero en Windows los índices pueden variar. Puede confundir usuarios.
- **Hardcodeo de rutas**: En `sistema.py` existe `"E:\Mis_Juegos_Yiri"` específica del desarrollador. Debería ser configurable.
- **Git**: Aunque se aplicaron las mejoras del plan.md, el `sincronizar_proyecto_git` intenta pull antes de que exista la rama remota, capturando la excepción; esto es correcto pero podría ser más elegante.
- **Pruebas**: El archivo `pruebas/test_nuevo_parser.py` está vacío. No hay suite de tests unitarios.

### 4.2 Próximas mejoras sugeridas

1. **Thread safety**: Implementar locks o patrones thread-local para el estado global.
2. **Optimización del radar**: Agregar debounce (cooldown) al manejador de watchdog para evitar invalidaciones masivas.
3. **Configuración externa**: Mover rutas fijas (ej. `Mis_Juegos_Yiri`) a un archivo de configuración o variables de entorno.
4. **Indicador de progreso de carga**: Mostrar barra de progreso o spinner mientras se descargan modelos por primera vez.
5. **MCP robusto**: No silenciar errores del servidor MCP; usar logging en su lugar.
6. **Pruebas automatizadas**: Crear tests para `controlador_acciones.py`, `git_bot.py` y `archivos.py`.
7. **Internacionalización**: Permitir cambiar idioma de voz y prompts (actualmente solo español).
8. **Aplicación portable**: Empaquetar como ejecutable standalone (PyInstaller) con modelos incluidos o descarga guiada.
9. **Memoria episódica**: Implementar resúmenes automáticos del chat para guardar como recuerdos.
10. **Modo "Planificador"**: Aunque se redirige a Programador, plan.md y prompts aún lo referencian; decidir si eliminar o reimplementar con enfoque de planificación pura.