# PROJECT_STATE.md

## 1. Resumen Ejecutivo

**OmniAssistant** es un asistente de escritorio inteligente que combina interacción por voz y texto con capacidades de **pair programming**, **control del sistema operativo**, **visión por computadora** y **memoria híbrida (RAG)**. Está diseñado para actuar como un copiloto técnico para desarrolladores, permitiendo desde la ejecución de comandos del sistema hasta el análisis profundo de código fuente y la sincronización con repositorios Git. Utiliza **Google Gemini** como motor principal de IA para el modo general y **DeepSeek** para modos especializados (Planificador y Programador), con un sistema de herramientas **MCP (Model Context Protocol)** para acceder a funcionalidades del sistema de forma segura.

## 2. Arquitectura

El proyecto está organizado en módulos especializados dentro de `modulos/`, más archivos raíz para la interfaz y configuración:

| Capa | Archivo / Módulo | Función |
|------|-------------------|---------|
| **Interfaz Usuario** | `main.py` | Interfaz flotante minimalista con Tkinter (voz + chat, alertas hardware) |
| | `main_gui.py` | Interfaz completa con CustomTkinter (sidebar, chat rendereado, tabs) |
| **Configuración** | `config.py` | Variables de entorno y constantes globales (API keys, modelo Whisper) |
| **Lógica Central** | `modulos/ia.py` | Enrutador de IA: orquesta Gemini y DeepSeek, gestiona contexto y acciones |
| **Audio** | `modulos/audio.py` | Captura de micrófono (Faster‑Whisper) y síntesis de voz (pyttsx3) |
| **Sistema** | `modulos/sistema.py` | Control de ventanas, procesos, exploración de archivos, monitoreo hardware |
| **Visión** | `modulos/vision.py` | Captura de pantalla (multi‑monitor) usando PIL |
| **Archivos** | `modulos/archivos.py` | Lectura/escritura/eliminación de archivos, soporte PDF, detección de tamaño |
| **Memoria** | `modulos/memoria.py` | Base vectorial ChromaDB para RAG, snapshot del proyecto en `.cortana/` |
| | `gestor_boveda.py` | Herramienta CLI para gestionar la bóveda de memoria (listar/borrar/reset) |
| **Búsqueda** | `modulos/busqueda.py` | Búsqueda web mediante DuckDuckGo (ddgs) |
| **Git** | `modulos/git_bot.py` | Sincronización y comandos Git: init, add, commit, push, remotos |
| **MCP** | `servidor_sistema_mcp.py` | Servidor MCP que expone herramientas (estado PC, hardware, bóveda, archivos) |
| | `modulos/cliente_mcp.py` | Cliente MCP asíncrono usado por `ia.py` |
| **Crawler** | `modulos/crawler.py` | Extrae todo el código de un proyecto ignorando carpetas no relevantes |
| **Utilidades** | `prueba_mcp.py`, `modulos/limpiar_memoria.py` | Pruebas y mantenimiento |

### 2.1 Flujo de datos principal

```
Usuario (voz/texto)
     │
     ▼
  main.py / main_gui.py   ← Interfaz
     │
     ▼
  modulos/ia.py           ← Enrutador
     │
     ├─ Gemini (modo general) → herramientas MCP, acciones SO, búsqueda web
     └─ DeepSeek (planificador/programador) → generación de plan.md, código
     │
     ▼
  modulos/sistema.py, archivos.py, audio.py, memoria.py, git_bot.py, etc.
```

## 3. Estado Actual

### ✅ Funcionalidades construidas y operativas

#### Interfaz de usuario
- **Ventana flotante Tkinter** con transparencia, alertas de hardware y modo oscuro.
- **GUI CustomTkinter** con sidebar, pestañas Chat/Logs, burbujas de usuario/IA con markdown renderizado (tablas, código, listas, negritas).
- Entrada por teclado (Enter) y botón de envío, soporte para Shift+Enter.
- Barra de búsqueda de archivos adjuntos (📎).

#### Voz
- Captura con tecla personalizable (F8 por defecto) usando Faster‑Whisper (modelo medium, CUDA).
- Síntesis de voz con pyttsx3 (voz en español, velocidad 180).
- Interrupción de la voz con tecla Espacio.

#### Control del sistema
- Abrir/cerrar programas, juegos y carpetas mediante comandos en lenguaje natural.
- Radar inteligente que busca accesos directos en escritorio, menú inicio y unidades.
- Soporte multimonitor: mover ventanas a monitores específicos (@1, @2).
- Monitoreo de hardware con alertas (GPU >82°C, RAM >92%).

#### Memoria e inteligencia
- **RAG con ChromaDB**: guardado y búsqueda vectorial de fragmentos de documentos.
- **Snapshot del proyecto** en `.cortana/snapshot.json`.
- **Ingesta de archivos**: adjuntar múltiples archivos (txt, pdf, docx, código) e inyectarlos en contexto volátil o bóveda permanente.
- **Crawler**: escanea todo el proyecto, genera un `PROJECT_STATE.md` con DeepSeek (thinking).

#### Modos de IA
- **General** (Gemini Flash): chat natural, control PC, búsqueda web, visión, Git.
- **Planificador** (DeepSeek V4 Flash + thinking): analiza arquitectura y genera planes.
- **Programador** (DeepSeek V4 Flash): escribe y modifica código según plan.

#### Herramientas MCP
- **estado_pc**, **hardware**, **buscar/guardar en bóveda**, **explorar ruta**, **leer documento**.
- Comunicación segura mediante subprocesos STDIO.

#### Control de versiones
- Sincronización con GitHub (crear repo, push, reset remoto).
- Ejecución de comandos Git libres con confirmación de seguridad.

## 4. Deuda Técnica / Próximos Pasos

### 🔴 Errores y riesgos detectados

| Categoría | Problema | Impacto | Solución propuesta |
|-----------|----------|---------|-------------------|
| **Duplicación** | Dos interfaces (`main.py` + `main_gui.py`) incompatibles entre sí | Mantenimiento duplicado, confusión de usuario | Unificar en `main_gui.py` como interfaz principal; eliminar `main.py` o convertirlo en respaldo |
| **Estabilidad audio** | `pyttsx3` falla en algunos sistemas (driver SAPI, hilos bloqueantes) | Cortana no habla o se cuelga | Migrar a `edge-tts` (asíncrono, multiplataforma) |
| **Lógica de acciones frágil** | La detección de comandos (`guardar_archivo:`, `eliminar:`) se hace con `"texto" in respuesta_ia.lower()` | Falsos positivos, comandos no detectados si cambia formato | Usar expresiones regulares ancladas al inicio de línea o un parser YAML/JSON en la respuesta |
| **Silenciador MCP** | El servidor MCP redirige `stdout` a `/dev/null` | Errores internos del servidor quedan ocultos | Crear un buffer de logs interno y exponerlo como herramienta de diagnóstico |
| **Contexto plano** | El historial de chat (`CONTEXTO_CHAT`) es una lista lineal sin persistencia ni límite de tokens | Se pierde contexto en sesiones largas, no hay resúmenes automáticos | Implementar resumen periódico del historial con Gemini y almacenar en bóveda |
| **Manejo de errores** | Múltiples `try/except` genéricos que capturan todo | Dificulta depuración, enmascara bugs | Usar excepciones específicas y logging estructurado (por ejemplo, `logging` con niveles) |
| **Coste DeepSeek** | El crawler usa `deepseek-v4-flash` con thinking para cada análisis | Alto coste por token | Permitir seleccionar modelo (Gemini local, DeepSeek Lite) y cachear resultados |
| **Falta de tests** | No hay pruebas unitarias ni de integración | Riesgo de regresiones al modificar código | Agregar `pytest` para módulos críticos (memoria, archivos, control sistema) |
| **Código duplicado** | `prueba_mcp.py` y `modulos/prueba_mcp.py` son casi idénticos | Confusión | Eliminar el duplicado y mantener solo el del raíz |
| **Seguridad** | Las confirmaciones de borrado/Git se basan en un modelo `gemini-flash-lite` | Posible manipulación si el prompt se contamina | Usar confirmación explícita del usuario (botón UI o palabra clave fija como "SÍ CONFIRMO") |
| **Dependencias duras** | `servidor_sistema_mcp.py` importa módulos internos (sistema, archivos, memoria) | Acoplamiento fuerte | Refactorizar para inyectar dependencias o usar un registro de servicios |

### 🟡 Mejoras recomendadas (corto plazo)

1. **Logging estructurado**: reemplazar `print()` por `logging` con formato timestamp y niveles.
2. **Persistencia del historial**: guardar últimas N conversaciones en la bóveda para continuar sesiones.
3. **Interfaz de confirmación**: en lugar de texto en el chat, usar botones modales en la GUI para autorizar borrados y Git.
4. **Modo offline**: habilitar fallback con modelos locales (Ollama/Llama.cpp) cuando no haya internet.
5. **Soporte multilenguaje**: traducir prompts al inglés para modelos que no soporten español.
6. **Mejora del renderizado**: los bloques de código en `AIBubble` a veces se cortan si contienen líneas muy largas sin wrap horizontal.
7. **Paralelismo**: la captura de voz bloquea la UI durante la grabación; usar hilos separados con señales.

### 🟢 Visión a largo plazo

- **Plugin MCP externo**: que el asistente pueda conectarse a servidores MCP remotos (bases de datos, APIs).
- **Agentes autónomos**: permitir que Cortana ejecute tareas en background sin supervisión constante (por ejemplo, "escanea este proyecto cada hora y avísame si encuentra vulnerabilidades").
- **Interfaz web**: proveer un dashboard accesible desde el navegador para control remoto.
- **Memoria semántica**: además de vectores, usar grafos de conocimiento para relaciones entre entidades.
- **Soporte macOS/Linux**: actualmente depende de `win32gui` y `nvidia-smi`; abstraer esas capas con adaptadores.