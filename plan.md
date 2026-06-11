**
```markdown
# Plan de Consolidación de OmniAssistant (Cortana)

## Fase 1: Correcciones Críticas (Prioridad Máxima)
### 1.1 Unificar servidor MCP duplicado
- **Archivos involucrados:** `servidor_sistema_mcp.py` (raíz) y `modulos/servidor_sistema_mcp.py`
- **Acción:** Eliminar el de la raíz y actualizar la referencia en `modulos/cliente_mcp.py` (línea 13) para que apunte a `modulos/servidor_sistema_mcp.py`
- **Verificación:** Ejecutar `cliente_sistema.ejecutar("reporte_estado_pc")` y comprobar que funciona.
- **Esfuerzo:** 15 minutos.

### 1.2 Mejorar reemplazo de bloques (seguridad en edición)
- **Archivo:** `modulos/ia.py` (función de reemplazo, ~línea 350)
- **Acción:**
  - Sustituir `contenido_actual.replace(buscar_edit, reemplazar_edit, 1)` por una función que use `re.sub` con límites de línea exactos.
  - Añadir validación: si el bloque buscado aparece más de una vez, lanzar advertencia y pedir confirmación al usuario.
- **Esfuerzo:** 1 hora.

### 1.3 Preservar contexto completo al cambiar de modo
- **Archivos:** `main_gui.py`, `modulos/ia.py`
- **Acción:**
  - En `main_gui.py`, al cambiar de modo, guardar también `motor_ia.CONTEXTO_CHAT` en el historial del modo (junto con las burbujas visuales).
  - Al restaurar un modo, cargar `CONTEXTO_CHAT` desde el historial antes de renderizar las burbujas.
- **Esfuerzo:** 30 minutos.

### 1.4 Edición en archivos grandes para Modo Programador
- **Archivos:** `modulos/ia.py` (parser de comandos), `modulos/archivos.py` (nueva función de búsqueda difusa)
- **Problema:** DeepSeek no puede modificar archivos como `main_gui.py` o `ia.py` porque:
  - Se inyecta el contenido completo en el contexto, saturando tokens.
  - El regex de `reemplazar_bloque:` es demasiado estricto (falla por espacios, backticks, etc.).
  - No hay feedback visual de errores específicos.
- **Acción:**
  1. No recargar automáticamente el archivo completo si ya fue leído antes (flag `ARCHIVO_CARGADO`).
  2. Hacer el regex de `reemplazar_bloque:` tolerante a espacios y backticks.
  3. Si el reemplazo falla, usar `difflib` para encontrar el bloque más cercano y mostrar la diferencia al usuario.
  4. Permitir que el usuario envíe una versión corregida del bloque.
- **Esfuerzo:** 2 horas.

---

## Fase 2: Estabilización del Entorno
### 2.1 Centralizar estado del workspace (sandbox)
- **Archivos:** `config.py`, `modulos/ia.py`, `main_gui.py`
- **Acción:**
  - Crear una clase `EstadoGlobal` en `config.py` que contenga `WORKSPACE_ACTUAL`, `MODO_ACTUAL`, `CONTEXTO_CHAT`, etc., como atributos de clase.
  - Reemplazar todas las asignaciones directas (`config.RUTA_WORKSPACE_ACTUAL = ...`) por setters que actualicen también las variables en `ia.py` y la UI.
- **Esfuerzo:** 45 minutos.

### 2.2 Lazy loading de Whisper
- **Archivo:** `modulos/audio.py`
- **Acción:**
  - Mover la carga del modelo Whisper dentro de la función `capturar_voz_micro`, con un decorador `@lazy_load` o un singleton condicional.
  - Añadir feedback visual en la UI ("Cargando modelo de voz...") durante la primera carga.
- **Esfuerzo:** 30 minutos.

### 2.3 Reemplazar `print()` por logging profesional
- **Archivos:** Todos los módulos (priorizar `ia.py`, `sistema.py`, `archivos.py`, `memoria.py`)
- **Acción:**
  - Importar `from modulos.logger import logger` en cada módulo.
  - Sustituir `print(...)` por `logger.info(...)`, `logger.warning(...)`, `logger.error(...)`.
  - Añadir un nivel DEBUG para trazas internas de MCP y acciones.
- **Esfuerzo:** 1 hora.

### 2.4 GitHub Fix – Corrección de errores en el sistema Git
- **Archivos involucrados:** `modulos/git_bot.py`, `modulos/ia.py`, `config.py`
- **Análisis de fallos:** Identificados 5 puntos críticos:
  1. **Token de GitHub no validado** → Añadir verificación al inicio (`GET /user` con el token).
  2. **Repositorio duplicado mal manejado** → Usar `git remote set-url origin <url>` si el remote ya existe.
  3. **Push sin control de conflictos** → Capturar `stderr` completo y mostrarlo al usuario.
  4. **Workspace ausente** → Validar que `ruta_real` no sea `None` antes de crear el pendiente.
  5. **Comandos libres sin restricción** → Implementar lista blanca de comandos Git permitidos.
- **Acción concreta:**
  - En `git_bot.py`:
    - Sustituir `print()` por `logger.info()` y `logger.error()`.
    - Modificar `sincronizar_proyecto_git` para que use `git remote set-url` si el remote ya existe.
    - Capturar `stderr` completo en el resultado del push y retornarlo.
  - En `ia.py`:
    - Añadir comprobación de `ruta_real is not None` antes de asignar `PENDIENTE_DE_GIT`.
    - En el semáforo de Git, incluir un mensaje claro si el workspace no está anclado.
  - En `config.py`:
    - Añadir función `verificar_token_github()` que se ejecute en el arranque y muestre un warning si el token es inválido.
- **Esfuerzo:** 2 horas.
- **Verificación:** Probar `github:` con un proyecto real, con y sin token válido, y con conflictos simulados.

---

## Fase 3: Optimización y Refinamiento
### 3.1 Pool persistente de conexiones MCP
- **Archivo:** `modulos/cliente_mcp.py`
- **Acción:**
  - Convertir `GestorMCP` en un singleton que mantenga una sesión `stdio_client` abierta mientras el asistente esté activo.
  - Implementar reconexión automática si el servidor MCP se cae.
- **Esfuerzo:** 2 horas.

### 3.2 Watchdog para snapshots automáticos
- **Archivos:** `modulos/memoria.py`, `main_gui.py`
- **Acción:**
  - Integrar `watchdog` (librería externa) para monitorizar cambios en el workspace.
  - Cuando se detecte una modificación en cualquier archivo del proyecto, actualizar automáticamente el snapshot y notificar en la UI.
- **Esfuerzo:** 2 horas.

### 3.3 Refactor: Extraer controlador de acciones
- **Archivo:** `modulos/ia.py` (función `enviar_a_gemini`)
- **Acción:**
  - Mover toda la lógica de parseo de comandos (guardar_archivo, reemplazar, buscar, git, etc.) a un nuevo módulo `modulos/controlador_acciones.py`.
  - Dejar en `ia.py` solo el enrutamiento de modelos, la construcción de contexto y la invocación del controlador.
- **Esfuerzo:** 3 horas.

---

## Fase 4: Internacionalización y Calidad de Vida
### 4.1 Unificar idioma a español
- **Archivos:** `modulos/ia.py` (prompts de sistema), `main_gui.py` (etiquetas), `modulos/audio.py` (mensajes)
- **Acción:**
  - Centralizar todos los strings en un archivo `modulos/lang/es.py` (diccionario).
  - Reemplazar cadenas literales por referencias al diccionario.
- **Esfuerzo:** 1.5 horas.

### 4.2 Pruebas unitarias básicas
- **Carpeta:** `pruebas/`
- **Acción:**
  - Escribir tests para `modulos/archivos.py` (seguridad de rutas, límites de tamaño).
  - Escribir tests para `modulos/sistema.py` (búsqueda de ventanas, cierre).
  - Ejecutar con `pytest` y configurar GitHub Actions para CI.
- **Esfuerzo:** 2.5 horas.

---

## Resumen de Tiempo Total Estimado
- **Fase 1:** ~3h 45min (1.1 + 1.2 + 1.3 + 1.4) ← **Crítico**
- **Fase 2:** ~4h 15min (2.1 + 2.2 + 2.3 + 2.4)
- **Fase 3:** ~7h (3.1 + 3.2 + 3.3)
- **Fase 4:** ~4h (4.1 + 4.2)
- **Total:** ~19 horas de trabajo efectivo.

> **Nota:** Se recomienda ejecutar las fases en orden estricto. Cada fase contiene tareas independientes que pueden ser realizadas en cualquier orden dentro de la misma fase. Después de completar cada tarea, hacer una prueba manual rápida para validar que no se rompió nada.
```
---FIN---

El plan está actualizado con todas las secciones que hablamos, incluyendo la nueva **Fase 1.4** para el modo programador y el **GitHub Fix** dentro de la Fase 2. Las fases están ordenadas por prioridad: primero lo crítico (seguridad y funcionalidad básica), luego estabilización, optimización y calidad de vida. ¿Listo para empezar a ejecutar?