import os
import re
import difflib
import threading
import modulos.ia as motor_ia
from modulos.archivos import crear_carpeta, escribir_archivo, leer_contenido_archivo
from modulos.sistema import ejecutar_comando_sistema, buscar_archivo_o_carpeta, obtener_ventanas_activas, forzar_ventana_a_monitor
from modulos.memoria import guardar_snapshot, cargar_snapshot

# ─── Función para dividir comandos múltiples en una línea ──────────────
def _dividir_comandos(linea: str) -> list[str]:
    """Divide una línea en múltiples comandos si contiene varios verbos."""
    verbos = ["abrir:", "navegar:", "mover:", "cerrar:", "explorar:", "mover."]
    indices = []
    lower = linea.lower()
    for v in verbos:
        pos = lower.find(v)
        while pos != -1:
            indices.append((pos, v))
            pos = lower.find(v, pos + 1)
    if len(indices) <= 1:
        return [linea]
    indices.sort(key=lambda x: x[0])
    comandos = []
    for i, (pos, v) in enumerate(indices):
        if i == len(indices) - 1:
            cmd = linea[pos:].strip()
        else:
            next_pos = indices[i+1][0]
            cmd = linea[pos:next_pos].strip()
        comandos.append(cmd)
    return comandos

def procesar_acciones_ia(respuesta_ia, texto_usuario, ui_callback, modo_voz):
    """
    Controlador centralizado para parsear y ejecutar acciones solicitadas por la IA.
    Retorna un comando de búsqueda si lo detecta, o "INTERRUPTED" si la acción bloquea el flujo.
    """
    import config
    WORKSPACE_ACTUAL = config.estado.workspace_actual
    CONTEXTO_CHAT = config.estado.contexto_chat
    ARCHIVOS_EN_MEMORIA = config.estado.archivos_en_memoria
    MODO_ACTUAL = config.estado.modo_actual

    reportes_acciones = []
    comando_busqueda_detectado = None

    # --- PROTECCIÓN SANDBOX INTELIGENTE ---
    if MODO_ACTUAL != "general" and not WORKSPACE_ACTUAL and any(cmd in respuesta_ia.lower() for cmd in ["guardar_archivo:", "editar_archivo:", "reemplazar_bloque:", "crear_carpeta:", "eliminar:", "<replace_block>", "<write_file>"]):
        msg_err = "⚠️ Error de seguridad: No se pueden modificar archivos sin un Workspace seleccionado."
        print(f"[ERROR] {msg_err}")
        if ui_callback: ui_callback("⚙️ Sistema", msg_err, "#ff4500")
        CONTEXTO_CHAT.append({'role': 'user', 'parts': [f"[SISTEMA] {msg_err}"]})
        return "INTERRUPTED"

    # 0. LECTURAS EN FORMATO XML (DeepSeek V4 Fallback)
    if "<read_file>" in respuesta_ia.lower():
        for m in re.finditer(r'<read_file>\s*<path>\s*(.+?)\s*</path>\s*</read_file>', respuesta_ia, re.IGNORECASE):
            ruta_corta = m.group(1).replace('<', '').replace('>', '').strip()
            ruta_real = os.path.join(WORKSPACE_ACTUAL, ruta_corta) if WORKSPACE_ACTUAL and not os.path.isabs(ruta_corta) else ruta_corta
            if ruta_real in ARCHIVOS_EN_MEMORIA:
                if ui_callback: ui_callback("⚙️ Sistema", f"📄 (Caché) Archivo {ruta_corta} ya está en memoria.", "#80868B")
                continue
            contenido_leido = leer_contenido_archivo(ruta_real)
            if len(contenido_leido) > 80000:
                contenido_leido = contenido_leido[:80000] + "\n... [CONTENIDO TRUNCADO POR SEGURIDAD]"
            ARCHIVOS_EN_MEMORIA.add(ruta_real)
            CONTEXTO_CHAT.append({'role': 'user', 'parts': [f"[CONTENIDO DE '{ruta_real}']:\n{contenido_leido}"]})
            if ui_callback: ui_callback("⚙️ Sistema", f"📄 Archivo cargado (XML): {ruta_corta}", "#80868B")

    # 1. GUARDAR ARCHIVO (Soporta Markdown y XML)
    if "guardar_archivo:" in respuesta_ia.lower() or "<write_file>" in respuesta_ia.lower():
        try:
            operaciones_guardar = []
            for m in re.finditer(r'guardar_archivo:\s*(.+?)\s*-{3,}CONTENIDO-{3,}\s*([\s\S]*?)(?=\nguardar_archivo:|<write_file>|$)', respuesta_ia, re.IGNORECASE):
                operaciones_guardar.append((m.group(1), m.group(2)))
            for m in re.finditer(r'<write_file>\s*<path>\s*(.+?)\s*</path>\s*<content>\s*([\s\S]*?)\s*</content>\s*</write_file>', respuesta_ia, re.IGNORECASE):
                operaciones_guardar.append((m.group(1), m.group(2)))

            for ruta_f, contenido_f in operaciones_guardar:
                ruta_f = ruta_f.replace('`', '').replace('*', '').replace('<', '').replace('>', '').strip()
                contenido_f = contenido_f.strip()
                contenido_f = re.sub(r'^```\w*\n?|\n?```$', '', contenido_f).strip()
                ruta_f_abs = os.path.join(WORKSPACE_ACTUAL, ruta_f) if WORKSPACE_ACTUAL and not os.path.isabs(ruta_f) else ruta_f
                resultado_escritura = escribir_archivo(ruta_f_abs, contenido_f)
                if "ERROR" in resultado_escritura:
                    CONTEXTO_CHAT.append({'role': 'user', 'parts': [f"[RESULTADO ESCRITURA] Fallo al guardar {ruta_f}: {resultado_escritura}"]})
                    if ui_callback: ui_callback("⚙️ Sistema", f"❌ Error guardando {ruta_f}: {resultado_escritura}", "#ff4500")
                else:
                    if ruta_f_abs in ARCHIVOS_EN_MEMORIA:
                        for msg in CONTEXTO_CHAT:
                            if isinstance(msg.get('parts', [''])[0], str) and f"[CONTENIDO DE '{ruta_f_abs}']:" in msg['parts'][0]:
                                msg['parts'][0] = f"[CONTENIDO DE '{ruta_f_abs}']:\n{contenido_f}"
                    CONTEXTO_CHAT.append({'role': 'user', 'parts': [f"[RESULTADO ESCRITURA] Archivo {ruta_f} guardado correctamente."] })
                    if ui_callback: ui_callback("⚙️ Sistema", f"✅ Archivo guardado: {ruta_f}", "#86efac")
        except Exception as e:
            print(f"❌ Error local al guardar el archivo: {e}")

    # 2. REEMPLAZAR BLOQUE
    if "reemplazar_bloque:" in respuesta_ia.lower() or "<replace_block>" in respuesta_ia.lower() or "<reemplazar_bloque>" in respuesta_ia.lower():
        try:
            operaciones_reemplazo = []
            for m in re.finditer(r'reemplazar_bloque:\s*(.+?)\s*-{3,}BUSCAR-{3,}\s*([\s\S]*?)\s*-{3,}REEMPLAZAR-{3,}\s*([\s\S]*?)\s*-{3,}FIN-{3,}', respuesta_ia, re.IGNORECASE):
                operaciones_reemplazo.append((m.group(1), m.group(2), m.group(3)))
            for m in re.finditer(r'<replace_block>\s*<path>\s*(.+?)\s*</path>\s*<search>\s*([\s\S]*?)\s*</search>\s*<replace>\s*([\s\S]*?)\s*</replace>\s*</replace_block>', respuesta_ia, re.IGNORECASE):
                operaciones_reemplazo.append((m.group(1), m.group(2), m.group(3)))
            for m in re.finditer(r'<reemplazar_bloque>\s*<ruta>\s*(.+?)\s*</ruta>\s*<buscar>\s*([\s\S]*?)\s*</buscar>\s*<reemplazar>\s*([\s\S]*?)\s*</reemplazar>\s*</reemplazar_bloque>', respuesta_ia, re.IGNORECASE):
                operaciones_reemplazo.append((m.group(1), m.group(2), m.group(3)))

            for ruta_edit, buscar_edit, reemplazar_edit in operaciones_reemplazo:
                ruta_edit = ruta_edit.replace('`','').replace('*','').replace('<', '').replace('>', '').strip()
                buscar_edit = re.sub(r'^```\w*\n?|\n?```$', '', buscar_edit.strip()).strip('\n')
                reemplazar_edit = re.sub(r'^```\w*\n?|\n?```$', '', reemplazar_edit.strip()).strip('\n')
                ruta_real_edit = os.path.join(WORKSPACE_ACTUAL, ruta_edit) if WORKSPACE_ACTUAL and not os.path.isabs(ruta_edit) else ruta_edit
                contenido_actual = leer_contenido_archivo(ruta_real_edit)
                if not contenido_actual.startswith("ERROR"):
                    contenido_norm = contenido_actual.replace('\r\n', '\n')
                    buscar_norm = buscar_edit.replace('\r\n', '\n')
                    count_exacto = contenido_norm.count(buscar_norm)
                    if count_exacto == 1:
                        nuevo_contenido = contenido_norm.replace(buscar_norm, reemplazar_edit, 1)
                        escribir_archivo(ruta_real_edit, nuevo_contenido)
                        for msg in CONTEXTO_CHAT:
                            if isinstance(msg.get('parts', [''])[0], str) and f"[CONTENIDO DE '{ruta_real_edit}']:" in msg['parts'][0]:
                                msg['parts'][0] = f"[CONTENIDO DE '{ruta_real_edit}']:\n{nuevo_contenido}"
                        exito_msg = f"[RESULTADO EDICIÓN] Modificación exacta exitosa en {ruta_edit}"
                        CONTEXTO_CHAT.append({'role': 'user', 'parts': [exito_msg]})
                        if ui_callback: ui_callback("⚙️ Sistema", f"✅ Bloque actualizado con precisión en {ruta_edit}", "#86efac")
                        continue
                    elif count_exacto > 1:
                        msg_fallo = f"❌ Ambigüedad: El bloque aparece {count_exacto} veces. Dame más líneas de contexto."
                        CONTEXTO_CHAT.append({'role': 'user', 'parts': [msg_fallo]})
                        if ui_callback: ui_callback("⚙️ Sistema", f"❌ Ambigüedad en {ruta_edit}", "#ff4500")
                        continue
                    lineas_buscar = buscar_norm.split('\n')
                    patron_regex = ""
                    for linea in lineas_buscar:
                        if linea.strip():
                            patron_regex += r'[ \t]*' + re.escape(linea.strip()) + r'[ \t]*\n'
                        else:
                            patron_regex += r'\s*\n'
                    patron_regex = patron_regex.rstrip('\n')
                    coincidencias = list(re.finditer(patron_regex, contenido_norm))
                    if len(coincidencias) == 1:
                        match = coincidencias[0]
                        nuevo_contenido = contenido_norm[:match.start()] + reemplazar_edit + contenido_norm[match.end():]
                        escribir_archivo(ruta_real_edit, nuevo_contenido)
                        for msg in CONTEXTO_CHAT:
                            if isinstance(msg.get('parts', [''])[0], str) and f"[CONTENIDO DE '{ruta_real_edit}']:" in msg['parts'][0]:
                                msg['parts'][0] = f"[CONTENIDO DE '{ruta_real_edit}']:\n{nuevo_contenido}"
                        exito_msg = f"[RESULTADO EDICIÓN] Modificación flexible (Regex) exitosa en {ruta_edit}"
                        CONTEXTO_CHAT.append({'role': 'user', 'parts': [exito_msg]})
                        if ui_callback: ui_callback("⚙️ Sistema", f"✅ Bloque ajustado (Flexible) en {ruta_edit}", "#86efac")
                    elif len(coincidencias) > 1:
                        msg_fallo = f"❌ Ambigüedad en búsqueda flexible. Demasiados resultados similares."
                        CONTEXTO_CHAT.append({'role': 'user', 'parts': [msg_fallo]})
                        if ui_callback: ui_callback("⚙️ Sistema", f"❌ Ambigüedad flexible en {ruta_edit}", "#ff4500")
                    else:
                        msg_fallo = f"❌ Fallo crítico: No encontré el bloque en {ruta_edit}."
                        CONTEXTO_CHAT.append({'role': 'user', 'parts': [msg_fallo]})
                        if ui_callback: ui_callback("⚙️ Sistema", f"❌ Bloque no encontrado en {ruta_edit}", "#ff4500")
                else:
                    msg_fallo = f"❌ Error leyendo '{ruta_edit}' para editar: {contenido_actual}"
                    print(msg_fallo)
                    if ui_callback: ui_callback("⚙️ Sistema", msg_fallo, "#ff4500")
                    CONTEXTO_CHAT.append({'role': 'user', 'parts': [msg_fallo]})
        except Exception as e:
            print(f"❌ Error en reemplazo de bloque: {e}")

    # 3. ANÁLISIS LÍNEA POR LÍNEA
    lineas = respuesta_ia.split('\n')
    in_code_block = False

    for linea in lineas:
        if linea.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        comandos = _dividir_comandos(linea)
        for cmd in comandos:
            cmd_limpia = cmd.lower().replace("[", "").replace("]", "").replace("*", "").replace("`", "").strip()
            cmd_limpia = re.sub(r'^(\-\s|\d+\.\s)', '', cmd_limpia)

            if "guardar_archivo:" in cmd_limpia or "---contenido---" in cmd_limpia or "<write_file>" in cmd_limpia:
                continue
            if any(t in cmd_limpia for t in ["reemplazar_bloque:", "---buscar---", "---reemplazar---", "---fin---", "<replace_block>", "<reemplazar_bloque>", "<buscar>", "<reemplazar>"]):
                continue
            if "<read_file>" in cmd_limpia:
                continue

            # LECTURA DE ARCHIVOS
            if cmd_limpia.startswith("leer_archivo:"):
                idx = cmd.lower().find("leer_archivo:") + 13
                raw_path = cmd[idx:].strip()
                ruta_corta = raw_path.split('|')[0].replace('`','').replace('*','').replace('<', '').replace('>', '').strip()
                ruta_real = os.path.join(WORKSPACE_ACTUAL, ruta_corta) if WORKSPACE_ACTUAL and not os.path.isabs(ruta_corta) else ruta_corta
                if ruta_real in ARCHIVOS_EN_MEMORIA:
                    if ui_callback: ui_callback("⚙️ Sistema", f"📄 (Caché) Archivo {ruta_corta} ya está en memoria.", "#80868B")
                    continue
                contenido_leido = leer_contenido_archivo(ruta_real)
                if len(contenido_leido) > 80000:
                    contenido_leido = contenido_leido[:80000] + "\n... [CONTENIDO TRUNCADO POR SEGURIDAD]"
                ARCHIVOS_EN_MEMORIA.add(ruta_real)
                CONTEXTO_CHAT.append({'role': 'user', 'parts': [f"[CONTENIDO DE '{ruta_real}']:\n{contenido_leido}"]})
                if ui_callback: ui_callback("⚙️ Sistema", f"📄 Archivo cargado en memoria: {ruta_corta}", "#80868B")
                continue

            # EDICIÓN DE 1 LÍNEA
            if cmd_limpia.startswith("editar_archivo:"):
                match = re.search(r'editar_archivo:\s*(.+?)\s*\*?\|\*?\s*buscar:\s*(.+?)\s*\*?\|\*?\s*reemplazar:\s*(.+)', cmd, re.IGNORECASE)
                if match:
                    ruta_edit = match.group(1).replace('`','').replace('*','').replace('<', '').replace('>', '').strip()
                    buscar_edit = match.group(2).strip().strip('"\'`')
                    reemplazar_edit = match.group(3).strip().strip('"\'`')
                    ruta_real_edit = os.path.join(WORKSPACE_ACTUAL, ruta_edit) if WORKSPACE_ACTUAL and not os.path.isabs(ruta_edit) else ruta_edit
                    contenido_actual = leer_contenido_archivo(ruta_real_edit)
                    if not contenido_actual.startswith("ERROR"):
                        buscar_norm = " ".join(buscar_edit.split())
                        contenido_norm = " ".join(contenido_actual.split())
                        if buscar_norm in contenido_norm:
                            if buscar_edit in contenido_actual:
                                nuevo_contenido = contenido_actual.replace(buscar_edit, reemplazar_edit, 1)
                                if nuevo_contenido != contenido_actual:
                                    escribir_archivo(ruta_real_edit, nuevo_contenido)
                                    for msg in CONTEXTO_CHAT:
                                        if isinstance(msg.get('parts', [''])[0], str) and f"[CONTENIDO DE '{ruta_real_edit}']:" in msg['parts'][0]:
                                            msg['parts'][0] = f"[CONTENIDO DE '{ruta_real_edit}']:\n{nuevo_contenido}"
                                    CONTEXTO_CHAT.append({'role': 'user', 'parts': [f"[RESULTADO EDICIÓN] Modificación exitosa en {ruta_edit}"]})
                                    if ui_callback: ui_callback("⚙️ Sistema", f"✅ Edición rápida en {ruta_edit}", "#86efac")
                            else:
                                CONTEXTO_CHAT.append({'role': 'user', 'parts': [f"[RESULTADO EDICIÓN] Difiere en espacios. Sé más preciso."]})
                        else:
                            CONTEXTO_CHAT.append({'role': 'user', 'parts': [f"[RESULTADO EDICIÓN] Fallo: Texto no encontrado."]})
                            if ui_callback: ui_callback("⚙️ Sistema", f"❌ Texto no encontrado en {ruta_edit}", "#ff4500")
                    else:
                        msg_fallo = f"❌ Error leyendo '{ruta_edit}' para editar: {contenido_actual}"
                        if ui_callback: ui_callback("⚙️ Sistema", msg_fallo, "#ff4500")
                continue

            # SNAPSHOT
            if cmd_limpia.startswith("snapshot:"):
                if WORKSPACE_ACTUAL:
                    resumen_estado = cmd[cmd.lower().find("snapshot:") + 9:].replace('<', '').replace('>', '').strip()
                    guardar_snapshot(WORKSPACE_ACTUAL, resumen_estado)
                    config.estado.snapshot_actual = cargar_snapshot(WORKSPACE_ACTUAL)
                    if ui_callback: ui_callback("⚙️ Sistema", "📸 Snapshot guardado", "#FFA500")
                continue

            # BUSCAR WEB
            if cmd_limpia.startswith("buscar:"):
                comando_busqueda_detectado = cmd[cmd.lower().find("buscar:") + 7:].replace('<', '').replace('>', '').strip()
                continue

            # GITHUB
            if cmd_limpia.startswith(("github:", "<github>")):
                idx = cmd.lower().find("github:") + 7 if "github:" in cmd_limpia else cmd.lower().find("<github>") + 8
                ruta_sucia = cmd[idx:].replace('</github>', '').strip()
                ruta_corta = ruta_sucia.split("---")[0].strip() if "---" in ruta_sucia else ruta_sucia.strip()
                ruta_real = WORKSPACE_ACTUAL if WORKSPACE_ACTUAL else buscar_archivo_o_carpeta(ruta_corta)
                if ruta_real:
                    config.estado.pendiente_de_git = {"accion": "github", "ruta": ruta_real, "url_custom": None}
                    msg_alerta = f"⚠️ ALERTA: Vas a subir el proyecto a GitHub:\n'{ruta_real}'\n\n¿Autorizás el Push? (SÍ / NO)."
                    if ui_callback: ui_callback("🤖 Cortana", msg_alerta, "#FF4500")
                    CONTEXTO_CHAT.extend([{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [msg_alerta]}])
                    return "INTERRUPTED"
                continue

            if cmd_limpia.startswith("github_reset:"):
                datos_git = cmd[cmd.lower().find("github_reset:") + 13:].strip()
                partes = datos_git.split("||", 1) if "||" in datos_git else [datos_git, ""]
                ruta_real = WORKSPACE_ACTUAL if WORKSPACE_ACTUAL else buscar_archivo_o_carpeta(partes[0].strip())
                if ruta_real:
                    config.estado.pendiente_de_git = {"accion": "github_reset", "ruta": ruta_real, "url_custom": partes[1].strip() if len(partes)>1 else None}
                    msg_alerta = f"⚠️ ALERTA CRÍTICA: Vas a DESVINCULAR y subir el repo.\n\n¿Autorizás esta operación crítica? (SÍ / NO)"
                    if ui_callback: ui_callback("🤖 Cortana", msg_alerta, "#FF4500")
                    CONTEXTO_CHAT.extend([{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [msg_alerta]}])
                    return "INTERRUPTED"
                continue

            if cmd_limpia.startswith("git_comando:"):
                datos_git = cmd[cmd.lower().find("git_comando:") + 12:].strip()
                partes = datos_git.split("||", 1) if "||" in datos_git else ["", ""]
                ruta_real = WORKSPACE_ACTUAL if WORKSPACE_ACTUAL else buscar_archivo_o_carpeta(partes[0].strip())
                if ruta_real and partes[1].strip():
                    config.estado.pendiente_de_git = {"accion": "git_libre", "ruta": ruta_real, "url_custom": partes[1].strip()}
                    msg_alerta = f"⚠️ ALERTA: Vas a ejecutar un comando libre en Git.\nComando: {partes[1].strip()}\n\n¿Autorizás? (SÍ / NO)"
                    if ui_callback: ui_callback("🤖 Cortana", msg_alerta, "#FF4500")
                    CONTEXTO_CHAT.extend([{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [msg_alerta]}])
                    return "INTERRUPTED"
                continue

            # CREAR CARPETA
            if cmd_limpia.startswith("crear_carpeta:"):
                ruta_corta = cmd[cmd.lower().find("crear_carpeta:") + 14:].replace("[", "").replace("]", "").replace("*", "").replace('<', '').replace('>', '').strip()
                ruta_final = os.path.join(WORKSPACE_ACTUAL, ruta_corta) if WORKSPACE_ACTUAL and not os.path.isabs(ruta_corta) else ruta_corta
                res_carp = crear_carpeta(ruta_final)
                if ui_callback: ui_callback("⚙️ Sistema", f"📁 {res_carp}", "#80868B")
                continue

            # ESCANEAR PROYECTO CRAWLER
            if cmd_limpia.startswith("escanear_proyecto:"):
                if WORKSPACE_ACTUAL:
                    if ui_callback: ui_callback("⚙️ Sistema", "🔍 Iniciando Crawler...", "#80868B")
                    try:
                        from modulos.crawler import extraer_codigo_proyecto
                        codigo_completo = extraer_codigo_proyecto(WORKSPACE_ACTUAL)
                        prompt_analisis = f"""Actúa como el Arquitecto Principal del proyecto.
        A continuación te proporciono el código completo de mi aplicación actual:

        {codigo_completo}

        Tu tarea es crear un documento de estado (PROJECT_STATE.md) que servirá como 'Fuente de la Verdad' para futuras planificaciones.
        El documento DEBE contener estrictamente:
        1. **Resumen Ejecutivo:** Propósito general del software.
        2. **Arquitectura:** Lista de los módulos principales y para qué sirve cada archivo.
        3. **Estado Actual:** Qué funcionalidades ya están construidas y operativas.
        4. **Deuda Técnica / Próximos Pasos:** Posibles errores ocultos, funciones repetitivas que deban limpiarse o mejoras de arquitectura.

        Responde ÚNICAMENTE con el Markdown final estructurado. No uses saludos, ni confirmaciones."""
                        if ui_callback: ui_callback("⚙️ Sistema", "🧠 Analizando arquitectura global con DeepSeek...", "#80868B")
                        response = motor_ia.cliente_deepseek.chat.completions.create(
                            model="deepseek-reasoner",
                            messages=[{"role": "user", "content": prompt_analisis}]
                        )
                        estado_md = response.choices[0].message.content
                        if estado_md.startswith("```markdown"):
                            estado_md = estado_md.split("```markdown")[1].rsplit("```", 1)[0].strip()
                        elif estado_md.startswith("```"):
                            estado_md = estado_md.split("```")[1].rsplit("```", 1)[0].strip()
                        ruta_state = os.path.join(WORKSPACE_ACTUAL, "PROJECT_STATE.md")
                        escribir_archivo(ruta_state, estado_md)
                        msg_exito = "✅ ¡PROJECT_STATE.md generado con éxito! El Planificador ya tiene visión total del código."
                        if ui_callback: ui_callback("⚙️ Sistema", msg_exito, "#86efac")
                        print(msg_exito)
                    except Exception as e:
                        if ui_callback: ui_callback("⚙️ Sistema", f"❌ Error en el Crawler: {e}", "#ff4500")
                else:
                    if ui_callback: ui_callback("🤖 Cortana", "Necesito estar dentro del Modo Planificador o Programador para saber qué proyecto escanear.", "#FFA500")
                continue

            # COMANDOS DE SISTEMA
            if cmd_limpia.startswith(("abrir:", "navegar:", "cerrar:", "mover:", "explorar:")):
                verbo = cmd_limpia.split(":")[0]
                resto = cmd[cmd.lower().find(":")+1:].strip()
                resultado = ejecutar_comando_sistema(f"{verbo}:{resto}")
                if resultado:
                    # Si el resultado es una sugerencia (empieza con "⚠️ No encontré el programa")
                    if resultado.startswith("⚠️ No encontré el programa"):
                        # Mostrar como mensaje de sistema y NO agregar a reportes de acciones
                        if ui_callback:
                            ui_callback("⚙️ Sistema", resultado, "#FFA500")
                        # Guardar en el contexto para que la IA sepa que el usuario debe responder
                        CONTEXTO_CHAT.append({'role': 'user', 'parts': [f"[SISTEMA] {resultado}"]})
                    else:
                        reportes_acciones.append(f"Acción SO: {resultado}")
                continue

    if reportes_acciones:
        texto_reporte = "\n".join([f"*({r})*" for r in reportes_acciones])
        print(texto_reporte)
        if ui_callback: ui_callback("⚙️ Sistema", texto_reporte, "#80868B")

    return comando_busqueda_detectado