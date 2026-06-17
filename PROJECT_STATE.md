# PROJECT_STATE.md — Fuente de la Verdad

## 1. Resumen Ejecutivo

**OmniAssistant (Argus)** es un asistente de IA multimodal y multiagente integrado en el escritorio de Windows. Permite al usuario interactuar mediante texto, voz, captura de pantalla y adjuntos de archivos. El sistema cuenta con tres modos de operación (General, Planificador, Programador) que enrutan las consultas a modelos de lenguaje específicos (Gemini Flash, DeepSeek Reasoning y DeepSeek Chat) y ejecutan acciones concretas sobre el sistema operativo, el sistema de archivos, Git, la web, la memoria vectorial (Bóveda) y la automatización de ventanas.

El proyecto está diseñado con una arquitectura modular, utilizando un hilo principal de interfaz gráfica (CustomTkinter) con un sidebar de control, un motor de voz (Whisper + Edge-TTS) y un backend de agentes con capacidad de ejecución de comandos mediante un parser de intenciones.

## 2. Arquitectura

### Módulos y archivos principales

| Archivo | Rol | Descripción |
|---------|-----|-------------|
| `config.py` | Configuración central | Define rutas seguras, límites de archivos, API keys, estados globales mediante la clase `EstadoGlobal`. |
| `main_gui.py` | Interfaz de usuario | Ventana principal con CustomTkinter, sidebar de modos, área de chat con burbujas (usuario/IA), renderizado Markdown, input con soporte para arrastre de archivos y micrófono. |
| `modulos/ia.py` | Motor de IA | Enruta consultas al modelo correspondiente (Gemini o DeepSeek), maneja streaming, MCP tools, interceptor de adjuntos y semáforos de seguridad (Git, borrado). |
| `modulos/controlador_acciones.py` | Parser de acciones | Interpreta la respuesta de la IA y ejecuta operaciones de archivos (leer, escribir, reemplazar bloques), Git, snapshot, búsqueda web, comandos de sistema. |
| `modulos/archivos.py` | Gestión de archivos | Funciones seguras de lectura/escritura/eliminación con validación de rutas (sandbox) y límites de tamaño. |
| `modulos/sistema.py` | Interacción con Windows | Manejo de ventanas (mover, cerrar), búsqueda de programas/archivos, ejecución de comandos, monitoreo de hardware. |
| `modulos/audio.py` | Voz | Captura con micrófono (Whisper lazy loading), síntesis de voz con Edge-TTS, reproducción con pygame, interrupción por tecla. |
| `modulos/memoria.py` | Memoria a largo plazo | Base de datos vectorial ChromaDB (bóveda), funciones guardar/buscar, snapshots del proyecto, watchdog de cambios en tiempo real. |
| `modulos/busqueda.py` | Búsqueda web | Consultas a DuckDuckGo (ddgs) con límite de resultados. |
| `modulos/git_bot.py` | Operaciones Git | Inicialización, add, commit, pull (rebase), push, comandos libres. Manejo de remotos y conflictos. |
| `modulos/vision.py` | Captura de pantalla | Toma capturas de monitores específicos o totales usando Pillow. |
| `modulos/crawler.py` | Análisis de proyecto | Recorre el árbol de directorios y extrae el contenido de archivos de código/texto para crear un estado global. |
| `modulos/prompts.py` | Prompts de sistema | Genera instrucciones para cada modo (General, Planificador, Programador) incluyendo contexto dinámico. |
| `modulos/cliente_mcp.py` | Cliente MCP | Conecta con el servidor MCP interno para ejecutar herramientas del sistema (estado PC, exploración, etc.). |
| `modulos/servidor_sistema_mcp.py` | Servidor MCP | Expone herramientas como `reporte_estado_pc`, `buscar_en_boveda`, `guardar_en_boveda`, `explorar_ruta`, `leer_documento`. |
| `gestor_boveda.py` | Utilidad de administración | Interfaz de consola para listar/borrar/formatear la bóveda ChromaDB. |
| `modulos/limpiar.py` | Script de limpieza | Borra todos los registros de la colección principal de memoria. |

### Flujo de datos típico

1. Usuario escribe texto o activa voz → `main_gui.py` captura y envía a `ia.py`.
2. `ia.py` determina el modo actual y llama al modelo de IA correspondiente (Gemini o DeepSeek) con el prompt adecuado (`prompts.py`).
3. La respuesta streamed se muestra en la GUI y se pasa a `controlador_acciones.py` para detectar comandos de acción.
4. Las acciones ejecutan operaciones seguras (archivos, sistema, Git, web, memoria, MCP).
5. Los resultados se retroalimentan al chat y al contexto del asistente.

## 3. Estado Actual

### Funcionalidades operativas verificadas

| Funcionalidad | Estado | Detalle |
|---------------|--------|---------|
| **Chat multimodal** | ✅ | Entrada de texto + voz (Whisper) + adjuntos de archivos. Respuestas streamed en tiempo real. |
| **Tres modos de IA** | ✅ | Modo General (Gemini Flash), Planificador (DeepSeek Reasoning), Programador (DeepSeek Chat). Cambio desde sidebar con preservación de historial. |
| **Renderizado Markdown** | ✅ | Bloques de código con resaltado sintáctico, tablas, listas, negrita/cursiva/inline code. Botón copiar en cada bloque. |
| **Operaciones de archivos** | ✅ | Lectura, escritura, creación de carpetas, eliminación (con confirmación), reemplazo de bloques (exacto y flexible), edición de una línea. Sandbox y límites de tamaño. |
| **Control de sistema Windows** | ✅ | Abrir/cerrar programas, mover ventanas entre monitores, búsqueda inteligente de programas (radar), comandos de apagado/cancelación. |
| **Git integrado** | ✅ | Inicialización, commit automático, pull (rebase), push, manejo de remotos, confirmación de usuario mediante semáforo. |
| **Búsqueda web** | ✅ | DuckDuckGo con límite de resultados. |
| **Memoria a largo plazo (Bóveda)** | ✅ | ChromaDB persistente. Guarda y recupera información por etiquetas. Integración con MCP. |
| **Snapshots de proyecto** | ✅ | Guarda estado del workspace en `.cortana/snapshot.json` y lo carga automáticamente. |
| **Watchdog de archivos** | ✅ | Detecta cambios manuales en el workspace y limpia la caché de la IA para mantener consistencia. |
| **Captura de pantalla** | ✅ | Toma capturas de pantalla (monitor específico o todos) y las envía a Gemini como imagen. |
| **Síntesis de voz** | ✅ | Edge-TTS con reproducción en hilo separado, interrupción por tecla. |
| **MCP (Model Context Protocol)** | ✅ | Servidor y cliente internos para herramientas del sistema (hardware, exploración, bóveda). |
| **Crawler de proyecto** | ✅ | Extrae todo el código de un proyecto y lo envía a DeepSeek para generar PROJECT_STATE.md. |
| **Gestor de bóveda** | ✅ | Script independiente para listar, borrar o formatear la bóveda desde terminal. |

### Limitaciones conocidas

- **Compatibilidad**: El sistema está fuertemente ligado a Windows (win32gui, nvidia-smi, powershell). No es portable a Linux/macOS sin refactorización.
- **Dependencias externas**: Requiere `faster-whisper`, `edge-tts`, `gitpython`, `chromadb`, `sentence-transformers`, `psutil`, `screeninfo`, `thefuzz`, `ddgs`, entre otras.
- **Instalación inicial**: El modelo Whisper se descarga automáticamente al primer uso (puede tardar). La bóveda se crea vacía.
- **Seguridad**: El sandbox solo se aplica en modo General. En modos Planificador/Programador el workspace es protegido, pero no hay limitación de rutas fuera del proyecto.
- **Git**: El auto-commit usa un mensaje fijo. No se manejan autenticaciones (se asume que el usuario tiene credenciales configuradas).

## 4. Deuda Técnica / Próximos Pasos

### Deuda técnica identificada

1. **Módulo `ia.py` demasiado monolítico**:
   - Contiene lógica de enrutamiento, streaming, MCP, interceptor de adjuntos, semáforos de seguridad y procesamiento posterior. Fragmentar en submódulos mejoraría la mantenibilidad.

2. **Manejo de errores inconsistente**:
   - Algunos `try/except` son genéricos, otros no registran errores. En `modulos/audio.py` no se captura la falla de carga de Whisper más allá del `Global` de `_cargar_whisper_si_necesario()`.

3. **Doble interpretación de acciones**:
   - `controlador_acciones.py` parsea la respuesta de la IA línea por línea, pero también `ia.py` detecta comandos directos (como "sube los cambios") antes de enviar a la IA. Podría unificarse en un solo pipeline.

4. **Caché de contexto en memoria**:
   - `contexto_chat` crece sin límite (aunque se trunca a 100 mensajes). No se persiste el historial entre sesiones. Podría migrarse a la bóveda con metadatos de sesión.

5. **Dependencia de `keyboard`**:
   - La detección de teclas (F8, espacio) en `main_gui.py` y `audio.py` utiliza la librería `keyboard`, que requiere privilegios de administrador en algunas configuraciones. Podría reemplazarse por hooks de Windows nativos.

6. **Servidor MCP interno frágil**:
   - El servidor se ejecuta en un subproceso y redirige stdout/stderr a `os.devnull` para silenciar logs. Si ocurre un error, la comunicación falla silenciosamente.

7. **Falta de tests automatizados**:
   - No hay pruebas unitarias ni de integración. El archivo `pruebas/test_nuevo_parser.py` está vacío.

### Próximos pasos recomendados

1. **Refactorizar `ia.py`**:
   - Separar en `enrutador.py`, `stream_handler.py`, `interceptor.py`, `semáforos.py`.
   - Mover el manejo de confirmaciones (Git, borrado, adjuntos) a un controlador dedicado.

2. **Implementar persistencia de conversaciones**:
   - Guardar historial de chat en la bóveda con etiqueta de sesión y fecha. Opción de restaurar sesiones anteriores.

3. **Mejorar el sandbox**:
   - Ampliar la protección a los modos Planificador/Programador, permitiendo solo operaciones dentro del workspace explícitamente anclado.

4. **Optimizar el parser de acciones**:
   - Unificar detección de comandos (actualmente hay tanto patrón de línea como etiquetas `<...>`) en un solo sistema basado en JSON o instrucciones estructuradas.

5. **Añadir tests**:
   - Escribir tests unitarios para `archivos.py`, `git_bot.py`, `controlador_acciones.py` (usando fixtures de archivos temporales y repositorios).
   - Tests de integración para el flujo completo de voz->texto->comando.

6. **Mejorar la experiencia de instalación**:
   - Crear un script `setup.bat` o `install.py` que instale dependencias y descargue el modelo Whisper automáticamente.

7. **Documentar API de plugins**:
   - Permitir que terceros agreguen nuevas herramientas MCP sin modificar el core.

8. **Revisar seguridad de ejecución remota**:
   - Validar que los comandos de sistema (abrir/cerrar/mover) no puedan ser inyectados por el modelo de IA (ya hay un sandbox de rutas, pero no hay sanitización del comando en sí).