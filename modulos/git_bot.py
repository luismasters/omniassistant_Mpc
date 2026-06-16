import os
import logging
try:
    import git
except ImportError:
    git = None

logger = logging.getLogger(__name__)

def sincronizar_proyecto_git(ruta_workspace, reset_remote=False, url_custom=None):
    """
    Fase 2 del Plan: Secuencia segura (Init -> Add -> Commit -> Pull -> Push)
    """
    if git is None:
        return "❌ Error: La librería 'gitpython' no está instalada. Ejecuta 'pip install gitpython'."
    
    if not ruta_workspace or not os.path.exists(ruta_workspace):
        return "❌ Error: La ruta del workspace no existe."

    try:
        # Fase 1: Inicialización Segura (Bajo demanda, no global)
        try:
            repo = git.Repo(ruta_workspace)
        except git.exc.InvalidGitRepositoryError:
            # Tarea 8: init_repo si no existe
            repo = git.Repo.init(ruta_workspace)
            return f"✅ Repositorio inicializado en {ruta_workspace}. Configura un remoto (origin) para poder hacer push."

        # Manejo de remotos (Resetear/Agregar si el usuario lo pidió)
        if reset_remote and url_custom:
            try:
                repo.delete_remote('origin')
            except Exception:
                pass
            repo.create_remote('origin', url_custom)
        
        # Tarea 4: Verificación de remoto
        if not repo.remotes:
            return "❌ No hay remoto configurado (origin). Pídele a Cortana que agregue el remoto usando 'git_comando:'."

        origin = repo.remote(name='origin')

        # Tarea 5: Asegurar cambios locales ANTES del pull (Add y Commit)
        hay_cambios_locales = repo.is_dirty(untracked_files=True)
        if hay_cambios_locales:
            repo.git.add(all=True)
            repo.index.commit("Auto-commit: Actualización generada vía OmniAssistant (Cortana)")

        # Tarea 6: Pull con rebase AHORA que el árbol está limpio
        try:
            repo.git.pull('origin', repo.active_branch.name, '--rebase')
        except Exception as e:
            error_str = str(e).lower()
            if "couldn't find remote ref" in error_str or "no such ref" in error_str:
                # Es normal que falle si la rama remota aún no existe (primer push)
                pass
            else:
                return f"⚠️ Advertencia o conflicto al hacer pull: {e}"

        # Push Final
        push_info = origin.push()
        
        # Validación de errores en el Push
        for info in push_info:
            if info.flags & git.remote.PushInfo.ERROR:
                return f"❌ Error al hacer push: {info.summary}"

        if not hay_cambios_locales:
            return "ℹ️ El proyecto ya estaba al día (no había cambios locales), sincronización verificada."

        return "✅ Proyecto sincronizado con GitHub exitosamente (Add -> Commit -> Pull -> Push)."

    except Exception as e:
        logger.error(f"Error en sincronización Git: {e}")
        return f"❌ Error crítico en Git: {str(e)}"


def ejecutar_comando_git_libre(ruta_workspace, comando):
    """Permite ejecutar comandos sueltos, ej: git status, git log"""
    if git is None:
        return "❌ Error: 'gitpython' no instalado."
    
    try:
        repo = git.Repo(ruta_workspace)
        # Limpiamos el comando por si el usuario incluyó la palabra 'git'
        cmd_limpio = comando.replace("git ", "").strip().split(" ")
        
        resultado = repo.git.execute(["git"] + cmd_limpio)
        return f"✅ Comando ejecutado exitosamente:\n{resultado}"
    except git.exc.InvalidGitRepositoryError:
        return "❌ Error: La carpeta actual no es un repositorio Git válido."
    except Exception as e:
        return f"❌ Error ejecutando comando Git: {e}"