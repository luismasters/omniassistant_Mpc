# PROJECT_STATE.md

## 1. Resumen Ejecutivo

**OmniAssistant (Cortana)** es un asistente de IA multimodal de escritorio con capacidad de voz, visión, control de sistema, edición de archivos, integración con Git, memoria persistente vectorial (ChromaDB), y soporte multi‑modelo (Gemini Flash para modo general, DeepSeek V4 para planificación y programación). Actúa como un copiloto inteligente que entiende el contexto del usuario, ejecuta comandos del sistema, lee/escribe archivos dentro de un sandbox controlado, y mantiene una bóveda de conocimiento a largo plazo. La interfaz gráfica está desarrollada con CustomTkinter, soporta múltiples modos de operación, entrada por voz y adjuntos de archivos.

## 2. Arquitectura

El sistema se organiza en módulos independientes que se comunican a través de un controlador central (`ia.py`) y una capa de servicios MCP.

### 2.1. Módulos principales

| Archivo / Módulo | Propósito |
|------------------|-----------|
| `main_gui.py` | Interfaz gráfica con CustomTkinter: sidebar, burbujas de chat (usuario/IA), entrada de texto, soporte adjuntos y voz. |
| `config.py` | Configuración global: rutas seguras, límites de archivos, API keys, estados del sistema. |
| `modulos/ia.py` | Orquestador principal. Enruta mensajes a Gemini o DeepSeek según el modo activo, gestiona contexto, ejecuta herramientas MCP y comandas propias. |
| `modulos/prompts.py` | Genera prompts de sistema adaptados a cada modo (general, planificador, programador). |
| `modulos/controlador_acciones.py` | Parsea la respuesta de la IA y ejecuta acciones concretas (guardar, reemplazar bloques, git, búsqueda, etc.) con soporte de fuzzy matching. |
| `modulos/archivos.py` | Funciones seguras de lectura/escritura/eliminación de archivos con validación de rutas y límites. Incluye sandbox inteligente (modo general sin restricciones). |
| `modulos/sistema.py` | Control de ventanas (abrir/cerrar/mover), búsqueda de archivos, radar inteligente de programas, telemetría (CPU, RAM, GPU). |
| `modulos/audio.py` | Captura de voz por micrófono (Whisper local con lazy‑loading), síntesis de voz (pyttsx3), detección de interrupción por tecla Espacio. |
| `modulos/vision.py` | Captura de pantalla usando PIL y screeninfo. |
| `modulos/busqueda.py` | Búsqueda web mediante DuckDuckGo (ddgs). |
| `modulos/memoria.py` | Base de datos vectorial ChromaDB para memoria a largo plazo, watchdog de cambios en workspace (limpia caché de IA automáticamente), snapshots JSON. |
| `modulos/git_bot.py` | Integración con GitHub: init, add, commit, push, manejo de remote existente, comandos libres con lista blanca, validación de token. |
| `modulos/cliente_mcp.py` | Cliente MCP asíncrono para comunicarse con el servidor MCP interno. |
| `modulos/servidor_sistema_mcp.py` | Servidor MCP que expone herramientas: reporte de PC, hardware, búsqueda/guardado en bóveda, exploración de directorios, lectura de archivos. |
| `modulos/crawler.py` | Extrae todo el código de un proyecto (ignorando carpetas no deseadas) para análisis. |
| `modulos/logger.py` | Configuración de logging (archivo + consola). |
| `modulos/limpiar.py` | Utilitario para vaciar la bóveda de memoria. |
| `gestor_boveda.py` | Herramienta CLI para listar, eliminar o resetear la bóveda de ChromaDB. |
| `plan.md` | Plan de consolidación (fases 1‑4) – describe las correcciones planificadas. |
| `pruebas/` | Carpeta con tests básicos (aún no implementados completamente). |

### 2.2. Flujo de comunicación

```
Usuario (GUI/voz) → ia.py → (Gemini/DeepSeek) → respuesta
                                         ↓
                              controlador_acciones.py → archivos, sistema, git, memoría, búsqueda web
                                                             ↓
                                                     servidor_sistema_mcp.py (herramientas nativas)
```

## 3. Estado Actual

### 3.1. Funcionalidades operativas

- **Chat multimodal** con renderizado de Markdown (negrita, itálica, código, tablas, listas, bloques de código con copiado).
- **Entrada por voz** (tecla F8) con transcripción Whisper (lazy‑loading del modelo).
- **Síntesis de voz** (pyttsx3) con detección de interrupción (tecla Espacio).
- **Adjuntar archivos** desde el botón 📎 → lectura e inyección en contexto con confirmación para guardar en bóveda permanente.
- **Cambio de modos** (General, Planificador, Programador) con preservación de historial visual y contexto de IA (CONTEXTO_CHAT) – implementación completa de Fase 1.3.
- **Edición quirúrgica de archivos** mediante `reemplazar_bloque:` con fuzzy matching (difflib, umbral ≥80%) y soporte de formato XML alternativo (`<replace_block>`, `<reemplazar_bloque>`). Se maneja ambigüedad (más de una coincidencia) y se notifica al usuario.
- **Escaneo completo del proyecto** (`escanear_proyecto:`) que genera PROJECT_STATE.md usando DeepSeek.
- **Integración con Git** (push, reset, comandos libres seguros) con semáforo de confirmación, manejo de remote existente y validación del token al inicio.
- **Control del sistema** (abrir/cerrar/mover ventanas, navegar web, explorar directorios) con búsqueda inteligente por radar de programas.
- **Memoria persistente** (ChromaDB) con herramientas MCP para guardar y recuperar información.
- **Watchdog** que detecta cambios en el workspace y limpia la caché de la IA automáticamente (Fase 3.2 implementada).
- **Snapshots** de estado del proyecto (JSON en `.cortana/snapshot.json`).
- **Búsqueda web** mediante DuckDuckGo.
- **Logging** centralizado (archivo + consola) – parcialmente migrado desde `print()` (Fase 2.3 incompleta).
- **Sandbox inteligente**: el modo general permite acceso a cualquier ruta; los modos planificador/programador solo dentro del workspace anclado.
- **Unificación del servidor MCP**: solo existe en `modulos/servidor_sistema_mcp.py` y el cliente apunta a esa ruta (Fase 1.1 completada).

### 3.2. Limitaciones conocidas

- El servidor MCP se inicia en cada petición (no persistente) – Fase 3.1 pendiente.
- Whisper en modelo `medium` ocupa ~2 GB de RAM; el lazy‑loading evita que se cargue al inicio, pero no hay feedback visual en la UI durante la primera carga (solo mensaje en consola).
- El modo Planificador y Programador dependen de un workspace seleccionado; si no se ancla, fallan con mensaje de advertencia.
- **Migración de `print()` a logging incompleta**: `ia.py`, `audio.py`, `memoria.py` y `sistema.py` aún contienen muchos `print()` directos.
- **No hay internacionalización**: todos los strings están en español duro (Fase 4.1 pendiente).
- **Pruebas unitarias no implementadas**: carpeta `pruebas/` contiene esbozos vacíos (Fase 4.2 pendiente).
- **Centralización del estado global**: no existe una clase `EstadoGlobal`; las variables se asignan directamente en `config.py`, `ia.py` y `main_gui.py` (Fase 2.1 pendiente).
- El reemplazo de bloques puede fallar si el código contiene caracteres especiales no escapados en el patrón de búsqueda (aunque el fuzzy matching mitiga esto).
- La edición de archivos grandes (>80k caracteres) trunca el contenido leído para evitar saturar tokens (Fase 1.4 parcialmente implementada).
- El reemplazo de bloques usa `replace(buscar, reemplazar, 1)` sin límites de línea exactos; la ambigüedad se maneja con advertencia, pero no se usa `re.sub` con límites de línea como se planeó en Fase 1.2.
- No hay confirmación visual para el radar de cambios (watchdog) cuando el workspace cambia mientras el modo no es planificador/programador.
- La síntesis de voz usa `pyttsx3`, que tiene dependencia de `winsound` y no es multiplataforma.
- El botón de "Nueva conversación" no está implementado en la UI; la función `_nueva_conversacion` existe pero no se enlaza a ningún control.

## 4. Deuda Técnica / Próximos Pasos

### 4.1. Prioridad alta (Fase 1 – Correcciones Críticas)

- [ ] **1.2 (mejora pendiente)**: Sustituir `replace()` por `re.sub` con límites de línea exactos en `controlador_acciones.py` para evitar reemplazos ambiguos. Actualmente se usa advertencia, pero no se bloquea.
- [ ] **1.4 (completar)**: Implementar flag `ARCHIVO_CARGADO` para no recargar archivos grandes que ya fueron leídos, y usar `difflib` como fallback más robusto (ya hay fuzzy, pero podría mejorarse la notificación al usuario).

### 4.2. Prioridad media (Fase 2 – Estabilización)

- [ ] **2.1**: Centralizar estado global en una clase `EstadoGlobal` en `config.py` con setters que actualicen la UI y los módulos.
- [ ] **2.2 (mejora)**: Añadir feedback visual en la UI durante la carga de Whisper ("Cargando modelo de voz...").
- [ ] **2.3**: Reemplazar todos los `print()` restantes por `logger.info/warning/error` (priorizar `ia.py`, `audio.py`, `memoria.py`, `sistema.py`).
- [ ] **2.4 (verificación adicional)**: Probar `github:` con proyectos reales, con y sin token válido, y con conflictos simulados para asegurar que el manejo de `stderr` y la lista blanca funcionan correctamente.

### 4.3. Prioridad baja (Fase 3 y 4 – Optimización y Calidad de Vida)

- [ ] **3.1**: Convertir `GestorMCP` en un singleton reconectable que mantenga la sesión abierta.
- [ ] **3.2 (mejora)**: Notificar en la UI cuando el watchdog detecte cambios en el workspace (actualmente solo limpia caché en segundo plano).
- [ ] **3.3**: Separar completamente la lógica de acciones de `ia.py` (ya está en `controlador_acciones.py`, pero aún hay dependencias).
- [ ] **4.1**: Centralizar todos los strings en `modulos/lang/es.py` y referenciarlos en los módulos.
- [ ] **4.2**: Escribir pruebas unitarias con pytest para `archivos.py`, `sistema.py`, `git_bot.py`.
- [ ] **4.3**: Eliminar dependencia de `winsound` y `pyttsx3` (considerar alternativas multiplataforma como `sounddevice` para síntesis).
- [ ] **4.4**: Mejorar la UI: tema claro, soporte de fuentes dinámicas, búsqueda dentro del historial, implementar botón "Nueva conversación".

> **Nota:** El plan detallado se encuentra en `plan.md` con tiempos estimados y orden de ejecución recomendado. Se sugiere comenzar por las tareas pendientes de la Fase 1 para garantizar estabilidad antes de optimizar.