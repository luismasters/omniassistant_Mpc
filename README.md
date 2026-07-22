# Argus — Asistente de IA Multimodal para Windows

**Argus** es un asistente de IA integrado al escritorio de Windows, diseñado para operar en tres modos (**General**, **Mentor Tecnológico** y **Gamer**) con cambio dinámico de modelo de lenguaje (Gemini 3.1 Flash Lite / DeepSeek Reasoner / Groq Llama 3.1 8B). Soporta interfaz dual (CustomTkinter nativa y Web HUD flotante/escritorio basado en PyWebView + Edge Chromium WebView2), voz, visión, gamepad multi-mando, búsqueda web, control de audio maestro y por app, memoria persistente, y un sistema extensible de Skills.

---

## ✨ Características principales

- **Interfaz dual (CustomTkinter + PyWebView Web HUD)**: Chat con renderizado de Markdown (código, tablas, listas), selección de modo, adjuntar archivos, guardar en memoria. Integra rostros de expresión vectorial en tiempo real: tanto EMO (`EmoBezelFace`) como Argus v2 (`RostroArgus`) a 60 FPS con temas neón dinámicos.
- **3 Modos de Visualización Win32**: Alterna dinámicamente entre Ventana Tradicional, Widget Flotante y Modo Escritorio / Wallpaper anclado al fondo del escritorio de Windows (`WorkerW` estilo Wallpaper Engine / Rainmeter).
- **Voz completa**: Captura STT con Whisper (acelerado por GPU/CPU), síntesis TTS con Edge TTS, reproducción con cola thread-safe y corte por tecla.
- **Modelos múltiples**: Gemini 3.1 Flash Lite (SDK `google-genai`), DeepSeek Reasoner y soporte integrado para Groq (Llama 3.3 70B, Llama 3.1 8B, Qwen 3.6 27B, GPT-OSS 120B) seleccionables en caliente.
- **Memoria persistente (ChromaDB)**: Guardado y búsqueda de recuerdos con caché de embeddings y radar de cambios en proyectos (`watchdog`).
- **Control de sistema**: Abrir/cerrar/mover ventanas, explorar directorios, apagar PC, búsqueda inteligente de programas.
- **Control de audio (`control_audio`)**: Gestión de volumen maestro, volumen por aplicación (pycaw), mute/unmute y cambio de dispositivos de salida.
- **Git integrado**: Push/pull con confirmaciones nativas por palabra clave, comandos libres, reset de remoto.
- **Gamepad avanzado**: Servicio continuo en subproceso con fallback a XInput nativo (`ctypes Win32`) para capturar combos L3+R3 (push-to-talk) incluso dentro de juegos en pantalla completa.
- **Skills extensibles**: Sistema de inyección contextual para búsqueda web, control de audio y capacidades personalizadas.
- **Seguridad**: Sandbox de archivos, confirmaciones nativas (sin gasto innecesario de tokens).
- **Visión**: Captura de pantalla multi-monitor.

---

## 📋 Requisitos

- **Sistema operativo**: Windows 10/11 (utiliza APIs nativas de Windows y Win32 `WorkerW`)
- **Python**: 3.10 o superior
- **GPU (opcional)**: NVIDIA con CUDA para aceleración de Whisper
- **Gamepad (opcional)**: DualSense, Xbox One / Series X|S para modo gaming
- **Conexión a internet**: Para APIs de Gemini, DeepSeek y Groq

---

## 🚀 Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/luismasters/omniassistant_Mpc.git
cd OmniAssistant
```

### 2. Crear entorno virtual (recomendado)

```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar API Keys

Crear un archivo `.env` en la raíz del proyecto con:

```env
GEMINI_API_KEY=tu_api_key_de_gemini
DEEPSEEK_API_KEY=tu_api_key_de_deepseek
GROQ_API_KEY=tu_api_key_de_groq
GITHUB_TOKEN=tu_token_de_github_opcional
```

> **Dónde obtener las API Keys:**
> - Gemini: https://aistudio.google.com/apikey
> - DeepSeek: https://platform.deepseek.com/api_keys
> - Groq: https://console.groq.com/keys
> - GitHub Token: https://github.com/settings/tokens

### 5. Ejecutar

Para iniciar la **GUI Desktop (CustomTkinter)**:
```bash
python main_gui.py
```

Para iniciar el **Web HUD (PyWebView + Edge Chromium)**:
```bash
python main_web.py
```

---

## 📦 Dependencias adicionales (skills)

Algunas skills requieren dependencias extra:

### Control de audio

```bash
pip install pycaw comtypes
```

> ⚠️ Para cambiar el dispositivo de salida de audio, puede requerir el módulo PowerShell `AudioDeviceCmdlets`.

---

## 🎮 Modos de uso

| Modo | Modelo por Defecto | Descripción |
|------|--------------------|-------------|
| **General** | Gemini 3.1 Flash Lite | Asistente cotidiano: chat, web, control de PC, memoria persistente |
| **Mentor Tecnológico** | DeepSeek Reasoner | Asesoría de stack, proyectos de portafolio, simulación de entrevistas y perfil de mentor (`perfil_mentor.json`) |
| **Gamer** | Groq Llama 3.1 8B | Respuesta ultra rápida para consultas breves durante juegos. Desactiva micrófono de teclado y activa PTT por mando (L3+R3) |

> 🧠 **Nota:** Los modelos indicados arriba son los asignados *por defecto*, pero podés cambiar a cualquiera de los modelos disponibles usando el selector desplegable en tiempo real.

### Atajos

- **F8**: Push-to-talk (mantener presionado para hablar en teclado)
- **L3+R3 (gamepad)**: Push-to-talk en mando (funciona en primer plano y dentro de juegos vía XInput)
- **Esc / Espacio**: Cortar reproducción de voz en curso

---

## 🧠 Skills disponibles

| Skill | Descripción | Estado |
|-------|-------------|--------|
| `busqueda_web_actualizada` | Búsqueda en DuckDuckGo con prioridad de resultados recientes | ✅ v1.0 Operativa |
| `control_audio` | Control de volumen maestro, por app y silenciar/activar | ✅ v1.0 Operativa |
| `monitor_hardware` | Monitoreo de temperatura CPU/GPU con LibreHardwareMonitor | 🔄 Planificada |
| `recordatorios` | Recordatorios programados con notificación y voz | 🔄 Planificada |

---

## 🔍 Escaneo de proyectos (Crawler)

El comando `escanear_proyecto:` analiza la arquitectura del workspace actual en dos fases:

| Fase | Motor | Descripción |
|------|-------|-------------|
| **Recorrido de archivos** | **Python** (`modulos/crawler.py`) | Recorre el workspace ignorando carpetas no deseadas (`.git`, `__pycache__`, `venv`), concatena archivos de código y documentación. |
| **Análisis y generación de PROJECT_STATE.md** | **Gemini 3.1 Flash Lite** | Procesa el contenido consolidado y genera un resumen estructurado de arquitectura, estado y deuda técnica. |

---

## 🏗️ Arquitectura del proyecto

```
OmniAssistant/
├── config.py                  # Configuración y estado global thread-safe
├── main_gui.py                # Interfaz gráfica principal (CustomTkinter)
├── main_web.py                # Punto de entrada Web HUD (PyWebView + Edge Chromium)
├── gestor_boveda.py           # CLI para gestión directa de memoria
├── test_emo_face.py           # Prototipo autónomo de pruebas para rostro EMO
├── mapeo_control_prueba.py    # Herramienta de pruebas para mandos gamepad
├── requirements.txt           # Dependencias del proyecto
├── .env                       # API Keys (no versionado)
├── gui/
│   ├── index.html             # Frontend HTML del Web HUD
│   ├── app.js                 # Lógica del cliente Web HUD
│   ├── emo_face.js            # Renderizado 60 FPS del rostro EMO
│   └── styles.css             # Estilos y temas neón
├── modulos/
│   ├── ia.py                  # Enrutador IA (Gemini + DeepSeek + Groq)
│   ├── prompts.py             # Plantillas de system prompt por modo
│   ├── audio_custom.py        # Captura y síntesis de voz (Whisper + Edge TTS)
│   ├── memoria.py             # Persistencia ChromaDB y radar de cambios
│   ├── perfil_usuario.py      # Extracción y gestión del perfil de usuario
│   ├── perfil_mentor.py       # Gestor del perfil del mentor
│   ├── ui_manager.py          # Gestor Strategy de modos de visualización Win32
│   ├── win32_desktop.py       # Integración ctypes Win32 (WorkerW reparenting & DPI)
│   ├── web_bridge.py          # Puente bidireccional Python <-> JS (PyWebView API)
│   ├── controlador_acciones.py # Parseo y ejecución de acciones del sistema
│   ├── sistema.py             # Control de procesos y ventanas Windows
│   ├── archivos.py            # I/O con sandbox de seguridad
│   ├── busqueda.py            # Búsqueda DuckDuckGo
│   ├── vision.py              # Captura de pantalla multi-monitor
│   ├── git_bot.py             # Automatización Git con confirmación nativa
│   ├── gamepad_control.py     # Integración de gamepad con la interfaz
│   ├── gamepad_service.py     # Subproceso independiente de lectura de gamepad
│   ├── xinput_reader.py       # Lector XInput nativo Win32 (fallback para juegos)
│   ├── gamepad_inputs.py      # Mapeos de entradas de mandos
│   ├── cliente_mcp.py         # Cliente MCP
│   ├── servidor_sistema_mcp.py # Servidor MCP
│   ├── crawler.py             # Generación automática de PROJECT_STATE.md
│   ├── logger.py              # Logging estructurado
│   ├── limpiar.py             # Limpieza de contexto y memoria
│   └── skills/                # Skills extensibles
│       ├── __init__.py
│       ├── gestor_skills.py   # Gestor de skills con detección contextual
│       ├── busqueda_web_actualizada/
│       └── control_audio/     # Control de audio via pycaw
├── tests/                     # Suite de pruebas unitarias e integrales
└── logs/
    └── omniassistant.log      # Logs de la aplicación
```

---

## 🛠️ Prioridades actuales y Roadmap

### Tareas completadas
- [x] Migración completa a `google-genai` (nuevo SDK oficial) ✅
- [x] Web HUD nativo flotante/escritorio con PyWebView (`main_web.py` + `gui/`) ✅
- [x] Skill `control_audio` (volumen maestro, por app y mute) ✅
- [x] Arquitectura de visualización Win32 (Fondo de Escritorio / WorkerW, Flotante, Tradicional) ✅
- [x] Subproceso Gamepad con fallback XInput nativo para juegos ✅

### Próximos pasos
- [ ] Skill `monitor_hardware` (temperatura CPU/GPU via LibreHardwareMonitor)
- [ ] Skill `recordatorios` (alertas temporales con voz)
- [ ] Confirmaciones GUI con diálogos popups nativos (`CTkDialog` / Modales Web)
- [ ] Detección de skills por embeddings semánticos (`all-MiniLM-L6-v2`)
- [ ] Estructuración de la suite de tests en `tests/`

---

## 📄 Licencia

Uso personal y educativo.