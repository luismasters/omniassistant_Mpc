# Arquitectura C+D — Verificación web con señal estructurada

> Documento de diseño de la verificación de información en internet.
> Complementa a `ROADMAP.md` (planificación) y a `AUDITORIA_ARQUITECTURA.md` (auditoría histórica).

## 1. Idea central (C + D)

La verificación web se separa en **dos decisiones distintas**:

- **Decisión C (semántica): la toma el LLM.** El modelo decide *si* el turno
  requiere información reciente y *qué* debe buscar, expresándolo en una señal
  estructurada al final de su respuesta.
- **Decisión D (ejecución): la toma Python.** Si la señal dice `[WEB: SI]`, el
  pipeline ejecuta determinísticamente la búsqueda y la segunda generación con
  evidencia. Python no decide *si* buscar: ejecuta lo que el modelo declaró.

El LLM deja de "incumplir" porque la decisión se vuelve explícita y observable
en su propia salida. Python deja de "adivinar" (heurísticas por palabras,
longitudes o nombres) porque solo ejecuta.

## 2. Señal estructurada

Al final del borrador de la primera generación, el modelo adjunta líneas propias
que el sistema oculta del streaming:

```
[WEB: SI]
[CONSULTA: <consulta completa, AUTOCONTENIDA, sin pronombres ni ambigüedad>]
```

o, cuando no hace falta verificar:

```
[WEB: NO]
```

- `[WEB: SI]` → el modelo declara que el dato puede variar en el tiempo
  (precios, rankings, resultados, versiones, lanzamientos, disponibilidad) o que
  continúa un tema ya verificado con web.
- `[CONSULTA: ...]` → obligatoria con `[WEB: SI]`; debe ser autocontenida
  (resolver referencias usando el historial) e incluir contexto temporal.
- `[WEB: NO]` → respuesta con el contexto conversacional; no se busca nada.

### Precedencia con `buscar:` legacy durante la transición

El comando `buscar: consulta` sigue válido. `fusionar_comando_busqueda`
(`modulos/senal_web.py`) unifica ambas fuentes con esta precedencia:

1. `[WEB: SI]` + `[CONSULTA]` → usa la consulta de la señal.
2. `[WEB: SI]` sin `[CONSULTA]` + `buscar:` → usa el legacy (warning).
3. Sin señal + `buscar:` → comportamiento exacto de antes.
4. `[WEB: NO]` sin `buscar:` → no se busca.
5. `[WEB: NO]` + `buscar:` → se conserva `buscar:` + warning (transición).

Garantía: si el modelo declara `[WEB: SI]`, Python **siempre** ejecuta la
búsqueda con la consulta resultante. La ejecución es determinística.

## 3. Marcador `[TEMA WEB ANTERIOR]`

Cuando existe evidencia web de turnos previos (`config.estado.obtener_evidencia_web()`
no vacía), se inyecta un marcador en el contexto de la primera generación:

- Indica que en un turno anterior hubo verificación web y que, **si el turno
  actual continúa el mismo tema**, se debe re-verificar con web.
- Si el turno introduce un tema diferente, el modelo **no hereda** la obligación.

Python no determina si el turno pertenece al mismo tema: esa decisión es
semántica y la toma el modelo. Python solo condiciona la *presencia* del
marcador a que exista evidencia previa.

## 4. Ocultamiento de señales durante el streaming

`OcultadorStreamWeb` (`modulos/senal_web.py`) filtra las etiquetas del flujo de
chunks en tiempo real:

- Acumula el texto de la línea en curso y solo deja pasar líneas **completas**
  que no sean señal.
- La última línea pendiente se retiene hasta `finalizar()` y se descarta si es
  señal.
- Soporta tokens partidos entre chunks (`[WE` + `B: SI]`).

Resultado: las señales **jamás** aparecen en UI, consola ni TTS, aunque lleguen
partidas.

## 5. Separación respuesta cruda vs. respuesta limpia

- **Respuesta cruda** (`respuesta_ia`): incluye las etiquetas; es lo que el
  parser necesita para decidir. Se conserva internamente.
- **Respuesta limpia** (`draft_limpio = senal_web['respuesta_limpia']`): el
  borrador sin señales; es lo que se muestra y se usa como fallback de
  presentación/persistencia.
- `limpiar_respuesta_web(texto)` sanea cualquier texto (incluida la salida de la
  segunda generación) antes de UI/TTS/persistencia.

## 6. Segunda generación con evidencia

Cuando la señal es `[WEB: SI]`:

1. Se marca la burbuja actual como PROVISIONAL en la UI.
2. Python ejecuta una única búsqueda (`buscar_en_internet`).
3. Se arma el mensaje de la segunda generación (`construir_mensajes_segunda_generacion`
   en `modulos/mensajes_web.py`):
   - historial conversacional existente,
   - pregunta actual,
   - un **marcador neutro** de modelo (nunca el borrador, para que la respuesta
     no se base en posibles alucinaciones de la primera generación),
   - reglas estrictas de evidencia + evidencia web de consultas anteriores +
     resultados actuales.
4. La segunda generación responde con temperatura baja y **solo con lo que la
   evidencia confirme** (distingue confirmado/inferido/no-encontrado/
   contradictorio; no inventa y no confunde "no encontrado" con "no existe").
5. La respuesta verificada **reemplaza** al borrador provisional (nunca se
   concatena).
6. La evidencia real del turno se persiste (rotación FIFO, máx. 3 entradas) en
   una lista separada (`evidencia_web`), disponible para futuros follow-ups.

Módulos clave:

- `modulos/senal_web.py` — señal, parser, ocultador, fusión legacy, marcador.
- `modulos/mensajes_web.py` — construcción de la segunda generación, evidencia
  persistida, mensaje de modelo persistido, decisión de presentación.
- `modulos/ia.py` — integración del flujo en `enviar_a_gemini`.
- `modulos/prompts.py` — protocolo `[WEB: SI/NO]` en prompts general y gamer.

## 7. Resultado de validación

| Check | Resultado |
|---|---|
| `pytest -q` (venv 3.13) | **108 passed** |
| `compileall config.py modulos tests` | **OK** |
| `node --check gui/app.js` | **OK** |

Prueba funcional real (API Gemini + DuckDuckGo, harness temporal fuera del repo):

| Escenario | Señal | Búsquedas | 2ª generación |
|---|---|---|---|
| E1 — pregunta que requiere web | `[WEB: SI]` + `[CONSULTA: ...]` | 1 | 1 |
| E2 — pregunta conceptual | `[WEB: NO]` | 0 | 0 |
| E3 — follow-up del mismo tema (marcador presente) | `[WEB: SI]` + `[CONSULTA: ...]` autocontenida | 1 | 1 |
| E4 — tema diferente con evidencia previa | `[WEB: NO]` | 0 | 0 |

- UI y consola **sin exposición de señales** en los 4 escenarios.
- En E1 y E3 la segunda generación recibió `[RESULTADOS DE BÚSQUEDA]` (evidencia)
  y la respuesta final citó fuentes y fechas.
- En E2 y E4 el marcador estaba presente (evidencia previa) pero el modelo no
  heredó la búsqueda.
