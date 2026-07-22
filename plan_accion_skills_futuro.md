# ARGUS — Roadmap de Skills y Funcionalidades
**Última actualización:** 2026-07-22  
**Estado del proyecto:** v0.4.0 — Web HUD (PyWebView), Modos Win32, Gamepad XInput y Skill de Control de Audio activas.

---

## Cómo funciona el sistema de Skills

Cada skill vive en `modulos/skills/<nombre_skill>/` y contiene tres archivos principales:

| Archivo | Propósito |
|---|---|
| `SKILL.md` | Metadatos: descripción, cuándo activarse, versión, autor. |
| `instructions.md` | Las instrucciones exactas que se inyectan en el prompt de Argus cuando la skill se activa. |
| `ejemplos.md` | Casos de uso concretos para ilustrar el comportamiento esperado. |

El `gestor_skills.py` detecta si una skill es relevante para la consulta del usuario (por palabras clave) y la inyecta automáticamente en el contexto. Las skills activas sin MCP adaptan las herramientas para forzar el flujo correcto.

---

## Skills implementadas

### ✅ `busqueda_web_actualizada` — v1.0
**Estado:** Operativa.  
**Función:** Búsqueda en DuckDuckGo priorizando resultados recientes. Incluye retry automático y limpieza de filtros incompatibles.  
**Activa cuando:** El usuario usa palabras como "hoy", "actual", "noticias", "precio", "lanzamiento", año actual, etc.  
**Pendiente:** Detección de relevancia por embeddings en vez de palabras clave hardcodeadas.

### ✅ `control_audio` — v1.0
**Estado:** Operativa.  
**Función:** Control completo del sistema de audio en Windows: volumen maestro, volumen por aplicación (Discord, Spotify, navegador, juegos), mute/unmute y detección de aplicaciones con audio activo.  
**Activa cuando:** El usuario menciona palabras como `volumen`, `subir`, `bajar`, `silenciar`, `mutear`, `audio`, `sonido`, `headset`, `parlantes`, `auriculares`, `salida de audio`.  
**Dependencias:** `pycaw`, `comtypes`.  
**Ubicación:** `modulos/skills/control_audio/` (`audio_control.py`).

---

## Skills planificadas

### Tier 1 — Impacto diario inmediato

---

#### ⏰ `recordatorios` — Prioridad: ALTA
**¿Qué hace?**  
Programar recordatorios temporales con notificación de Windows y voz. "Recordame en 30 minutos que tengo que tomar agua", "Avisame a las 22hs".

**¿Por qué es prioritaria?**  
Es uno de los casos de uso más naturales de un asistente de voz. Manos libres para programar alertas durante sesiones de trabajo o juegos.

**Palabras clave de activación:**  
`recordame`, `recordatorio`, `avisame`, `alarma`, `en X minutos`, `a las`, `despertame`, `timer`, `temporizador`

**Dependencias:**  
- `threading.Timer` (stdlib, sin instalación extra)  
- `win10toast` o `plyer` (notificaciones de Windows)
- Edge TTS (ya disponible en Argus)

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
Temperatura real de CPU (no solo carga %), frecuencia de CPU/GPU, velocidad de ventiladores, TDP y comparativa con límites seguros.

**¿Por qué es prioritaria?**  
`psutil` estándar no lee temperaturas de CPU en Windows. Se necesita LibreHardwareMonitor como fuente de datos real.

**Palabras clave de activación:**  
`temperatura`, `temp`, `cpu`, `gpu`, `calor`, `ventilador`, `fan`, `frecuencia`, `overclock`, `throttling`, `hardware`

**Dependencias:**  
- LibreHardwareMonitor corriendo como servicio o proceso en segundo plano  
- `wmi` (paquete de Python)

**Arquitectura recomendada:**
```
LibreHardwareMonitor (proceso externo)
    ↓ expone namespace WMI: root\LibreHardwareMonitor
modulos/skills/monitor_hardware/hardware_reader.py
    ↓ lee sensores via wmi.WMI(namespace="root\LibreHardwareMonitor")
Argus responde con datos de sensores reales
```

---

### Tier 2 — Productividad y entretenimiento

---

#### 🎮 `steam_integration` — Prioridad: MEDIA
**¿Qué hace?**  
Consultar biblioteca de Steam: horas jugadas, logros, juegos instalados, actualizaciones pendientes y noticias de parches.

**Palabras clave de activación:**  
`steam`, `juego`, `horas`, `logros`, `logro`, `biblioteca`, `jugué`, `mis juegos`, `actualización de juego`

**Dependencias:**  
- Steam Web API Key  
- `requests` (ya disponible)

---

#### 🌤️ `clima_tiempo` — Prioridad: MEDIA
**¿Qué hace?**  
Consultar clima actual y pronóstico para cualquier ciudad usando `wttr.in` (servicio público gratuito sin API key).

**Palabras clave de activación:**  
`clima`, `tiempo`, `temperatura afuera`, `lluvia`, `pronóstico`, `va a llover`

---

#### 📋 `portapapeles_inteligente` — Prioridad: MEDIA
**¿Qué hace?**  
Historial de los últimos textos copiados, búsqueda en historial y guardado nombrado de clips.

**Palabras clave de activación:**  
`portapapeles`, `copié`, `clipboard`, `pegá`, `guardá este texto`

---

### Tier 3 — Capacidades avanzadas

---

#### 📺 `resumen_contenido` — Prioridad: BAJA-MEDIA
**¿Qué hace?**  
Resumir artículos web o transcripciones de YouTube a partir de una URL (`yt-dlp` + `trafilatura`).

#### 🌐 `traductor` — Prioridad: BAJA
**¿Qué hace?**  
Traducción rápida de frases o fragmentos de código contextuales.

#### 💻 `monitor_procesos` — Prioridad: BAJA-MEDIA
**¿Qué hace?**  
Listar procesos que más consumen CPU/RAM y opción de finalizar procesos colgados (`psutil`).

---

## Mejoras a funcionalidades existentes

### 🔧 Confirmaciones GUI (reemplazar juez IA)
**Estado:** Pendiente  
**Descripción:** Reemplazar el mecanismo donde la IA interpreta confirmaciones por diálogos modales nativos (`CTkDialog` o popups Web). Aplica a borrado de archivos, Git push/reset y comandos críticos.  
**Beneficio:** Latencia cero, cero gasto de tokens y seguridad total.

### 🔧 Detección de skills por embeddings
**Estado:** Planificado  
**Descripción:** Reemplazar la detección por palabras clave hardcodeadas en `gestor_skills.py` por comparación de similitud coseno de embeddings usando el modelo `all-MiniLM-L6-v2` ya cargado en memoria por ChromaDB.

### 🔧 Coincidencia de palabras exactas en confirmaciones locales
**Estado:** Pendiente  
**Descripción:** Ajustar `_evaluar_confirmacion_local()` usando expresiones regulares `\b` para evitar falsos positivos por subcadenas (ej. "no sé" vs "sí").

---

## Tabla resumen de prioridades

| Skill / Mejora | Tipo | Prioridad | Estado | Dependencias externas |
|---|---|---|---|---|
| `busqueda_web_actualizada` | Skill | 🔴 Alta | ✅ Operativa (v1.0) | — |
| `control_audio` | Skill | 🔴 Alta | ✅ Operativa (v1.0) | pycaw |
| Migración `google-genai` | Mejora | 🔴 Alta | ✅ Completado | google-genai |
| Web HUD PyWebView | Mejora | 🔴 Alta | ✅ Completado | pywebview |
| Modos Win32 (WorkerW) | Mejora | 🔴 Alta | ✅ Completado | ctypes Win32 |
| `recordatorios` | Skill | 🔴 Alta | 🔄 Pendiente | plyer / win10toast |
| `monitor_hardware` | Skill | 🔴 Alta | 🔄 Pendiente | LibreHardwareMonitor + wmi |
| Confirmaciones GUI | Mejora | 🟡 Media | 🔄 Pendiente | — |
| Detección por embeddings | Mejora | 🟡 Media | 🔄 Pendiente | — (MiniLM ya en RAM) |
| `clima_tiempo` | Skill | 🟡 Media | 🔄 Pendiente | wttr.in |
| `steam_integration` | Skill | 🟡 Media | 🔄 Pendiente | Steam Web API |
| `portapapeles_inteligente` | Skill | 🟡 Media | 🔄 Pendiente | pyperclip |
| `resumen_contenido` | Skill | 🟢 Baja | 🔄 Pendiente | yt-dlp, trafilatura |
| `monitor_procesos` | Skill | 🟢 Baja | 🔄 Pendiente | psutil |

---

## Orden de implementación sugerido (Próximas etapas)

```
Fase Actual (Completada):
  ✅ Migración a google-genai (SDK oficial)
  ✅ Web HUD PyWebView + Edge Chromium
  ✅ Skill control_audio (pycaw)
  ✅ Modos de visualización Win32 (WorkerW Wallpaper Mode)
  ✅ Gamepad subproceso + fallback XInput

Próxima Fase (Fase 1):
  ① recordatorios                    ← fácil implementación, alto impacto
  ② monitor_hardware + LibreHW       ← monitoreo real de CPU/GPU
  ③ Confirmaciones GUI (Modales)     ← cero tokens para confirmaciones

Fase 2 (Próximas semanas):
  ④ Detección de skills por embeddings
  ⑤ clima_tiempo (wttr.in)
  ⑥ portapapeles_inteligente

Fase 3 (Futuro):
  ⑦ steam_integration
  ⑧ resumen_contenido
  ⑨ monitor_procesos
```

---

*Documento actualizado según el estado real del repositorio — Argus v0.4.0*