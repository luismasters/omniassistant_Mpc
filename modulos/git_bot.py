import os
import subprocess
import requests
from config import GITHUB_TOKEN

def ejecutar_comando(comando, cwd):
    # Ejecuta comandos de consola en silencio y captura la respuesta
    resultado = subprocess.run(comando, shell=True, cwd=cwd, capture_output=True, text=True)
    return resultado.returncode == 0, resultado.stdout, resultado.stderr

def sincronizar_proyecto_git(ruta_proyecto, mensaje_commit="Subida automática vía Cortana"):
    print(f"⚙️ [GIT REAL] Analizando la carpeta: {ruta_proyecto}")
    
    if not os.path.exists(ruta_proyecto):
        return f"Error: La carpeta {ruta_proyecto} no existe."
        
    nombre_repo = os.path.basename(os.path.normpath(ruta_proyecto))
    
    # 1. Verificar si es un repositorio Git local (Escáner de carpeta virgen)
    ruta_git = os.path.join(ruta_proyecto, ".git")
    
    if not os.path.exists(ruta_git):
        print("⚙️ [GIT REAL] Inicializando nuevo repositorio local...")
        exito, _, err = ejecutar_comando("git init", ruta_proyecto)
        if not exito: return f"Error al inicializar git localmente: {err}"
        
    # 2. Verificar si tiene conexión a GitHub (Radar de la nube)
    exito, stdout, _ = ejecutar_comando("git remote -v", ruta_proyecto)
    tiene_remote = "origin" in stdout
    
    if not tiene_remote:
        print(f"⚙️ [GIT REAL] Creando repositorio '{nombre_repo}' en tu GitHub...")
        url_api = "https://api.github.com/user/repos"
        headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
        # Lo creamos PRIVADO por defecto para cuidar tu código
        payload = {"name": nombre_repo, "private": True} 
        
        res = requests.post(url_api, headers=headers, json=payload)
        
        if res.status_code == 201: 
            url_clon = res.json()['clone_url']
        elif res.status_code == 422: 
            # Si el repo ya existía en la nube, reconstruimos la URL dinámicamente
            user_res = requests.get("https://api.github.com/user", headers=headers)
            usuario = user_res.json().get('login')
            url_clon = f"https://github.com/{usuario}/{nombre_repo}.git"
            print("⚙️ [GIT REAL] El repo ya existía en la nube, reconectando puente...")
        else:
            return f"Error conectando con la API de GitHub: {res.text}"
            
        # (Acá termina el bloque de requests.post a la API...)
            
        ejecutar_comando(f"git remote add origin {url_clon}", ruta_proyecto)

    # 3. Guardar cambios (Commit Automático) - ESTO VA PRIMERO AHORA
    print("⚙️ [GIT REAL] Preparando commit y subiendo a la nube...")
    ejecutar_comando("git add .", ruta_proyecto)
    ejecutar_comando(f'git commit -m "{mensaje_commit}"', ruta_proyecto)
    
    # 4. Renombrar la rama y subir (Git necesita que el commit ya exista para esto)
    ejecutar_comando("git branch -M main", ruta_proyecto)
    exito, stdout, err = ejecutar_comando("git push -u origin main", ruta_proyecto)
    
    if exito or "Everything up-to-date" in err or "Everything up-to-date" in stdout:
        return f"Éxito total. Tu proyecto '{nombre_repo}' está sincronizado y a salvo en GitHub."
    else:
        return f"Se guardó localmente, pero falló la subida a internet: {err}"