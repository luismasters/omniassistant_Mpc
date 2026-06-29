# Ejemplos — Skill Control de Audio

## Ejemplo 1: Subir volumen
**Usuario:** "Argus, subí el volumen."  
**Skill activa:** Sí (palabra clave "volumen").  
**Acción emitida:**
```
audio: subir_volumen
```
**Respuesta de Argus:** "Listo, volumen subido al 60%."

---

## Ejemplo 2: Establecer volumen exacto
**Usuario:** "Poné el volumen al 40%."  
**Skill activa:** Sí.  
**Acción emitida:**
```
audio: establecer_volumen 40
```
**Respuesta de Argus:** "Volumen al 40%, hecho."

---

## Ejemplo 3: Silenciar una app
**Usuario:** "Silenciá Discord."  
**Skill activa:** Sí.  
**Acción emitida:**
```
audio: silenciar_app Discord
```
**Respuesta de Argus:** "Discord silenciado."

---

## Ejemplo 4: Ver volumen actual
**Usuario:** "¿A cuánto está el volumen?"  
**Skill activa:** Sí.  
**Acción emitida:**
```
audio: obtener_volumen
```
**Respuesta de Argus:** "El volumen maestro está al 55%."

---

## Ejemplo 5: Ver apps con audio
**Usuario:** "¿Qué apps tienen sonido?"  
**Skill activa:** Sí.  
**Acción emitida:**
```
audio: listar_apps
```
**Respuesta de Argus:** "Ahora mismo tienen audio: Discord (80%), Brave (100%), Street Fighter 6 (100%)."

---

## Ejemplo 6: Cambiar dispositivo de salida
**Usuario:** "Pasá el audio al headset."  
**Skill activa:** Sí.  
**Acción emitida:**
```
audio: cambiar_dispositivo headset
```
**Respuesta de Argus:** "Audio cambiado al headset."

---

## Ejemplo 7: Silenciar todo
**Usuario:** "Silenciá todo."  
**Skill activa:** Sí.  
**Acción emitida:**
```
audio: silenciar
```
**Respuesta de Argus:** "Audio maestro silenciado."

---

## Ejemplo 8: Volumen al máximo
**Usuario:** "Subí el volumen a tope."  
**Skill activa:** Sí.  
**Acción emitida:**
```
audio: establecer_volumen 100
```
**Respuesta de Argus:** "Volumen al máximo (100%)."