import json
import os
import threading
import datetime
from modulos.logger import logger

# Ruta al archivo de perfil del mentor (raíz del proyecto)
RUTA_PERFIL_MENTOR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "perfil_mentor.json")

_lock_perfil_mentor = threading.Lock()

ESQUEMA_MENTOR_DEFECTO = {
    "stack_objetivo": {
        "frontend": "Pendiente de definir",
        "backend": "Pendiente de definir",
        "bases_de_datos": "Pendiente de definir",
        "otras_herramientas": []
    },
    "tecnologias_aprendidas": [],
    "tecnologias_en_estudio": [],
    "proyectos_de_portafolio": [],
    "ultimo_avance_registrado": "Ninguno",
    "historial_sesiones": [],
    "claves_de_contexto_faltantes": [
        "¿Prefieres enfocarte en desarrollo Frontend, Backend o Fullstack?",
        "¿Qué lenguajes o tecnologías aprendiste en la UTN FRGP y con cuáles te sentiste más cómodo?",
        "¿Tienes en mente alguna idea de proyecto para construir como parte de tu portafolio?"
    ]
}

def cargar_perfil_mentor() -> dict:
    """
    Carga el perfil del mentor desde disco. Thread-safe.
    Si no existe o está corrupto, crea la estructura inicial por defecto.
    """
    with _lock_perfil_mentor:
        if not os.path.exists(RUTA_PERFIL_MENTOR):
            logger.info("perfil_mentor.json no encontrado. Creando estructura por defecto.")
            _guardar_perfil_mentor_sin_lock(ESQUEMA_MENTOR_DEFECTO)
            return dict(ESQUEMA_MENTOR_DEFECTO)
        try:
            with open(RUTA_PERFIL_MENTOR, "r", encoding="utf-8") as f:
                perfil = json.load(f)
            # Asegurar claves mínimas
            for k, v in ESQUEMA_MENTOR_DEFECTO.items():
                if k not in perfil:
                    perfil[k] = v
            return perfil
        except Exception as e:
            logger.exception(f"Error cargando perfil_mentor.json: {e}")
            return dict(ESQUEMA_MENTOR_DEFECTO)

def guardar_perfil_mentor(perfil: dict) -> None:
    """Guarda el perfil del mentor en disco. Thread-safe."""
    with _lock_perfil_mentor:
        _guardar_perfil_mentor_sin_lock(perfil)

def _guardar_perfil_mentor_sin_lock(perfil: dict) -> None:
    try:
        with open(RUTA_PERFIL_MENTOR, "w", encoding="utf-8") as f:
            json.dump(perfil, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.exception(f"Error escribiendo perfil_mentor.json: {e}")

def obtener_bitacora_workspace(workspace_path: str = "") -> str:
    """
    Busca si existe BITACORA_MENTOR.md o bitacora.md en el workspace anclado.
    Si existe, retorna las últimas entradas (máx 1200 caracteres) para economía de tokens.
    """
    if not workspace_path or not os.path.exists(workspace_path):
        return ""
    
    nombres_posibles = ["BITACORA_MENTOR.md", "bitacora_mentor.md", "BITACORA.md", "bitacora.md"]
    for nombre in nombres_posibles:
        ruta_file = os.path.join(workspace_path, nombre)
        if os.path.isfile(ruta_file):
            try:
                with open(ruta_file, "r", encoding="utf-8") as f:
                    contenido = f.read().strip()
                if contenido:
                    if len(contenido) > 1200:
                        contenido = "... [recortado por economía de tokens]\n" + contenido[-1200:]
                    return f"[BITÁCORA ANCLADA AL WORKSPACE ({nombre})]:\n{contenido}\n"
            except Exception as e:
                logger.warning(f"Error leyendo bitácora del workspace {ruta_file}: {e}")
    return ""

def texto_perfil_mentor_para_prompt(workspace_path: str = "") -> str:
    """
    Formatea el perfil del mentor en formato Markdown para inyectar en el prompt.
    Optimizado para economía de tokens.
    """
    p = cargar_perfil_mentor()
    
    stack = p.get("stack_objetivo", {})
    frontend = stack.get("frontend", "Pendiente")
    backend = stack.get("backend", "Pendiente")
    db = stack.get("bases_de_datos", "Pendiente")
    otras = ", ".join(stack.get("otras_herramientas", [])) or "Ninguna"
    
    aprendidas = ", ".join(p.get("tecnologias_aprendidas", [])) or "Ninguna"
    estudio = ", ".join(p.get("tecnologias_en_estudio", [])) or "Ninguna"
    
    proyectos_str = ""
    for proj in p.get("proyectos_de_portafolio", []):
        if isinstance(proj, dict):
            nombre_p = proj.get("nombre", "Proyecto")
            desc_p = proj.get("descripcion", "")
            proyectos_str += f"- **{nombre_p}**: {desc_p}\n"
        else:
            proyectos_str += f"- {proj}\n"
    if not proyectos_str:
        proyectos_str = "- Ninguno registrado aún\n"
        
    preguntas_str = ""
    for preg in p.get("claves_de_contexto_faltantes", []):
        preguntas_str += f"- {preg}\n"
    if not preguntas_str:
        preguntas_str = "- Todo el contexto básico completado\n"
        
    avance = p.get("ultimo_avance_registrado", "Ninguno")
    
    historial = p.get("historial_sesiones", [])
    historial_str = ""
    if historial:
        for s in historial[-3:]:
            fecha = s.get("fecha", "Reciente")
            res = s.get("resumen", "")
            pasos = ", ".join(s.get("proximos_pasos", [])) if isinstance(s.get("proximos_pasos"), list) else s.get("proximos_pasos", "")
            historial_str += f"  * [{fecha}] Resumen: {res}"
            if pasos:
                historial_str += f" | Próximos pasos: {pasos}"
            historial_str += "\n"
    else:
        historial_str = f"  * Único avance guardado: {avance}\n"

    texto_bitacora_ws = obtener_bitacora_workspace(workspace_path)

    texto = (
        "[PERFIL ESPECÍFICO DE MENTORÍA TECNOLÓGICA (LUIS)]:\n"
        "Este es el estado del progreso técnico y la bitácora de sesiones de Luis. "
        "YA TIENES ESTA INFORMACIÓN EN CONTEXTO, no necesitas realizar lecturas de archivos de bitácora al iniciar.\n"
        "- STACK OBJETIVO:\n"
        f"  * Frontend: {frontend}\n"
        f"  * Backend: {backend}\n"
        f"  * Bases de Datos: {db}\n"
        f"  * Otras herramientas: {otras}\n"
        f"- Tecnologías Aprendidas/Conocidas: {aprendidas}\n"
        f"- Tecnologías en Estudio Actual: {estudio}\n"
        f"- Proyectos de Portafolio Planificados/En curso:\n{proyectos_str}"
        f"- HISTORIAL DE ÚLTIMAS SESIONES Y AVANCES:\n{historial_str}"
        f"- Claves de contexto faltantes (Si es oportuno y fluye con la charla, hazle una de estas preguntas para completar su perfil):\n"
        f"{preguntas_str}"
    )
    if texto_bitacora_ws:
        texto += f"\n{texto_bitacora_ws}"
        
    return texto

def extraer_y_procesar_sesion_mentor(ultimos_mensajes: list, workspace_path: str = "") -> None:
    """
    Extrae hechos tecnológicos y actualiza perfil_mentor.json (y BITACORA_MENTOR.md si hay workspace)
    usando Gemini Flash Lite con estricta economía de tokens.
    """
    if not ultimos_mensajes:
        return
        
    mensajes_relevantes = ultimos_mensajes[-14:]
    conversacion = ""
    for msg in mensajes_relevantes:
        role = msg.get("role", "user")
        parts = msg.get("parts", [])
        text = ""
        for part in parts:
            if isinstance(part, str):
                text += part
            elif isinstance(part, dict) and "text" in part:
                text += part["text"]
        if len(text) > 500:
            text = text[:500] + "... [truncado]"
        conversacion += f"{role.upper()}: {text}\n"

    if not conversacion.strip():
        return

    from modulos.ia import cliente_genai
    from google.genai import types

    perfil_actual = cargar_perfil_mentor()
    fecha_hoy = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    prompt = (
        "Analiza la siguiente conversación reciente entre Luis (el estudiante) y su Mentor Tecnológico (Argus).\n"
        "Tu tarea es extraer actualizaciones para su perfil de mentoría y devolver el perfil_mentor.json actualizado.\n\n"
        f"Perfil actual de mentoría:\n{json.dumps(perfil_actual, ensure_ascii=False, indent=2)}\n\n"
        "INSTRUCCIONES DE ACTUALIZACIÓN:\n"
        "1. Revisa si Luis menciona nuevas tecnologías que aprendió o que quiere aprender. Agrégalas a 'tecnologias_aprendidas' o 'tecnologias_en_estudio'.\n"
        "2. Revisa si Luis responde a alguna de las 'claves_de_contexto_faltantes'. Si es así, actualiza los campos correspondientes y ELIMINA esa pregunta de la lista.\n"
        "3. Revisa si definieron o avanzaron en algún proyecto de portafolio y actualiza 'proyectos_de_portafolio'.\n"
        "4. En 'ultimo_avance_registrado', guarda un resumen de 1 sola frase con el logro principal de la sesión.\n"
        "5. En 'historial_sesiones', agrega un nuevo objeto: "
        f'{{"fecha": "{fecha_hoy}", "resumen": "resumen breve de lo trabajado", "temas": ["tema1", "tema2"], "proximos_pasos": ["paso1", "paso2"]}}. '
        "MANTÉN MÁXIMO 5 SESIONES en 'historial_sesiones' (elimina la más antigua si supera 5).\n"
        "6. Devuelve el JSON completo con las modificaciones integradas.\n"
        "7. IMPORTANTE: No inventes información. Si no hubo avances significativos, actualiza la lista con un resumen sucinto.\n"
        "8. Responde ÚNICAMENTE con el objeto JSON limpio. No uses formato de markdown (sin ```json) ni explicaciones.\n\n"
        f"Conversación reciente:\n{conversacion}\n\n"
        "JSON Actualizado:"
    )
    
    try:
        respuesta = cliente_genai.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=1500
            )
        )
        texto = respuesta.text.strip()
        
        # Despojar markdown si viniera
        if texto.startswith("```"):
            lineas = texto.split("\n")
            if lineas[0].strip().startswith("```"):
                lineas = lineas[1:]
            if lineas and lineas[-1].strip() == "```":
                lineas = lineas[:-1]
            texto = "\n".join(lineas).strip()
            
        nuevo_perfil = json.loads(texto)
        if isinstance(nuevo_perfil, dict):
            # Validar que no se pierdan claves principales
            for k in ESQUEMA_MENTOR_DEFECTO.keys():
                if k not in nuevo_perfil:
                    nuevo_perfil[k] = perfil_actual.get(k, ESQUEMA_MENTOR_DEFECTO[k])

            # Limitar historial a 5 entradas máx
            if "historial_sesiones" in nuevo_perfil and isinstance(nuevo_perfil["historial_sesiones"], list):
                nuevo_perfil["historial_sesiones"] = nuevo_perfil["historial_sesiones"][-5:]

            guardar_perfil_mentor(nuevo_perfil)
            logger.info("✅ perfil_mentor.json actualizado con éxito tras la sesión.")

            # Si hay workspace activo, actualizar también BITACORA_MENTOR.md en esa carpeta
            if not workspace_path:
                import config as _cfg
                workspace_path = getattr(_cfg.estado, "workspace_actual", "")

            if workspace_path and os.path.exists(workspace_path):
                try:
                    ruta_bitacora = os.path.join(workspace_path, "BITACORA_MENTOR.md")
                    historial = nuevo_perfil.get("historial_sesiones", [])
                    ultima = historial[-1] if historial else None
                    if ultima:
                        resumen = ultima.get("resumen", "")
                        temas = ", ".join(ultima.get("temas", [])) if isinstance(ultima.get("temas"), list) else ultima.get("temas", "")
                        pasos = ", ".join(ultima.get("proximos_pasos", [])) if isinstance(ultima.get("proximos_pasos"), list) else ultima.get("proximos_pasos", "")
                        
                        linea_nueva = f"\n### Sesión {fecha_hoy}\n- **Resumen:** {resumen}\n- **Temas tratados:** {temas}\n- **Próximos pasos:** {pasos}\n"
                        
                        if not os.path.exists(ruta_bitacora):
                            with open(ruta_bitacora, "w", encoding="utf-8") as f:
                                f.write(f"# Bitácora de Mentoría — Argus Copilot\n{linea_nueva}")
                        else:
                            with open(ruta_bitacora, "a", encoding="utf-8") as f:
                                f.write(linea_nueva)
                        logger.info(f"✅ BITACORA_MENTOR.md actualizada en workspace: {ruta_bitacora}")
                except Exception as e_ws:
                    logger.warning(f"Error escribiendo BITACORA_MENTOR.md en workspace: {e_ws}")
    except Exception as e:
        logger.exception(f"Error procesando sesión del mentor: {e}")

