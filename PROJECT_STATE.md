# PROJECT_STATE.md

## 1. Resumen Ejecutivo

OmniAssistant es un asistente de escritorio inteligente con interfaz gráfica (CustomTkinter) que integra múltiples modelos de IA (Gemini Flash, DeepSeek V4) para proporcionar capacidades de chat, planificación de software, programación asistida, control del sistema operativo (apertura/cierre de programas, gestión de ventanas, monitorización de hardware), búsqueda web, visión por captura de pantalla, gestión de memoria vectorial híbrida (ChromaDB) y sincronización con GitHub. El sistema opera en tres modos (General, Planificador, Programador) y ofrece interacción por voz (Whisper + TTS) y texto. Está diseñado como un asistente personal "pair programmer" y administrador del sistema.

## 2. Arquitectura

### 2.1. Estructura de directorios

```
OmniAssistant/
├── config.py                    # Configuración global, API keys, límites, constantes
├── main_gui.py                  # Interfaz gráfica principal (CustomTkinter)
├── servidor_sistema_mcp.py      # Servidor MCP (Model Context Protocol) para herramientas de sistema
├── gestor_boveda.py             # Gestor independiente de la base de datos vectorial (ChromaDB)
├── README.md                    # Documentación del proyecto
├── logs/                        # Directorio de logs (generado automáticamente)
├── modulos/
│   ├── ia.py                    # Orquestador principal de IA (Gemini + DeepSeek), enrutador de modos
│   ├── audio.py                 # Captura de voz (Whisper) y síntesis de voz (TTS con pyttsx3)
│   ├── sistema.py               # Control del SO: apertura/cierre de programas, gestión de ventanas, monitorización
│   ├── archivos.py              # Operaciones seguras de archivos (lectura, escritura, creación, eliminación, búsqueda)
│   ├── busqueda.py              # Búsqueda web mediante DuckDuckGo
│   ├── vision.py                # Captura de pantalla (PIL + screeninfo)
│   ├── git_bot.py               # Integración con Git/GitHub (commit, push, reset)
│   ├── memoria.py               # Motor de memoria vectorial (ChromaDB, embeddings, snapshots)
│   ├── cliente_mcp.py           # Cliente MCP para conectar con servidores de herramientas
│   ├── crawler.py               # Extractor de código de proyectos (para análisis arquitectónico)
│   ├── logger.py                # Configuración de logging (archivo + consola)
│   └── limpiar.py               # Script para vaciar la base de memoria
├── boveda_memoria/              # Base de datos ChromaDB persistente (generada automáticamente)
└── pruebas/
    └── test_seguridad.txt       # Archivo de prueba
```

### 2.2. Descripción funcional de cada módulo

- **config.py**: Punto central de configuración. Almacena API keys (Gemini, DeepSeek, GitHub), límites de tamaño de archivos, rutas seguras, parámetros de Whisper, modos de operación.
- **main_gui.py**: Interfaz de usuario basada en CustomTkinter. Implementa:
  - Panel lateral con cambio de modo (General/Planificador/Programador)
  - Área de chat con burbujas de usuario e IA (soporte Markdown: negrita, cursiva, código, tablas, listas)
  - Barra de entrada de texto con botón de adjuntar archivos
  - Pestaña de logs en tiempo real
  - Integración con tecla rápida para entrada de voz (F8)
  - Historial por modo preservado al cambiar de modo
  - Animación streaming de respuestas
- **servidor_sistema_mcp.py**: Servidor FastMCP que expone herramientas de sistema (estado PC, hardware, búsqueda en bóveda, guardado en bóveda, exploración de rutas, lectura de documentos) como servicios MCP consumibles por el cliente MCP.
- **gestor_boveda.py**: Herramienta CLI independiente para administrar la bóveda de memoria: listar etiquetas, eliminar documentos, formatear base de datos.
- **modulos/ia.py**: Cerebro del asistente. Contiene:
  - Inicialización de clientes Gemini y DeepSeek
  - Enrutador `enviar_a_gemini()` que redirige según `MODO_ACTUAL`
  - Construcción de contexto de sistema según modo
  - Integración con herramientas MCP
  - Interceptor de acciones rápidas (guardar_archivo, snapshot, buscar, eliminar, github, etc.)
  - Procesamiento de archivos adjuntos (carga en memoria volátil o permanente)
- **modulos/audio.py**: Módulo de audio que utiliza Faster-Whisper para transcripción y pyttsx3 para síntesis de voz. Implementa captura de micrófono con tecla de activación y detección de voz.
- **modulos/sistema.py**: Control del sistema operativo Windows. Incluye:
  - Radar inteligente para encontrar programas y juegos (usa thefuzz para coincidencias difusas)
  - Gestión de ventanas (multimonitor, mover, forzar cierre)
  - Exploración de directorios con atajos
  - Monitoreo de hardware (CPU, RAM, GPU, VRAM)
- **modulos/archivos.py**: Operaciones de archivos con validación de seguridad (sandbox, espacio en disco, tamaño de contenido). Funciones: leer, escribir, crear carpetas, eliminar (con confirmación), listar, buscar local.
- **modulos/busqueda.py**: Búsqueda web simple usando la librería `ddgs` (DuckDuckGo).
- **modulos/vision.py**: Captura de pantalla con soporte multimonitor usando PIL y screeninfo.
- **modulos/git_bot.py**: Automatización de Git: inicializar repos, añadir remoto, commit, push, ejecutar comandos libres (con validación de seguridad).
- **modulos/memoria.py**: Capa de persistencia vectorial con ChromaDB. Almacena recuerdos con embeddings (all-MiniLM-L6-v2), busca por similitud semántica, gestiona snapshots de proyectos en JSON.
- **modulos/cliente_mcp.py**: Cliente asíncrono MCP que permite a `ia.py` llamar herramientas del servidor MCP de forma síncrona (usando asyncio.run).
- **modulos/crawler.py**: Extractor de código de proyectos: recorre todo el árbol, ignora carpetas no deseadas, concatena archivos de código para análisis masivo.
- **modulos/logger.py**: Configura logging dual (archivo + consola) con formato estándar.
- **modulos/limpiar.py**: Script simple para vaciar la base de datos de memoria.

## 3. Estado Actual

### 3.1. Funcionalidades completamente operativas

- **Interfaz gráfica oscura** con cambio de modos, historial persistente por modo, streaming de respuestas, renderizado Markdown (negrita, cursiva, código, tablas, listas, encabezados).
- **Entrada de voz** con tecla F8: captura, transcripción con Whisper, envío a IA.
- **Síntesis de voz**: respuestas leídas en español con pyttsx3.
- **Modo General (Gemini Flash)**: Chat conversacional con herramientas MCP (estado PC, hardware, bóveda), visión por captura de pantalla, búsqueda web.
- **Modo Planificador (DeepSeek V4 con Thinking)**: Análisis arquitectónico de proyectos, generación de planes (plan.md), generación de PROJECT_STATE.md mediante crawler.
- **Modo Programador (DeepSeek V4 Fast)**: Escritura de archivos en workspace, creación de carpetas, ejecución de comandos Git, sincronización GitHub.
- **Control del sistema operativo**: Abrir programas/archivos/carpetas, cerrar procesos, mover ventanas entre monitores, explorar directorios, ejecutar comandos de sistema.
- **Operaciones de archivos seguras**: Lectura/escritura dentro del sandbox, creación/eliminación con confirmación, búsqueda local.
- **Memoria vectorial (ChromaDB)**: Guardado y búsqueda semántica de recuerdos, persistencia en disco.
- **Snapshots de proyectos**: Guardado/carga del estado del proyecto en archivo JSON dentro de `.cortana/`.
- **Adjuntar archivos desde GUI**: Subida de archivos con opción de guardar en bóveda permanente o mantener en contexto volátil.
- **Git automático**: Commit, push, reset remoto, comandos libres (con validación de seguridad).
- **Servidor MCP**: Herramientas de sistema expuestas como servicios MCP y consumidas por el cliente MCP.
- **Logging**: Registro en archivo y consola con niveles DEBUG/INFO.
- **Gestor de bóveda CLI**: Listar, eliminar documentos y formatear base de datos.
- **Crawler de proyectos**: Extracción completa del código para análisis arquitectónico por DeepSeek.

### 3.2. Funcionalidades parciales o en desarrollo

- **Visión por cámara web**: No implementada (solo captura de pantalla).
- **Integración con otras APIs**: Solo Gemini y DeepSeek (no hay soporte para otros modelos).
- **Soporte macOS/Linux**: El código está fuertemente acoplado a Windows (win32gui, nvidia-smi, etc.).
- **Manejo de errores en streaming**: Algunos fallos en chunks pueden interrumpir la respuesta sin recuperación.
- **Auto-actualización de snapshots**: El snapshot no se actualiza automáticamente al cambiar archivos; requiere comando manual.

## 4. Deuda Técnica / Próximos Pasos

### 4.1. Bugs identificados

1. **`modulos/ia.py` línea ~212**: `mcp_explorar_ruta` y `mcp_leer_documento` están registradas como funciones pero el mapeo de nombres en el interceptor de function_call no coincide exactamente: las herramientas MCP se llaman `explorar_ruta` y `leer_documento` en el servidor, pero en el cliente se llaman `mcp_explorar_ruta` y `mcp_leer_documento`. Gemini podría llamar a `explorar_ruta` y no encontrar el handler.

2. **`modulos/ia.py` línea ~274**: En el bloque de `if usaste_mcp:`, se reutiliza `mensajes_para_gemini` que ya incluye el mensaje del usuario y la respuesta parcial. Al agregar `{'role': 'user', 'parts': [f"[DATO DEL SISTEMA: ...]"]}` se inserta un segundo mensaje de usuario, lo que puede confundir al modelo (estructura de conversación incorrecta). Además, `modelo_gemini` no está definido en ese ámbito (se definió dentro del bloque `if modelo_activo == "gemini"`).

3. **`modulos/audio.py` línea ~2**: Importa `sounddevice` pero no está listado en requirements (puede faltar dependencia). Además usa `scipy.io.wavfile` que también debe estar instalado.

4. **`main_gui.py` línea ~740**: En `motor_microfono`, el uso de `audio_modulo.hablando_actualmente` puede causar race conditions porque se modifica desde otro hilo.

5. **`main_gui.py`**: El método `_agregar_sistema` no elimina el `_welcome_label` si existe, puede quedar superpuesto.

6. **`modulos/sistema.py`**: `obtener_ruta_dinamica` se ejecuta en cada llamada, creando overhead innecesario. Las rutas podrían cachearse.

### 4.2. Mejoras de arquitectura

1. **Separar la lógica de enrutamiento de `ia.py`**: Actualmente `enviar_a_gemini` es un monolito de ~500 líneas. Debería dividirse en:
   - Un manejador de comandos/acciones
   - Un gestor de contexto
   - Un enrutador de modelos
   - Un serializador de respuestas

2. **Estandarizar el formato de mensajes**: Mezcla el formato de Gemini (`parts`) con el de OpenAI (`content`). Crear un adaptador para unificar.

3. **Mover la lógica de MCP a un módulo separado**: El servidor MCP está duplicado en `servidor_sistema_mcp.py` y `modulos/servidor_sistema_mcp.py`. Consolidar.

4. **Implementar caché de embeddings**: Las consultas repetitivas a ChromaDB podrían cachearse en memoria para reducir latencia.

5. **Mejorar la gestión de errores en streaming**: Si un chunk falla, no hay reintento ni notificación al usuario.

6. **Desacoplar la interfaz de la lógica de negocio**: `main_gui.py` contiene referencias directas a `modulos.ia` y `modulos.audio`. Usar un patrón observador o signals.

### 4.3. Deuda técnica

1. **Código duplicado**: `servidor_sistema_mcp.py` y `modulos/servidor_sistema_mcp.py` son idénticos.
2. **Módulo `limpiar.py` usa `coleccion_principal` que no está definida**: `from memoria import coleccion_principal` no funciona porque en `memoria.py` la variable se llama `coleccion_principal` (con `_`).
3. **Uso de variables globales mutables**: `CONTEXTO_CHAT`, `ARCHIVO_PENDIENTE_INYECCION`, `DOCUMENTO_VOLATIL`, etc. modificadas desde múltiples hilos sin locks.
4. **Falta de typing**: La mayoría de funciones carecen de type hints.
5. **Dependencias no declaradas**: No hay `requirements.txt` ni `pyproject.toml`. Se asume instalación manual.
6. **Falta de tests**: No hay tests unitarios ni de integración.
7. **Documentación desactualizada**: El README.md menciona características que no están implementadas (cámara web, telemetría en vivo con alertas).

### 4.4. Próximos pasos recomendados

1. **Refactor urgente**: Arreglar los bugs 1, 2 y 3 para evitar fallos en producción.
2. **Agregar `requirements.txt`** con todas las dependencias exactas.
3. **Crear sistema de logging más robusto** con rotación de archivos.
4. **Implementar tests unitarios** para `modulos/archivos.py`, `modulos/sistema.py` y el enrutador de `ia.py`.
5. **Migrar a async en `ia.py`**: Actualmente usa `asyncio.run()` dentro de una función síncrona, lo que puede causar problemas en entornos con event loop ya corriendo.
6. **Mejorar el manejo de memoria**: El contexto de chat se acumula sin límite de tokens; implementar ventana deslizante basada en tokens.
7. **Agregar soporte para más modelos**: Permitir configuración dinámica de modelos mediante archivo YAML o JSON.