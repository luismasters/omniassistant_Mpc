# PROJECT_STATE.md — Fuente de la Verdad

## 1. Resumen Ejecutivo

**Argus** (antes OmniAssistant/Cortana) es un asistente de inteligencia artificial integrado a la PC del usuario (Luis). Su propósito es actuar como copiloto multitarea, permitiendo interacción por voz y texto, con capacidades de:
- Comprensión y generación de lenguaje natural (Gemini Flash, DeepSeek V4).
- Control del sistema operativo (abrir/cerrar aplicaciones, mover ventanas entre monitores, apagar PC).
- Gestión de archivos (leer, escribir, editar, eliminar) dentro de un sandbox seguro.
- Navegación web y búsqueda en Internet.
- Memoria a largo plazo (ChromaDB vectorial) y vigilancia de cambios en proyectos (Watchdog).
- Operaciones Git (commit, pull, push) bajo demanda.
- Captura de pantalla y visión (actualmente solo imagen, sin análisis de contenido).
- Síntesis de voz (Edge TTS) y reconocimiento de voz (Whisper).
- Modos especializados: **General** (chat libre), **Planificador** (arquitectura de software), **Programador** (mantenimiento de código).

## 2. Arquitectura

### 2.1. Estructura de Archivos

```
├── config.py                      # Configuración centralizada (API keys, límites, estado global)
├── main_gui.py                    # Interfaz gráfica con CustomTkinter (Chat, Sidebar, Logs)
├── gestor_boveda.py               # CLI para gestionar la memoria vectorial (listar/eliminar/limpiar)
├── plan.md                        # Plan de acción para Git (documento de planeación interno)
├── prueba_voz.py                  # Script de prueba para voces Edge TTS
├── modulos/
│   ├── ia.py                      # Enrutador principal de IA, streaming, orquestación
│   ├── archivos.py                # Operaciones seguras de archivos (sandbox + workspace)
│   ├── audio_custom.py            # Sistema de voz Edge TTS (recomendado, más estable)
│   ├── audio.py                   # Sistema de voz Edge TTS (versión anterior, posible conflicto)
│   ├── audio_piper.py             # Sistema de voz XTTSv2 (alternativa experimental)
│   ├── busqueda.py                # Búsqueda web con DuckDuckGo
│   ├── cliente_mcp.py             # Cliente MCP para comunicación con servidor interno
│   ├── controlador_acciones.py    # Parser de acciones (escribe/lee/edita archivos, Git, comandos SO)
│   ├── crawler.py                 # Extracción de código completo de un proyecto
│   ├── git_bot.py                 # Operaciones Git (init, add, commit, pull, push)
│   ├── limpiar.py                 # Limpieza total de la bóveda de memoria
│   ├── logger.py                  # Configuración de logging (archivo + consola)
│   ├── memoria.py                 # Base de datos vectorial ChromaDB + Watchdog de archivos
│   ├── prompts.py                 # Prompts del sistema según el modo activo
│   ├── servidor_sistema_mcp.py    # Servidor MCP que expone herramientas del sistema (CPU, RAM, exploración)
│   ├── sistema.py                 # Control de ventanas, hardware, exploración de directorios
│   └── vision.py                  # Captura de pantalla (Pillow + screeninfo)
└── pruebas/
    ├── test_nuevo_parser.py       # Prueba vacía (pendiente)
    └── test_seguridad.txt         # Nota de prueba del sistema de archivos
```

### 2.2. Flujo de Datos

1. **Entrada**: Texto desde GUI o voz (Whisper + micro).
2. **IA**: `ia.py` recibe el mensaje, selecciona modelo según modo (Gemini/DeepSeek), adjunta contexto (memoria, snapshot, archivos en memoria).
3. **Streaming**: La respuesta se envía en tiempo real a `main_gui.py` (burbuja de chat) y, si está activo el modo voz, se sintetiza con Edge TTS y se reproduce.
4. **Acciones**: `controlador_acciones.py` parsea la respuesta de la IA en busca de comandos (leer/guardar/editar archivos, Git, mover ventanas, etc.) y los ejecuta.
5. **Memoria**: Las interacciones relevantes pueden guardarse en ChromaDB (`memoria.py`) mediante herramientas MCP o acciones explícitas.
6. **Retroalimentación**: Los resultados de las acciones (éxito/error) se inyectan en el contexto del chat para que la IA los conozca en futuros turnos.

### 2.3. Modos de Operación

| Modo           | Modelo                | Prompt especializado                    |
|----------------|-----------------------|-----------------------------------------|
| **General**    | Gemini Flash Lite     | Asistente natural, control de PC        |
| **Planificador** | DeepSeek Reasoner   | Arquitecto de software, no escribe código |
| **Programador**  | DeepSeek Chat        | Ingeniero de mantenimiento, solo edita si se le ordena |

### 2.4. Dependencias Clave Externas

- `google-generativeai` (Gemini)
- `openai` (DeepSeek)
- `chromadb` + `sentence-transformers` (memoria vectorial)
- `edge-tts` (síntesis de voz)
- `faster-whisper` (reconocimiento de voz)
- `pygame` + `sounddevice` (reproducción/grabación de audio)
- `gitpython` (Git)
- `psutil`, `pywin32`, `screeninfo` (control de sistema)
- `Pillow` (captura de pantalla)
- `watchdog` (monitoreo de archivos)
- `thefuzz` (coincidencia difusa de nombres)
- `mcp` (framework de servidor cliente MCP)

## 3. Estado Actual

### 3.1. Funcionalidades Completas y Operativas

- ✅ **Interfaz gráfica completa** con CustomTkinter: sidebar de modos, burbujas de chat con markdown (negrita, cursiva, código, tablas), input bar con adjuntos, logs.
- ✅ **Streaming de IA** con Gemini (incluyendo herramientas MCP) y DeepSeek (modo planificador/programador).
- ✅ **Reconocimiento de voz** con Whisper (lazy loading, configurable).
- ✅ **Síntesis de voz** con Edge TTS (multihilo, interrumpible con tecla ESC).
- ✅ **Memoria a largo plazo** ChromaDB con embeddings (búsqueda semántica y guardado).
- ✅ **Watchdog de proyecto** que invalida caché cuando se modifica un archivo externo.
- ✅ **Operaciones seguras de archivos** (sandbox, validación de espacio, límites de tamaño).
- ✅ **Control de sistema**: abrir/cerrar programas, mover ventanas entre monitores, apagar PC.
- ✅ **Búsqueda web** automática (DuckDuckGo) con segunda pasada de IA para resumir.
- ✅ **Captura de pantalla** (monitor específico o todo).
- ✅ **Git**: inicialización, add, commit, pull, push (con verificación de remoto y manejo de errores).
- ✅ **Crawler de proyecto** → genera `PROJECT_STATE.md` usando DeepSeek.
- ✅ **Modos Planificador y Programador** con prompts diferenciados y manejo de workspace.
- ✅ **Logging** centralizado (archivo + consola).

### 3.2. Funcionalidades Parciales o con Problemas Conocidos

- ⚠️ **Múltiples módulos de audio**: `audio.py`, `audio_custom.py`, `audio_piper.py` coexisten. `audio_custom.py` es el usado actualmente; los otros pueden causar confusión o conflictos de importación.
- ⚠️ **Lazy loading de Whisper** funciona, pero la carga inicial puede congelar la UI brevemente (no está en hilo separado).
- ⚠️ **DeepSeek Planificador** usa `deepseek-reasoner`, pero la respuesta a veces incluye razonamiento interno que se muestra en consola y podría filtrarse al usuario.
- ⚠️ **El gateway de adjuntos** (`[adjunto: ruta]`) solo lee archivos y los pone en memoria volátil; la inyección en bóveda requiere confirmación del usuario.
- ⚠️ **El modo Programa** tiene un candado de seguridad que impide editar archivos sin orden explícita, lo cual puede ser demasiado restrictivo.
- ⚠️ **Manejo de errores en IA** es genérico (except) y no distingue entre errores de API, límites de tokens, etc.

## 4. Deuda Técnica / Próximos Pasos

### 4.1. Deuda Técnica Identificada

1. **Duplicación de módulos de audio**  
   *Impacto*: Mantenimiento confuso, posible uso de recursos duplicados.  
   *Acción*: Unificar en un solo módulo (`audio_custom.py`) y eliminar `audio.py` y `audio_piper.py`.

2. **Carga sincrónica de Whisper**  
   *Impacto*: Pequeño lag al primer uso de voz.  
   *Acción*: Mover la carga a un hilo separado con callback o indicador de carga.

3. **Falta de tipado estático**  
   *Impacto*: Dificulta el mantenimiento y la detección temprana de errores.  
   *Acción*: Agregar anotaciones de tipo gradualmente, empezando por módulos críticos (`ia.py`, `controlador_acciones.py`).

4. **Gestión de estado global**  
   *Impacto*: `config.estado` es mutable y se comparte entre módulos; puede llevar a inconsistencias.  
   *Acción*: Refactorizar usando un patrón de estado único o una clase singleton con métodos de acceso.

5. **Dependencia `edge-tts` con `asyncio`**  
   *Impacto*: Se crean y cierran loops de eventos en cada síntesis (posible fuga de recursos en cargas altas).  
   *Acción*: Usar un loop persistente o migrar a `run_coroutine_threadsafe`.

6. **Falta de tests automatizados**  
   *Impacto*: La carpeta `tests/` está casi vacía.  
   *Acción*: Agregar tests unitarios para `archivos.py`, `git_bot.py`, y `controlador_acciones.py`.

7. **Manejo de errores en `ia.py`**  
   *Impacto*: Cualquier excepción en Gemini o DeepSeek captura todo y no da feedback al usuario.  
   *Acción*: Clasificar errores (timeout, autenticación, límite de tokens) y mostrar mensajes específicos.

8. **Seguridad de tokens y API keys**  
   *Impacto*: Las keys se cargan desde `.env` pero no se valida su formato ni se renuevan.  
   *Acción*: Agregar validación de formato y notificación de vencimiento.

### 4.2. Próximos Pasos Recomendados

| Prioridad | Tarea | Responsable |
|-----------|-------|-------------|
| Alta      | Unificar módulos de audio (`audio.py`, `audio_custom.py`, `audio_piper.py`) | Luis |
| Alta      | Mover carga de Whisper a hilo separado | Luis |
| Alta      | Agregar tests básicos para `archivos.py` y `git_bot.py` | Luis |
| Media     | Mejorar manejo de errores en `ia.py` (diferenciar tipos) | Luis |
| Media     | Refactorizar estado global (`config.estado`) en clase singleton | Luis |
| Media     | Agregar anotaciones de tipo en `controlador_acciones.py` | Luis |
| Baja      | Migrar `edge-tts` a loop asyncio persistente | Luis |
| Baja      | Validar y refrescar API keys automáticamente | Luis |

### 4.3. Riesgos Conocidos

- **Git**: Si el remoto no está configurado o hay conflictos de merge, el push puede fallar silenciosamente (aunque `git_bot.py` reporta errores, la UI no siempre los muestra visiblemente).
- **Watchdog**: La invalidación de caché funciona, pero si el usuario modifica un archivo mientras la IA está en medio de una respuesta, podría haber inconsistencias.
- **Límite de tokens**: El contexto del chat puede crecer hasta 100 mensajes, pero no hay control de tamaño individual. Archivos grandes truncados a 80k chars pueden causar pérdida de información.
- **DeepSeek Planificador**: El modelo `deepseek-reasoner` puede generar respuestas muy largas con razonamiento interno que no debería mostrarse al usuario.

---
*Generado por Argus — Arquitecto Principal*  
*Fecha: Abril 2025*