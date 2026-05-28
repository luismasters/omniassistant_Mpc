import datetime
import winsound
import google.generativeai as genai

# Importaciones de configuración
from config import GEMINI_API_KEY

# Importaciones de módulos del sistema
from modulos.archivos import crear_carpeta, crear_archivo, eliminar_elemento, leer_contenido_archivo, obtener_ruta_real
from modulos.sistema import obtener_estado_pc, hardware_detectado, ejecutar_comando_sistema, obtener_ventanas_activas, buscar_carpeta_windows
from modulos.busqueda import buscar_en_internet
from modulos.audio import hablar_no_bloqueante
from modulos.vision import capturar_pantalla
from modulos.git_bot import sincronizar_proyecto_git
from modulos.memoria import buscar_contexto, guardar_recuerdo # <-- EL CEREBRO RAG

genai.configure(api_key=GEMINI_API_KEY)

CONTEXTO_CHAT = []
PENDIENTE_DE_GUARDADO = "" # <--- NUESTRA VARIABLE SEMÁFORO

def enviar_a_gemini(texto_usuario, modo_voz=False):
    global CONTEXTO_CHAT, PENDIENTE_DE_GUARDADO
    
    texto_usuario_lower = texto_usuario.lower().strip()

    # =================================================================
    # 1. EL SEMÁFORO DE CONFIRMACIÓN (Evaluador IA)
    # =================================================================
    if PENDIENTE_DE_GUARDADO:
        print("🧠 [SEMÁFORO IA] Evaluando tu respuesta con Gemini...")
        
        # Le pedimos a Gemini que actúe como un juez de intenciones
        evaluador = genai.GenerativeModel("gemini-flash-lite-latest")
        prompt_juez = f"El usuario debe confirmar si aprueba guardar un dato. Su respuesta fue: '{texto_usuario}'. ¿El usuario está afirmando/aprobando o está negando/rechazando? Responde ÚNICAMENTE con la palabra CONFIRMADO o la palabra CANCELADO."
        
        try:
            decision_ia = evaluador.generate_content(prompt_juez).text.strip().upper()
        except Exception as e:
            print(f"⚠️ Error en evaluador: {e}")
            decision_ia = "CANCELADO" # Ante cualquier error, abortamos por seguridad
            
        if "CONFIRMADO" in decision_ia:
            print("🧠 [MEMORIA] Inyectando en la bóveda ChromaDB...")
            guardar_recuerdo(texto_a_guardar=PENDIENTE_DE_GUARDADO, etiqueta_tema="Manual")
            msg = "¡Listo! El recuerdo ya está sellado en tu bóveda permanente."
        else:
            msg = "Entendido, descarto esa información. No se guardó nada."
        
        # Limpiamos la variable y le respondemos al usuario
        PENDIENTE_DE_GUARDADO = ""
        print(f"\n🤖 Cortana:\n---\n{msg}\n---")
        if modo_voz: hablar_no_bloqueante(msg)
        return # Cortamos la ejecución acá para no gastar más tokens

    # =================================================================
    # 2. EXTRACTOR INTELIGENTE (Fase de captura blindada)
    # =================================================================
    comandos_guardado = [
        "memoriza esto", "memorizá esto", "memorices", "memorizar", "memoriza", "memorizá",
        "guardar recuerdo", "recordá esto", "recuerda esto", "recordar", "recuerda", 
        "acordate de", "acordate que", "guarda esto"
    ]
    
    comando_detectado = None
    comandos_guardado.sort(key=len, reverse=True) # Ordenamos de más largo a más corto
    
    for cmd in comandos_guardado:
        if cmd in texto_usuario_lower:
            comando_detectado = cmd
            break
            
    if comando_detectado:
        print("🧠 [EXTRACTOR IA] Limpiando y estructurando el dato para la bóveda...")
        extractor = genai.GenerativeModel("gemini-flash-lite-latest")
        prompt_extractor = f"El usuario quiere que memorices algo. Su frase fue: '{texto_usuario}'. Extrae ÚNICAMENTE la información relevante (ej: la lista de juegos, la clave, el dato específico) de forma clara y directa. Responde SOLO con el dato a guardar, sin agregar saludos, confirmaciones ni explicaciones adicionales."
        
        try:
            dato_limpio = extractor.generate_content(prompt_extractor).text.strip()
            if dato_limpio:
                PENDIENTE_DE_GUARDADO = dato_limpio # Retenemos el dato limpio en el aire
                msg = f"Detecté que querés memorizar esto: '{dato_limpio}'. ¿Me confirmás si lo guardo de forma permanente en tu bóveda?"
                print(f"\n🤖 Cortana:\n---\n{msg}\n---")
                if modo_voz: hablar_no_bloqueante(msg)
                return # Abortamos la llamada al asistente general y esperamos tu respuesta
        except Exception as e:
            print(f"⚠️ Error al extraer dato: {e}")
            # Si falla la extracción, no guardamos basura y dejamos que siga el flujo normal

    # Si no estamos guardando nada, sigue el flujo normal...
    print("\n🧠 PENSANDO (Gemini)...")
    try:
        estado_en_vivo = obtener_estado_pc()
        fecha_hoy = datetime.datetime.now().strftime("%A, %d de %B de %Y") 
        ventanas_abiertas = obtener_ventanas_activas()

        # =================================================================
        # 3. EL RADAR INVISIBLE (Extracción automática)
        # =================================================================
        recuerdos = buscar_contexto(texto_usuario)
        texto_memoria = ""
        if recuerdos:
            # recuerdos[0] contiene el texto puro que encontró ChromaDB
            texto_memoria = f"[MEMORIA AUTOMÁTICA RECUPERADA]:\nEl usuario tiene este recuerdo en su bóveda que podría relacionarse con su petición actual:\n'{recuerdos[0]}'\n\n"

        contexto_sistema = (
            "tu nombre es: Cortana, un asistente de IA integrado a la PC de Luis (Técnico en Programación). Hablále como un colega, de forma súper natural y directa.\n"
            "⚠️ REGLA DE PERSONALIDAD: Sé breve (corto y al pie). NUNCA menciones la fecha actual, ni el uso de CPU/GPU, ni expliques tus procesos internos, a menos que Luis te lo pregunte específicamente. Actuá normal y relajado.\n\n"
            f"[CONTEXTO OCULTO PARA TUS CÁLCULOS] Fecha actual: {fecha_hoy} | Estado PC: {estado_en_vivo} | Hardware: {hardware_detectado['gpu']} / {hardware_detectado['cpu']}\n"
            f"[VENTANAS ABIERTAS AHORA MISMO]: {ventanas_abiertas}\n\n"
            f"{texto_memoria}" # <--- ACÁ INYECTAMOS TU BÓVEDA VECTORIAL
            "⚠️ REGLA DE MEMORIA Y VERDAD:\n"
            "1. PRIORIDAD DE MEMORIA: Si recibes datos en [MEMORIA AUTOMÁTICA RECUPERADA], úsalos como fuente ÚNICA Y EXCLUSIVA para responder sobre datos personales (listas, claves, preferencias).\n"
            "2. PROHIBICIÓN DE ALUCINAR: NUNCA inventes ni infieras datos personales. Si la información no está explícitamente en la memoria, admite honestamente: 'No tengo ese dato guardado'.\n"
            "3. NATURALIDAD: Jamás digas 'según mis registros', 'en mi base de datos' o 'recuperé un recuerdo'. Habla como si recordaras las cosas naturalmente.\n"
            "4. CONOCIMIENTO GENERAL: Para temas técnicos (programación, dudas del mundo), usa tu conocimiento general libremente.\n\n"
            "⚠️ REGLA DE VISIÓN: Si el usuario te pide que mires su pantalla o te pregunta por lo que está viendo, analiza la imagen que se adjunta de forma automática. No digas que 'viste una captura', actúa como si miraras su monitor directamente.\n\n"
            "⚠️ REGLA ESTRICTA DE RUTAS: NUNCA escribas rutas absolutas que empiecen con 'C:\\' ni inventes nombres de usuario. Si Luis te pide abrir una carpeta del sistema, usá su nombre corto ('descargas', 'escritorio', 'documentos'). Si te pide leer un archivo, usá solo el nombre del archivo (Ej: 'comprobante.pdf'), ya que el radar de Python se encarga de buscarlo en las carpetas automáticamente.\n\n"
            "⚠️ REGLA DE COMANDOS (Escribí uno por línea al final):\n"
            "- Para páginas web, usá: navegar: sitio_web @ monitor (Ej: navegar: gmail.com @ 1)\n" 
            "- Para mover ventanas, agregá @ y SOLO el número al final. Ej: abrir: brave @ 2\n"
            "- Para apps, juegos o carpetas, usá el nombre exacto: abrir: nombre_corto @ monitor (Ej: abrir: street fighter 6 @ 1)\n"
            "- Para cerrar, usá: cerrar: programa\n"
            "- Para crear carpetas o archivos vacíos, usá: crear_carpeta: ruta o crear_archivo: ruta.ext\n"
            "- Para eliminar archivos o carpetas, usá: eliminar: ruta\n"
            "- Para LEER y analizar código o texto, usá: leer: nombre_archivo.ext (Ej: leer: comprobante.pdf)\n"
            "- Para subir, guardar o sincronizar proyectos en GitHub, usá SOLO el nombre de la carpeta: github: nombre_carpeta (Ej: github: OmniAssistant)\n"
            "⚠️ REGLA ANTIMENTIRAS (LECTURA): Si el usuario te pregunta por un detalle específico de un documento (fechas, montos, nombres) que ya leíste, NO confíes en tu memoria ni adivines. Estás obligada a volver a usar el comando 'leer: nombre_archivo.ext' para buscar el dato exacto fresco en el texto original.\n\n"
        )

        modelo_gemini = genai.GenerativeModel(
            model_name="gemini-flash-lite-latest", 
            system_instruction=contexto_sistema
        )

        mensajes_para_gemini = list(CONTEXTO_CHAT)
        partes_usuario = [texto_usuario]
        
        verbos_vision = ["captura", "capturá", "capturar"]
        objetivos_vision = ["pantalla", "monitor", "1", "2", "uno", "dos", "la 1", "el 1", "la 2", "el 2"]
        
        if any(v in texto_usuario_lower for v in verbos_vision) and any(o in texto_usuario_lower for o in objetivos_vision):
            winsound.Beep(1500, 100)
            winsound.Beep(2000, 100)
            num_pantalla = None
            if any(p in texto_usuario_lower for p in ["pantalla 1", "monitor 1", "pantalla uno", "monitor uno", "la 1", "el 1"]):
                num_pantalla = 2 
            elif any(p in texto_usuario_lower for p in ["pantalla 2", "monitor 2", "pantalla dos", "monitor dos", "la 2", "el 2"]):
                num_pantalla = 1 
                
            imagen_pantalla = capturar_pantalla(num_pantalla)
            if imagen_pantalla:
                partes_usuario.append(imagen_pantalla) 
                
        mensajes_para_gemini.append({'role': 'user', 'parts': partes_usuario})

        response = modelo_gemini.generate_content(
            mensajes_para_gemini,
            stream=True,
            generation_config=genai.GenerationConfig(temperature=0.1)
        )
        
        respuesta_ia = ""
        print(f"\n🤖 Cortana dice:\n---")
        for chunk in response:
            if chunk.text:
                print(chunk.text, end='', flush=True) 
                respuesta_ia += chunk.text
        print("\n---")
        
        lineas = respuesta_ia.split('\n')
        reportes_acciones = []
        comando_busqueda_detectado = None
        comando_leer_detectado = None
        
        # --- SALIDA: LAS MANOS (POST-PROCESAMIENTO) ---
        for linea in lineas:
            linea_limpia = linea.lower().replace("[", "").replace("]", "").replace("*", "").strip()
            
            if "buscar:" in linea_limpia:
                comando_busqueda_detectado = linea_limpia[linea_limpia.find("buscar:") + 7:].strip()
            
            elif "leer:" in linea_limpia:
                comando_leer_detectado = linea_limpia[linea_limpia.find("leer:") + 5:].strip()
                
            elif "crear_carpeta:" in linea_limpia:
                ruta = linea_limpia[linea_limpia.find("crear_carpeta:") + 14:].strip()
                res = crear_carpeta(ruta)
                reportes_acciones.append(f"crear_carpeta: {ruta} -> {res}")
                
            elif "crear_archivo:" in linea_limpia:
                ruta = linea_limpia[linea_limpia.find("crear_archivo:") + 14:].strip()
                res = crear_archivo(ruta)
                reportes_acciones.append(f"crear_archivo: {ruta} -> {res}")
            
            elif any(cmd in linea_limpia for cmd in ["abrir:", "cerrar:", "navegar:", "mover:"]):
                if "mover:" in linea_limpia:
                    linea_limpia = linea_limpia.replace("mover:", "abrir:")
                
                if "abrir:" in linea_limpia: inicio_idx = linea_limpia.find("abrir:")
                elif "cerrar:" in linea_limpia: inicio_idx = linea_limpia.find("cerrar:")
                else: inicio_idx = linea_limpia.find("navegar:")
                
                cmd_extraido = linea_limpia[inicio_idx:].strip()
                res = ejecutar_comando_sistema(cmd_extraido)
                reportes_acciones.append(f"Comando [{cmd_extraido}]: {res}")
                
            elif "eliminar:" in linea_limpia:
                ruta = linea_limpia[linea_limpia.find("eliminar:") + 9:].strip()
                res = eliminar_elemento(ruta)
                reportes_acciones.append(f"eliminar: {ruta} -> {res}")
            elif "github:" in linea_limpia:
                ruta_corta = linea_limpia[linea_limpia.find("github:") + 7:].strip()
                
                ruta_real = buscar_carpeta_windows(ruta_corta) 
                
                if ruta_real:
                    res = sincronizar_proyecto_git(ruta_real)
                else:
                    res = f"Fallo Git: No encontré la carpeta '{ruta_corta}' con el radar."
                
                reportes_acciones.append(res)      

        # =====================================================================
        # LÓGICA DE DOBLE LLAMADA (Internet o Lectura de Código/PDF)
        # =====================================================================
        if comando_busqueda_detectado:
            datos_encontrados = buscar_en_internet(comando_busqueda_detectado)
            if "No se encontraron resultados" in datos_encontrados or not datos_encontrados.strip() or "error" in datos_encontrados.lower():
                msg_error = "Che Luis, busqué en la web pero no encontré nada relevante."
                print(f"\n🤖 Cortana:\n---\n{msg_error}\n---")
                if modo_voz: hablar_no_bloqueante(msg_error)
                CONTEXTO_CHAT.append({'role': 'user', 'parts': [texto_usuario]})
                CONTEXTO_CHAT.append({'role': 'model', 'parts': [msg_error]})
            else:
                print("🧠 [GEMINI REAL] Procesando resultados de la web...")
                contexto_busqueda = (
                    f"Resultados de internet:\n{datos_encontrados}\n\n"
                    "Por favor, respondé a mi pregunta original usando esta información."
                )
                mensajes_secundarios = list(CONTEXTO_CHAT)
                mensajes_secundarios.extend([
                    {'role': 'user', 'parts': [texto_usuario]},
                    {'role': 'model', 'parts': [respuesta_ia]},
                    {'role': 'user', 'parts': [contexto_busqueda]}
                ])
                segunda_respuesta = modelo_gemini.generate_content(mensajes_secundarios, stream=True)
                respuesta_final = ""
                print(f"\n🤖 Cortana (Con datos de la Web):\n---")
                for chunk in segunda_respuesta:
                    if chunk.text:
                        print(chunk.text, end='', flush=True) 
                        respuesta_final += chunk.text
                print("\n---")
                if modo_voz: hablar_no_bloqueante(respuesta_final)
                CONTEXTO_CHAT.extend([{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [respuesta_final]}])

        elif comando_leer_detectado:
            datos_archivo = leer_contenido_archivo(comando_leer_detectado)
            
            if datos_archivo == "CODIGO_ERROR_NO_ENCONTRADO" or datos_archivo.startswith("CODIGO_ERROR_LECTURA:"):
                msg_error = f"Che, escaneé las carpetas pero no encontré ni pude abrir '{comando_leer_detectado}'."
                print(f"\n🤖 Cortana:\n---\n{msg_error}\n---")
                if modo_voz: hablar_no_bloqueante(msg_error)
                CONTEXTO_CHAT.append({'role': 'user', 'parts': [texto_usuario]})
                CONTEXTO_CHAT.append({'role': 'model', 'parts': [msg_error]})
            else:
                print("🧠 [GEMINI REAL] Analizando el documento/código...")
                contexto_lectura = (
                    f"Acabo de leer el archivo '{comando_leer_detectado}'. Este es su contenido real:\n\n"
                    f"--- INICIO DEL DOCUMENTO ---\n{datos_archivo}\n--- FIN DEL DOCUMENTO ---\n\n"
                    "Por favor, respondé a mi pregunta original revisando esta información. Si es código, marcá los errores. Si es un PDF o documento, resumilo o respondé mi duda."
                )
                mensajes_secundarios = list(CONTEXTO_CHAT)
                mensajes_secundarios.extend([
                    {'role': 'user', 'parts': [texto_usuario]},
                    {'role': 'model', 'parts': [respuesta_ia]},
                    {'role': 'user', 'parts': [contexto_lectura]}
                ])
                segunda_respuesta = modelo_gemini.generate_content(mensajes_secundarios, stream=True)
                respuesta_final = ""
                print(f"\n🤖 Cortana (Análisis de Documento):\n---")
                for chunk in segunda_respuesta:
                    if chunk.text:
                        print(chunk.text, end='', flush=True) 
                        respuesta_final += chunk.text
                print("\n---")
                if modo_voz: hablar_no_bloqueante(respuesta_final)
                CONTEXTO_CHAT.extend([{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [respuesta_final]}])

        else:
            if modo_voz: hablar_no_bloqueante(respuesta_ia)
            CONTEXTO_CHAT.extend([{'role': 'user', 'parts': [texto_usuario]}, {'role': 'model', 'parts': [respuesta_ia]}])

        if len(CONTEXTO_CHAT) > 6: 
            CONTEXTO_CHAT = CONTEXTO_CHAT[-6:]
            if CONTEXTO_CHAT[0]['role'] == 'model': CONTEXTO_CHAT.pop(0)

        if reportes_acciones:
            print("\n".join([f"*(Acción ejecutada: {r})*" for r in reportes_acciones]))
            
    except Exception as e:
        print(f"\n❌ Error en Gemini: {e}")