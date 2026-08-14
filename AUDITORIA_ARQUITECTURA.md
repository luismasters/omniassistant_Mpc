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

---

## 7. 🔀 Fusión & ensamblado de contexto (flujo real, auditado)

Auditoría del recorrido completo del mensaje desde el input hasta el LLM y la respuesta.

### 7.1 Entradas del usuario (convergen todas en `enviar_a_gemini`)

| Entrada | Ruta | `modo_voz` |
|---------|------|------------|
| Texto escrito | JS → `web_bridge.recibir_mensaje` | `False` |
| Voz (mic) | `web_bridge.iniciar_escucha_voz` → `capturar_voz_micro` → `enviar_a_gemini(texto, modo_voz=True)` (web_bridge.py:563-580) | `True` |
| Voz por gamepad (L3+R3) | `iniciar_escucha_voz_gamepad` → `capturar_voz_micro(condicion_seguir_grabando=self.check_gamepad_combo_js)` (web_bridge.py:802-823) | `True` |
| Wake word | `activar_desactivar_wake_word` → `enviar_a_gemini` (web_bridge.py:873-884) | `True` |

El gamepad corre en **subproceso aislado** (`gamepad_service.py`) vía `modulos/gamepad_control.py`, para no interferir con el event loop de PyWebView. Los combos (L3+R3) llegan por la callback `callback_activar_voz`.

### 7.2 Interceptación antes del LLM (`procesar_mensaje`, ia.py:554-614)

Antes de armar el prompt, Argus decide si puede resolver la petición sin LLM:

1. **Comandos directos de sistema** — `_es_intencion_comando_directo()` (ia.py:192-210) detecta patrones y derivan a `controlador_acciones.procesar_acciones` (IA, cerrar/abrir/mover ventanas, `mover:`, `argus:`, audio, recordatorios, `buscar:`, `github:`, `capturar:`, bóveda, `escanear_proyecto:`).
2. **Acciones naturales de ventana** — frases tipo "movete a la pantalla 2", "maximizate", "ponte al frente" se detectan con heurística de palabras (ia.py:380-430) y se resuelven localmente (regla CRÍTICA: respuesta corta "Listo, acción ejecutada.").
3. **Búsqueda web** — se fusiona el legado `buscar:` con el parser de señales `[WEB: SI]/[CONSULTA: ...]` de la Arquitectura C+D (`modulos/senal_web.py`), incluyendo el marcador `[TEMA WEB ANTERIOR]`.
4. **Captura de pantalla** — los verbos de visión ("mirá", "fijate", "qué ves", "capturá") disparan `capturar_pantalla()` de `modulos/vision.py` (multimonitor por número).

Solo si nada interceptó, se arma el contexto completo y se llama al modelo.

### 7.3 Ensamblado del contexto (en orden)

1. **Modo actual** — `MODO_ACTUAL = config.estado.modo_actual` (chat/mentor/gamer/general). En `gamer` se inyecta `texto_perfil_gamer_para_prompt()`; en `mentor` se usa `obtener_prompt_mentor`.
2. **Prompt base por modo** — `obtener_prompt_*` en `modulos/prompts.py` (incluye reglas de comandos, visión, respuesta corta).
3. **Contexto de ventanas/workspace** — `texto_workspace`, `texto_snapshot`, `texto_doc_volatil` pasan como argumentos al prompt (prompts.py:129).
4. **Recuperación automática de memoria** — Fase 4: si no es comando directo, se recupera memoria relevante de la Bóveda/ChromaDB y se agrega a `contexto_sistema` (ia.py:614-622).
5. **Selección de modelo** — `config.estado.modelo_seleccionado`: Gemini 3.1 Flash Lite (default) / Pro (High) / 3.6 Flash (High), DeepSeek Reasoner, Groq (Llama 3.3/3.1, Qwen, GPT-OSS). En `gamer` el default es Gemini Flash Lite.
6. **Inyección de skills** — `gestor_skills.obtener_skill_relevante(texto_usuario)` por palabras clave hardcodeadas (gestor_skills.py). Si activa, se inyecta `[SKILL ACTIVADA: <nombre>]` + `instructions.md` al final del contexto. **Detalle clave:** con skill activa se **deshabilitan las tools MCP** (`if not skill_activa: gemini_config.tools = lista_herramientas_mcp`).
7. **Herencia temática web** — si hay evidencia previa (`config.estado.obtener_evidencia_web()`), se agrega `texto_marcador_tema_web_anterior()` (instrucción semántica para el LLM, no heurística Python).
8. **Multimodal** — las imágenes capturadas se pasan como `Part.from_bytes(...)` directo (FIX google-genai v2: PIL no se envuelve en Part ni Content).

### 7.4 Verificación web C+D y segunda generación

- El LLM decide con la señal estructurada `[WEB: SI]`/`[WEB: NO]` + `[CONSULTA: ...]`; Python solo ejecuta la búsqueda.
- `modulos/senal_web.py`: oculta las señales del streaming, parsea, fusiona con `buscar:` legacy y emite el marcador `[TEMA WEB ANTERIOR]`.
- `modulos/mensajes_web.py`: segunda generación con **evidencia** y persistencia separada. El borrador provisional (`marcarRespuestaProvisional`) se reemplaza al final por la respuesta verificada (ia.py:1181-1211, web_bridge.py:231-241).

### 7.5 Radar de proyecto (memoria sincronizada)

`iniciar_radar_proyecto` (memoria.py:486-498) monta un watchdog `watchdog.Observer` sobre la carpeta de trabajo con **debounce de 500 ms**. Al confirmar un cambio de archivo:

1. Detecta si la ruta está en `archivos_memoria` (config.estado).
2. Elimina el archivo de la copia de memoria.
3. Remueve del `contexto_chat` todo mensaje que contenga `[CONTENIDO DE '<ruta>']:` — **vía `reemplazar_contexto_chat()`, nunca asignación directa** (FIX documentado de condición de carrera: el handler corre en un `threading.Timer` mientras el hilo principal puede estar en `agregar_mensaje_chat()`).
4. Notifica por `ui_callback`.

### 7.6 Perfiles derivados (extracción post-conversación)

- `perfil_gamer.py: extraer_y_procesar_sesion_gamer` parsea los últimos mensajes con el LLM, los filtra contra el sistema de olvidos (`olvidos.py`, prefijos `funcional:`, `vida:`, `mentor:`, `gamer:`, `boveda:`) y persiste en `perfil_gamer.json` (thread-safe, corrupto → reset).
- `resumen_memoria.py` transforma todos los perfiles (usuario, mentor, gamer, bóveda) en secciones curadas para la UI con ids canónicos (`mentor:`, `gamer:`), y enruta edición/olvido a la implementación única por prefijo.

### 7.7 Observaciones de la auditoría

1. **La regla `if not skill_activa: tools = MCP` es un tradeoff importante**: activar una skill le quita a Gemini las tools MCP (la herramienta principal de "hacer"). No hay fallback ni aviso al usuario.
2. **Skills = 3** (`control_audio`, `busqueda_web_actualizada`, `recordatorios`), todas con `instructions.md`. La activación por keyword sigue hardcodeada en `gestor_skills.py`.
3. **El routing a modelo y la inyección de contexto están acoplados en una sola función gigante** (`procesar_mensaje`, ~700 líneas): intercepción, ensamblado, multimodal y stream. Es el archivo más riesgoso de tocar.
4. **`escanear_proyecto:` (crawler + Gemini → `PROJECT_STATE.md`) es un comando directo**: se resuelve en `controlador_acciones` y **saltea** tanto la recuperación automática de memoria como el envío al LLM general — ojo porque genera costos de tokens cuando corre en modo "crawler + Gemini".