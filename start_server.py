"""
Simple local launcher for the Traffic Dashboard.

This script is used by START.bat and START.sh so the app can be started
with a single command on Windows or Unix-like systems.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

from dotenv import load_dotenv


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
    print("Server is warming up. The browser will open automatically once the app is ready.")
    print("Press Ctrl+C to stop the server.")

    def _open_browser() -> None:
        # Wait until the local server actually responds before opening a tab.
        healthcheck_url = f"{app_url}/health"
        deadline = time.time() + 90
        last_notice_at = 0.0

        while time.time() < deadline:
            try:
                with urllib.request.urlopen(healthcheck_url, timeout=2):
                    webbrowser.open(app_url)
                    return
            except Exception:
                now = time.time()
                if now - last_notice_at >= 10:
                    print("Waiting for the dashboard backend to finish starting...")
                    last_notice_at = now
                time.sleep(1)

        print(f"Server startup is taking longer than expected. Open {app_url} manually once it is ready.")

    threading.Thread(target=_open_browser, daemon=True).start()

    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "main:app",
        "--host",
        host,
        "--port",
        str(port),
    ]
    server_process = subprocess.Popen(command, cwd=str(ROOT_DIR))

    try:
        return server_process.wait()
    except KeyboardInterrupt:
        if server_process.poll() is None:
            server_process.terminate()
            try:
                server_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server_process.kill()
                server_process.wait()
        raise


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nServer stopped.")
        raise SystemExit(0)
