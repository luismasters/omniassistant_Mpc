# PROJECT_STATE.md

## 1. Resumen Ejecutivo

**OmniAssistant (Cortana)** es un asistente de inteligencia artificial de escritorio desarrollado en Python, diseñado para operar en Windows. Combina múltiples modelos de IA (Gemini Flash Lite, DeepSeek V4 Reasoning y Fast) en tres modos de operación (General, Planificador, Programador) con capacidades de voz, visión, control del sistema, gestión de archivos, integración con GitHub, y memoria persistente vectorial. Su objetivo es proporcionar un asistente conversacional completo que pueda entender y ejecutar comandos naturales, editar código, administrar proyectos, y mantener contexto a largo plazo.

## 2. Arquitectura

### 2.1 Módulos Principales

| Archivo | Rol | Descripción |
|---------|-----|-------------|
| `config.py` | Configuración central | Variables de entorno, límites, rutas seguras, claves API, estados globales |
| `main_gui.py` | Interfaz gráfica | Ventana principal con sidebar, área de chat, input, logs, manejo de modos |
| `modulos/ia.py` | Motor de IA | Enrutador de modelos, construcción de contextos, parseo de comandos, ejecución de herramientas |
| `modulos/archivos.py` | Gestión de archivos | Lectura/escritura segura, validación de rutas (sandbox), creación/eliminación |
| `modulos/audio.py` | Procesamiento de voz | Captura con micrófono (Whisper), síntesis de voz (pyttsx3), control por tecla |
| `modulos/sistema.py` | Control del SO | Apertura/cierre de ventanas, exploración de directorios, hardware, procesos |
| `modulos/memoria.py` | Memoria persistente | ChromaDB vectorial, guardado/búsqueda de recuerdos, snapshot del proyecto, watchdog |
| `modulos/prompts.py` | Prompts de sistema | Separación de instrucciones por modo (general/planificador/programador) |
| `modulos/git_bot.py` | Integración Git | Subida automática a GitHub, comandos seguros, manejo de conflictos |
| `modulos/busqueda.py` | Búsqueda web | DuckDuckGo, integración con Gemini para búsqueda en tiempo real |
| `modulos/vision.py` | Captura de pantalla | Multi-monitor, integración con Gemini para análisis visual |
| `modulos/cliente_mcp.py` | Cliente MCP | Comunicación asíncrona con servidor MCP para herramientas del sistema |
| `modulos/servidor_sistema_mcp.py` | Servidor MCP | Herramientas: estado PC, hardware, bóveda, exploración, lectura |
| `modulos/crawler.py` | Escaneo de proyectos | Recorre árbol del proyecto, ignora carpetas innecesarias, genera contexto |
| `modulos/logger.py` | Sistema de logs | Archivos rotativos, salida a consola, niveles DEBUG/INFO |
| `gestor_boveda.py` | Utilidad de gestión | Interfaz CLI para listar/borrar/hard-reset de la memoria vectorial |

### 2.2 Flujo de Datos

```
Usuario → GUI (main_gui.py) → Envío de mensaje
  → modulos/ia.py (enrutador)
    → Modo General → Gemini Flash Lite + MCP + búsqueda + visión
    → Modo Planificador/Programador → DeepSeek V4 (reasoning/chat)
  → Parseo de respuesta (guardar/reemplazar/git/abrir/cerrar/etc.)
  → Actualización de contexto, memoria, snapshots
  → UI callback (streaming de texto, burbujas, logs)
```

## 3. Estado Actual

### 3.1 Funcionalidades Operativas

- **Interfaz gráfica completa**: Chat con burbujas de usuario/IA, renderizado de Markdown (negrita, itálica, código, tablas), scroll automático, placeholder, adjuntar archivos
- **Tres modos de IA**: General (Gemini), Planificador (DeepSeek Reasoning), Programador (DeepSeek Fast) con preservación de contexto al cambiar
- **Voz**: Captura por micrófono con tecla F8, transcripción con Whisper, síntesis de voz con pyttsx3, interrupción por espacio
- **Visión**: Captura de pantalla multi-monitor, integración con Gemini
- **Control del sistema**: Abrir/cerrar aplicaciones, mover ventanas a monitores, explorar directorios, apagar PC
- **Búsqueda web**: DuckDuckGo, integración con Gemini para respuestas contextuales
- **Memoria persistente**: ChromaDB con embeddings, guardado/búsqueda por etiquetas, snapshots JSON por proyecto
- **Edición de código**: Guardar archivos, reemplazo exacto/fuzzy de bloques, lectura condicional con caché, creación de carpetas
- **Git**: Subida automática a GitHub, comandos seguros, manejo de conflictos, desvinculación de remotos
- **MCP**: Servidor local para herramientas del sistema (estado PC, hardware, bóveda)
- **Crawler**: Escaneo completo del proyecto, generación automática de PROJECT_STATE.md con DeepSeek Reasoning
- **Logs**: Sistema de logging profesional con archivos y consola
- **Seguridad**: Sandbox inteligente (modo general libre, modos restringidos al workspace), límites de tamaño/espacio, confirmaciones para borrado/git
- **Watchdog**: Detección de cambios en archivos del proyecto, invalidación automática de caché de IA

### 3.2 Limitaciones Conocidas

- **Whisper se carga al inicio**: Aumenta tiempo de arranque (~2-3 segundos)
- **MCP no tiene pool persistente**: Se crea una nueva conexión por cada llamada
- **La edición fuzzy puede fallar en archivos muy grandes**: El algoritmo secuencial puede ser lento con >1000 líneas
- **No hay pruebas unitarias automatizadas**: Solo existe un esqueleto en `pruebas/`
- **El sidebar no muestra el estado de conexión de los modelos**: Solo muestra el modelo activo
- **Los mensajes de error de API (Gemini/DeepSeek) no se muestran claramente en UI**: Se imprimen en consola pero no en el chat

## 4. Deuda Técnica / Próximos Pasos

### 4.1 Crítico (Prioridad Alta)

1. **Unificar servidor MCP duplicado**  
   - `servidor_sistema_mcp.py` existe en raíz y en `modulos/`. Eliminar el de raíz, actualizar referencia en `cliente_mcp.py`.

2. **Mejorar reemplazo de bloques (seguridad en edición)**  
   - Usar `re.sub` con límites de línea exactos en lugar de `str.replace`.  
   - Si el bloque buscado aparece más de una vez, lanzar advertencia y pedir confirmación.

3. **Preservar contexto completo al cambiar de modo**  
   - Guardar también `motor_ia.CONTEXTO_CHAT` en el historial del modo (actualmente solo guarda burbujas visuales).  
   - Al restaurar un modo, cargar `CONTEXTO_CHAT` antes de renderizar.

4. **Edición en archivos grandes para Modo Programador**  
   - No recargar archivos completos si ya fueron leídos (flag `ARCHIVO_CARGADO`).  
   - Hacer regex de `reemplazar_bloque:` tolerante a espacios y backticks.  
   - Si falla, usar `difflib` para encontrar el bloque más cercano y mostrar diferencia.

### 4.2 Estabilización (Prioridad Media)

5. **Centralizar estado global**  
   - Crear clase `EstadoGlobal` en `config.py` con todos los estados (workspace, modo, contexto, etc.) para evitar variables sueltas.

6. **Lazy loading de Whisper**  
   - Mover carga del modelo a `capturar_voz_micro` con decorador/singleton.  
   - Añadir feedback visual "Cargando modelo de voz..." en UI.

7. **GitHub Fix – Corrección de errores en sistema Git**  
   - Validar token de GitHub al inicio.  
   - Usar `git remote set-url` si el remote ya existe.  
   - Capturar `stderr` completo en push.  
   - Validar `ruta_real is not None` antes de asignar pendiente.

### 4.3 Optimización (Prioridad Baja)

8. **Pool persistente de conexiones MCP**  
   - Convertir `GestorMCP` en singleton con sesión `stdio_client` abierta.  
   - Implementar reconexión automática.

9. **Watchdog para snapshots automáticos**  
   - Integrar `watchdog` para detectar cambios en workspace y actualizar snapshot automáticamente.

10. **Refactor: Extraer controlador de acciones**  
    - Mover parseo de comandos (guardar, reemplazar, git, etc.) a `modulos/controlador_acciones.py`.

### 4.4 Calidad de Vida (Prioridad Opcional)

11. **Internacionalización**  
    - Centralizar strings en `modulos/lang/es.py` (diccionario).  
    - Reemplazar literales por referencias.

12. **Pruebas unitarias**  
    - Escribir tests para `archivos.py` (seguridad de rutas, límites).  
    - Escribir tests para `sistema.py` (búsqueda de ventanas, cierre).  
    - Ejecutar con `pytest` y configurar CI.

---

> **Nota**: Este documento fue generado automáticamente mediante el Crawler del sistema. Corresponde al estado actual del código fuente tal como se proporcionó. Se recomienda revisar y actualizar periódicamente para mantenerlo como fuente única de verdad.