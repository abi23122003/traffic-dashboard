"""Compatibility entrypoint for Uvicorn.

This allows commands like `uvicorn main:app` to work while the real
FastAPI application lives in app.py.
"""

from app import app


__all__ = ["app"]
