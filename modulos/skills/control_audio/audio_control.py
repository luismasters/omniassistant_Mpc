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


def _obtener_com_device_activatable(dev):
    """
    Intenta extraer el puntero COM real (IMMDevice, con método .Activate)
    de un objeto AudioDevice de pycaw, sin importar la versión instalada.
    FIX: distintas versiones de pycaw exponen el puntero COM crudo bajo
    distintos nombres de atributo interno (`_dev`, `dev`, etc.), o incluso
    lo entregan directo sin envolver. Antes el código asumía siempre `_dev`
    en el camino principal, y en el fallback (AudioUtilities.GetSpeakers())
    asumía que el objeto devuelto YA era el puntero COM crudo — ninguna de
    las dos suposiciones se cumplía en todas las versiones, y terminaba en
    AttributeError: 'AudioDevice' object has no attribute 'Activate'.
    """
    if dev is None:
        return None
    if hasattr(dev, "Activate"):
        return dev
    for attr in ("_dev", "dev", "_device"):
        raw = getattr(dev, attr, None)
        if raw is not None and hasattr(raw, "Activate"):
            return raw
    return None


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

    # Intento 1: recorrer todos los dispositivos activos y usar el real por defecto
    try:
        all_devices = AudioUtilities.GetAllDevices()
        for dev in all_devices:
            if getattr(dev, 'state', None) == 1:  # ACTIVE
                raw = _obtener_com_device_activatable(dev)
                if raw is not None:
                    try:
                        iface = raw.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                        vol = cast(iface, POINTER(IAudioEndpointVolume))
                        vol.GetMasterVolumeLevelScalar()  # test de que responde
                        return vol
                    except Exception:
                        continue
    except Exception:
        pass

    # Intento 2 (fallback): API clásica, con la misma extracción robusta
    try:
        speakers = AudioUtilities.GetSpeakers()
        raw = _obtener_com_device_activatable(speakers)
        if raw is not None:
            iface = raw.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            return cast(iface, POINTER(IAudioEndpointVolume))
    except Exception:
        pass

    raise RuntimeError(
        "No se pudo obtener la interfaz de volumen maestro con la versión de "
        "pycaw instalada. Probá: pip install --upgrade pycaw"
    )


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


# ─── CAMBIO NATIVO DE DISPOSITIVO POR DEFECTO (sin PowerShell externo) ───────
# IPolicyConfig es una interfaz COM NO documentada oficialmente por Microsoft,
# pero estable desde Windows 7 y es la misma que usan internamente herramientas
# reales como EarTrumpet, SoundSwitch, NAudio y el propio AudioDeviceCmdlets.
# Se implementa acá directo con comtypes para no depender de que el usuario
# instale el módulo de PowerShell AudioDeviceCmdlets.
#
# ADVERTENCIA: no fue posible probar esto en un entorno Windows real durante
# su creación. Por eso se usa como PRIMER intento en una cadena de fallbacks
# (nativo → pycaw.SetAsDefault → PowerShell), nunca como único camino.

def _fabricar_policy_config():
    import comtypes
    from comtypes import GUID, COMMETHOD, HRESULT, IUnknown, CoCreateInstance, CLSCTX_ALL
    from ctypes import c_wchar_p, c_int, c_void_p, c_longlong, POINTER

    CLSID_POLICY_CONFIG = GUID("{870af99c-171d-4f9e-af0d-e63df40c2bc9}")
    IID_IPOLICY_CONFIG = GUID("{f8679f50-850a-41cf-9c72-430f290290c8}")

    class IPolicyConfig(IUnknown):
        _case_insensitive_ = True
        _iid_ = IID_IPOLICY_CONFIG
        _methods_ = [
            COMMETHOD([], HRESULT, 'GetMixFormat',
                      (['in'], c_wchar_p, 'device_id'),
                      (['out'], POINTER(c_void_p), 'device_format')),
            COMMETHOD([], HRESULT, 'GetDeviceFormat',
                      (['in'], c_wchar_p, 'device_id'),
                      (['in'], c_int, 'default'),
                      (['out'], POINTER(c_void_p), 'ppformat')),
            COMMETHOD([], HRESULT, 'ResetDeviceFormat',
                      (['in'], c_wchar_p, 'device_id')),
            COMMETHOD([], HRESULT, 'SetDeviceFormat',
                      (['in'], c_wchar_p, 'device_id'),
                      (['in'], c_void_p, 'endpoint_format'),
                      (['in'], c_void_p, 'mix_format')),
            COMMETHOD([], HRESULT, 'GetProcessingPeriod',
                      (['in'], c_wchar_p, 'device_id'),
                      (['in'], c_int, 'default'),
                      (['out'], POINTER(c_longlong), 'default_period'),
                      (['out'], POINTER(c_longlong), 'minimum_period')),
            COMMETHOD([], HRESULT, 'SetProcessingPeriod',
                      (['in'], c_wchar_p, 'device_id'),
                      (['in'], c_longlong, 'period')),
            COMMETHOD([], HRESULT, 'GetShareMode',
                      (['in'], c_wchar_p, 'device_id'),
                      (['out'], POINTER(c_void_p), 'mode')),
            COMMETHOD([], HRESULT, 'SetShareMode',
                      (['in'], c_wchar_p, 'device_id'),
                      (['in'], c_void_p, 'mode')),
            COMMETHOD([], HRESULT, 'GetPropertyValue',
                      (['in'], c_wchar_p, 'device_id'),
                      (['in'], c_int, 'fx_store'),
                      (['in'], c_void_p, 'key'),
                      (['out'], c_void_p, 'pv')),
            COMMETHOD([], HRESULT, 'SetPropertyValue',
                      (['in'], c_wchar_p, 'device_id'),
                      (['in'], c_int, 'fx_store'),
                      (['in'], c_void_p, 'key'),
                      (['in'], c_void_p, 'pv')),
            COMMETHOD([], HRESULT, 'SetDefaultEndpoint',
                      (['in'], c_wchar_p, 'device_id'),
                      (['in'], c_int, 'role')),
            COMMETHOD([], HRESULT, 'SetEndpointVisibility',
                      (['in'], c_wchar_p, 'device_id'),
                      (['in'], c_int, 'visible')),
        ]

    try:
        comtypes.CoInitialize()
    except OSError:
        pass

    return CoCreateInstance(CLSID_POLICY_CONFIG, IPolicyConfig, CLSCTX_ALL)


def _establecer_dispositivo_nativo(device_id: str) -> bool:
    """
    Establece el dispositivo por defecto para los 3 roles de Windows
    (eConsole=0, eMultimedia=1, eCommunications=2) usando IPolicyConfig
    directo, sin depender de AudioDeviceCmdlets.
    """
    try:
        policy_config = _fabricar_policy_config()
        for role in (0, 1, 2):
            policy_config.SetDefaultEndpoint(device_id, role)
        return True
    except Exception:
        logger.exception("Error estableciendo dispositivo vía IPolicyConfig nativo")
        return False


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


def _buscar_dispositivo_powershell(nombre_o_indice: str):
    """
    Busca un dispositivo usando la MISMA fuente de datos que
    listar_dispositivos_audio() (AudioDeviceCmdlets vía PowerShell).
    FIX: antes cambiar_dispositivo_audio buscaba el dispositivo con pycaw
    (AudioUtilities.GetAllDevices()), una fuente DISTINTA a la que usa el
    listado. pycaw suele exponer el FriendlyName crudo del endpoint (ej.
    "JBL Go4 Lu"), mientras que AudioDeviceCmdlets/Windows le agrega el
    prefijo "Altavoces (" al nombre que el usuario ve en pantalla — la
    búsqueda por substring nunca coincidía, y el índice que el usuario veía
    en el listado tampoco correspondía al orden interno de pycaw. Usando acá
    la misma fuente que el listado, índice y nombre siempre coinciden con
    lo que el usuario efectivamente vio.
    Devuelve (indice_powershell, nombre_dispositivo) o (None, None).
    """
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-AudioDevice -List | Where-Object {$_.Type -eq 'Playback'} | "
             "ForEach-Object { '{0}|{1}' -f $_.Index, $_.Name }"],
            capture_output=True, text=True, timeout=5
        )
        # DIAGNÓSTICO: antes esta función fallaba en silencio (sin excepción)
        # cuando returncode != 0 o stdout venía vacío, sin dejar rastro en el
        # log. Ahora se registra siempre el resultado crudo para poder ver
        # exactamente qué devolvió PowerShell en el caso de fallo.
        logger.info(
            f"[AUDIO] PowerShell returncode={result.returncode} "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        if result.returncode != 0 or not result.stdout.strip():
            logger.warning(f"[AUDIO] PowerShell no devolvió datos usables (returncode={result.returncode})")
            return None, None

        filas = [l.strip() for l in result.stdout.strip().splitlines() if "|" in l]
        objetivo = nombre_o_indice.strip()

        # Búsqueda por índice exacto (el mismo número que ve el usuario en el listado)
        if objetivo.isdigit():
            for fila in filas:
                idx, nombre = fila.split("|", 1)
                if idx.strip() == objetivo:
                    return idx.strip(), nombre.strip()
            logger.warning(f"[AUDIO] Índice '{objetivo}' no encontrado entre las filas: {filas}")
            return None, None

        # Búsqueda por nombre parcial, case-insensitive
        objetivo_lower = objetivo.lower()
        for fila in filas:
            idx, nombre = fila.split("|", 1)
            if objetivo_lower in nombre.strip().lower():
                return idx.strip(), nombre.strip()

        logger.warning(f"[AUDIO] Nombre '{objetivo}' no coincidió con ninguna fila: {filas}")
        return None, None
    except Exception:
        logger.exception("Error buscando dispositivo vía PowerShell/AudioDeviceCmdlets")
        return None, None


def _limpiar_nombre_dispositivo(texto: str) -> str:
    """
    Quita comillas simples/dobles que suelen quedar pegadas al nombre del
    dispositivo. FIX: el modelo emite comandos como
    `audio: cambiar_dispositivo "Altavoces (JBL Go4 Lu)"`, y el parser de
    controlador_acciones.py separa los argumentos con `.split()` por espacios
    sin despojar las comillas — así que el nombre le llegaba a esta función
    literalmente como `"Altavoces (JBL Go4 Lu)"` (con las comillas incluidas),
    y por eso NUNCA coincidía por substring contra el nombre real reportado
    por PowerShell/pycaw (que no tiene comillas). Esta limpieza es la causa
    real de los fallos anteriores — no era un problema de PowerShell ni pycaw.
    """
    return texto.strip().strip('"').strip("'").strip()


def cambiar_dispositivo_audio(nombre_o_indice: str) -> str:
    """
    Cambia el dispositivo de salida de audio predeterminado.
    Acepta el nombre del dispositivo o su índice numérico (de listar_dispositivos).

    ORDEN DE INTENTOS:
    1. AudioDeviceCmdlets (PowerShell) — MISMA fuente de datos que
       listar_dispositivos_audio, así que el índice/nombre que el usuario
       vio en el listado es garantizado el mismo acá. Prioridad #1 si el
       módulo está instalado (evita el desajuste entre pycaw y PowerShell
       que causaba falsos "no encontrado").
    2. pycaw + IPolicyConfig nativo — si AudioDeviceCmdlets no está disponible.
    3. pycaw SetAsDefault() — si la versión instalada lo expone.
    """
    nombre_o_indice = _limpiar_nombre_dispositivo(nombre_o_indice)

    # Intento 1: AudioDeviceCmdlets, misma fuente que el listado
    idx_ps, nombre_ps = _buscar_dispositivo_powershell(nombre_o_indice)
    if idx_ps is not None:
        try:
            result = subprocess.run(
                ["powershell", "-Command", f"Set-AudioDevice -Index {idx_ps}"],
                capture_output=True, text=True, timeout=8
            )
            logger.info(
                f"[AUDIO] Set-AudioDevice -Index {idx_ps} -> returncode={result.returncode} "
                f"stdout={result.stdout!r} stderr={result.stderr!r}"
            )
            if result.returncode == 0:
                return f"✅ Dispositivo cambiado a: {nombre_ps}"
        except Exception:
            logger.exception("Error ejecutando Set-AudioDevice")
    else:
        logger.warning(f"[AUDIO] _buscar_dispositivo_powershell no encontró coincidencia para '{nombre_o_indice}'")

    # Intentos 2 y 3: pycaw como respaldo, si AudioDeviceCmdlets no está
    # instalado o falló por algún motivo
    import comtypes
    try:
        comtypes.CoInitialize()
    except OSError:
        pass

    try:
        from pycaw.pycaw import AudioUtilities
        devices = AudioUtilities.GetAllDevices()

        target = None
        if nombre_o_indice.strip().isdigit():
            idx = int(nombre_o_indice.strip()) - 1
            activos = [d for d in devices if d.state == 1]
            if 0 <= idx < len(activos):
                target = activos[idx]
        else:
            nombre_lower = nombre_o_indice.lower()
            for d in devices:
                if d.state == 1 and nombre_lower in d.FriendlyName.lower():
                    target = d
                    break

        if target:
            device_id = getattr(target, 'id', None)
            if device_id and _establecer_dispositivo_nativo(device_id):
                return f"✅ Dispositivo cambiado a: {target.FriendlyName}"
            if hasattr(target, 'SetAsDefault'):
                try:
                    target.SetAsDefault()
                    return f"✅ Dispositivo cambiado a: {target.FriendlyName}"
                except Exception:
                    pass
    except Exception:
        logger.exception("Error cambiando dispositivo de audio vía pycaw")

    return (
        f"⚠️ No se pudo cambiar al dispositivo '{nombre_o_indice}' por ninguno de los "
        "métodos disponibles. Verificá el nombre/índice exacto con 'listar_dispositivos'. "
        "Si el problema persiste, instalá:\n"
        "PowerShell (admin): Install-Module -Name AudioDeviceCmdlets"
    )