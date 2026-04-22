"""
Simple local launcher for the Traffic Dashboard.

This script is used by START.bat and START.sh so the app can be started
with a single command on Windows or Unix-like systems.
"""

from __future__ import annotations

import os
import threading
import time
import webbrowser
from pathlib import Path

from dotenv import load_dotenv
import uvicorn


ROOT_DIR = Path(__file__).resolve().parent


def main() -> int:
    os.chdir(ROOT_DIR)
    load_dotenv(ROOT_DIR / ".env")

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    browser_host = "127.0.0.1" if host == "0.0.0.0" else host
    app_url = f"http://{browser_host}:{port}"

    print("Starting Traffic Dashboard...")
    print(f"Server URL: {app_url}")
    print("Press Ctrl+C to stop the server.")

    def _open_browser() -> None:
        # Give the ASGI server a moment to bind before opening the browser.
        time.sleep(2)
        try:
            webbrowser.open(app_url)
        except Exception:
            pass

    threading.Thread(target=_open_browser, daemon=True).start()
    uvicorn.run("main:app", host=host, port=port, reload=False)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nServer stopped.")
        raise SystemExit(0)
