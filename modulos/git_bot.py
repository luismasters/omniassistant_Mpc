import os
import subprocess
import requests
import logging
from config import GITHUB_TOKEN

# Iniciamos el logger profesional
logger = logging.getLogger(__name__)

def ejecutar_comando(comando, cwd):
    """Ejecuta comandos de consola en silencio y captura la respuesta."""
    try:
        resultado = subprocess.run(comando, shell=True, cwd=cwd, capture_output=True, text=True, check=False)
        return resultado.returncode == 0, resultado.stdout.strip(), resultado.stderr.strip()
    except Exception as e:
        logger.error(f"Excepción al ejecutar comando {comando}: {e}")
        return False, "", str(e)

def sincronizar_proyecto_git(ruta_proyecto, mensaje_commit="Subida automática vía Cortana", reset_remote=False, url_custom=None):
    logger.info(f"[GIT] Analizando la carpeta: {ruta_proyecto}")
    
    if not os.path.exists(ruta_proyecto):
        return f"❌ Error: La carpeta {ruta_proyecto} no existe."
        
    nombre_repo = os.path.basename(os.path.normpath(ruta_proyecto))
    
    # 1. Verificar si es un repositorio Git local
    ruta_git = os.path.join(ruta_proyecto, ".git")
    if not os.path.exists(ruta_git):
        logger.info("[GIT] Inicializando nuevo repositorio local...")
        exito, _, err = ejecutar_comando("git init", ruta_proyecto)
        if not exito: return f"❌ Error al inicializar git localmente:\n{err}"
        
    # 2. Gestión de Remotos
    exito, stdout, _ = ejecutar_comando("git remote -v", ruta_proyecto)
    tiene_remote = "origin" in stdout
    
    if reset_remote and tiene_remote:
        logger.info("[GIT] Eliminando conexión remota anterior...")
        ejecutar_comando("git remote remove origin", ruta_proyecto)
        tiene_remote = False
    
    if not tiene_remote or url_custom:
        if url_custom:
            logger.info(f"[GIT] Vinculando a URL personalizada: {url_custom}...")
            # Si ya tenía remote pero pedimos url_custom sin reset, lo pisamos
            if tiene_remote:
                ejecutar_comando(f"git remote set-url origin {url_custom}", ruta_proyecto)
            else:
                ejecutar_comando(f"git remote add origin {url_custom}", ruta_proyecto)
        else:
            logger.info(f"[GIT] Creando repositorio '{nombre_repo}' en tu GitHub...")
            url_api = "https://api.github.com/user/repos"
            headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
            payload = {"name": nombre_repo, "private": True} 
            
            res = requests.post(url_api, headers=headers, json=payload)
            
            if res.status_code == 201: 
                url_clon = res.json()['clone_url']
            elif res.status_code == 422: 
                user_res = requests.get("https://api.github.com/user", headers=headers)
                if user_res.status_code == 200:
                    usuario = user_res.json().get('login')
                    url_clon = f"https://github.com/{usuario}/{nombre_repo}.git"
                    logger.info("[GIT] El repo ya existía, reconectando...")
                else:
                    return f"❌ Error validando token de GitHub. Verifica tu GITHUB_TOKEN."
            else:
                return f"❌ Error conectando con la API de GitHub: {res.text}"
                
            if tiene_remote:
                ejecutar_comando(f"git remote set-url origin {url_clon}", ruta_proyecto)
            else:
                ejecutar_comando(f"git remote add origin {url_clon}", ruta_proyecto)

    # 3. Guardar cambios
    logger.info("[GIT] Preparando commit y subiendo a la nube...")
    ejecutar_comando("git add .", ruta_proyecto)
    
    # Comprobamos si hay algo para comitear
    exito_st, out_st, _ = ejecutar_comando("git status --porcelain", ruta_proyecto)
    if out_st:
        exito_cmt, _, err_cmt = ejecutar_comando(f'git commit -m "{mensaje_commit}"', ruta_proyecto)
        if not exito_cmt:
            return f"❌ Fallo al hacer commit:\n{err_cmt}"
    else:
        logger.info("[GIT] No hay cambios nuevos para comitear.")

    # 4. Sincronizar (Push)
    ejecutar_comando("git branch -M main", ruta_proyecto)
    exito, stdout, err = ejecutar_comando("git push -u origin main", ruta_proyecto)
    
    if exito or "Everything up-to-date" in err or "Everything up-to-date" in stdout:
        destino = url_custom if url_custom else nombre_repo
        return f"✅ Éxito total. Proyecto respaldado correctamente en: {destino}"
    else:
        # Aquí capturamos conflictos (ej: non-fast-forward)
        return f"⚠️ Se guardó en tu PC, pero falló la subida a GitHub (posible conflicto):\n{err}"

def ejecutar_comando_git_libre(ruta_proyecto, comando_git):
    """Ejecuta comandos de lectura o sincronización segura de Git."""
    if not os.path.exists(ruta_proyecto):
        return f"❌ Error: La carpeta {ruta_proyecto} no existe."
        
    comando_git = comando_git.strip()
    if not comando_git.startswith("git "):
        return f"❌ Error de seguridad: Solo se permiten comandos Git. Recibido: {comando_git}"
        
    # Lista blanca de comandos permitidos (evitar borrados destructivos)
    comandos_seguros = ["git status", "git log", "git pull", "git fetch", "git branch", "git diff", "git show", "git checkout"]
    es_seguro = any(comando_git.startswith(cmd) for cmd in comandos_seguros)
    
    if not es_seguro:
        return f"❌ Comando bloqueado por seguridad. Solo se permiten comandos de lectura o pull. Comando intentado: {comando_git}"

    logger.info(f"[GIT] Ejecutando comando libre: {comando_git}")
    exito, stdout, err = ejecutar_comando(comando_git, ruta_proyecto)
    
    if exito:
        return f"✅ Comando '{comando_git}' ejecutado:\n{stdout}"
    else:
        return f"❌ Error al ejecutar '{comando_git}':\n{err}"