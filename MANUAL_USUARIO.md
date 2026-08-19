# Manual de usuario — Argus

Tu asistente IA de escritorio para Windows. Hablale, escribile, jugá con él: Argus maneja tu PC, guarda memoria, busca en internet con fuentes, te da mentoría, y te acompaña mientras jugás.

> Todo lo que dice y hace Argus es en español. Podés hablarlo por micrófono o escribirle.

---

## 1. Lo esencial en 30 segundos

| Acción | Cómo |
|---|---|
| Escribirle | Escribí abajo y presioná **Enter** (Shift+Enter = salto de línea) |
| Hablarle por teclado | Mantené presionado **F8**, hablá, y soltá cuando termines |
| Hablarle con el mando | Mantené **L3 + R3** (clic de ambos joysticks), hablá y soltá |
| Cortar la grabación | Soltá la tecla, esperá 2,5 s de silencio, o decí **"procede"** |
| Cortar la voz de Argus | Presioná **Esc**, o decí **"corta"** |
| Activar wake word | Botón 🎙️ junto al campo de texto, y después decí **"OK Argus"** |
| Que mire tu pantalla | "Mirá la pantalla" / "fijate qué ves" / "capturá la pantalla" |

---

## 2. La pantalla principal

La ventana de Argus tiene tres zonas:

- **Barra lateral (izquierda):** el avatar/rostro EMO, las tres capacidades (General, Mentoría, Gaming), el tema de mentoría activo, el workspace, la memoria y la sección de gaming/mandos.
- **Header (arriba):** el título del modo, los chips de capacidad activa y tema, el clima, el reloj y los botones de acción (⏰ recordatorios, 🧠 actualizar memoria, ↩️ retomar historial, 🔄 limpiar contexto, 🗑️ limpiar pantalla).
- **Chat (centro):** la conversación con Argus, el campo de entrada, el selector de modelo y el botón de micrófono (wake word).

### El chip de capacidad (💬 / 🎓 / 🎮)
Muestra qué capacidad está activa en el turno actual. **Clic en el chip = fijarla (pin 📌)**; vuelve a hacer clic para volver a automático (⚡). Cuando está fijada, Argus responde siempre con esa capacidad, sin importar lo que escribas.

### El chip de tema (🎯)
En turnos de mentoría muestra el tema activo. Se cambia desde el selector de la barra lateral.

### Botones del header

| Botón | Qué hace |
|---|---|
| ⏰ Recordatorios | Abre el panel de recordatorios (pendientes, completados, nuevo) |
| 🧠 Actualizar memoria | Extrae los datos de la conversación actual y los guarda en tu perfil |
| ↩️ Retomar historial | Recupera la última conversación guardada y la muestra en el chat |
| 🔄 Limpiar contexto | Reinicia el contexto de IA (borra lo que Argus "recuerda" de esta charla) |
| 🗑️ Limpiar pantalla | Borra solo lo visible en pantalla (no toca la memoria de Argus) |

---

## 3. Cómo hablar con Argus

### Por texto
Escribí el mensaje y presioná Enter. Shift+Enter agrega un salto de línea.

### Por voz (F8)
1. Mantené presionado **F8** (un pitido confirma que el micrófono está activo).
2. Hablá con naturalidad.
3. Soltá F8 para terminar. Argus transcribe con Whisper y responde por voz si le hablaste por voz.

**Consejos:**
- La grabación también termina sola si hacés una pausa de 2,5 segundos, o si decís **"procede"** (configurable con `PALABRA_CORTE_VOZ` en el `.env`).
- Máximo de seguridad: 180 segundos seguidos.
- Funciona incluso con juegos en pantalla completa.

### Con el mando (L3 + R3)
Idéntico a F8 pero con el gamepad (Xbox o DualSense). Ideal para jugar sin soltar el control. Mantené L3 y R3 juntos para hablar, soltá para enviar.

### Wake word "OK Argus" (sin tocar nada)
1. Activá el wake word con el botón 🎙️ (queda iluminado con un anillo de pulso).
2. Decí **"OK Argus"** (también entiende "ok argos", "okey argus", etc.).
3. Escuchá el pitido y decí directamente tu pedido.

Es gratuito y funciona sin internet (Vosk, modelo de español que se descarga automáticamente la primera vez).

### Cómo cortar la voz de Argus
- Presioná **Esc**.
- O decí **"corta"** (si el wake word está activo).

### Escuchar una respuesta puntual
Cada mensaje de Argus tiene un botón **🔊 Escuchar** que reproduce ese texto con voz (Edge TTS, sin gastar tokens).

---

## 4. Las tres capacidades

Argus tiene tres personalidades o *capacidades*, y las activa **automáticamente según lo que escribís** (o las elegís vos desde la barra lateral).

### 💬 General
El asistente de todos los días: responde preguntas, maneja tu PC, crea archivos, busca en internet. Conocé su capacidad multimodal (mira tu pantalla, lee archivos, ve imágenes).

### 🎓 Mentoría
Argus se vuelve tu guía didáctico. Explica conceptos, te arma caminos de aprendizaje, hace coaching de entrevistas y lleva **un registro de temas con su propio progreso** (ver sección 5).

**Frases que activan mentoría sola:**
- "ayudame a preparar la entrevista técnica de React"
- "qué roadmap me recomendás para backend"
- "retomemos la bitácora de desarrollo"

### 🎮 Gaming
Argus asume que estás jugando: respuestas **ultra cortas**, detecta automáticamente el juego activo por la ventana, te da builds, guías y frame data, y te alerta si el hardware se está exigiendo (CPU > 90 %, RAM > 85 %, GPU > 85 °C). En este modo se libera VRAM de Whisper para no degradar el juego.

**Frases que activan gaming sola:**
- "qué build le conviene a mi personaje"
- "cómo le gano al jefe final"
- "estoy jugando la partida"

> **Pin de capacidad:** si querés forzar una capacidad, hacé clic en el chip del header (📌). Para volver al modo automático, clic de nuevo (⚡).

---

## 5. Mentoría: temas, sesiones y avance

El modelo de mentoría es **tema → sesión → avance**: cada tema que trabajes tiene su propio objetivo, progreso, dificultades, hitos y "dónde quedamos".

### Crear un tema
Decí o escribí, por ejemplo:
- **"Nuevo tema: inglés técnico"**
- **"Tema: Arduino"**
- **"Empecemos con música"**
- O desde la barra lateral: botón **＋** en "Tema activo" y completá el modal (nombre + objetivo opcional). Al crearlo queda como tema activo.

### Cambiar de tema
- Mencioná el nombre de un tema existente: "retomemos el tema de desarrollo".
- O usá el **selector de temas** de la barra lateral (solo visible en modo Mentoría).

### Cómo sigue el avance
Mientras hablás en modo Mentoría, Argus anota objetivos, próximos pasos, dificultades y hitos en el tema activo. Al cerrar la sesión (cambiar de modo o cerrar la app), extrae un resumen automático y guarda **"último avance"** y **"próximos pasos"**. Si hay un workspace anclado, también escribe `BITACORA_MENTOR.md` en esa carpeta.

### Seguimiento visual
En el panel de memoria (🧠), la sección **"Temas de mentoría"** muestra un ítem por tema con el ⭐ en el activo, objetivos activos, hitos, "Quedamos:…" y cantidad de sesiones. Desde ahí podés **olvidar un tema completo** (🗑️) o editar datos.

### Ejemplos de uso
- "Simulame una entrevista para backend Java" → Argus toma el rol del entrevistador, pregunta de a una y te da feedback.
- "¿Dónde quedamos?" → Argus te retoma el tema activo con tus últimos avances y próximos pasos.
- "Quiero organizar mi carrera de acá a dos años" → la detección semántica lo encamina a mentoría.

---

## 6. Búsqueda web con fuentes verificadas

Cuando tu pregunta necesita datos actuales, Argus **decide solo** buscar en internet y responde **con fuente y fecha**, distinguiendo lo confirmado de lo no confirmado.

- **Automatico:** "¿A cuánto está el dólar hoy?", "¿quién ganó la última CPT?", "¿qué series se estrenan esta semana?"
- **Evidencia con fuentes:** la respuesta muestra el dominio y la fecha de cada dato. Si un dato no se confirma (por ejemplo, el bronce de un podio), Argus dice literalmente *"No pude confirmarlo con las fuentes encontradas"* en vez de inventar.
- **Seguimiento:** podés preguntar "¿y el tercero?" y Argus entiende que seguís con el mismo tema.

### Cómo se ve en el chat
Mientras busca, la burbuja se marca **"Verificando…"** y después se reemplaza por la respuesta final con el chip **"✓ Verificado con fuentes"**. Es automático, no tenés que hacer nada.

---

## 7. Memoria: lo que Argus sabe

Argus tiene memoria a largo plazo en tu PC (una "bóveda" local, sin gastar tokens). La usa para conocerte mejor y para no repetirte.

### Cómo se guarda
- **Automático:** al cerrar la app, al cambiar de modo, o con el botón 🧠 del header, Argus analiza la conversación y guarda los hechos importantes (tu perfil, proyectos, mentoría, gaming). Los secretos (contraseñas, claves) se descartan.
- **Por chat:** "acordate que tomo rosuvastatina a las 21" → Argus pide confirmación y lo guarda.
- **Manual desde el panel 🧠:** botón **"✍️ Guardar nota"** (texto con etiqueta opcional) o **"📄 Guardar archivo en bóveda"** (indexa un PDF o archivo de texto sin gastar contexto).

### Cómo se recupera
En cada turno Argus busca en su memoria en paralelo y, si encuentra algo relevante, lo inyecta en su contexto. Por eso puede contestar "¿Qué me recetó el médico?" sin que lo repitas.

### El panel "Lo que Argus sabe"
Abrilo con el botón **🧠 Memoria** de la barra lateral. Muestra secciones: Sobre vos, Preferencias y rutina, Proyectos, Aprendizaje y carrera, **Temas de mentoría**, Gaming y Memoria.

Cada dato tiene:
- **✏️ Editar:** corrige el contenido guardado.
- **🗑️ Olvidar:** borra el dato de forma permanente (con confirmación).

### Olvidar por chat
- "olvidate de lo de netflix"
- "olvidá el proyecto viejo"

> **Importante — qué hace y qué no hace el "olvidar":** olvidar evita que el dato **vuelva a aparecer en el futuro** (la IA no lo volverá a aprender ni a recuperarlo). **No borra** la conversación actual: los mensajes viejos que mencionan el dato siguen existiendo en el historial de esta charla.

### Retomar y limpiar
- **↩️ Retomar historial:** recupera la última conversación guardada (incluso tras reiniciar Argus).
- **"¿Dónde quedamos?" / "retomá la conversación":** Argus retoma desde donde quedó.
- **"Limpiá el contexto" o 🔄:** arranca de cero la conversación actual.

---

## 8. Archivos y proyectos (workspace)

Argus puede crear, leer y editar archivos de tu PC. **En modo Mentoría o Gaming se exige un workspace anclado** (carpeta de trabajo). En modo General se permite con una advertencia si salís de la carpeta de trabajo.

### Anclar un workspace
Clic en **📁 Workspace** de la barra lateral y elegí la carpeta del proyecto. Argus la ancla, carga su estado y vigila los cambios (Radar): si modificás un archivo que tiene en memoria, lo relee automáticamente.

### Comandos de archivo (escribilos o decilos)

| Comando | Ejemplo |
|---|---|
| `guardar_archivo: ruta ---CONTENIDO--- texto` | "guardá unas notas en el escritorio" |
| `leer_archivo: ruta` | "leé el archivo config.json" |
| `editar_archivo: ruta \| buscar: X \| reemplazar: Y` | "cambiá el título del index.html" |
| `reemplazar_bloque: ruta ---BUSCAR--- X ---REEMPLAZAR--- Y ---FIN---` | "actualizá la función de login" |
| `crear_carpeta: ruta` | "creá la carpeta proyectos" |
| `mcp_explorar_ruta: ruta` | "¿qué hay en el escritorio?" |
| `snapshot: resumen` | "guardá el estado del proyecto" |
| `escanear_proyecto:` | "escaneá el proyecto" (genera `PROJECT_STATE.md` con la arquitectura) |

### Adjuntar archivos
Botón **＋** junto al campo de texto → **📄 Adjuntar archivo** (o **🖼️ Adjuntar imagen**). Los adjuntos se agregan como etiquetas sobre el input y Argus los lee/analiza. Ejemplo: adjuntar `app.js` y preguntar "¿qué hace esta función?".

> Los archivos de hasta 10 MB, contenido hasta 10 MB, PDF de hasta 100 páginas y scripts `.py`/`.scr` no se abren automáticamente (seguridad).

---

## 9. Controlar tu PC con voz o texto

### Abrir y navegar
- **"abrí Discord"**, "abrí Chrome", "abrí Minecraft", "abrí la carpeta de descargas".
- **"navegar: youtube"**, "navegar: github". Para un monitor puntual: "navegar: youtube @ 2".
- **"cerrá Discord"**, **"mové Brave al monitor 2"** (`mover: brave @ 2`).
- **"¿qué hay en el escritorio?"** → Argus lista el contenido sin abrir ventanas.

### Estado y hardware del PC
- "¿cómo está la PC?" → CPU (carga), RAM, temperatura de GPU y VRAM en vivo.
- "¿qué componentes tiene mi PC?" → modelo exacto de CPU, GPU y placa madre.
- "apagá la PC" → programa el apagado en 30 minutos. "cancelá el apagado" lo cancela.

> **Honestidad del hardware:** Argus reporta la carga de CPU (no "temperatura" si no tiene sensor) y solo da la temperatura de GPU cuando el dato viene de una fuente real.

### Mover y controlar la propia ventana de Argus
- "Argus, movete a la pantalla 2" (la maximiza en ese monitor, siempre encima).
- "Argus, maximizate" / "minimizate" / "vení al frente".

---

## 10. Vision: Argus mira tu pantalla

Decile frases como:
- "mirá la pantalla"
- "fijate qué ves"
- "capturá la pantalla" → toma todos los monitores
- "capturá la pantalla 2" → un monitor puntual
- En modo Gaming: "compará estos objetos" (analiza lo que ve en el juego)

Argus toma una captura, la analiza con visión y responde **basándose en lo que ve**: "te quedan 3 de 4 corazones", "ese es un error de sintaxis en la línea 12", "ese objeto tiene mejor DPS".

---

## 11. Audio: controlá el sonido

Argus controla el volumen de Windows:

| Pedido | Qué hace |
|---|---|
| "¿cuánto está el volumen?" | Muestra el volumen actual |
| "subí el volumen" / "bajá el volumen" | ±10 % (podés decir cuánto) |
| "ponelo al 80" / "a tope" / "al mínimo" | Fija el volumen exacto |
| "silenciá" / "desmuteá" | Silencia / reactiva |
| "¿cuánto está el volumen de Discord?" | Volumen de una app puntual |
| "silenciá Discord" | Silencia solo esa app |
| "¿qué apps tienen audio?" | Lista los procesos con audio |
| "pasá el audio al headset" | Cambia el dispositivo de salida |

> Si decís "el juego" o "la música" sin nombre exacto, Argus primero lista las apps con audio y recién después actúa.

---

## 12. Recordatorios y alarmas

Creá recordatorios por chat o desde el botón **⏰** del header (panel con pestañas: Pendientes, Completados, Nuevo).

**Ejemplos por chat:**
- "recordame tomar la medicina a las 21:00 todos los días" → diario
- "avisame en 15 minutos" → relativo
- "recordame el 25 de agosto que sale X" → avisa el primer mensaje de ese día
- "recordame el cumpleaños de Yuskeli, 6 de diciembre" → aviso el día anterior y el mismo día
- "¿qué recordatorios tengo?" → lista
- "cancelá el recordatorio del agua" → cancela

Cuando un recordatorio dispara, aparece una **nube animada** sobre el rostro de Argus y se anuncia por voz. El panel ⏰ permite **editar**, **marcar completado**, **reactivar** y **eliminar**.

---

## 13. Git / GitHub (sincronizar proyectos)

- **"Subí los cambios"** / "sincronizar proyecto" → Argus hace init → add → commit → pull → push del workspace (con confirmación SÍ/NO).
- **"subí esto a un repo nuevo"** → desvincula el remoto y sube con la URL nueva.
- **"git status"** → ejecuta comandos git libres sobre el workspace.

> Necesitás `GITHUB_TOKEN` en el `.env` para las operaciones de GitHub.

---

## 14. Clima

Argus conoce el clima de tu ciudad (configurable con `CIUDAD_CLIMA` en el `.env`):

- **Widget en el header:** temperatura, condición, humedad, viento, amanecer/atardecer.
- **En el chat:** "¿hace frío hoy para salir?" → responde sin buscar en internet (caché de 10 minutos).

---

## 15. Modelos de IA

En el selector junto al campo de texto podés cambiar el modelo en cualquier momento:

- **Auto (Por Defecto)** → usa tu preferencia global (por defecto **Gemini 3.5 Flash Lite**).
- **Gemini:** Flash Lite 3.5 / Flash Lite 3.1 / Flash 3.6 / Pro 3.1.
- **DeepSeek Reasoner.**
- **Groq:** Llama 3.3 70B / Llama 3.1 8B / Qwen 3.6 27B / GPT-OSS 120B.

**Fallbacks automáticos:** si el modelo elegido está saturado (errores 503/429), Argus prueba primero un modelo de reserva y, si sigue fallando, cae a DeepSeek. No perdés el turno. El chip **🧩 MCP ✓/✗** del header indica si las herramientas de sistema están activas (solo con modelo Gemini y sin skill activa en el turno).

> Nota: sin `GEMINI_API_KEY` la app arranca igual y te avisa amablemente que falta configurar la clave. Las claves opcionales (`DEEPSEEK_API_KEY`, `GROQ_API_KEY`, `GITHUB_TOKEN`) habilitan los modelos correspondientes.

---

## 16. Gamepad y modo Gaming

### Detectá y elegí el mando
- En la barra lateral (sección Gaming) se muestra el estado ("Sin mando detectado" o el nombre del mando).
- **🔄 Re-escanear mandos:** fuerza la detección.
- **Selector de mandos:** elegí el mando activo o "Todos los mandos".
- Soporta Xbox (XInput nativo, funciona incluso si el juego capturó el mando) y DualSense/PS5 (Pygame).

### El perfil gamer
Argus guarda por juego: personaje, nivel, build, dificultad, objetivo, estrategia y progreso. Se alimenta solo (al cerrar la app o cambiar de modo). Por eso en modo Gaming sabe quién es tu personaje sin que se lo repitas:

- "¿qué build me conviene para este jefe?" → responde con tu personaje y build actuales.

### Diagnóstico del mando
`mapeo_control_prueba.py` muestra el nombre del mando y el índice exacto de L3/R3 si necesitás verificar el mapeo.

---

## 17. El avatar EMO y las emociones

Argus tiene un rostro animado que **refleja emociones** según la respuesta ([EMOTION: happy/sad/angry/thinking]). Podés:

- Alternar entre el **avatar robot** (🤖) y el **holograma** (🔮) arriba del sidebar.
- **Acariciar al robot:** hacé clic en su cabeza → reacciona feliz con un beep.
- Ver su **estado** bajo el avatar: REPOSO, escuchando, pensando, hablando, error.

---

## 18. Seguridad y confirmaciones

Ante acciones sensibles Argus **pide confirmación y evalúa tu respuesta** (sin IA):

- Borrar archivos o carpetas.
- Subir (push) a GitHub o ejecutar comandos git.
- Guardar datos en la bóveda.

**Confirmás** con: "sí", "dale", "ok", "confirmo", "adelante". **Cancelás** con: "no", "cancelar", "pará", "olvidalo".

Además:
- En modo Mentoría/Gaming solo modifica archivos dentro del workspace.
- Los scripts no se ejecutan automáticamente.
- Los secretos no se guardan en la memoria.

---

## 19. Configuración avanzada (archivo `.env`)

En la raíz del proyecto, el archivo `.env` ajusta el comportamiento:

| Variable | Para qué sirve | Default |
|---|---|---|
| `GEMINI_API_KEY` | Clave de Gemini (la única imprescindible) | — |
| `DEEPSEEK_API_KEY` | Fallback y modelo DeepSeek | — |
| `GROQ_API_KEY` | Modelos Groq | — |
| `GITHUB_TOKEN` | Operaciones de GitHub | — |
| `WHISPER_MODEL_SIZE` | Tamaño del transcritor de voz (más grande = más preciso) | `medium` |
| `WHISPER_DEVICE` / `WHISPER_COMPUTE_TYPE` | Aceleración (GPU `cuda`/`float16` o CPU `int8`) | `cuda`/`float16` |
| `PALABRA_CORTE_VOZ` | Palabra que corta la grabación | `procede` |
| `RMS_UMBRAL_VOZ` | Sensibilidad del micrófono (subí si capta ruido) | `150` |
| `CIUDAD_CLIMA` | Ciudad del widget de clima | San Martin, Bs. As. |
| `ARGUS_MODELO_DEFECTO` | Modelo global "Auto" | Gemini 3.5 Flash Lite |
| `ARGUS_RUTA_JUEGOS` | Carpeta extra de juegos portables para el radar | — |
| `ARGUS_ACTIVACION_CAPACIDAD_EMBEDDINGS` | Poner `0` desactiva la detección semántica de capacidades | `1` |

> **Voz de Argus:** se cambia editando `modulos/audio_custom.py` (`VOZ_ACTIVA`, por defecto `es-MX-JorgeNeural`). Cualquier voz de Edge TTS sirve (ej. `es-AR-ElenaNeural`).

---

## 20. Preguntas frecuentes

**¿Se necesita internet para todo?** No. La memoria (bóveda), el wake word y la transcripción son locales. La búsqueda web y la generación de respuestas necesitan conexión (y las claves API).

**¿Argus me guarda todo lo que digo?** Solo guarda datos relevantes y no guarda secretos. El 100 % vive en tu PC, y podés ver/editarlo/olvidarlo desde el panel 🧠.

**¿Por qué no me muestra la temperatura de la CPU?** Argus es honesto: si no hay sensor disponible, te lo dice en vez de inventar.

**Le pedí "olvidá X" pero la conversación lo sigue mostrando.** Es normal: el olvido evita que X **reaparezca en el futuro**, pero no borra el historial actual de la charla.

**Se nota lento el modelo elegido.** Cambialo desde el selector (Gemini Flash Lite es el más rápido) o esperá el fallback automático que prueba una reserva y cae a DeepSeek si hace falta.

**¿Cómo habilito más de un monitor para capturar?** "capturá la pantalla 2" captura el segundo monitor; sin número, Argus toma todos.

---

## 21. Referencia rápida de frases

| Categoría | Frase de ejemplo |
|---|---|
| PC | "abrí Discord", "cerrá Chrome", "apagá la PC", "¿cómo está la PC?" |
| Ventanas | "movete a la pantalla 2", "maximizate", "vení al frente" |
| Web | "¿a cuánto está el dólar hoy?", "¿quién ganó la última CPT?" |
| Mentoría | "nuevo tema: inglés", "retomemos la bitácora", "simulame una entrevista" |
| Gaming | "¿qué build me conviene?", "compará estos objetos", "¿cuánta vida me queda?" |
| Audio | "subí el volumen", "ponelo al 40", "silenciá Discord", "pasá el audio al headset" |
| Recordatorios | "recordame tomar la medicina a las 21 todos los días", "avisame en 15 minutos" |
| Archivos | "guardá unas notas en el escritorio", "¿qué hay en el escritorio?", "escaneá el proyecto" |
| Memoria | "acordate que tomo rosuvastatina", "olvidate de lo de netflix", "¿dónde quedamos?" |
| Visión | "mirá la pantalla", "fijate qué ves", "capturá la pantalla 2" |
| Git | "subí los cambios", "sincronizar proyecto" |
| Clima | "¿hace frío hoy para salir?" |

---

*Manual de Argus — v0.5.0 HUD. Actualizado el 14/08/2026.*
