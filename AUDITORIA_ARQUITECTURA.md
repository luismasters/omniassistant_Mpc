# 🏗️ Auditoría de Arquitectura — Argus OmniAssistant

> ⚠️ **Documento HISTÓRICO.** Esta auditoría corresponde al estado del 25/07/2026. Varios puntos ya fueron resueltos (rotación de logs, tests, requirements). Para la planificación viva y la deuda técnica actualizada, consultá **[ROADMAP.md](ROADMAP.md)**.

**Fecha:** 25 de Julio de 2026  
**Versión analizada:** v0.5.0 HUD  
**Propósito:** Análisis estructural, deuda técnica y hoja de ruta de mejoras

---

## 1. 📐 Arquitectura General

```
OmniAssistant/
├── main_web.py          ← Entry point PRINCIPAL (PyWebView)
├── main_gui.py          ⚠️ DEPRECADO (Tkinter/customtkinter)
│
├── config.py            ← Estado global + API keys
├── gui/                 ← Frontend Web (HTML+CSS+JS)
│   ├── index.html
│   ├── styles.css       (1627 líneas — enorme)
│   ├── app.js           (1200 líneas — enorme)
│   ├── emo_face.js      ← Canvas EMO a 60fps
│   └── holo_hud.js      ← HUD holográfico
│
├── modulos/
│   ├── ia.py            ← Enrutador de IA (Gemini/DeepSeek/Groq)
│   ├── sistema.py       ← Win32 API, ventanas, monitores
│   ├── audio_custom.py  ← Whisper STT + Edge TTS
│   ├── controlador_acciones.py ← Parseo de comandos
│   ├── web_bridge.py    ← Puente Python ↔ JS (PyWebView API)
│   ├── prompts.py       ← System prompts para la IA
│   ├── memoria.py       ← ChromaDB vectorial
│   └── skills/          ← Sistema de Skills extensible
│       ├── gestor_skills.py
│       ├── control_audio/
│       │   ├── SKILL.md
│       │   ├── instructions.md
│       │   └── audio_control.py
│       └── recordatorios/
│           ├── instuctions.md
│           └── gestor_recordatorios.py
│
├── tests/               ← 📁 VACÍA
└── logs/                ← Logs (crece sin límite)
```

---

## 2. ✅ Fortalezas

### 2.1 Arquitectura modular limpia
- Separación clara entre backend (`modulos/`), frontend (`gui/`) y entrada (`main_*.py`)
- Sistema de skills basado en archivos: cada skill es una carpeta con `SKILL.md` + `instructions.md`
- Fácil de extender: crear nueva carpeta en `skills/` y el `gestor_skills.py` la detecta automáticamente

### 2.2 Memoria persistente con ChromaDB
- Búsqueda semántica con SentenceTransformers (`all-MiniLM-L6-v2`)
- Caché de embeddings con TTL de 5 minutos
- Búsqueda anticipada: inicia la query a ChromaDB mientras la IA piensa

### 2.3 Soporte multimodal real
- **Voz:** Whisper (STT) + Edge TTS (síntesis) + Pygame (reproducción)
- **Visión:** Captura de pantalla vía PIL + envío a Gemini
- **Gamepad:** XInput nativo + HTML5 Gamepad API + Pygame como fallback
- **Web:** Interfaz moderna con PyWebView + WebView2 Chromium

### 2.4 Interceptores inteligentes
- Comandos `argus:` se detectan ANTES de llamar a la IA → silenciosos y rápidos
- Frases de limpieza de contexto se interceptan localmente
- Confirmaciones de seguridad (borrado, git, bóveda) sin depender del modelo

### 2.5 Manejo robusto de errores (añadido recientemente)
- Global exception hooks en `main_gui.py` y `main_web.py` (`sys.excepthook` + `threading.excepthook`)
- Protecciones contra crashes silenciosos en hilos de micrófono y TTS

---

## 3. ⚠️ Deuda Técnica y Riesgos

### 🔴 CRÍTICO

| # | Problema | Archivo | Impacto |
|---|----------|---------|---------|
| 1 | **Sin tests automatizados** | `tests/` (vacía) | Cada cambio requiere pruebas manuales. Riesgo alto de regression. |
| 2 | **Logging sin rotación** | `modulos/logger.py` | `omniassistant.log` crece infinitamente. Puede llenar el disco. |
| 3 | **Sin manejo de rate limiting** | `modulos/ia.py` | Si la API de Gemini/Groq/DeepSeek rate-limita, el programa no reintenta con backoff. |
| 4 | **Credenciales en .env sin validación** | `config.py` | Si falta GEMINI_API_KEY, el programa crashea con `raise ValueError`. Pero Groq y DeepSeek pueden faltar sin aviso. |

### 🟡 ALTO

| # | Problema | Archivo | Impacto |
|---|----------|---------|---------|
| 5 | **requirements.txt con versiones flotantes** | `requirements.txt` | `pywebview>=6.2.1`, `scipy>=1.13,<1.18` — puede romper con nuevas versiones. |
| 6 | **Sin type hints en módulos clave** | `sistema.py`, `audio_custom.py`, `controlador_acciones.py` | Dificulta el mantenimiento y la detección de errores en IDE. |
| 7 | **Archivos JS/CSS monolíticos** | `gui/app.js` (1200 líneas), `gui/styles.css` (1627 líneas) | Difícil de mantener, sin separación de componentes. |
| 8 | **Estado global sin serialización** | `config.py` (EstadoGlobal) | Si el programa crashea, se pierde el contexto de chat. No hay persistencia. |
| 9 | **Sin script de instalación** | No hay `setup.py` ni `pyproject.toml` | No se puede instalar con `pip install -e .` |

### 🟢 MEDIO

| # | Problema | Archivo | Impacto |
|---|----------|---------|---------|
| 10 | **Sin versionado semántico** | No hay `__version__` | No se puede trackear qué versión está corriendo. |
| 11 | **TTS sin timeout de red** | `modulos/audio_custom.py` | Edge TTS hace llamada HTTP a Azure. Si no hay internet, bloquea. |
| 12 | **Whisper carga completo en VRAM** | `modulos/audio_custom.py` | Modelo `medium` en GPU ocupa ~3GB de VRAM. En modo Gaming se descarga, pero tarda. |
| 13 | **Sin documentación de API** | No hay docstring formal en web_bridge.py | Quien quiera conectar un frontend alternativo no sabe qué métodos llamar. |
| 14 | **Sin graceful shutdown** | `main_web.py` | Si se cierra con Ctrl+C, los hilos daemon mueren abruptamente. |

---

## 4. 🛠️ Plan de Acción Priorizado

### Fase 1 — Estabilización (1-2 días)

- [ ] **1.1** Agregar `logging.handlers.RotatingFileHandler` a `modulos/logger.py` (max 10MB, 5 backups)
- [ ] **1.2** Agregar retry con exponential backoff en `modulos/ia.py` para llamadas a APIs
- [ ] **1.3** Agregar `__version__ = "0.5.0"` en `config.py` o `__init__.py`

### Fase 2 — Testing (3-5 días)

- [ ] **2.1** Configurar pytest + pytest-cov
- [ ] **2.2** Tests unitarios para `modulos/sistema.py` (ventanas, monitores)
- [ ] **2.3** Tests unitarios para `modulos/controlador_acciones.py` (parsing de comandos)
- [ ] **2.4** Tests de integración para `modulos/ia.py` (simular respuestas de API)
- [ ] **2.5** Mocks para ChromaDB y APIs externas

### Fase 3 — Calidad de Código (3-5 días)

- [ ] **3.1** Fragmentar `gui/app.js` en módulos: `chat.js`, `voice.js`, `gamepad.js`, `emo.js`
- [ ] **3.2** Fragmentar `gui/styles.css` en: `base.css`, `chat.css`, `sidebar.css`, `holo.css`
- [ ] **3.3** Agregar type hints a todos los módulos
- [ ] **3.4** Crear `pyproject.toml` con `[project]` para instalación pip

### Fase 4 — Features y UX (1-2 semanas)

- [ ] **4.1** Persistencia del contexto de chat en SQLite (recuperación tras crash)
- [ ] **4.2** Selector de voz para TTS (diferentes voces Edge)
- [ ] **4.3** Más modos de visualización (minimalista, solo chat, solo EMO)
- [ ] **4.4** Sistema de plugins para skills en vez de archivos MD
- [ ] **4.5** Panel de monitoreo en la UI (uso de RAM/VRAM, latencia de API)

### Fase 5 — Despliegue (1 semana)

- [ ] **5.1** Empaquetado con PyInstaller para distribución
- [ ] **5.2** Instalador MSI/NSIS para Windows
- [ ] **5.3** Posibilidad de ejecución headless (solo backend, sin GUI)

---

## 5. 📊 Métricas del Proyecto

| Métrica | Valor |
|---------|-------|
| Líneas de Python | ~12,000 |
| Líneas de JavaScript | ~2,500 |
| Líneas de CSS | ~1,627 |
| Líneas de HTML | ~333 |
| Archivos totales | ~55 |
| Módulos Python | ~25 |
| Skills instaladas | 3 (audio, web, recordatorios) |
| Dependencias | 23 (requirements.txt) |
| Tests | **0** |

---

## 6. 🔮 Recomendaciones Estratégicas

1. **Priorizar tests ahora** — Cada fix manual que hicimos (exception hooks, argus commands) podría haberse validado con un test automático. Sin tests, el proyecto no escala.

2. **Migrar skills a plugins** — El sistema actual de archivos `SKILL.md` + `instructions.md` es frágil. Un sistema de plugins con entrada/salida definida (interfaz `ISkill`) sería más robusto y permitiría skills comunitarias.

3. **Separar frontend web del backend** — Permitir que Argus funcione como API REST además de PyWebView. Así se podría conectar desde cualquier dispositivo (celular, tablet, etc.).

4. **Implementar modo offline parcial** — Muchas funcionalidades (control de ventanas, audio local, recordatorios) no requieren internet. Si la API de Gemini falla, se podría caer a un modelo local más pequeño (Llama.cpp, Ollama).

5. **Grabar sesiones de voz para debugging** — Cuando Whisper falla, no hay forma de saber qué dijo el usuario. Guardar el audio crudo (opcional, con permiso) facilitaría el debugging.