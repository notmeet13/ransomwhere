import sys
import os
from pathlib import Path

# Add the project root to sys.path
# This allows 'import ForenSync' to work
ROOT_DIR = Path(__file__).parent.parent
sys.path.append(str(ROOT_DIR))
sys.path.append(str(ROOT_DIR / "ForenSync"))

from ForenSync.app import app as fastapi_app

# Vercel needs 'app' to be the entry point
app = fastapi_app
