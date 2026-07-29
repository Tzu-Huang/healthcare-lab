import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ["LAB_APP_HOST"] = "127.0.0.1"
os.environ["LAB_APP_PORT"] = "5051"
os.environ["HEALTHCARE_LAB_DB"] = ".tmp/inspection-healthcare-lab.db"

from backend.app_factory import main

main()
