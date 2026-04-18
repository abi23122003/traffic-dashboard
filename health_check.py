"""Phase 1 health check: HTTP + REST + WebSocket validations."""

import asyncio
from typing import Tuple

import requests
import websockets

BASE_URL = "http://localhost:5000"
WS_URL = "ws://localhost:5000/ws/incidents"


def check_server_ping() -> Tuple[bool, str]:
    try:
        response = requests.get(BASE_URL, timeout=8)
        # Server is considered reachable if we get any HTTP response.
        return True, f"reachable (status {response.status_code})"
    except requests.RequestException as exc:
        return False, f"unreachable ({exc})"


def check_incidents_endpoint() -> Tuple[bool, str]:
    try:
        response = requests.get(f"{BASE_URL}/api/incidents", timeout=8)
        ok = response.status_code == 200
        return ok, f"status {response.status_code}"
    except requests.RequestException as exc:
        return False, f"request failed ({exc})"


def check_officers_endpoint() -> Tuple[bool, str]:
    try:
        response = requests.get(f"{BASE_URL}/api/officers/status", timeout=8)
        ok = response.status_code == 200
        return ok, f"status {response.status_code}"
    except requests.RequestException as exc:
        return False, f"request failed ({exc})"


async def check_websocket_connection() -> Tuple[bool, str]:
    try:
        async with websockets.connect(WS_URL, open_timeout=8, close_timeout=3):
            return True, "connected"
    except Exception as exc:
        return False, f"connect failed ({exc})"


def print_result(name: str, ok: bool, detail: str) -> None:
    state = "PASS" if ok else "FAIL"
    print(f"[{state}] {name}: {detail}")


def main() -> None:
    passed = 0

    ok, detail = check_server_ping()
    print_result("1) Server ping http://localhost:5000", ok, detail)
    passed += int(ok)

    ok, detail = check_incidents_endpoint()
    print_result("2) GET /api/incidents == 200", ok, detail)
    passed += int(ok)

    ok, detail = check_officers_endpoint()
    print_result("3) GET /api/officers/status == 200", ok, detail)
    passed += int(ok)

    ok, detail = asyncio.run(check_websocket_connection())
    print_result("4) WebSocket ws://localhost:5000/ws/incidents", ok, detail)
    passed += int(ok)

    print(f"Summary: {passed}/4 checks passed")


if __name__ == "__main__":
    main()


