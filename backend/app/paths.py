"""Shared filesystem paths for the project."""

from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
ROOT_DIR = APP_DIR.parent
DATA_DIR = ROOT_DIR / "data"
STATIC_DIR = ROOT_DIR.parent / "frontend" / "static"
TEMPLATES_DIR = ROOT_DIR.parent / "frontend" / "templates"
LOGS_DIR = ROOT_DIR / "logs"
ENV_FILE = ROOT_DIR / ".env"
