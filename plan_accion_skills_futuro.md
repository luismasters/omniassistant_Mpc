# ARGUS — Roadmap de Skills
**Última actualización:** 2026-06-24  
**Estado del proyecto:** v0.3.0 — Base sólida, expansión de capacidades en curso.

---

## Cómo funciona el sistema de Skills

Cada skill vive en `modulos/skills/<nombre_skill>/` y contiene tres archivos:

| Archivo | Propósito |
|---|---|
| `SKILL.md` | Metadatos: descripción, cuándo activarse, versión, autor. |
| `instructions.md` | Las instrucciones exactas que se inyectan en el prompt de Argus cuando la skill se activa. |
| `ejemplos.md` | Casos de uso concretos para ilustrar el comportamiento esperado. |

El `gestor_skills.py` detecta si una skill es relevante para la consulta del usuario (por palabras clave) y la inyecta automáticamente en el contexto. Skills activas en modo sin MCP desactivan las herramientas Gemini para forzar el flujo correcto.

---

## Skills implementadas

### ✅ `busqueda_web_actualizada` — v1.0
**Estado:** Operativa con fixes aplicados (2026-06-24).  
**Función:** Búsqueda en DuckDuckGo priorizando resultados recientes. Incluye retry automático y limpieza de filtros incompatibles (`after:` removido).  
**Activa cuando:** El usuario usa palabras como "hoy", "actual", "noticias", "precio", "lanzamiento", año actual, etc.  
**Pendiente:** Detección de relevancia por embeddings en vez de palabras clave hardcodeadas.

---

## Skills planificadas

### Tier 1 — Impacto diario inmediato

---

#### 🎚️ `control_audio` — Prioridad: ALTA
**¿Qué hace?**  
Control completo de audio del sistema: volumen maestro, volumen por aplicación, mute/unmute, cambio de dispositivo de salida (parlantes ↔ headset).

**¿Por qué es prioritaria?**  
Es la skill más natural para un asistente por voz. "Bajá el volumen", "silenciá Discord", "pasá el audio al headset" son comandos de uso diario que hoy requieren ir al mouse.

**Palabras clave de activación:**  
`volumen`, `subir`, `bajar`, `silenciar`, `mutear`, `audio`, `sonido`, `headset`, `parlantes`, `salida de audio`

**Dependencias:**  
- `pycaw` (Control de audio de Windows via COM)  
- `comtypes` (ya instalado con pycaw)

**Comandos que debe entender Argus:**
```
"Subí el volumen al 80%"          → SetMasterVolume(0.8)
"Silenciá Discord"                 → SetAppVolume("Discord.exe", mute=True)
"Pasá el audio al headset"         → SetDefaultDevice("headset")
"¿Cuánto está el volumen?"         → GetMasterVolume()
```

**Archivos a crear:**
```
modulos/skills/control_audio/
├── SKILL.md
├── instructions.md
├── ejemplos.md
└── audio_control.py       ← funciones reales con pycaw
```

**Notas de implementación:**  
`pycaw` expone la API `IAudioEndpointVolume` de Windows. Para volumen por app usar `ISimpleAudioVolume`. El cambio de dispositivo de salida requiere `IPolicyConfig` que no está en la API oficial — hay que usar un wrapper como `AudioDeviceCmdlets` o hacerlo via PowerShell.

---

#### ⏰ `recordatorios` — Prioridad: ALTA
**¿Qué hace?**  
Programar recordatorios temporales con notificación de Windows y voz. "Recordame en 30 minutos que tengo que tomar agua", "Avisame a las 22hs".

**¿Por qué es prioritaria?**  
El caso de uso más natural de un asistente. Complementa perfectamente el control por voz — manos libres para programar alertas.

**Palabras clave de activación:**  
`recordame`, `recordatorio`, `avisame`, `alarma`, `en X minutos`, `a las`, `despertame`, `timer`, `temporizador`

**Dependencias:**  
- `threading.Timer` (stdlib, sin instalación)  
- `win10toast` o `plyer` (notificaciones de Windows)
- Edge TTS (ya disponible en Argus)

**Comandos que debe entender Argus:**
```
"Recordame en 20 minutos cerrar el juego"
"Poné una alarma a las 23:30"
"Avisame en 1 hora"
"¿Qué recordatorios tengo?"
"Cancelá el recordatorio del juego"
```

**Comportamiento:**
1. Argus parsea tiempo (relativo o absoluto) y el mensaje.
2. Inicia un `threading.Timer` con el delta calculado.
3. Al dispararse: notificación de Windows + voz de Edge TTS.
4. Lista activa guardada en memoria volátil (se pierde al cerrar Argus — aceptable por ahora).

**Archivos a crear:**
```
modulos/skills/recordatorios/
├── SKILL.md
├── instructions.md
├── ejemplos.md
└── gestor_recordatorios.py    ← clase con lista activa y cancelación
```

---

#### 🌡️ `monitor_hardware` — Prioridad: ALTA
**¿Qué hace?**  
Temperatura real de CPU (no solo carga %), frecuencia de CPU/GPU, velocidad de ventiladores, TDP, y comparativa con límites seguros.

**¿Por qué es prioritaria?**  
Resuelve directamente el problema diagnosticado hoy: `psutil` no lee temperaturas de CPU en Windows. Se necesita LibreHardwareMonitor como fuente de datos.

**Palabras clave de activación:**  
`temperatura`, `temp`, `cpu`, `gpu`, `calor`, `ventilador`, `fan`, `frecuencia`, `overclock`, `throttling`, `hardware`

**Dependencias:**  
- LibreHardwareMonitor corriendo como servicio (o proceso)  
- `wmi` Python package  
- O alternativamente: OpenHardwareMonitor + WMI bridge

**Arquitectura recomendada:**
```
LibreHardwareMonitor (proceso externo, corre siempre)
    ↓ expone namespace WMI: root\LibreHardwareMonitor
modulos/skills/monitor_hardware/hardware_reader.py
    ↓ lee sensores via wmi.WMI(namespace="root\LibreHardwareMonitor")
Argus responde con datos reales
```

**Datos que va a poder reportar:**
```
CPU Temp:     Núcleo 1-6 individualmente + promedio
CPU Freq:     Frecuencia actual vs máxima (detecta throttling)
GPU Temp:     Temperatura GPU (redundante con nvidia-smi, pero unificado)
GPU Freq:     Frecuencia de memoria y shader
Fans:         RPM de cada ventilador detectado
RAM:          Uso real + velocidad
```

**Notas de implementación:**  
LibreHardwareMonitor debe iniciarse con permisos de administrador. Se puede agregar al arranque de Argus con `subprocess.Popen` o instrucciones para el usuario de ponerlo en el inicio de Windows.

---

### Tier 2 — Productividad real

---

#### 🎮 `steam_integration` — Prioridad: MEDIA
**¿Qué hace?**  
Consultar biblioteca de Steam: horas jugadas, logros, juegos instalados, actualizaciones pendientes, amigos online, estado del servidor de un juego.

**¿Por qué vale la pena?**  
Dado el perfil de uso (SF6, juegos en Steam), es una skill altamente personalizada. "¿Cuántas horas tengo en SF6?", "¿Está caído el servidor de Street Fighter?" son preguntas frecuentes.

**Palabras clave de activación:**  
`steam`, `juego`, `horas`, `logros`, `logro`, `biblioteca`, `jugué`, `mis juegos`, `actualización de juego`

**Dependencias:**  
- Steam Web API (API Key gratuita en steamcommunity.com/dev/apikey)  
- `requests` (ya disponible)  
- SteamID del usuario (configurar en `.env`)

**Endpoints clave de Steam API:**
```
GetOwnedGames       → biblioteca completa + horas
GetPlayerAchievements → logros por juego
GetPlayerSummaries  → estado del usuario
GetNewsForApp       → noticias/parches de un juego
```

**Archivos a crear:**
```
modulos/skills/steam_integration/
├── SKILL.md
├── instructions.md
├── ejemplos.md
└── steam_api.py       ← wrapper de Steam Web API
```

---

#### 🌤️ `clima_tiempo` — Prioridad: MEDIA
**¿Qué hace?**  
Consultar clima actual y pronóstico para cualquier ciudad. Sin API key — usa `wttr.in` que es público y gratuito.

**Palabras clave de activación:**  
`clima`, `tiempo`, `temperatura afuera`, `lluvia`, `pronóstico`, `va a llover`, `calor afuera`, `frio`

**Dependencias:**  
- `requests` (ya disponible)  
- `wttr.in` (servicio público, sin API key)

**Implementación:**
```python
import requests
def obtener_clima(ciudad="San Martín, Buenos Aires"):
    r = requests.get(f"https://wttr.in/{ciudad}?format=j1")
    data = r.json()
    # Parsear temp_C, weatherDesc, humidity, windspeedKmph
```

**Archivos a crear:**
```
modulos/skills/clima_tiempo/
├── SKILL.md
├── instructions.md
├── ejemplos.md
└── clima.py
```

---

#### 📋 `portapapeles_inteligente` — Prioridad: MEDIA
**¿Qué hace?**  
Historial de los últimos N textos copiados, búsqueda en historial, guardado nombrado de clips ("guardá esto como 'API key'").

**Palabras clave de activación:**  
`portapapeles`, `copié`, `clipboard`, `pegá`, `guardá este texto`, `tenía copiado`

**Dependencias:**  
- `pyperclip` (leer/escribir portapapeles)  
- `pywin32` (ya disponible, para hook de eventos de portapapeles)

**Archivos a crear:**
```
modulos/skills/portapapeles_inteligente/
├── SKILL.md
├── instructions.md
├── ejemplos.md
└── clipboard_manager.py
```

---

### Tier 3 — Capacidades avanzadas

---

#### 📺 `resumen_contenido` — Prioridad: BAJA-MEDIA
**¿Qué hace?**  
Resumir artículos web o transcripciones de YouTube a partir de una URL. "Resumime este video", "¿De qué trata este artículo?"

**Dependencias:**  
- `yt-dlp` (transcripciones de YouTube)  
- `trafilatura` (extracción de texto de artículos web)  
- DeepSeek Reasoner (ya disponible, para resúmenes largos)

**Palabras clave de activación:**  
`resumí`, `resumen`, `de qué trata`, `qué dice`, `video`, URL en la consulta

---

#### 🌐 `traductor` — Prioridad: BAJA
**¿Qué hace?**  
Traducción rápida de texto o frases sin salir de Argus. "Traducí esto al inglés", "Cómo se dice X en japonés".

**Dependencias:**  
- `deep-translator` (Google Translate sin API key)  
- O llamada directa a DeepSeek con prompt de traducción (sin dependencia externa)

**Palabras clave de activación:**  
`traducí`, `traducir`, `en inglés`, `en japonés`, `cómo se dice`, `qué significa en`

---

#### 💻 `monitor_procesos` — Prioridad: BAJA-MEDIA
**¿Qué hace?**  
Listar procesos que más consumen CPU/RAM, matar procesos específicos, detectar procesos sospechosos.

**Dependencias:**  
- `psutil` (ya disponible)

**Palabras clave de activación:**  
`qué está consumiendo`, `proceso`, `lento`, `qué está usando la RAM`, `matar proceso`

---

## Mejoras a funcionalidades existentes

Además de skills nuevas, hay mejoras concretas a lo ya implementado:

### 🔧 Confirmaciones GUI (reemplazar juez IA)
**Estado:** Pendiente  
**Descripción:** Reemplazar el mecanismo actual donde Gemini evalúa si el usuario dijo "sí" por un popup `CTkDialog` nativo en la GUI. Aplica a: borrados de archivos, push a GitHub, comandos git libres.  
**Beneficio:** Más rápido, sin consumo de tokens, sin riesgo de que la IA malinterprete.

### 🔧 Migración a `google.genai` (nuevo SDK)
**Estado:** Urgente — el SDK actual `google.generativeai` está deprecado  
**Descripción:** Migrar `ia.py` de `google.generativeai` a `google.genai`. La API cambia principalmente en cómo se inicializa el cliente y se pasan las herramientas.  
**Referencia:** https://github.com/google-gemini/deprecated-generative-ai-python

### 🔧 Detección de skills por embeddings
**Estado:** Planificado  
**Descripción:** Reemplazar la detección por palabras clave hardcodeadas en `gestor_skills.py` por comparación de embeddings semánticos. Usar el modelo `all-MiniLM-L6-v2` que ya está cargado por ChromaDB.  
**Beneficio:** Detecta skills aunque el usuario use sinónimos o frases no previstas.

### 🔧 Unificar estado global
**Estado:** Deuda técnica  
**Descripción:** Eliminar `_AppState` en `main_gui.py` y usar solo `config.EstadoGlobal` con locks. Evita race conditions en contextos multi-thread.

### 🔧 Inicio de LibreHardwareMonitor automático
**Estado:** Depende de skill `monitor_hardware`  
**Descripción:** Al iniciar Argus, verificar si LibreHardwareMonitor está corriendo. Si no, lanzarlo en segundo plano automáticamente.

---

## Tabla resumen de prioridades

| Skill / Mejora | Tipo | Prioridad | Esfuerzo | Dependencias externas |
|---|---|---|---|---|
| `control_audio` | Nueva skill | 🔴 Alta | Medio | pycaw |
| `recordatorios` | Nueva skill | 🔴 Alta | Bajo | plyer / win10toast |
| `monitor_hardware` | Nueva skill | 🔴 Alta | Medio-Alto | LibreHardwareMonitor + wmi |
| Migración `google.genai` | Mejora | 🔴 Alta | Bajo | — |
| Confirmaciones GUI | Mejora | 🟡 Media | Bajo | — |
| `steam_integration` | Nueva skill | 🟡 Media | Medio | Steam Web API key |
| `clima_tiempo` | Nueva skill | 🟡 Media | Bajo | — (wttr.in público) |
| `portapapeles_inteligente` | Nueva skill | 🟡 Media | Bajo | pyperclip |
| Detección skills por embeddings | Mejora | 🟡 Media | Medio | — (MiniLM ya cargado) |
| `resumen_contenido` | Nueva skill | 🟢 Baja | Alto | yt-dlp, trafilatura |
| `monitor_procesos` | Nueva skill | 🟢 Baja | Bajo | — (psutil ya instalado) |
| `traductor` | Nueva skill | 🟢 Baja | Bajo | deep-translator |
| Unificar estado global | Mejora | 🟢 Baja | Medio | — |

---

## Orden de implementación sugerido

```
Fase 1 (esta semana):
  ① Migración google.genai           ← urgente, SDK deprecado
  ② control_audio                    ← impacto diario inmediato
  ③ recordatorios                    ← impacto diario inmediato

Fase 2 (próximas semanas):
  ④ monitor_hardware + LibreHW       ← resuelve el problema de temperatura CPU
  ⑤ Confirmaciones GUI               ← seguridad y velocidad
  ⑥ clima_tiempo                     ← rápido de implementar, muy útil

Fase 3 (un mes):
  ⑦ steam_integration
  ⑧ portapapeles_inteligente
  ⑨ Detección skills por embeddings

Fase 4 (futuro):
  ⑩ resumen_contenido
  ⑪ monitor_procesos
  ⑫ traductor
  ⑬ Unificar estado global
```

---

*Documento generado en sesión de desarrollo — Argus v0.3.0*  
*Próxima revisión sugerida: después de implementar Fase 1*