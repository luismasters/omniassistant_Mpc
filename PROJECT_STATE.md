# PROJECT_STATE.md — OmniAssistant

## 1. Resumen Ejecutivo

OmniAssistant es un asistente de escritorio inteligente y multimodal que integra capacidades de IA conversacional (Google Gemini / DeepSeek), control del sistema operativo Windows, reconocimiento de voz, visión artificial, gestión de memoria híbrida (RAG con ChromaDB) y automatización de Git. Está diseñado para funcionar como pair programmer, planificador técnico y asistente personal, todo desde una interfaz gráfica moderna en modo oscuro con interacción por voz y texto.

El proyecto se encuentra en una etapa intermedia de desarrollo, con funcionalidades core operativas pero con varios puntos de mejora en robustez, seguridad y mantenibilidad.

---

## 2. Arquitectura

### 2.1. Diagrama de Módulos

```
OmniAssistant/
├── main_gui.py                  # Interfaz gráfica principal (CustomTkinter)
├── config.py                    # Configuración global y API keys
├── servidor_sistema_mcp.py      # Servidor MCP para herramientas del sistema
├── gestor_boveda.py             # Gestor de base de datos vectorial (CLI)
├── modulos/
│   ├── ia.py                    # Cerebro: enrutador de modelos IA
│   ├── sistema.py               # Control SO: ventanas, procesos, hardware
│   ├── audio.py                 # Captura voz (faster-whisper) + TTS
│   ├── vision.py                # Captura de pantalla
│   ├── archivos.py              # Operaciones seguras de archivos
│   ├── busqueda.py              # Búsqueda web (DuckDuckGo)
│   ├── git_bot.py               # Gestión de repositorios GitHub
│   ├── memoria.py               # Motor vectorial ChromaDB
│   ├── crawler.py               # Extracción de código de proyectos
│   ├── cliente_mcp.py           # Cliente MCP para comunicación con servidor
│   └── logger.py                # Configuración de logging
```

### 2.2. Descripción de cada módulo

| Módulo | Propósito | Estado |
|--------|-----------|--------|
| **ia.py** | Enrutador que selecciona Gemini Flash (modo general), DeepSeek V4 (planificador/programador). Gestiona contexto de chat, ejecuta herramientas MCP y acciones del sistema | Funcional, con lógica compleja y cierta duplicación |
| **sistema.py** | Control de ventanas (multimonitor), radar de programas, apertura/cierre de aplicaciones, telemetría de hardware | Funcional, con dependencias pesadas (win32gui, psutil) |
| **archivos.py** | Sandbox de archivos con validación de ruta, tamaño y espacio. Operaciones CRUD seguras | Implementado pero con supuestos de sandbox que no se usan consistentemente |
| **memoria.py** | Base vectorial ChromaDB con modelo all-MiniLM-L6-v2. Guardado/búsqueda de recuerdos + snapshots físicos | Funcional, con potencial de optimización |
| **audio.py** | Transcripción con faster-whisper (modelo medium, CUDA) y síntesis con pyttsx3 | Operativo, con consumo significativo de recursos |
| **vision.py** | Captura de pantalla multi-monitor vía PIL | Simple y funcional |
| **busqueda.py** | Búsqueda web con DuckDuckGo (ddgs) | Funcional, pero frágil (dependencia de ddgs) |
| **git_bot.py** | Sincronización con GitHub (init, add, commit, push) y comandos libres | Funcional, sin manejo de conflictos |
| **crawler.py** | Recorre proyectos, filtra archivos y devuelve código concatenado | Simple y efectivo |
| **cliente_mcp.py** | Cliente asíncrono MCP para conectar con servidor de sistema | Funcional, pero con problemas de concurrencia |
| **servidor_sistema_mcp.py** | Expone herramientas (estado PC, bóveda, exploración, lectura) vía MCP | Funcional, con silenciado agresivo de stdout/stderr |
| **main_gui.py** | Interfaz gráfica con sidebar, burbujas de chat renderizadas, input con adjuntos y voz | Extensa y funcional, con mucha lógica de interfaz en un solo archivo |
| **config.py** | Variables de entorno, límites de seguridad y constantes | Centralizado pero con MODO_PROGRAMADOR hardcodeado |
| **gestor_boveda.py** | CLI para listar, eliminar y resetear la bóveda ChromaDB | Independiente y funcional |

---

## 3. Estado Actual

### 3.1. Funcionalidades operativas

- ✅ Interfaz gráfica completa con CustomTkinter (chat, logs, sidebar con modos)
- ✅ Chat multimodal: texto + voz (tecla F8) + adjuntos de archivos
- ✅ Reconocimiento de voz con faster-whisper (modelo medium, CUDA)
- ✅ Síntesis de voz con pyttsx3 (voz femenina en español)
- ✅ Tres modos de IA: General (Gemini), Planificador (DeepSeek thinking), Programador (DeepSeek fast)
- ✅ Búsqueda en internet vía DuckDuckGo
- ✅ Captura de pantalla multi-monitor
- ✅ Control de ventanas (abrir/cerrar/mover entre monitores)
- ✅ Radar inteligente de programas y juegos
- ✅ Memoria persistente con ChromaDB (guardado y búsqueda por etiquetas)
- ✅ Integración MCP para herramientas del sistema
- ✅ Automatización Git (init, push, reset remoto)
- ✅ Sistema de seguridad con sandbox de archivos (limitado)
- ✅ Crawler de proyectos para generar PROJECT_STATE.md
- ✅ Gestor de bóveda vía consola (listar, borrar, hard reset)
- ✅ Snapshots físicos del proyecto (archivos .cortana/snapshot.json)
- ✅ Placeholder inteligente en input de chat
- ✅ Scroll automático en chat
- ✅ Resaltado de sintaxis en bloques de código (tk.Text)
- ✅ Renderizado de tablas Markdown en el chat

### 3.2. Funcionalidades parciales o con problemas conocidos

- ⚠️ **Seguridad del sandbox**: `es_ruta_segura()` solo verifica que la ruta comience con `SANDBOX_BASE`, pero muchas operaciones (sistema.py, ia.py) usan rutas fuera del sandbox (Desktop, Downloads).
- ⚠️ **Concurrencia en MCP**: El cliente MCP usa `asyncio.run()` dentro de hilos, lo que puede causar conflictos si hay múltiples llamadas simultáneas.
- ⚠️ **Gestión de errores en IA**: El interceptor de acciones usa heurísticas frágiles (búsqueda de keywords en texto plano).
- ⚠️ **Consumo de VRAM**: Whisper medium con float16 puede consumir ~2-3GB de VRAM, compitiendo con otros procesos.
- ⚠️ **Dependencia de ddgs**: La librería DuckDuckGo no oficial puede dejar de funcionar sin previo aviso.

---

## 4. Deuda Técnica y Próximos Pasos

### 4.1. Problemas críticos a resolver

| Problema | Impacto | Solución propuesta |
|----------|---------|-------------------|
| **Sandbox inconsistente** | Riesgo de seguridad: el asistente puede leer/escribir fuera del área permitida | Unificar validación: toda operación de archivos debe pasar por `archivos.py` y rechazar rutas fuera de `SANDBOX_BASE`. Agregar whitelist de rutas permitidas (Desktop, Downloads) |
| **Concurrencia en MCP** | Fallos intermitentes bajo carga moderada | Usar un pool de conexiones asíncronas o serializar las llamadas MCP con un lock |
| **Manejo de errores frágil** | La IA puede generar acciones no detectadas por los patrones de búsqueda | Migrar a un parser de intenciones más robusto (p.ej., función dedicada con regex) |
| **Código monolítico en main_gui.py** | Dificulta mantenimiento y pruebas (~900 líneas) | Dividir en: `gui_chat.py` (burbujas, render), `gui_sidebar.py`, `gui_input.py` |
| **Dependencia de win32gui/win32con** | Solo funciona en Windows, sin fallback | Agregar detección de SO y mock para pruebas en otras plataformas |

### 4.2. Mejoras de arquitectura

- **Separación de responsabilidades en ia.py**: La función `enviar_a_gemini()` es demasiado larga y maneja demasiadas responsabilidades (enrutamiento, ejecución de acciones, seguridad). Dividir en: `RouterIA`, `ActionExecutor`, `SecurityGuard`.
- **Refactorizar interceptor de acciones**: Extraer la lógica de detección de comandos (guardar_archivo:, buscar:, eliminar:, etc.) a un módulo separado `action_parser.py`.
- **Implementar logging estructurado**: Actualmente el logging es básico. Usar `structlog` o al menos niveles más granulares.
- **Estandarizar respuestas de módulos**: Algunas funciones retornan tuplas, otras strings con formato, otras directamente imprimen en consola. Unificar con un `Result` object.

### 4.3. Próximos pasos recomendados (por orden de prioridad)

1. **🔴 Crítico**: Revisar y unificar la política de sandbox. Decidir si el asistente debe operar solo dentro de `OmniAssistant/` o si puede acceder a áreas del usuario con consentimiento explícito.
2. **🔴 Crítico**: Agregar manejo de errores robusto en la llamada a DeepSeek (timeouts, rate limits, fallback a Gemini).
3. **🟡 Alto**: Refactorizar `main_gui.py` en al menos 3 archivos (chat, sidebar, input).
4. **🟡 Alto**: Implementar pruebas unitarias para los módulos core (archivos, memoria, sistema).
5. **🟡 Alto**: Agregar un sistema de plugins o skills para extender funcionalidades sin modificar el núcleo.
6. **🟢 Medio**: Migrar el reconocimiento de voz a un modelo más liviano (tiny.en) como opción por defecto para reducir VRAM.
7. **🟢 Medio**: Implementar un sistema de autorización para acciones peligrosas (borrado, Git push) con una lista blanca de comandos.
8. **🟢 Medio**: Agregar un `requirements.txt` completo y un `setup.py` para facilitar la instalación.
9. **🔵 Bajo**: Internacionalizar la interfaz (soporte multi-idioma).
10. **🔵 Bajo**: Agregar un dashboard de telemetría en la sidebar (CPU, RAM, VRAM en tiempo real).

### 4.4. Funcionalidades futuras sugeridas

- **Asistente de depuración**: Capacidad de ejecutar código Python local y mostrar resultados en el chat.
- **Historial de conversaciones**: Guardar y cargar sesiones anteriores.
- **Comandos personalizables**: Permitir al usuario definir sus propios atajos y acciones.
- **Integración con APIs externas**: Clima, calendario, email.
- **Modo oscuro/claro configurable** (actualmente solo oscuro).
- **Exportar conversación a Markdown o PDF**.

---

## 5. Resumen de Salud del Proyecto

| Aspecto | Calificación | Notas |
|---------|-------------|-------|
| **Funcionalidad** | ⭐⭐⭐⭐☆ | Core completo, pero con fallos conocidos |
| **Arquitectura** | ⭐⭐⭐☆☆ | Modular pero con acoplamiento en ia.py y main_gui.py |
| **Seguridad** | ⭐⭐☆☆☆ | Sandbox inconsistente, acciones peligrosas sin autenticación |
| **Mantenibilidad** | ⭐⭐⭐☆☆ | Código documentado pero con funciones largas y poca separación |
| **Rendimiento** | ⭐⭐⭐☆☆ | Whisper con VRAM alta, MCP con overhead |
| **Pruebas** | ⭐☆☆☆☆ | Sin tests automatizados |
| **Documentación** | ⭐⭐⭐⭐☆ | README completo, comentarios en código |

**Conclusión**: OmniAssistant es un proyecto ambicioso y funcional, pero requiere una revisión de seguridad y refactorización antes de considerarse listo para producción. Los próximos pasos deben enfocarse en robustecer el sandbox, mejorar el manejo de errores y dividir la lógica monolítica en módulos más pequeños y testeables.