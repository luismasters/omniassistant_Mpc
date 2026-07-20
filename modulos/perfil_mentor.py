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
            return ESQUEMA_MENTOR_DEFECTO
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
            return ESQUEMA_MENTOR_DEFECTO

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

def texto_perfil_mentor_para_prompt() -> str:
    """
    Formatea el perfil del mentor en formato Markdown para inyectar en el prompt.
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
        proyectos_str += f"- {proj}\n"
    if not proyectos_str:
        proyectos_str = "- Ninguno registrado aún\n"
        
    preguntas_str = ""
    for preg in p.get("claves_de_contexto_faltantes", []):
        preguntas_str += f"- {preg}\n"
    if not preguntas_str:
        preguntas_str = "- Todo el contexto básico completado\n"
        
    avance = p.get("ultimo_avance_registrado", "Ninguno")
    
    texto = (
        "[PERFIL ESPECÍFICO DE MENTORÍA TECNOLÓGICA (LUIS)]:\n"
        "Este es el estado del progreso técnico de Luis. Úsalo para personalizar tus explicaciones y guías.\n"
        "- STACK OBJETIVO:\n"
        f"  * Frontend: {frontend}\n"
        f"  * Backend: {backend}\n"
        f"  * Bases de Datos: {db}\n"
        f"  * Otras herramientas: {otras}\n"
        f"- Tecnologías Aprendidas/Conocidas: {aprendidas}\n"
        f"- Tecnologías en Estudio Actual: {estudio}\n"
        f"- Proyectos de Portafolio Planificados/En curso:\n{proyectos_str}"
        f"- Último avance o tema discutido: {avance}\n"
        "- Claves de contexto faltantes (Si es oportuno y fluye con la charla, hazle una de estas preguntas para completar su perfil):\n"
        f"{preguntas_str}"
    )
    return texto

def extraer_y_procesar_sesion_mentor(ultimos_mensajes: list) -> None:
    """
    Extrae hechos tecnológicos y actualiza perfil_mentor.json usando Gemini Flash.
    """
    if not ultimos_mensajes:
        return
        
    from modulos.ia import cliente_genai
    from google.genai import types
    
    conversacion = ""
    for msg in ultimos_mensajes:
        role = msg.get("role", "user")
        parts = msg.get("parts", [])
        text = ""
        for part in parts:
            if isinstance(part, str):
                text += part
            elif isinstance(part, dict) and "text" in part:
                text += part["text"]
        conversacion += f"{role.upper()}: {text}\n"

    perfil_actual = cargar_perfil_mentor()
    
    prompt = (
        "Analiza la siguiente conversación entre Luis (el estudiante) y su Mentor Tecnológico (Argus).\n"
        "Tu tarea es extraer actualizaciones para su perfil de mentoría y devolver el perfil_mentor.json actualizado.\n\n"
        f"Perfil actual de mentoría:\n{json.dumps(perfil_actual, ensure_ascii=False, indent=2)}\n\n"
        "INSTRUCCIONES DE ACTUALIZACIÓN:\n"
        "1. Revisa si Luis menciona nuevas tecnologías que aprendió o que quiere aprender. Agrégalas a 'tecnologias_aprendidas' o 'tecnologias_en_estudio' según corresponda.\n"
        "2. Revisa si Luis responde a alguna de las 'claves_de_contexto_faltantes'. Si es así, actualiza los campos correspondientes ('stack_objetivo', etc.) y ELIMINA esa pregunta de la lista de preguntas faltantes.\n"
        "3. Revisa si definieron o avanzaron en algún proyecto de portafolio y actualiza 'proyectos_de_portafolio'.\n"
        "4. Sintetiza un breve resumen del tema principal discutido y guárdalo en 'ultimo_avance_registrado'.\n"
        "5. Devuelve el JSON completo con las modificaciones integradas.\n"
        "6. IMPORTANTE: No inventes información. Si Luis no respondió a una pregunta, no la quites. Si no hubo avances nuevos, devuelve el JSON idéntico al actual.\n"
        "7. Responde ÚNICAMENTE con el objeto JSON limpio. No uses formato de markdown (sin ```json) ni explicaciones.\n\n"
        f"Conversación reciente:\n{conversacion}\n\n"
        "JSON Actualizado:"
    )
    
    try:
        respuesta = cliente_genai.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=2048
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
            guardar_perfil_mentor(nuevo_perfil)
            logger.info("perfil_mentor.json actualizado con éxito tras la sesión.")
    except Exception as e:
        logger.exception(f"Error procesando sesión del mentor: {e}")
