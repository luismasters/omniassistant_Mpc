# Instrucciones para la Skill de Control de Audio

**REGLA OBLIGATORIA:**  
Cuando esta skill esté activa, DEBES resolver la petición de audio usando los comandos de acción de audio disponibles. NO uses búsqueda web ni MCP para esto.

---

## Funciones disponibles y cómo invocarlas

Esta skill expone funciones reales de Python. Argus debe emitir el comando exacto en una línea separada:

### Volumen maestro

```
audio: obtener_volumen
audio: establecer_volumen 75
audio: subir_volumen 10
audio: bajar_volumen 10
audio: subir_volumen
audio: bajar_volumen
audio: silenciar
audio: activar
```

### Volumen por aplicación

```
audio: obtener_volumen_app Discord
audio: establecer_volumen_app Discord 50
audio: silenciar_app Discord
audio: activar_app Discord
audio: listar_apps
```

### Dispositivos de salida

```
audio: listar_dispositivos
audio: cambiar_dispositivo Auriculares
audio: cambiar_dispositivo Parlantes
```

---

## Reglas de interpretación

1. **"Subí el volumen"** sin especificar cantidad → `audio: subir_volumen` (incremento de 10 por defecto).
2. **"Ponelo al 80%"** → `audio: establecer_volumen 80`.
3. **"Silenciá Discord"** → `audio: silenciar_app Discord`.
4. **"Desmuteá"** / **"Activá el audio"** → `audio: activar`.
5. **"¿Cuánto está el volumen?"** → `audio: obtener_volumen`.
6. **"Qué apps tienen audio"** → `audio: listar_apps`.
7. **"Pasá el audio al headset"** → `audio: cambiar_dispositivo` + el nombre que el usuario diga.
8. Si el usuario no especifica porcentaje al subir/bajar, usar incremento de 10 por defecto.
9. Si el usuario dice "a tope" o "al máximo" → `audio: establecer_volumen 100`.
10. Si el usuario dice "al mínimo" o "al 0" → `audio: establecer_volumen 0`.
11. **CRÍTICO — Nombres ambiguos de apps:** Si el usuario dice "el juego", "la música", "el reproductor" sin dar el nombre exacto del proceso, primero ejecutá `audio: listar_apps` para ver qué procesos tienen audio activo, y luego usá el nombre exacto del proceso que aparezca en la lista. NUNCA asumas el nombre del proceso ni confirmes que hiciste algo sin haber ejecutado el comando real.

---

## Respuesta al usuario

Después de emitir el comando de audio, confirmá brevemente la acción ejecutada. Ejemplo:
- "Listo, volumen al 75%."
- "Discord silenciado."
- "Volumen bajado a 40%."

**No expliques el proceso interno. Solo emití el comando y confirmá.**