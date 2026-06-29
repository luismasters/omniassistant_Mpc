# Skill: Control de Audio

**Descripción:**  
Permite a Argus controlar el audio del sistema Windows: volumen maestro, volumen por aplicación, silenciar/activar, listar apps con audio activo y cambiar dispositivo de salida de audio (parlantes, headset, etc.).

**Cuándo usar esta Skill:**  
- Cuando el usuario pida subir, bajar o establecer el volumen (maestro o de una app específica).
- Cuando el usuario quiera silenciar o activar el audio (general o de una app).
- Cuando el usuario pregunte cuánto está el volumen o qué apps tienen audio.
- Cuando el usuario quiera cambiar el dispositivo de salida (headset, parlantes, monitor).
- Cuando el usuario use palabras como: volumen, subir, bajar, silenciar, mutear, unmute, audio, sonido, headset, parlantes, auriculares, salida de audio.

**Herramientas que usa:**  
- `audio_control.py` (funciones locales via pycaw)
- PowerShell (para cambio de dispositivo, requiere módulo AudioDeviceCmdlets)

**Dependencias:**  
```
pip install pycaw comtypes
```

**Versión:** 1.0  
**Autor:** Luis  
**Fecha de creación:** 2026-06-25