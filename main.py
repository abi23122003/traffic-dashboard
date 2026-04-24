"""Compatibility entrypoint for Uvicorn.

This allows commands like `uvicorn main:app` to work while the real
FastAPI application lives in app/app.py.
"""

from app.app import app


__all__ = ["app"]
