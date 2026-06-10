[contenido del plan]\n"`

El archivo `modulos/ia.py` ha sido guardado correctamente con el cambio aplicado.--
### 📋 Verificación del cambio

La línea actualizada ahora se ve así en el prompt del Planificador:
```python
"- Para ACTUALIZAR EL PLAN: guardar_archivo: plan.md ---CONTENIDO--- [contenido del plan]\n"
```
Ahora cuando el Modo Planificador genere instrucciones, usará el formato `---CONTENIDO---` que el interceptor de acciones sí reconoce, permitiendo que `plan.md` se cree físicamente en el disco.

¿Quieres que proceda con el **Paso 2** (mejorar `editar_archivo` para ignorar espacios/mayúsculas) o prefieres probar primero este cambio?