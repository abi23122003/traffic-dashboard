"""Shared filesystem paths for the project."""

from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
ROOT_DIR = BACKEND_DIR.parent

DATA_DIR = BACKEND_DIR / "data"
STATIC_DIR = ROOT_DIR / "frontend" / "static"
TEMPLATES_DIR = ROOT_DIR / "frontend" / "templates"
LOGS_DIR = BACKEND_DIR / "logs"
ENV_FILE = ROOT_DIR / ".env"
