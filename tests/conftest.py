import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["OMNASSISTANT_NO_FILE_LOG"] = "1"
