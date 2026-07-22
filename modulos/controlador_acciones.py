import os
import re
import difflib
import threading
import modulos.ia as motor_ia
from modulos.archivos import crear_carpeta, escribir_archivo, leer_contenido_archivo, es_ruta_segura
from modulos.sistema import ejecutar_comando_sistema, buscar_archivo_o_carpeta, obtener_ventanas_activas, forzar_ventana_a_monitor
from modulos.memoria import guardar_snapshot, cargar_snapshot
from modulos.logger import logger

# ─── Función para dividir comandos múltiples en una línea ──────────────
def _dividir_comandos(linea: str) -> list[str]:
    """
    Divide una línea en múltiples comandos si contiene varios verbos de acción
    y remueve el texto conversacional previo en la misma línea.
    """
    verbos = [
        "abrir:", "navegar:", "mover:", "cerrar:", "explorar:", "audio:", "recordatorio:",
        "leer_archivo:", "editar_archivo:", "guardar_archivo:", "reemplazar_bloque:",
        "crear_carpeta:", "buscar:", "guardar_en_boveda:", "escanear_proyecto:",
        "github:", "github_reset:", "git_comando:", "snapshot:"
    ]
    indices = []
    lower = linea.lower()
    for v in verbos:
        pos = lower.find(v)
        while pos != -1:
            indices.append((pos, v))
            pos = lower.find(v, pos + len(v))

    if not indices:
        return [linea]

    indices.sort(key=lambda x: x[0])
    comandos = []
    for i, (pos, v) in enumerate(indices):
        if i == len(indices) - 1:
            cmd = linea[pos:].strip()
        else:
            next_pos = indices[i+1][0]
            cmd = linea[pos:next_pos].strip()
        # Limpiar conjunciones o puntuaciones al final (ej. "abrir: youtube y")
        cmd = re.sub(r'(\s+(y|e|and|\.|\,)\s*)$', '', cmd, flags=re.IGNORECASE).strip()
        if cmd:
            comandos.append(cmd)
    return comandos

# ─── Función auxiliar para normalizar rutas ──────────────────────────────
def _normalizar_ruta(ruta: str, workspace: str) -> str:
    """
    Normaliza una ruta relativa o absoluta, y la resuelve contra el workspace.
    Retorna la ruta absoluta normalizada, o None si no es válida.
    """
    if not ruta:
        return None
    # Eliminar caracteres problemáticos
    ruta_limpia = ruta.replace('`', '').replace('*', '').replace('<', '').replace('>', '').strip()
    if not ruta_limpia:
        return None
    # Si es relativa y hay workspace, combinar
    if not os.path.isabs(ruta_limpia) and workspace:
        ruta_abs = os.path.join(workspace, ruta_limpia)
    else:
        ruta_abs = ruta_limpia
    # Normalizar y obtener absoluta
    ruta_normalizada = os.path.normpath(os.path.abspath(ruta_abs))
    return ruta_normalizada

# ─── Función para verificar que una ruta está permitida ──────────────────
def _validar_ruta(ruta: str, workspace: str, modo: str) -> tuple[bool, str]:
    """
    Valida que la ruta sea segura según el modo y el workspace.
    Retorna (es_valida, mensaje_error).
    """
    if not ruta:
        return False, "Ruta vacía"
    ruta_norm = _normalizar_ruta(ruta, workspace)
    if not ruta_norm:
        return False, "Ruta no válida"
    # En modo general, permitir todo (pero advertir)
    if modo == "general":
        if not es_ruta_segura(ruta_norm):
            logger.warning(f"⚠️ Ruta fuera del sandbox en modo general: {ruta_norm}")
            # Aún así permitimos, pero lo advertimos
        return True, ruta_norm
    # En modos avanzados, solo permitir dentro del workspace
    if workspace and ruta_norm.startswith(os.path.normpath(os.path.abspath(workspace))):
        return True, ruta_norm
    else:
        logger.warning(f"Intento de acceder fuera del workspace: {ruta_norm} (workspace: {workspace})")
        return False, f"Ruta fuera del workspace: {ruta_norm}"

def _frasear_resultado_audio_para_voz(resultado: str) -> str:
    """
    Convierte el resultado técnico de un comando de audio (pensado para
    mostrarse en pantalla) en una frase corta y natural para leer en voz.
    FIX: antes se leía el string crudo tal cual — con emojis, dos puntos,
    paréntesis, y en los casos de error hasta instrucciones técnicas de
    instalación de varias líneas (ej. "Install-Module -Name
    AudioDeviceCmdlets"). Sonaba robótico y desproporcionadamente largo
    para lo que debería ser una simple confirmación hablada. El texto en
    pantalla no se toca — sigue siendo técnico y preciso a propósito,
    solo cambia lo que efectivamente se lee en voz.
    """
    texto = resultado.strip()
    for simbolo in ("✅", "⚠️", "❌", "🔊"):
        texto = texto.replace(simbolo, "")
    texto = texto.strip()

    # Solo se lee la primera línea/oración; el detalle técnico (cómo
    # instalar un módulo, etc.) queda disponible en pantalla nada más.
    primera_linea = texto.split("\n")[0].strip()

    # Reformulaciones puntuales para sonar más conversacional
    reemplazos = {
        "Dispositivo cambiado a:": "Listo, cambié la salida a",
        "Dispositivo de audio cambiado": "Listo, cambié el dispositivo de audio",
        "Audio maestro silenciado": "Listo, silencié el audio",
        "Audio maestro activado": "Listo, activé el audio",
        "Volumen maestro establecido al": "Listo, volumen al",
    }
    for viejo, nuevo in reemplazos.items():
        if primera_linea.startswith(viejo):
            primera_linea = primera_linea.replace(viejo, nuevo, 1)
            break

    return primera_linea.strip()


def procesar_acciones_ia(respuesta_ia, texto_usuario, ui_callback, modo_voz):
    """
    Controlador centralizado para parsear y ejecutar acciones solicitadas por la IA.
    Retorna un comando de búsqueda si lo detecta, o "INTERRUPTED" si la acción bloquea el flujo.
    """
    import config
    WORKSPACE_ACTUAL = config.estado.workspace_actual
    CONTEXTO_CHAT = config.estado.obtener_contexto_copia()
    ARCHIVOS_EN_MEMORIA = config.estado.obtener_archivos_copia()
    MODO_ACTUAL = config.estado.modo_actual

    reportes_acciones = []
    comando_busqueda_detectado = None

    # --- PROTECCIÓN SANDBOX INTELIGENTE (previo a cualquier acción de archivo) ---
    if MODO_ACTUAL != "general" and not WORKSPACE_ACTUAL and any(cmd in respuesta_ia.lower() for cmd in ["guardar_archivo:", "editar_archivo:", "reemplazar_bloque:", "crear_carpeta:", "eliminar:", "<replace_block>", "<write_file>"]):
        msg_err = "⚠️ Error de seguridad: No se pueden modificar archivos sin un Workspace seleccionado."
        logger.error(msg_err)
        if ui_callback:
            ui_callback("⚙️ Sistema", msg_err, "#ff4500")
        config.estado.agregar_mensaje_chat(
            {'role': 'user', 'parts': [f"[SISTEMA] {msg_err}"]},
            contar_para_perfil=False
        )
        return "INTERRUPTED"

    # 0. LECTURAS EN FORMATO XML (DeepSeek V4 Fallback)
    if "<read_file>" in respuesta_ia.lower():
        for m in re.finditer(r'<read_file>\s*<path>\s*(.+?)\s*</path>\s*</read_file>', respuesta_ia, re.IGNORECASE):
            ruta_corta = m.group(1).strip()
            ruta_valida, resultado = _validar_ruta(ruta_corta, WORKSPACE_ACTUAL, MODO_ACTUAL)
            if not ruta_valida:
                if ui_callback:
                    ui_callback("⚙️ Sistema", f"❌ Ruta no permitida: {ruta_corta}", "#FF4500")
                continue
            ruta_real = resultado
            if ruta_real in ARCHIVOS_EN_MEMORIA:
                if ui_callback:
                    ui_callback("⚙️ Sistema", f"📄 (Caché) Archivo {ruta_corta} ya está en memoria.", "#80868B")
                continue
            contenido_leido = leer_contenido_archivo(ruta_real)
            if len(contenido_leido) > 80000:
                contenido_leido = contenido_leido[:80000] + "\n... [CONTENIDO TRUNCADO POR SEGURIDAD]"
            config.estado.agregar_archivo_memoria(ruta_real)
            config.estado.agregar_mensaje_chat(
                {'role': 'user', 'parts': [f"[CONTENIDO DE '{ruta_real}']:\n{contenido_leido}"]},
                contar_para_perfil=False
            )
            if ui_callback:
                ui_callback("⚙️ Sistema", f"📄 Archivo cargado (XML): {ruta_corta}", "#80868B")

    # 1. GUARDAR ARCHIVO (Soporta Markdown y XML)
    if "guardar_archivo:" in respuesta_ia.lower() or "<write_file>" in respuesta_ia.lower():
        try:
            operaciones_guardar = []
            for m in re.finditer(r'guardar_archivo:\s*(.+?)\s*-{3,}CONTENIDO-{3,}\s*([\s\S]*?)(?=\nguardar_archivo:|<write_file>|$)', respuesta_ia, re.IGNORECASE):
                operaciones_guardar.append((m.group(1), m.group(2)))
            for m in re.finditer(r'<write_file>\s*<path>\s*(.+?)\s*</path>\s*<content>\s*([\s\S]*?)\s*</content>\s*</write_file>', respuesta_ia, re.IGNORECASE):
                operaciones_guardar.append((m.group(1), m.group(2)))

            for ruta_f, contenido_f in operaciones_guardar:
                ruta_valida, resultado = _validar_ruta(ruta_f, WORKSPACE_ACTUAL, MODO_ACTUAL)
                if not ruta_valida:
                    if ui_callback:
                        ui_callback("⚙️ Sistema", f"❌ Ruta no permitida: {ruta_f}", "#FF4500")
                    continue
                ruta_f_abs = resultado
                contenido_f = contenido_f.strip()
                contenido_f = re.sub(r'^```\w*\n?|\n?```$', '', contenido_f).strip()
                resultado_escritura = escribir_archivo(ruta_f_abs, contenido_f)
                if "ERROR" in resultado_escritura:
                    logger.error(f"Error al guardar {ruta_f_abs}: {resultado_escritura}")
                    config.estado.agregar_mensaje_chat(
                        {'role': 'user', 'parts': [f"[RESULTADO ESCRITURA] Fallo al guardar {ruta_f}: {resultado_escritura}"]},
                        contar_para_perfil=False
                    )
                    if ui_callback:
                        ui_callback("⚙️ Sistema", f"❌ Error guardando {ruta_f}: {resultado_escritura}", "#ff4500")
                else:
                    if ruta_f_abs in ARCHIVOS_EN_MEMORIA:
                        for msg in CONTEXTO_CHAT:
                            if isinstance(msg.get('parts', [''])[0], str) and f"[CONTENIDO DE '{ruta_f_abs}']:" in msg['parts'][0]:
                                msg['parts'][0] = f"[CONTENIDO DE '{ruta_f_abs}']:\n{contenido_f}"
                    config.estado.agregar_mensaje_chat(
                        {'role': 'user', 'parts': [f"[RESULTADO ESCRITURA] Archivo {ruta_f} guardado correctamente."]},
                        contar_para_perfil=False
                    )
                    if ui_callback:
                        ui_callback("⚙️ Sistema", f"✅ Archivo guardado: {ruta_f}", "#86efac")
        except Exception as e:
            logger.exception("Error en bloque guardar_archivo")
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
                ruta_valida, resultado = _validar_ruta(ruta_edit, WORKSPACE_ACTUAL, MODO_ACTUAL)
                if not ruta_valida:
                    if ui_callback:
                        ui_callback("⚙️ Sistema", f"❌ Ruta no permitida: {ruta_edit}", "#FF4500")
                    continue
                ruta_real_edit = resultado

                buscar_edit = re.sub(r'^```\w*\n?|\n?```$', '', buscar_edit.strip()).strip('\n')
                reemplazar_edit = re.sub(r'^```\w*\n?|\n?```$', '', reemplazar_edit.strip()).strip('\n')
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
                        config.estado.agregar_mensaje_chat(
                            {'role': 'user', 'parts': [exito_msg]},
                            contar_para_perfil=False
                        )
                        if ui_callback:
                            ui_callback("⚙️ Sistema", f"✅ Bloque actualizado con precisión en {ruta_edit}", "#86efac")
                        continue
                    elif count_exacto > 1:
                        msg_fallo = f"❌ Ambigüedad: El bloque aparece {count_exacto} veces. Dame más líneas de contexto."
                        config.estado.agregar_mensaje_chat(
                            {'role': 'user', 'parts': [msg_fallo]},
                            contar_para_perfil=False
                        )
                        if ui_callback:
                            ui_callback("⚙️ Sistema", f"❌ Ambigüedad en {ruta_edit}", "#ff4500")
                        continue
                    # Búsqueda flexible
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
                        config.estado.agregar_mensaje_chat(
                            {'role': 'user', 'parts': [exito_msg]},
                            contar_para_perfil=False
                        )
                        if ui_callback:
                            ui_callback("⚙️ Sistema", f"✅ Bloque ajustado (Flexible) en {ruta_edit}", "#86efac")
                    elif len(coincidencias) > 1:
                        msg_fallo = f"❌ Ambigüedad en búsqueda flexible. Demasiados resultados similares."
                        config.estado.agregar_mensaje_chat(
                            {'role': 'user', 'parts': [msg_fallo]},
                            contar_para_perfil=False
                        )
                        if ui_callback:
                            ui_callback("⚙️ Sistema", f"❌ Ambigüedad flexible en {ruta_edit}", "#ff4500")
                    else:
                        msg_fallo = f"❌ Fallo crítico: No encontré el bloque en {ruta_edit}."
                        config.estado.agregar_mensaje_chat(
                            {'role': 'user', 'parts': [msg_fallo]},
                            contar_para_perfil=False
                        )
                        if ui_callback:
                            ui_callback("⚙️ Sistema", f"❌ Bloque no encontrado en {ruta_edit}", "#ff4500")
                else:
                    msg_fallo = f"❌ Error leyendo '{ruta_edit}' para editar: {contenido_actual}"
                    logger.error(msg_fallo)
                    if ui_callback:
                        ui_callback("⚙️ Sistema", msg_fallo, "#ff4500")
                    config.estado.agregar_mensaje_chat(
                        {'role': 'user', 'parts': [msg_fallo]},
                        contar_para_perfil=False
                    )
        except Exception as e:
            logger.exception("Error en reemplazo de bloque")
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

            # Asegurar alineación directa al verbo si existe prefijo conversacional
            verbos_clave = ["abrir:", "navegar:", "cerrar:", "mover:", "explorar:", "audio:", "recordatorio:", "leer_archivo:", "editar_archivo:", "guardar_archivo:", "reemplazar_bloque:", "crear_carpeta:", "buscar:", "guardar_en_boveda:", "escanear_proyecto:", "github:"]
            for v_prefix in verbos_clave:
                pos_v = cmd_limpia.find(v_prefix)
                if pos_v > 0:
                    cmd_limpia = cmd_limpia[pos_v:].strip()
                    cmd = cmd[pos_v:].strip()
                    break

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
                ruta_corta = raw_path.split('|')[0].strip()
                ruta_valida, resultado = _validar_ruta(ruta_corta, WORKSPACE_ACTUAL, MODO_ACTUAL)
                if not ruta_valida:
                    if ui_callback:
                        ui_callback("⚙️ Sistema", f"❌ Ruta no permitida: {ruta_corta}", "#FF4500")
                    continue
                ruta_real = resultado
                if ruta_real in ARCHIVOS_EN_MEMORIA:
                    if ui_callback:
                        ui_callback("⚙️ Sistema", f"📄 (Caché) Archivo {ruta_corta} ya está en memoria.", "#80868B")
                    continue
                contenido_leido = leer_contenido_archivo(ruta_real)
                if len(contenido_leido) > 80000:
                    contenido_leido = contenido_leido[:80000] + "\n... [CONTENIDO TRUNCADO POR SEGURIDAD]"
                config.estado.agregar_archivo_memoria(ruta_real)
                config.estado.agregar_mensaje_chat(
                    {'role': 'user', 'parts': [f"[CONTENIDO DE '{ruta_real}']:\n{contenido_leido}"]},
                    contar_para_perfil=False
                )
                if ui_callback:
                    ui_callback("⚙️ Sistema", f"📄 Archivo cargado en memoria: {ruta_corta}", "#80868B")
                continue

            # CONTROL DE AUDIO
            if cmd_limpia.startswith("audio:"):
                try:
                    from modulos.skills.control_audio.audio_control import (
                        obtener_volumen, establecer_volumen, subir_volumen, bajar_volumen,
                        silenciar, obtener_volumen_app, establecer_volumen_app,
                        silenciar_app, listar_apps_con_audio, listar_dispositivos_audio,
                        cambiar_dispositivo_audio
                    )
                    partes_audio = cmd[cmd.lower().find("audio:") + 6:].strip().split()
                    if not partes_audio:
                        continue
                    subcmd = partes_audio[0].lower()
                    # FIX: el modelo suele emitir nombres entre comillas, ej.
                    # `audio: cambiar_dispositivo "Altavoces (JBL Go4 Lu)"` o
                    # `audio: silenciar_app "Discord"`. El .split() de arriba
                    # separa por espacios pero NO despoja las comillas, así
                    # que quedaban pegadas como parte literal del argumento
                    # (ej. '"Altavoces' y 'Lu)"'), rompiendo cualquier
                    # comparación por nombre en las funciones de audio_control.py.
                    # Se limpian acá, una sola vez, para todos los subcomandos.
                    args_audio = [a.strip('"').strip("'") for a in partes_audio[1:]] if len(partes_audio) > 1 else []

                    resultado_audio = ""
                    if subcmd == "obtener_volumen":
                        resultado_audio = obtener_volumen()
                    elif subcmd == "establecer_volumen" and args_audio:
                        resultado_audio = establecer_volumen(int(args_audio[0]))
                    elif subcmd == "subir_volumen":
                        incremento = int(args_audio[0]) if args_audio else 10
                        resultado_audio = subir_volumen(incremento)
                    elif subcmd == "bajar_volumen":
                        decremento = int(args_audio[0]) if args_audio else 10
                        resultado_audio = bajar_volumen(decremento)
                    elif subcmd == "silenciar":
                        resultado_audio = silenciar(True)
                    elif subcmd == "activar":
                        resultado_audio = silenciar(False)
                    elif subcmd == "obtener_volumen_app" and args_audio:
                        resultado_audio = obtener_volumen_app(" ".join(args_audio))
                    elif subcmd == "establecer_volumen_app" and len(args_audio) >= 2:
                        nombre_app = " ".join(args_audio[:-1])
                        pct = int(args_audio[-1])
                        resultado_audio = establecer_volumen_app(nombre_app, pct)
                    elif subcmd == "silenciar_app" and args_audio:
                        resultado_audio = silenciar_app(" ".join(args_audio), True)
                    elif subcmd == "activar_app" and args_audio:
                        resultado_audio = silenciar_app(" ".join(args_audio), False)
                    elif subcmd == "listar_apps":
                        resultado_audio = listar_apps_con_audio()
                    elif subcmd == "listar_dispositivos":
                        resultado_audio = listar_dispositivos_audio()
                    elif subcmd == "cambiar_dispositivo" and args_audio:
                        resultado_audio = cambiar_dispositivo_audio(" ".join(args_audio))
                    else:
                        resultado_audio = f"⚠️ Comando de audio no reconocido: {subcmd}"

                    if resultado_audio:
                        config.estado.agregar_mensaje_chat(
                            {'role': 'user', 'parts': [f"[RESULTADO AUDIO]: {resultado_audio}"]},
                            contar_para_perfil=False
                        )
                        if ui_callback:
                            ui_callback("⚙️ Sistema", f"🔊 {resultado_audio}", "#80868B")
                        # FIX: antes el resultado REAL del comando de audio solo se
                        # mostraba como texto de sistema, nunca se anunciaba por voz.
                        # Como el modelo ya venía narrando una confirmación provisional
                        # ("Aplicando el cambio...") mientras streameaba, sin esto el
                        # usuario en modo voz se quedaba sin saber si la acción
                        # realmente funcionó o falló — tenía que mirar la pantalla.
                        if modo_voz:
                            try:
                                from modulos.audio_custom import hablar_no_bloqueante
                                hablar_no_bloqueante(_frasear_resultado_audio_para_voz(resultado_audio))
                            except Exception:
                                logger.exception("Error anunciando por voz el resultado de audio")
                except ImportError:
                    msg = "⚠️ Skill control_audio: falta instalar pycaw. Ejecutá: pip install pycaw comtypes"
                    if ui_callback:
                        ui_callback("⚙️ Sistema", msg, "#FFA500")
                except Exception as e:
                    logger.exception(f"Error en comando de audio: {cmd}")
                    if ui_callback:
                        ui_callback("⚙️ Sistema", f"❌ Error en control de audio: {str(e)[:80]}", "#FF4500")
                continue

            # EDICIÓN DE 1 LÍNEA
            if cmd_limpia.startswith("editar_archivo:"):
                match = re.search(r'editar_archivo:\s*(.+?)\s*\*?\|\*?\s*buscar:\s*(.+?)\s*\*?\|\*?\s*reemplazar:\s*(.+)', cmd, re.IGNORECASE)
                if match:
                    ruta_edit = match.group(1).strip()
                    ruta_valida, resultado = _validar_ruta(ruta_edit, WORKSPACE_ACTUAL, MODO_ACTUAL)
                    if not ruta_valida:
                        if ui_callback:
                            ui_callback("⚙️ Sistema", f"❌ Ruta no permitida: {ruta_edit}", "#FF4500")
                        continue
                    ruta_real_edit = resultado
                    buscar_edit = match.group(2).strip().strip('"\'`')
                    reemplazar_edit = match.group(3).strip().strip('"\'`')
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
                                    config.estado.agregar_mensaje_chat(
                                        {'role': 'user', 'parts': [f"[RESULTADO EDICIÓN] Modificación exitosa en {ruta_edit}"]},
                                        contar_para_perfil=False
                                    )
                                    if ui_callback:
                                        ui_callback("⚙️ Sistema", f"✅ Edición rápida en {ruta_edit}", "#86efac")
                            else:
                                config.estado.agregar_mensaje_chat(
                                    {'role': 'user', 'parts': [f"[RESULTADO EDICIÓN] Difiere en espacios. Sé más preciso."]},
                                    contar_para_perfil=False
                                )
                        else:
                            config.estado.agregar_mensaje_chat(
                                {'role': 'user', 'parts': [f"[RESULTADO EDICIÓN] Fallo: Texto no encontrado."]},
                                contar_para_perfil=False
                            )
                            if ui_callback:
                                ui_callback("⚙️ Sistema", f"❌ Texto no encontrado en {ruta_edit}", "#ff4500")
                    else:
                        msg_fallo = f"❌ Error leyendo '{ruta_edit}' para editar: {contenido_actual}"
                        if ui_callback:
                            ui_callback("⚙️ Sistema", msg_fallo, "#ff4500")
                continue

            # SNAPSHOT
            if cmd_limpia.startswith("snapshot:"):
                if WORKSPACE_ACTUAL:
                    resumen_estado = cmd[cmd.lower().find("snapshot:") + 9:].replace('<', '').replace('>', '').strip()
                    guardar_snapshot(WORKSPACE_ACTUAL, resumen_estado)
                    config.estado.snapshot_actual = cargar_snapshot(WORKSPACE_ACTUAL)
                    if ui_callback:
                        ui_callback("⚙️ Sistema", "📸 Snapshot guardado", "#FFA500")
                continue

            # BUSCAR WEB
            if cmd_limpia.startswith("buscar:"):
                comando_busqueda_detectado = cmd[cmd.lower().find("buscar:") + 7:].replace('<', '').replace('>', '').strip()
                continue

            # GUARDAR EN BÓVEDA (con confirmación)
            if cmd_limpia.startswith("guardar_en_boveda:"):
                idx = cmd.lower().find("guardar_en_boveda:") + 18
                dato = cmd[idx:].strip().strip('"\'`')
                if dato:
                    config.estado.pendiente_de_boveda = dato
                    msg_alerta = f"⚠️ ¿Confirmás que querés guardar esto en la bóveda?\n\n{dato[:200]}"
                    if ui_callback:
                        ui_callback("🤖 Argus", msg_alerta, "#FFA500")
                    config.estado.agregar_mensaje_chat({'role': 'user', 'parts': [texto_usuario]})
                    config.estado.agregar_mensaje_chat({'role': 'model', 'parts': [msg_alerta]})
                    return "INTERRUPTED"
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
                    if ui_callback:
                        ui_callback("🤖 Argus", msg_alerta, "#FF4500")
                    config.estado.agregar_mensaje_chat({'role': 'user', 'parts': [texto_usuario]})
                    config.estado.agregar_mensaje_chat({'role': 'model', 'parts': [msg_alerta]})
                    return "INTERRUPTED"
                continue

            if cmd_limpia.startswith("github_reset:"):
                datos_git = cmd[cmd.lower().find("github_reset:") + 13:].strip()
                partes = datos_git.split("||", 1) if "||" in datos_git else ["", ""]  # <--- CORREGIDO
                ruta_real = WORKSPACE_ACTUAL if WORKSPACE_ACTUAL else buscar_archivo_o_carpeta(partes[0].strip())
                if ruta_real:
                    config.estado.pendiente_de_git = {"accion": "github_reset", "ruta": ruta_real, "url_custom": partes[1].strip() if len(partes)>1 else None}
                    msg_alerta = f"⚠️ ALERTA CRÍTICA: Vas a DESVINCULAR y subir el repo.\n\n¿Autorizás esta operación crítica? (SÍ / NO)"
                    if ui_callback:
                        ui_callback("🤖 Argus", msg_alerta, "#FF4500")
                    config.estado.agregar_mensaje_chat({'role': 'user', 'parts': [texto_usuario]})
                    config.estado.agregar_mensaje_chat({'role': 'model', 'parts': [msg_alerta]})
                    return "INTERRUPTED"
                continue

            if cmd_limpia.startswith("git_comando:"):
                datos_git = cmd[cmd.lower().find("git_comando:") + 12:].strip()
                partes = datos_git.split("||", 1) if "||" in datos_git else ["", ""]  # <--- CORREGIDO
                ruta_real = WORKSPACE_ACTUAL if WORKSPACE_ACTUAL else buscar_archivo_o_carpeta(partes[0].strip())
                if ruta_real and partes[1].strip():
                    config.estado.pendiente_de_git = {"accion": "git_libre", "ruta": ruta_real, "url_custom": partes[1].strip()}
                    msg_alerta = f"⚠️ ALERTA: Vas a ejecutar un comando libre en Git.\nComando: {partes[1].strip()}\n\n¿Autorizás? (SÍ / NO)"
                    if ui_callback:
                        ui_callback("🤖 Argus", msg_alerta, "#FF4500")
                    config.estado.agregar_mensaje_chat({'role': 'user', 'parts': [texto_usuario]})
                    config.estado.agregar_mensaje_chat({'role': 'model', 'parts': [msg_alerta]})
                    return "INTERRUPTED"
                continue

            # CREAR CARPETA
            if cmd_limpia.startswith("crear_carpeta:"):
                ruta_corta = cmd[cmd.lower().find("crear_carpeta:") + 14:].strip()
                ruta_valida, resultado = _validar_ruta(ruta_corta, WORKSPACE_ACTUAL, MODO_ACTUAL)
                if not ruta_valida:
                    if ui_callback:
                        ui_callback("⚙️ Sistema", f"❌ Ruta no permitida: {ruta_corta}", "#FF4500")
                    continue
                ruta_final = resultado
                res_carp = crear_carpeta(ruta_final)
                if ui_callback:
                    ui_callback("⚙️ Sistema", f"📁 {res_carp}", "#80868B")
                continue

            # RECORDATORIOS
            if cmd_limpia.startswith("recordatorio:"):
                idx = cmd.lower().find("recordatorio:") + 13
                subcmd = cmd[idx:].strip()
                logger.debug(f"[RECORDATORIOS] Procesando subcmd: '{subcmd}'")
                from modulos.skills.recordatorios.gestor_recordatorios import gestor_recordatorios
                if subcmd.startswith("crear"):
                    resto = subcmd.replace("crear", "", 1).lstrip(" |:").strip()
                    logger.debug(f"[RECORDATORIOS] Resto después de 'crear': '{resto}'")
                    # Dividir por pipes respetando pipes literales o espacios
                    partes = [p.strip() for p in resto.split("|") if p.strip()]
                    logger.debug(f"[RECORDATORIOS] Partes parseadas: {partes}")
                    p1 = partes[0] if len(partes) > 0 else "en 10 minutos"
                    p2 = partes[1] if len(partes) > 1 else "Recordatorio sin título"
                    opciones = partes[2] if len(partes) > 2 else ""

                    # Auto-detectar si p1 o p2 es la expresión de tiempo
                    def _es_expresion_tiempo(s: str) -> bool:
                        s_l = s.lower()
                        return any(kw in s_l for kw in ["en ", "a las", "de ", ":", "mañana", "hoy", "cumple"]) or (any(c.isdigit() for c in s) and len(s) < 25)

                    if _es_expresion_tiempo(p1):
                        tiempo = p1
                        mensaje = p2
                    elif _es_expresion_tiempo(p2):
                        tiempo = p2
                        mensaje = p1
                    else:
                        tiempo = p1
                        mensaje = p2

                    logger.info(f"[RECORDATORIOS] Creando: mensaje='{mensaje}', tiempo='{tiempo}', opciones='{opciones}'")
                    try:
                        rec = gestor_recordatorios.crear_recordatorio(mensaje, tiempo, opciones)
                        logger.info(f"[RECORDATORIOS] CREADO OK: ID={rec.get('id')} exp={rec.get('expiracion_iso')}")
                        if ui_callback:
                            ui_callback("⚙️ Sistema", f"⏰ Recordatorio programado: '{mensaje}' ({rec['expiracion_iso']})", "#39ff14")
                    except Exception as e:
                        logger.exception(f"[RECORDATORIOS] Error creando recordatorio: {e}")
                        if ui_callback:
                            ui_callback("⚙️ Sistema", f"❌ Error al crear recordatorio: {str(e)[:80]}", "#ff4500")
                elif subcmd.startswith("listar"):
                    recs = gestor_recordatorios.listar_recordatorios()
                    txt = "\n".join([f"- [{r['id']}] {r['mensaje']} ({r['expiracion_iso']})" for r in recs]) or "No hay recordatorios pendientes."
                    if ui_callback:
                        ui_callback("⚙️ Sistema", f"📋 Recordatorios pendientes:\n{txt}", "#80868B")
                elif subcmd.startswith("cancelar"):
                    target = subcmd.replace("cancelar", "", 1).strip(" |:")
                    exito = gestor_recordatorios.cancelar_recordatorio(target)
                    if ui_callback:
                        msg_c = f"✅ Recordatorio '{target}' cancelado." if exito else f"❌ No se encontró recordatorio: {target}"
                        ui_callback("⚙️ Sistema", msg_c, "#39ff14" if exito else "#ff4500")
                continue

            # ESCANEAR PROYECTO CRAWLER
            if cmd_limpia.startswith("escanear_proyecto:"):
                if WORKSPACE_ACTUAL:
                    if ui_callback:
                        ui_callback("⚙️ Sistema", "🔍 Iniciando Crawler...", "#80868B")
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
                        if ui_callback:
                            ui_callback("⚙️ Sistema", "🧠 Analizando arquitectura global con Gemini Flash...", "#80868B")
                        # Usar Gemini Flash Lite (google-genai SDK) para el análisis.
                        # Más rápido y económico que DeepSeek Reasoner para esta tarea.
                        from google.genai import types
                        config_crawler = types.GenerateContentConfig(temperature=0.2)
                        response = motor_ia.cliente_genai.models.generate_content(
                            model="gemini-3.1-flash-lite",
                            contents=prompt_analisis,
                            config=config_crawler
                        )
                        estado_md = response.text.strip() if response.text else ""
                        if estado_md.startswith("```markdown"):
                            estado_md = estado_md.split("```markdown")[1].rsplit("```", 1)[0].strip()
                        elif estado_md.startswith("```"):
                            estado_md = estado_md.split("```")[1].rsplit("```", 1)[0].strip()
                        ruta_state = os.path.join(WORKSPACE_ACTUAL, "PROJECT_STATE.md")
                        escribir_archivo(ruta_state, estado_md)
                        msg_exito = "✅ ¡PROJECT_STATE.md generado con éxito! El Mentor ya tiene visión total del código."
                        if ui_callback:
                            ui_callback("⚙️ Sistema", msg_exito, "#86efac")
                        logger.info(msg_exito)
                    except Exception as e:
                        logger.exception("Error en crawler")
                        if ui_callback:
                            ui_callback("⚙️ Sistema", f"❌ Error en el Crawler: {e}", "#ff4500")
                else:
                    if ui_callback:
                        ui_callback("🤖 Argus", "Necesito tener un proyecto anclado para saber qué proyecto escanear.", "#FFA500")
                continue

            # COMANDOS DE SISTEMA
            if cmd_limpia.startswith(("abrir:", "navegar:", "cerrar:", "mover:", "explorar:")):
                verbo = cmd_limpia.split(":")[0]
                resto = cmd[cmd.lower().find(":")+1:].strip()
                resultado = ejecutar_comando_sistema(f"{verbo}:{resto}")
                if resultado:
                    if resultado.startswith("⚠️ No encontré el programa"):
                        if ui_callback:
                            ui_callback("⚙️ Sistema", resultado, "#FFA500")
                        config.estado.agregar_mensaje_chat(
                            {'role': 'user', 'parts': [f"[SISTEMA] {resultado}"]},
                            contar_para_perfil=False
                        )
                    else:
                        reportes_acciones.append(f"Acción SO: {resultado}")
                continue

    if reportes_acciones:
        texto_reporte = "\n".join([f"*({r})*" for r in reportes_acciones])
        print(texto_reporte)
        if ui_callback:
            ui_callback("⚙️ Sistema", texto_reporte, "#80868B")

    # Si la petición era una orden de comando/acción directa o se ejecutaron acciones de SO,
    # ignorar búsquedas web secundarias para evitar retrasos innecesarios.
    try:
        from modulos.ia import _es_intencion_comando_directo
        if _es_intencion_comando_directo(texto_usuario) or reportes_acciones:
            if comando_busqueda_detectado:
                logger.info(f"🚫 Ignorando búsqueda web '{comando_busqueda_detectado}' al ejecutar comando de sistema.")
                comando_busqueda_detectado = None
    except Exception:
        pass

    return comando_busqueda_detectado