import logging
import logging.handlers
import os
import sys
from pathlib import Path

# Configurar ruta de los logs
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "omniassistant.log"

# Formato estándar para los logs
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

# Forzar UTF-8 en consola para Windows (evita UnicodeEncodeError con emojis en stdout/stderr)
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

class _RotatingFileHandlerRobusto(logging.handlers.RotatingFileHandler):
    """
    RotatingFileHandler tolerante a bloqueos de archivo en Windows.

    En Windows no se puede renombrar un archivo que otra proceso tiene abierto.
    Si la rotación falla (ej. otra instancia de Argus mantiene omniassistant.log
    abierto), en lugar de dejar el handler roto y escupir "Logging error" en cada
    línea, se reabre el stream y se reintenta en la siguiente emisión.
    """
    def doRollover(self):
        try:
            super().doRollover()
        except (PermissionError, OSError):
            # La rotación falló por un archivo bloqueado. Reabrimos el stream
            # para que el logging siga funcionando y reintentamos en el próximo emit.
            if self.stream is None:
                try:
                    self.stream = self._open()
                except OSError:
                    pass

# Handler para guardar en archivo físico (con rotación para evitar llenar el disco)
# Deshabilitable vía OMNASSISTANT_NO_FILE_LOG=1 (útil para CI / headless / tests).
if not os.environ.get("OMNASSISTANT_NO_FILE_LOG"):
    file_handler = _RotatingFileHandlerRobusto(
        str(LOG_FILE),
        encoding='utf-8',
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,              # 5 archivos de respaldo (omniassistant.log.1 ... .5)
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Handler para mostrar en consola de VS Code
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # Configurar el logger principal
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
else:
    # En modo CI/headless, un NullHandler para no generar logs en disco.
    logging.getLogger().addHandler(logging.NullHandler())

# Exportamos el logger para usarlo en otros módulos
logger = logging.getLogger(__name__)