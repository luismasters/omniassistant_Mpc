# Plan de Acción: Solución de Problemas con Git en OmniAssistant

## Estado actual (Análisis)
- Los módulos `git_bot.py`, `ia.py` y `controlador_acciones.py` tienen fallas de diseño que impiden el correcto funcionamiento de las operaciones Git (push, pull, commit).
- **Problemas clave**:
  1. Instancia global de `GitManager` en `ia.py` → bloquea toda la app si el repositorio no está inicializado.
  2. `git_bot.py` no verifica existencia de remoto ni ejecuta `pull` antes de `push`.
  3. No hay manejo de errores descriptivo ni logging.
  4. `ia.py` ignora el resultado de `push()`.
  5. Falta configuración de Git en `config.py`.

## Objetivo
Restablecer el flujo Git completo (commit, pull, push) con retroalimentación clara al usuario y sin comprometer la estabilidad de la aplicación.

## Plan de Acción (Orden de implementación)

### Fase 1: Estabilización de la inicialización
**Riesgo**: Si `GitManager()` falla al importar `ia.py`, la GUI no arranca.  
**Dependencias**: `main_gui.py`, `ia.py`, `git_bot.py`, `config.py`.  
**Tareas**:
1. **Retrasar la creación del objeto GitManager**:
   - En lugar de instanciar globalmente en `ia.py`, crear el objeto dentro del método `ejecutar_intencion` cuando se detecte la intención `"git_push"`, o mediante un método `_obtener_git_manager()` que haga la inicialización bajo demanda.
   - Manejar la excepción de inicialización del repositorio (por ejemplo, `InvalidGitRepositoryError`) y devolver un mensaje de error amigable en lugar de lanzarla.
2. **Añadir en `config.py` una bandera `GIT_ENABLED`**:
   - Variable booleana que indique si se debe usar Git. Por defecto `True`. Si al inicializar `GitManager` falla, se desactiva automáticamente.
3. **Modificar `controlador_acciones.py`**:
   - Agregar un `try/except` alrededor de la importación de `AsistenteIA` (o de la llamada que lo usa) para que un error en Git no detenga la GUI. Puede mostrar un mensaje informativo al usuario.

**Criterio de éxito**: La GUI se inicia sin errores, aunque Git no esté configurado.

### Fase 2: Mejora del módulo `git_bot.py`
**Riesgo**: Operaciones Git fallan silenciosamente o generan conflictos.  
**Dependencias**: `git_bot.py` solo; no afecta a otros módulos hasta Fase 3.  
**Tareas**:
4. **Agregar verificación de remoto**:
   - En el método `push()`, antes de ejecutar, verificar si `repo.remotes` contiene al menos un remoto. Si no, retornar un mensaje de error: `"No hay remoto configurado. Ejecuta 'git remote add origin <url>' manualmente."`.
5. **Implementar secuencia `pull -> add -> commit -> push`**:
   - Antes de `push()`, ejecutar `repo.git.pull()` (o `repo.git.pull('--rebase')` para evitar merges automáticos). Capturar posibles conflictos y reportar.
6. **Verificar cambios antes del commit**:
   - Usar `repo.is_dirty()` o `repo.index.diff(None)` para saber si hay archivos modificados. Si no hay cambios, evitar el commit y devolver mensaje `"No hay cambios que subir."`.
7. **Mejorar mensajes de error**:
   - En todos los `except` capturar el mensaje específico (ej: `str(e)`) y retornarlo en lugar de `False` genérico.
   - Agregar logging con `import logging` para registrar cada operación (info, warning, error).
8. **Agregar método `init_repo()`**:
   - Método separado que intente inicializar el repositorio si no existe, llamando a `git.Repo.init(BASE_DIR)`. Esto permitiría que Git funcione incluso si el usuario no ha hecho `git init`.

**Criterio de éxito**: `GitManager` puede hacer pull, commit y push con retroalimentación detallada.

### Fase 3: Integración en `ia.py` y `controlador_acciones.py`
**Riesgo**: Cambios en `git_bot.py` no se reflejan en la interfaz.  
**Dependencias**: `ia.py`, `controlador_acciones.py`, `main_gui.py`.  
**Tareas**:
9. **Actualizar `ejecutar_intencion` en `ia.py`**:
   - Llamar a `git_manager.push()` solo si se obtuvo el manager exitosamente.
   - Almacenar el resultado (mensaje de error o éxito) en una variable como `self.ultimo_resultado_git`.
   - Mostrar el resultado en la interfaz, por ejemplo, actualizando un widget de estado.
10. **Modificar `controlador_acciones.py`**:
    - Si existe un método `ejecutar_accion_git`, asegurarse de que pase el control a `ia.ejecutar_intencion` con la intención correcta y que capture el resultado para mostrarlo en la GUI.
11. **Opcional: Agregar botón de estado Git en `main_gui.py`**:
    - Widget que muestre si Git está habilitado y el último resultado de una operación Git.

**Criterio de éxito**: El usuario puede ejecutar "subir a GitHub" desde la GUI y recibe un mensaje claro de éxito, error o advertencia.

## Dependencias externas
- **gitpython**: Asegurar que esté instalado (`pip install gitpython`). Incluir en `requirements.txt`.
- **Configuración de red/autenticación**: El usuario debe tener configurado el remoto con credenciales (token SSH o HTTPS). No se maneja dentro del código; solo se reporta si falta.

## Riesgos y mitigaciones
- **Riesgo**: Cambiar la inicialización tardía puede romper otras partes del código que esperen `git_manager` como global.  
  **Mitigación**: Crear un **patrón singleton** o una variable de clase en `AsistenteIA` que se inicialice bajo demanda y se reutilice.
- **Riesgo**: El `pull` automático puede sobrescribir cambios locales no commiteados.  
  **Mitigación**: Antes de `pull`, verificar si hay cambios sin commit; si los hay, abortar y pedir al usuario que los commitée primero.
- **Riesgo**: Conflictos de merge durante el `pull`.  
  **Mitigación**: Usar `repo.git.pull('--rebase')` y, si falla, capturar el error y devolver mensaje para que el usuario resuelva manualmente.

## Prioridades
1. **Fase 1** es crítica para que la aplicación arranque.
2. **Fase 2** es necesaria para que las operaciones Git funcionen correctamente.
3. **Fase 3** es la integración final (menos prioritaria si la Fase 1 y 2 están hechas, el usuario puede usar Git a través de código externo).

## Próximos pasos (Acciones concretas para el desarrollador)
- Revisar `ia.py` y mover la instancia de `GitManager` a dentro del método `ejecutar_intencion`.
- En `git_bot.py`, refactorizar `push()` según las tareas 4-8.
- Probar manualmente con `python -c "from modulos.git_bot import GitManager; gm = GitManager(); print(gm.push())"`.
- Actualizar `PROJECT_STATE.md` con el progreso.

---

**Nota**: Este plan no incluye implementación de código final, solo diseño lógico y secuencia de acciones. El desarrollador deberá traducir cada tarea a código siguiendo las reglas del proyecto.