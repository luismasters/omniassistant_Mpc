import logging
import sys
from pathlib import Path

# Configurar ruta de los logs
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "omniassistant.log"

# Formato estándar para los logs
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

# Handler para guardar en archivo físico
file_handler = logging.FileHandler(str(LOG_FILE), encoding='utf-8')
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

# Exportamos el logger para usarlo en otros módulos
logger = logging.getLogger(__name__)