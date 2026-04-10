from pathlib import Path
import sys

# Ensure imports resolve regardless of Vercel project root.
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR))

from app import app as fastapi_app

app = fastapi_app
