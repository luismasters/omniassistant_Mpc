"""
audio_control.py — Funciones de control de audio para Argus.
Usa pycaw (Windows Core Audio API) para control de volumen maestro y por app.
Requiere: pip install pycaw comtypes
"""
import subprocess
from modulos.logger import logger


# ─── HELPERS INTERNOS ────────────────────────────────────────────────────────

def _set_master_volume_powershell(porcentaje: int) -> bool:
    """Establece el volumen maestro via PowerShell. Retorna True si éxito."""
    try:
        script = f"$obj = New-Object -ComObject WScript.Shell; " \
                 f"Add-Type -TypeDefinition @'\npublic class Vol {{\n" \
                 f"[System.Runtime.InteropServices.DllImport(\"winmm.dll\")]\n" \
                 f"public static extern int waveOutSetVolume(IntPtr h, uint v);\n}}\n'@; " \
                 f"$vol = [uint32](([uint16]::MaxValue) * {porcentaje / 100.0}); " \
                 f"[Vol]::waveOutSetVolume([IntPtr]::Zero, ($vol -bor ($vol -shl 16)))"
        # Método más simple: usar nircmd si está disponible, o el API de audio via script
        result = subprocess.run(
            ["powershell", "-Command",
             f"$vol = {porcentaje}; "
             f"$wshShell = New-Object -ComObject WScript.Shell; "
             f"Add-Type -AssemblyName System.Windows.Forms; "
             f"[System.Windows.Forms.SendKeys]::SendWait(''); "
             f"$device = Get-AudioDevice -Playback 2>$null; "
             f"if ($device) {{ Set-AudioDevice -Volume {porcentaje} }} "
             f"else {{ $vol }}"],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def _get_master_volume_interface():
    """
    Devuelve la interfaz IAudioEndpointVolume.
    Usa pycaw con CoInitialize para compatibilidad con threads secundarios.
    """
    import comtypes
    import comtypes.client
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL

    try:
        comtypes.CoInitialize()
    except OSError:
        pass

    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

    # pycaw 20251023+: GetAllDevices retorna objetos AudioDevice con ._dev
    try:
        all_devices = AudioUtilities.GetAllDevices()
        for dev in all_devices:
            if getattr(dev, 'state', None) == 1:  # ACTIVE
                raw = getattr(dev, '_dev', None)
                if raw is not None:
                    try:
                        iface = raw.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                        vol = cast(iface, POINTER(IAudioEndpointVolume))
                        vol.GetMasterVolumeLevelScalar()  # test
                        return vol
                    except Exception:
                        continue
    except Exception:
        pass

    # Fallback: API clásica (pycaw < 2023)
    devices = AudioUtilities.GetSpeakers()
    iface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(iface, POINTER(IAudioEndpointVolume))


# ─── VOLUMEN MAESTRO ─────────────────────────────────────────────────────────

def obtener_volumen() -> str:
    """Devuelve el volumen maestro actual como porcentaje (0-100)."""
    try:
        volume = _get_master_volume_interface()
        nivel = round(volume.GetMasterVolumeLevelScalar() * 100)
        muted = volume.GetMute()
        estado = " (silenciado)" if muted else ""
        return f"Volumen maestro: {nivel}%{estado}"
    except ImportError:
        return "Error: pycaw no está instalado. Ejecutá: pip install pycaw"
    except Exception:
        # Fallback PowerShell
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "[Math]::Round((Get-Volume).SoundOutput * 100)"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip().isdigit():
                return f"Volumen maestro: {result.stdout.strip()}%"
        except Exception:
            pass
        return "No se pudo obtener el volumen maestro."


def establecer_volumen(porcentaje: int) -> str:
    """Establece el volumen maestro al porcentaje indicado (0-100)."""
    try:
        porcentaje = max(0, min(100, porcentaje))
        volume = _get_master_volume_interface()
        volume.SetMasterVolumeLevelScalar(porcentaje / 100.0, None)
        return f"✅ Volumen maestro establecido al {porcentaje}%"
    except ImportError:
        return "Error: pycaw no está instalado. Ejecutá: pip install pycaw"
    except Exception:
        # Fallback PowerShell via nircmd o WScript
        try:
            porcentaje = max(0, min(100, porcentaje))
            result = subprocess.run(
                ["powershell", "-Command",
                 f"(New-Object -ComObject WScript.Shell).SendKeys([char]173); "
                 f"$vol = {porcentaje}; "
                 f"Add-Type -AssemblyName System.Windows.Forms; "
                 f"[System.Audio.AudioPlaybackConnection] 2>$null; "
                 f"Set-Volume -Volume ($vol / 100) 2>$null"],
                capture_output=True, text=True, timeout=5
            )
            # Último fallback: nircmd
            result2 = subprocess.run(
                ["nircmd", "setsysvolume", str(int(porcentaje / 100 * 65535))],
                capture_output=True, text=True, timeout=3
            )
            if result2.returncode == 0:
                return f"✅ Volumen maestro al {porcentaje}%"
        except Exception:
            pass
        return f"No se pudo cambiar el volumen maestro. El control por app (ej: 'volumen del navegador al X%') sí funciona."


def subir_volumen(incremento: int = 10) -> str:
    """Sube el volumen maestro en `incremento` puntos porcentuales (default: 10)."""
    try:
        volume = _get_master_volume_interface()
        actual = round(volume.GetMasterVolumeLevelScalar() * 100)
        nuevo = min(100, actual + incremento)
        volume.SetMasterVolumeLevelScalar(nuevo / 100.0, None)
        return f"✅ Volumen subido de {actual}% a {nuevo}%"
    except Exception:
        return establecer_volumen(50)  # fallback razonable


def bajar_volumen(decremento: int = 10) -> str:
    """Baja el volumen maestro en `decremento` puntos porcentuales (default: 10)."""
    try:
        volume = _get_master_volume_interface()
        actual = round(volume.GetMasterVolumeLevelScalar() * 100)
        nuevo = max(0, actual - decremento)
        volume.SetMasterVolumeLevelScalar(nuevo / 100.0, None)
        return f"✅ Volumen bajado de {actual}% a {nuevo}%"
    except Exception:
        return "No se pudo bajar el volumen maestro."


def silenciar(silenciar: bool = True) -> str:
    """Silencia (True) o activa (False) el audio maestro."""
    try:
        volume = _get_master_volume_interface()
        volume.SetMute(1 if silenciar else 0, None)
        accion = "silenciado" if silenciar else "activado"
        return f"✅ Audio maestro {accion}"
    except Exception as e:
        logger.exception("Error silenciando audio")
        return f"Error al silenciar: {e}"


# ─── VOLUMEN POR APLICACIÓN ───────────────────────────────────────────────────

def _encontrar_sesion(nombre_app: str):
    """Busca la sesión de audio de una app por nombre (parcial, case-insensitive)."""
    import comtypes
    try:
        comtypes.CoInitialize()
    except OSError:
        pass
    from pycaw.pycaw import AudioUtilities
    sesiones = AudioUtilities.GetAllSessions()
    nombre_lower = nombre_app.lower()
    for sesion in sesiones:
        if sesion.Process:
            proc_name = sesion.Process.name().lower()
            if nombre_lower in proc_name:
                return sesion
    return None


def obtener_volumen_app(nombre_app: str) -> str:
    """Devuelve el volumen actual de una aplicación específica."""
    try:
        from pycaw.pycaw import ISimpleAudioVolume
        sesion = _encontrar_sesion(nombre_app)
        if not sesion:
            return f"No encontré ninguna app activa con el nombre '{nombre_app}'."
        vol = sesion._ctl.QueryInterface(ISimpleAudioVolume)
        nivel = round(vol.GetMasterVolume() * 100)
        muted = vol.GetMute()
        estado = " (silenciada)" if muted else ""
        proc = sesion.Process.name()
        return f"Volumen de {proc}: {nivel}%{estado}"
    except ImportError:
        return "Error: pycaw no está instalado. Ejecutá: pip install pycaw"
    except Exception as e:
        logger.exception(f"Error obteniendo volumen de {nombre_app}")
        return f"Error al obtener volumen de {nombre_app}: {e}"


def establecer_volumen_app(nombre_app: str, porcentaje: int) -> str:
    """Establece el volumen de una aplicación específica al porcentaje indicado."""
    try:
        from pycaw.pycaw import ISimpleAudioVolume
        porcentaje = max(0, min(100, porcentaje))
        sesion = _encontrar_sesion(nombre_app)
        if not sesion:
            return f"No encontré ninguna app activa con el nombre '{nombre_app}'."
        vol = sesion._ctl.QueryInterface(ISimpleAudioVolume)
        vol.SetMasterVolume(porcentaje / 100.0, None)
        proc = sesion.Process.name()
        return f"✅ Volumen de {proc} establecido al {porcentaje}%"
    except ImportError:
        return "Error: pycaw no está instalado. Ejecutá: pip install pycaw"
    except Exception as e:
        logger.exception(f"Error estableciendo volumen de {nombre_app}")
        return f"Error al establecer volumen de {nombre_app}: {e}"


def silenciar_app(nombre_app: str, silenciar_flag: bool = True) -> str:
    """Silencia o activa el audio de una aplicación específica."""
    try:
        from pycaw.pycaw import ISimpleAudioVolume
        sesion = _encontrar_sesion(nombre_app)
        if not sesion:
            return f"No encontré ninguna app activa con el nombre '{nombre_app}'."
        vol = sesion._ctl.QueryInterface(ISimpleAudioVolume)
        vol.SetMute(1 if silenciar_flag else 0, None)
        proc = sesion.Process.name()
        accion = "silenciada" if silenciar_flag else "activada"
        return f"✅ {proc} {accion}"
    except ImportError:
        return "Error: pycaw no está instalado. Ejecutá: pip install pycaw"
    except Exception as e:
        logger.exception(f"Error silenciando {nombre_app}")
        return f"Error al silenciar {nombre_app}: {e}"


def listar_apps_con_audio() -> str:
    """Lista todas las aplicaciones que actualmente producen audio."""
    try:
        from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
        sesiones = AudioUtilities.GetAllSessions()
        apps = []
        for sesion in sesiones:
            if sesion.Process:
                try:
                    vol = sesion._ctl.QueryInterface(ISimpleAudioVolume)
                    nivel = round(vol.GetMasterVolume() * 100)
                    muted = vol.GetMute()
                    estado = " 🔇" if muted else ""
                    apps.append(f"  • {sesion.Process.name()} — {nivel}%{estado}")
                except Exception:
                    apps.append(f"  • {sesion.Process.name()}")
        if apps:
            return "Apps con audio activo:\n" + "\n".join(apps)
        return "No hay aplicaciones produciendo audio en este momento."
    except ImportError:
        return "Error: pycaw no está instalado. Ejecutá: pip install pycaw"
    except Exception as e:
        logger.exception("Error listando apps con audio")
        return f"Error al listar apps: {e}"


# ─── DISPOSITIVOS DE SALIDA ───────────────────────────────────────────────────

def listar_dispositivos_audio() -> str:
    """Lista todos los dispositivos de salida de audio disponibles."""
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-AudioDevice -List | Where-Object {$_.Type -eq 'Playback'} | Select-Object Index, Name, Default | Format-Table -AutoSize"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return f"Dispositivos de audio disponibles:\n{result.stdout.strip()}"
        # Fallback: pycaw enumerate
        from pycaw.pycaw import AudioUtilities
        dispositivos = AudioUtilities.GetAllDevices()
        lista = [f"  • {d.FriendlyName}" for d in dispositivos if d.state == 1]
        return "Dispositivos de audio activos:\n" + "\n".join(lista) if lista else "No se encontraron dispositivos."
    except Exception as e:
        logger.exception("Error listando dispositivos")
        return f"Error al listar dispositivos: {e}"


def cambiar_dispositivo_audio(nombre_o_indice: str) -> str:
    """
    Cambia el dispositivo de salida de audio predeterminado.
    Acepta el nombre del dispositivo o su índice numérico (de listar_dispositivos).
    """
    import comtypes
    try:
        comtypes.CoInitialize()
    except OSError:
        pass

    # Intentar primero con pycaw si tiene el método disponible
    try:
        from pycaw.pycaw import AudioUtilities
        devices = AudioUtilities.GetAllDevices()

        # Si es un número, buscar por índice (base 1, igual que listar_dispositivos)
        target = None
        if nombre_o_indice.strip().isdigit():
            idx = int(nombre_o_indice.strip()) - 1
            activos = [d for d in devices if d.state == 1]
            if 0 <= idx < len(activos):
                target = activos[idx]
        else:
            # Buscar por nombre parcial
            nombre_lower = nombre_o_indice.lower()
            for d in devices:
                if d.state == 1 and nombre_lower in d.FriendlyName.lower():
                    target = d
                    break

        if target and hasattr(target, 'SetAsDefault'):
            target.SetAsDefault()
            return f"✅ Dispositivo cambiado a: {target.FriendlyName}"
        elif target:
            nombre_dispositivo = target.FriendlyName
            # Intentar via PowerShell con el nombre exacto
            result = subprocess.run(
                ["powershell", "-Command",
                 f"Set-AudioDevice -Name '{nombre_dispositivo}'"],
                capture_output=True, text=True, timeout=8
            )
            if result.returncode == 0:
                return f"✅ Dispositivo cambiado a: {nombre_dispositivo}"
    except Exception:
        pass

    # Fallback: PowerShell por índice
    try:
        idx_str = nombre_o_indice.strip()
        if idx_str.isdigit():
            result = subprocess.run(
                ["powershell", "-Command",
                 f"Set-AudioDevice -Index {idx_str}"],
                capture_output=True, text=True, timeout=8
            )
            if result.returncode == 0:
                return f"✅ Dispositivo de audio cambiado (índice {idx_str})"

        result = subprocess.run(
            ["powershell", "-Command",
             f"Set-AudioDevice -Name '{nombre_o_indice}'"],
            capture_output=True, text=True, timeout=8
        )
        if result.returncode == 0:
            return f"✅ Dispositivo cambiado a: {nombre_o_indice}"

        return (
            f"No se pudo cambiar al dispositivo '{nombre_o_indice}'. "
            "Para habilitar el cambio de dispositivo instalá el módulo PowerShell:\n"
            "PowerShell (admin): Install-Module -Name AudioDeviceCmdlets\n"
            "Luego podés usar el índice o nombre del dispositivo listado."
        )
    except Exception as e:
        logger.exception("Error cambiando dispositivo de audio")
        return f"Error al cambiar dispositivo: {e}"