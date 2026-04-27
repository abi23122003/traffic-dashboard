"""Compatibility entrypoint for Uvicorn.

This allows commands like `uvicorn main:app` to work while the real
FastAPI application lives in app/app.py.

Socket.IO is served via python-socketio's ASGIApp wrapper (asgi_app), which
intercepts /socket.io/* requests itself and forwards everything else to the
FastAPI app. Uvicorn must point at `main:app` which resolves to that wrapper.
"""

from app.app import asgi_app as app  # noqa: F401 – re-exported as `app`

__all__ = ["app"]
