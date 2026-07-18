# Argus — Asistente de IA Multimodal para Windows

**Argus** es un asistente de IA integrado al escritorio de Windows, diseñado para operar en tres modos (General, Programador y Planificador) con cambio dinámico de modelo de lenguaje (Gemini 3.1 Flash Lite / DeepSeek Reasoner). Soporta voz, visión, gamepad, búsqueda web, control de sistema, memoria persistente, y un sistema extensible de Skills.

---

## ✨ Características principales

- **Interfaz gráfica con CustomTkinter + Web**: Chat con renderizado de Markdown (código, tablas, listas), selección de modo, adjuntar archivos, guardar en memoria. También incluye una **interfaz web** (`main_web.py`) accesible desde el navegador.
- **Voz completa**: Captura con Whisper (GPU acelerada), síntesis con Edge TTS, reproducción con cola thread-safe y corte por tecla.
- **Modelos duales**: Gemini 3.1 Flash Lite (modo General) y DeepSeek Reasoner (modos Programador/Planificador).
- **Memoria persistente (ChromaDB)**: Guardado y búsqueda de recuerdos con caché de embeddings.
- **Control de sistema**: Abrir/cerrar/mover ventanas, explorar directorios, apagar PC, búsqueda inteligente de programas.
- **Control de audio**: Volumen maestro y por aplicación (pycaw), cambio de dispositivo de salida.
- **Git integrado**: Push/pull con confirmación nativa, comandos libres, reset de remoto.
- **Gamepad**: Soporte DualSense y Xbox One, combo L3+R3 push-to-talk.
- **Skills extensibles**: Sistema de inyección contextual para búsqueda web, control de audio y más.
- **Seguridad**: Sandbox de archivos, confirmaciones nativas (sin gasto de tokens).
- **Visión**: Captura de pantalla multi-monitor.

---

## 📋 Requisitos

- **Sistema operativo**: Windows 10/11 (usa APIs nativas de Windows)
- **Python**: 3.10 o superior
- **GPU (opcional)**: NVIDIA con CUDA para aceleración de Whisper
- **Gamepad (opcional)**: DualSense o Xbox One para modo gaming
- **Conexión a internet**: Para APIs de Gemini y DeepSeek

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
GITHUB_TOKEN=tu_token_de_github_opcional
```

> **Dónde obtener las API Keys:**
> - Gemini: https://aistudio.google.com/apikey
> - DeepSeek: https://platform.deepseek.com/api_keys
> - GitHub Token: https://github.com/settings/tokens

### 5. Ejecutar

```bash
python main_gui.py
```

---

## 📦 Dependencias adicionales (skills)

Algunas skills requieren dependencias extra:

### Control de audio

```bash
pip install pycaw comtypes
```

> ⚠️ Para cambiar dispositivo de salida de audio, puede requerir el módulo PowerShell `AudioDeviceCmdlets`.

### Ejecutar tests

```bash
pip install pytest
python -m pytest tests/ -v
```

---

## 🎮 Modos de uso

| Modo | Modelo | Descripción |
|------|--------|-------------|
| **General** | Gemini 3.1 Flash Lite | Asistente cotidiano: chat, web, control de PC, memoria |
| **Programador** | DeepSeek Reasoner | Edición de código, Git, arquitectura de software |
| **Planificador** | DeepSeek Reasoner | Planificación, análisis de proyectos, documentación |

### Atajos

- **F8**: Push-to-talk (mantener presionado para hablar)
- **L3+R3 (gamepad)**: Push-to-talk en modo gaming
- **Esc / Espacio**: Cortar reproducción de voz

---

## 🧠 Skills disponibles

| Skill | Descripción | Estado |
|-------|-------------|--------|
| `busqueda_web_actualizada` | Búsqueda en DuckDuckGo con prioridad de resultados recientes | ✅ v1.0 |
| `control_audio` | Control de volumen maestro y por aplicación | ✅ v1.0 |
| `monitor_hardware` | Monitoreo de temperatura CPU/GPU | 🔄 Planificada |
| `recordatorios` | Recordatorios programados | 🔄 Planificada |

---

## 🔍 ¿Cómo funciona el escaneo de proyectos (Crawler)?

El comando `escanear_proyecto:` se ejecuta en dos fases:

| Fase | Motor | Descripción |
|------|-------|-------------|
| **Recorrido de archivos** | **Python** (`modulos/crawler.py`) | Recorre el workspace ignorando carpetas no deseadas (`.git`, `__pycache__`, `venv`), concatena archivos `.py`, `.md`, `.json`, `.txt` en un solo bloque de texto. |
| **Análisis y generación del PROJECT_STATE.md** | **Gemini 3.1 Flash Lite** | Recibe el código completo y un prompt de análisis arquitectónico. Devuelve el documento Markdown estructurado con resumen ejecutivo, arquitectura, estado actual y deuda técnica. |

> **Nota:** El crawler funciona en cualquier modo siempre que haya un Workspace seleccionado.

---

## 🏗️ Arquitectura del proyecto

```
OmniAssistant/
├── config.py                  # Configuración y estado global
├── main_gui.py                # Interfaz gráfica principal (CustomTkinter)
├── main_web.py                # Interfaz web alternativa
├── gestor_boveda.py           # CLI para gestión de memoria
├── requirements.txt           # Dependencias del proyecto
├── .env                       # API Keys (no versionado)
├── web/
│   └── index.html             # Frontend web
├── modulos/
│   ├── ia.py                  # Enrutador IA (Gemini + DeepSeek)
│   ├── prompts.py             # Plantillas de system prompt
│   ├── audio_custom.py        # Captura y síntesis de voz
│   ├── memoria.py             # Persistencia ChromaDB
│   ├── controlador_acciones.py # Parseo y ejecución de acciones
│   ├── sistema.py             # Control de sistema Windows
│   ├── archivos.py            # I/O con sandbox de seguridad
│   ├── busqueda.py            # Búsqueda DuckDuckGo
│   ├── vision.py              # Captura de pantalla
│   ├── git_bot.py             # Automatización Git
│   ├── gamepad_control.py     # Soporte de gamepad
│   ├── cliente_mcp.py         # Cliente MCP
│   ├── servidor_sistema_mcp.py # Servidor MCP
│   ├── crawler.py             # Generación de PROJECT_STATE
│   ├── logger.py              # Logging
│   ├── limpiar.py             # Limpieza de ChromaDB
│   └── skills/                # Skills extensibles
│       ├── __init__.py
│       ├── gestor_skills.py   # Gestor de skills con detección contextual
│       ├── busqueda_web_actualizada/
│       │   ├── __init__.py
│       │   ├── SKILL.md
│       │   ├── instructions.md
│       │   └── ejemplos.md
│       └── control_audio/
│           ├── __init__.py
│           ├── audio_control.py
│           ├── SKILL.md
│           ├── instructions.md
│           └── ejemplos.md
├── tests/
│   ├── __init__.py
│   └── test_ia.py             # Tests unitarios
└── logs/
    └── omniassistant.log      # Logs de la aplicación
```

---

## 🧪 Tests

```bash
# Ejecutar todos los tests
python -m pytest tests/ -v

# Tests específicos
python -m pytest tests/test_ia.py -v -k "confirmacion"
python -m pytest tests/test_ia.py -v -k "voz"
python -m pytest tests/test_ia.py -v -k "EstadoGlobal"
```

---

## 🛠️ Deuda técnica y próximos pasos

Ver [`PROJECT_STATE.md`](PROJECT_STATE.md) para el estado detallado del proyecto y el roadmap.

### Prioridades actuales
- [x] Migración completa a `google-genai` (nuevo SDK) ✅
- [x] Tests unitarios y de integración ✅
- [x] README con guía de instalación ✅
- [ ] Skill `monitor_hardware` (temperatura CPU/GPU)
- [ ] Skill `recordatorios`
- [ ] Confirmaciones GUI con popups nativos (CTkDialog)
- [ ] Detección de skills por embeddings semánticos
- [ ] Interfaz web (`main_web.py`)

---

## 📄 Licencia

Uso personal y educativo.

---

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Por favor:
1. Hacé fork del proyecto
2. Creá una rama para tu feature (`git checkout -b feature/nueva-skill`)
3. Hacé commit de tus cambios (`git commit -m 'Agrega nueva skill'`)
4. Hacé push a la rama (`git push origin feature/nueva-skill`)
5. Abrí un Pull Request