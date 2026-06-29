# PROJECT_STATE.md — Argus (OmniAssistant)

## 1. Resumen Ejecutivo

**Argus** es un asistente de IA integrado en PC Windows con interfaz gráfica moderna (CustomTkinter). Su objetivo es actuar como copiloto inteligente para el usuario “Luis”, combinando:

- **Chat multimodal** (texto, voz, captura de pantalla)
- **Memoria persistente** mediante base de datos vectorial (ChromaDB)
- **Control de sistema** (abrir/cerrar programas, mover ventanas, gestionar audio)
- **Modos de trabajo** (General, Programador/Planificador con DeepSeek Reasoner)
- **Búsqueda web** con DuckDuckGo
- **Integración con Git** (push/pull automático con confirmación)
- **Sistema extensible de Skills** (control_audio, búsqueda_web_actualizada ya implementadas)

Está construido en Python puro, sin depender de servicios cloud para funcionalidades críticas (voz local con Whisper, audio con Edge TTS, etc.).

---

## 2. Arquitectura

### Estructura de directorios

```
/
├── config.py                 # Configuración global, variables de entorno, estado thread-safe
├── main_gui.py               # Interfaz gráfica principal (CustomTkinter) + lógica de UI
├── gestor_boveda.py          # Herramienta CLI para gestionar la memoria persistente
├── requirements.txt          # Dependencias del proyecto
├── plan_accion_skills_futuro.md  # Roadmap de skills (documentación)
├── modulos/
│   ├── ia.py                 # Enrutador principal de IA (Gemini ↔ DeepSeek) + MCP
│   ├── audio_custom.py       # Captura de voz (Whisper) + síntesis (Edge TTS) + reproducción
│   ├── archivos.py           # Operaciones seguras de archivos (leer/escribir/eliminar)
│   ├── sistema.py            # Control de ventanas, monitores, procesos, hardware (psutil, win32)
│   ├── busqueda.py           # Búsqueda web DuckDuckGo
│   ├── vision.py              # Captura de pantalla (PIL, screeninfo)
│   ├── memoria.py            # Gestión de ChromaDB (guardar/buscar recuerdos, snapshots, watchdog)
│   ├── git_bot.py            # Operaciones Git (init, add, commit, pull, push)
│   ├── controlador_acciones.py  # Parseo y ejecución de acciones IA (archivos, audio, git, sistema)
│   ├── prompts.py            # Templates de prompts para cada modo
│   ├── cliente_mcp.py        # Cliente MCP para servidor interno
│   ├── servidor_sistema_mcp.py  # Servidor MCP local (herramientas sistema, memoria)
│   ├── crawler.py            # Escaneo completo de proyectos (para modo Planificador)
│   ├── logger.py             # Configuración de logging
│   └── skills/
│       ├── gestor_skills.py  # Motor de detección e inyección de skills
│       ├── busqueda_web_actualizada/  # Skill para búsqueda web con prioridad temporal
│       └── control_audio/    # Skill para control de audio maestro y por app
```

### Flujo de datos principal

1. **Entrada del usuario** → main_gui.py (texto/tecla hablar/adjuntos)
2. **Procesamiento** → ia.py (determina modo, skills, inyecta contexto, llama a Gemini o DeepSeek)
3. **Acciones** → controlador_acciones.py (parsea comandos de IA y ejecuta operaciones reales)
4. **Retroalimentación** → UI callback (streaming de texto + voz)

### Patrones clave

- **Singleton** para estado global (`config.EstadoGlobal`) con locks thread-safe
- **Proxy MCP** local para aislar operaciones del sistema (servidor corre en proceso separado)
- **Debounce en Watchdog** para evitar múltiples recargas en cambios de archivos
- **Lazy loading** de Whisper (solo se carga al primer uso)

---

## 3. Estado Actual

### ✅ Funcionalidades operativas

| Funcionalidad | Estado | Notas |
|---|---|---|
| Chat con Gemini Flash (modo General) | ✅ | Streaming, contexto, adjuntos |
| Chat con DeepSeek V4 Reasoner (modo Programador) | ✅ | Streaming, reasoning visible |
| Captura de voz con Whisper (Faster-Whisper) | ✅ | Modelo medium, CUDA, VAD |
| Síntesis de voz con Edge TTS (es-MX-JorgeNeural) | ✅ | Stream continuo, pitch ajustable |
| Memoria persistente vectorial (ChromaDB) | ✅ | Guardado/búsqueda, etiquetado |
| Gestor de bóveda (CLI) | ✅ | Listar, eliminar, hard reset |
| Control de sistema (abrir, cerrar, mover ventanas) | ✅ | Radar inteligente de programas |
| Exploración de directorios | ✅ | Listado en chat |
| Captura de pantalla (monitor específico) | ✅ | Envío a Gemini para análisis visual |
| Búsqueda web (DuckDuckGo) | ✅ | Con filtro temporal, retry automático |
| Integración Git (init, add, commit, pull, push) | ✅ | Con confirmación vía juez IA |
| Escaneo de proyecto (crawler) | ✅ | Genera PROJECT_STATE.md automáticamente |
| Skills: `busqueda_web_actualizada` | ✅ | Detección por palabras clave |
| Skills: `control_audio` (volumen maestro y por app) | ✅ | pycaw + PowerShell fallback |
| Modo oscuro completo | ✅ | Paleta personalizada, código coloreado |
| Streaming de voz paralelo al texto | ✅ | Fragmentación por oraciones |
| Logging a archivo y consola | ✅ | logs/omniassistant.log |

### 🟡 Funcionalidades parciales / con limitaciones

| Funcionalidad | Limitación |
|---|---|
| Temperatura de CPU | `psutil` no mide temperatura en Windows → requiere LibreHardwareMonitor |
| Cambio de dispositivo de audio | Depende de PowerShell `AudioDeviceCmdlets` (no instalado por defecto) |
| Confirmaciones de UI | Usa Gemini como juez → consume tokens y es lento |
| Contexto por modo | Se guarda/restaura visualmente, pero no persiste entre reinicios |

### ❌ No implementado aún (del roadmap)

- Recordatorios (timer + notificación)
- Steam integration (API key requerida)
- Clima/Tiempo (wttr.in)
- Portapapeles inteligente
- Monitor de hardware real (LibreHardwareMonitor)
- Traductor
- Resumen de contenido web/YouTube

---

## 4. Deuda Técnica / Próximos Pasos

### 🔴 Prioridad alta (urgencia)

1. **Migración a `google.genai`** — El SDK `google.generativeai` está deprecado. La nueva API cambia inicialización y herramientas. Urgente antes de que deje de funcionar.
2. **Confirmaciones GUI nativas** — Reemplazar el juez Gemini (que consume tokens y es frágil) por `CTkDialog` nativo para confirmaciones de borrado, git, etc. Más rápido, sin coste.
3. **Unificar estado global** — Existe un `_AppState` en `main_gui.py` separado del `config.EstadoGlobal`. Esto puede causar race conditions. Unificar en una única fuente de verdad.

### 🟡 Prioridad media (mejoras importantes)

4. **Detección de skills por embeddings** — Actualmente se usan palabras clave hardcodeadas. Migrar a similitud semántica con el modelo `all-MiniLM-L6-v2` que ya carga ChromaDB. Más robusto.
5. **Manejo de errores en `audio_control.py`** — El fallback PowerShell para volumen maestro no es fiable. Implementar vía `winmm.dll` con ctypes directamente.
6. **Carga asíncrona de Whisper** — Whisper bloquea la UI unos segundos al primer uso. Mover a hilo con indicador de progreso.
7. **Persistencia de contexto por modo** — Guardar `contexto_chat` y `historial_por_modo` en disco (JSON) para que sobrevivan a reinicios.

### 🟢 Prioridad baja (deseables)

8. **LibreHardwareMonitor automático** — Verificar y lanzar el servicio al inicio para obtener temperaturas reales de CPU.
9. **Pruebas unitarias** — Actualmente no hay tests. Priorizar módulos críticos: `archivos.py`, `controlador_acciones.py`, `audio_control.py`.
10. **Refactor de `controlador_acciones.py`** — Función `procesar_acciones_ia` tiene más de 400 líneas. Separar en handlers por tipo de acción.
11. **Gestión de dependencias** — Algunas skills requieren paquetes opcionales (`pycaw`, `comtypes`, `win10toast`). Implementar detección y sugerencias de instalación automática.

### Bug conocido

- **Confirmación de borrado:** Cuando se usa el ratón para confirmar vía tecla física (no confirmación/gemini), a veces la UI no captura correctamente el evento y la acción se pierde. Pendiente de revisión.

---

*Documento generado automáticamente mediante análisis de código fuente.*  
*Última actualización: basada en el código proporcionado.*