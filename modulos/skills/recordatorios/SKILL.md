# Skill: Recordatorios (`recordatorios`)

**Descripción:**  
Permite a Argus programar, gestionar y notificar recordatorios temporales (relativos, fijos, diarios, recurrentes, fechas lejanas y cumpleaños) con avisos animados en la nube de diálogo de EMO y soporte para gestión manual desde la interfaz.

**Cuándo usar esta Skill:**  
- Cuando el usuario pida recordar algo ("recordame...", "avisame en 15 minutos...", "recordatorio a las 20hs").
- Cuando se mencionen temporizadores, alarmas, citas, fechas lejanas ("el 25 de agosto sale x juego").
- Cuando se registren cumpleaños o eventos con aviso previo ("recuerdame que el 6 de diciembre cumple años X").
- Cuando se soliciten secuencias o múltiples horarios ("tomar agua a las 10am, 2pm y 6pm").
- Palabras clave: `recordame`, `recordatorio`, `avisame`, `alarma`, `timer`, `temporizador`, `en X minutos`, `a las`, `cumpleaños`, `cumple`, `agenda`.

**Herramientas que usa:**  
- `gestor_recordatorios.py` (Clase `GestorRecordatorios`)
- Persistencia en JSON `recordatorios.json`

**Versión:** 1.0  
**Autor:** Luis & Antigravity  
**Fecha de creación:** 2026-07-22
