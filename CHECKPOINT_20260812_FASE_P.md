# CHECKPOINT — Fase P (Persistencia Durable) MVP implementada

**Fecha:** 2026-08-12 · **Punto de control:** después de la prueba de humo OK
**Propósito:** bandera para resumen posterior (auditoría por otra IA) desde aquí hasta donde llegue el trabajo.

---

## 1. Estado del hilo al cierre de este checkpoint

- ROADMAP.md es la única fuente de verdad (§8 = Deuda arquitectónica; §8.5.1 = decisión Fase P→Fase D→expansiones; §8.5.2 = contrato técnico Fase P).
- **Fase P MVP implementada y testeada** (341 + 24 = **365 tests verdes**, `node --check` OK, `py_compile` OK).
- Prueba de humo headless end-to-end **OK** (escritura → cierre por cambio de modo → reinicio simulado → detección `aborted` → recuperación por contexto → preferencias).

## 2. Decisiones tomadas (Bloque 0)

| ID | Decisión | Valor |
|---|---|---|
| L1 | Ubicación del store | `%LOCALAPPDATA%\ArgusCopilot\conversaciones\` (fuera del repo) |
| L4 | Trigger de "retomar" | Frase natural + botón ↩️ en header |
| L2 | Radar (watchdog) en main_web | Re-armado dentro de Fase P |
| — | Arranque | Fase P MVP antes del bloque de estabilidad (retry/backoff queda pendiente) |

## 3. Archivos creados/modificados

**Creados:**
- `modulos/persistencia.py` — store JSONL append-only por `context_id` genérico (sesión/turno/mensaje, checksum sha256 por registro, dedup por `(context_id, sesion_id, turno_seq, msg_seq)`, escritura dentro de lock, `recuperar_tail`, `purgar_historial`, `borrar_historial`, preferencias atómicas, `cargar_estado_proyecto` solo recarga, flag `OMNASSISTANT_NO_PERSISTENCIA`, override `ARGUS_PERSISTENCIA_DIR`, `iniciar_radar_persistente`, `sesion_abierta_en_disco`, `armar_context_id`).
- `tests/test_persistencia.py` — 24 tests (W/R/REC/LIM/CON/RE/COR/DUP/AISL/PREF/PROY/env/FD).

**Modificados:**
- `config.py` — `agregar_mensaje_chat` persiste cada mensaje dentro de `RLOCK_CONTEXTO`; `cambiar_modo` cierra la sesión del contexto saliente.
- `main_web.py` — arranque restaura prefs (workspace/modelo/visualización/modo), recarga snapshot, re-arma radar, marca sesiones `aborted`, reabre sesión; cierre hace flush de la sesión activa.
- `modulos/web_bridge.py` — `_guardar_preferencias` (al cambiar modelo/workspace/modo/visualización), carga de snapshot+radar al seleccionar workspace, métodos `recuperar_historial` / `borrar_historial_contexto` / `hay_historial_persistido`.
- `modulos/ia.py` — interceptor de frases "dónde quedamos / retomá la conversación" → hidrata tail.
- `gui/index.html` + `gui/app.js` — botón ↩️ retomar historial.
- `tests/conftest.py` — `OMNASSISTANT_NO_PERSISTENCIA=1` para tests offline.

## 4. Contrato aplicado (ROADMAP §8.5.2)

- Historial por `context_id` genérico (NUNCA `general/mentor/gamer` como schema; `armar_context_id` es el mapeo transitorio que Fase D reemplaza sin tocar el store).
- Recuperación SOLO explícita (frase o botón), con límites (25 mensajes / 2000 chars), excluye marcadores de sistema.
- `documento_volatil`, `evidencia_web`, `pendiente_*`, contadores → volátiles (sin cambios).
- `PROJECT_STATE.md`/`.cortana/snapshot.json` → solo se recargan, no se duplican.
- Olvido NO retroactivo sobre transcripto (H.1 intacto).

## 5. Suites/verificaciones en este punto

- `venv\Scripts\python.exe -m pytest` → **365 passed, 76 warnings** (warnings preexistentes de `EmbeddingDeterminista`).
- `node --check gui/app.js` → OK.
- `py_compile` de `persistencia.py`, `web_bridge.py`, `ia.py`, `main_web.py`, `config.py` → OK.
- Smoke headless: `smoke_fase_p.py` (temp) → RESULTADO OK.

## 6. Decisiones/ítems PENDIENTES al cierre del checkpoint

1. **Retomar: ¿reemplaza o anexa el contexto actual?** (hoy reemplaza con `reemplazar_contexto_chat`). A decidir.
2. Prueba manual real con GUI (`venv\Scripts\python.exe main_web.py`).
3. Bloque de estabilidad pendiente: retry/backoff en APIs (ia.py), versiones fijas en `requirements.txt`, ampliar tests de `archivos.py`/`memoria.py`/`git_bot.py`.
4. Fase D (desacoplamiento de modos) — diseño documentado en ROADMAP §8, sin implementar.
5. Etapa 4 del plan externo (previews de Git en modales HUD) — anotada como aporte, sin asentar aún.
6. Colateral: ingesta PDF → bóveda (GUIA_MEMORIA §7), sin empezar.
7. Migración `context_id` con id-map lazy en Fase D (contrato §8.5.2 I).

## 7. Cómo retomar la auditoría desde aquí

- Leer: ROADMAP §8 + §8.5.1 + §8.5.2; este CHECKPOINT; `modulos/persistencia.py`; `tests/test_persistencia.py`.
- El resumen posterior de esta sesión debería partir de la línea "Prueba de humo OK" e incluir TODO lo trabajado después de este checkpoint.
