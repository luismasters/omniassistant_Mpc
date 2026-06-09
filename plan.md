Plan de Acción: Estabilización y Persistencia de Contexto

Objetivo Principal: Resolver la pérdida de contexto al cambiar de pestaña/modo y eliminar los cuelgues (congelamientos) del asistente OmniAssistant.

⚠️ DIRECTIVA ESTRICTA PARA EL MODO PROGRAMADOR (PREVENCIÓN DE BUGS DE RUTA)
Para evitar errores [Errno 2], al usar el comando de guardado, la sintaxis DEBE ser matemáticamente exacta:
guardar_archivo: nombre_del_archivo.py || contenido
NUNCA agregues explicaciones, asteriscos, comillas ni texto adicional antes del separador ||. La ruta debe ser 100% limpia.

🔍 Diagnóstico: Causas Raíz

Pérdida del texto del input al cambiar de ventana

Archivo: main_gui.py (Líneas 344-362)

Problema: El método _clear_placeholder borra todo el contenido al recibir foco (FocusIn), incluso si el usuario había escrito texto real antes de cambiar de pestaña.

Pérdida del historial de chat al cambiar de modo

Archivo: main_gui.py (Método _cambiar_modo)

Problema: Al cambiar de modo (Ej. General a Programador), se destruyen las burbujas visuales sin guardar el historial del modo anterior.

Riesgo de cuelgue por MCP sin timeout

Archivo: ia.py, cliente_mcp.py

Problema: Las llamadas a funciones externas (Ej. servidor MCP) no tienen timeout. Si el servidor se cuelga, el hilo de IA en main_gui.py se bloquea indefinidamente.

Inestabilidad por logging deficiente

Archivo: logger.py, main_gui.py

Problema: Faltan manejadores globales para capturar excepciones no esperadas. Un error silencioso mata el programa sin dejar rastro.

⚠️ Análisis de Riesgos

Riesgo

Impacto

Mitigación

Sandbox bloquea escritura en workspace externo

Alto

Ejecutar el Paso 1 primero: Agregar soporte dinámico para WORKSPACE_ACTUAL en el Sandbox.

DeepSeek falla al editar archivos muy grandes

Medio

Hacer los cambios paso a paso, enfocándose en un archivo a la vez.

Restaurar burbujas lentas si hay muchos mensajes

Bajo

Limitar la restauración a los últimos 50 mensajes de la memoria.

Timeout MCP mal implementado causa falsos fallos

Medio

Probar con un timeout generoso (15 segundos) y loguear el evento.

🛠️ Plan de Ejecución Priorizado (6 Pasos)

Paso 1 — Flexibilizar sandbox para workspace anclado (URGENTE)

Archivos a modificar: config.py, archivos.py

Acciones:

En config.py, renombrar SANDBOX_BASE o crear una lista RUTAS_SEGURAS = [SANDBOX_BASE].

En archivos.py, modificar es_ruta_segura() para que, si existe un WORKSPACE_ACTUAL anclado (pasado desde ia.py), este también sea considerado una zona 100% segura para escribir.

Paso 2 — Corregir pérdida del input al cambiar pestaña

Archivos a modificar: main_gui.py

Acciones:

Agregar variable self.texto_sin_enviar = "" para guardar el texto real al perder el foco (FocusOut).

En _clear_placeholder, borrar el texto SOLO si el contenido exacto es el placeholder.

En FocusIn, restaurar self.texto_sin_enviar si contiene algo.

Paso 3 — Guardar historial visual por modo

Archivos a modificar: main_gui.py, ia.py

Acciones:

Agregar diccionario self.historiales = {} en el __init__ de la app.

En _cambiar_modo, guardar la lista de CONTEXTO_CHAT en el diccionario usando el modo actual como llave ANTES de limpiar la pantalla.

Al ingresar a un nuevo modo, restaurar su CONTEXTO_CHAT desde el diccionario y repintar las burbujas visuales.

Paso 4 — Agregar timeout a llamadas IA y MCP

Archivos a modificar: ia.py, cliente_mcp.py

Acciones:

Envolver cada llamada a funciones en bloques try/except específicos.

Agregar un parámetro timeout=15 a las conexiones.

Registrar cualquier timeout con logger.warning.

Paso 5 — Mejorar logging con archivo en disco

Archivos a modificar: logger.py, main_gui.py

Acciones:

Instalar sys.excepthook en main_gui.py para capturar cualquier error general que cierre el programa y guardarlo en el log.

Paso 6 — Verificación y Pruebas

Acciones:

Probar el cambio de pestañas sin perder texto no enviado.

Probar el salto entre Modo General, Planificador y Programador verificando que las burbujas reaparezcan.