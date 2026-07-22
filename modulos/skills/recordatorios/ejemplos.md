# Ejemplos de la Skill: Recordatorios

### Ejemplo 1: Recordatorio Relativo Simple
**Usuario:** "Recordame en 15 minutos que tengo que sacar el pan del horno"  
**Argus:**  
```
recordatorio: crear | en 15 minutos | Sacar el pan del horno
```  
¡Entendido! Te recordaré sacar el pan del horno en 15 minutos. 🍞

---

### Ejemplo 2: Medicina Recurrente Diaria
**Usuario:** "Recuérdame tomar la medicina rosuvastatina a las 9pm todos los días"  
**Argus:**  
```
recordatorio: crear | a las 21:00 | Tomar la medicina rosuvastatina | diario
```  
¡Anotado! Te avisaré todos los días a las 21:00 hs para tomar tu rosuvastatina. 💊

---

### Ejemplo 3: Múltiples Horarios Diarios
**Usuario:** "Recuérdame tomar agua todos los días a las 10am, 2pm y 6pm"  
**Argus:**  
```
recordatorio: crear | a las 10:00 | Tomar agua | diario
recordatorio: crear | a las 14:00 | Tomar agua | diario
recordatorio: crear | a las 18:00 | Tomar agua | diario
```  
¡Programado! Te recordaré tomar agua todos los días a las 10:00, 14:00 y 18:00 hs. 💧

---

### Ejemplo 4: Fecha Lejana (Primer mensaje del día)
**Usuario:** "Recuérdame que el 25 de agosto sale la nueva liga de PoE 2"  
**Argus:**  
```
recordatorio: crear | 25 de agosto | Sale la nueva liga de PoE 2 | sin_hora
```  
¡Guardado! El 25 de agosto, apenas me hables por primera vez en el día, te notificaré sobre la nueva liga de Path of Exile 2. ⚔️

---

### Ejemplo 5: Cumpleaños con Aviso Previo
**Usuario:** "Recuérdame que el 6 de diciembre cumple años Yuskeli"  
**Argus:**  
```
recordatorio: crear | 6 de diciembre | Cumpleaños de Yuskeli | cumpleaños
```  
¡Perfecto! Te recordaré el cumpleaños de Yuskeli el día anterior (5 de dic) y el mismo 6 de diciembre apenas inicies la jornada. 🎂

---

### Ejemplo 6: Secuencia de Inicio y Apagado
**Usuario:** "Recuérdame encender el calentador a las 10am y apagarlo a las 11am, luego encenderlo a las 4pm y apagarlo a las 5pm"  
**Argus:**  
```
recordatorio: crear | a las 10:00 | Encender el calentador
recordatorio: crear | a las 11:00 | Apagar el calentador
recordatorio: crear | a las 16:00 | Encender el calentador
recordatorio: crear | a las 17:00 | Apagar el calentador
```  
¡Hecho! He programado el ciclo completo del calentador a las 10:00, 11:00, 16:00 y 17:00 hs. ♨️
