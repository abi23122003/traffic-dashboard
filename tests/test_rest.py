"""Quick REST endpoint verification for incident/officer/live feeds."""

import requests

BASE_URL = "http://localhost:5000"


def print_first_item(label: str, response: requests.Response) -> None:
    print(f"{label} status: {response.status_code}")
    try:
        data = response.json()
    except ValueError:
        print(f"{label} response is not JSON: {response.text}")
        return

    first_item = None
    if isinstance(data, list):
        first_item = data[0] if data else None
    elif isinstance(data, dict):
        incidents = data.get("incidents")
        if isinstance(incidents, list):
            first_item = incidents[0] if incidents else None
        else:
            first_item = data

    print(f"{label} first item: {first_item}")


def main() -> None:
    try:
        incidents_resp = requests.get(f"{BASE_URL}/api/incidents", timeout=10)
        print_first_item("/api/incidents", incidents_resp)

        officers_resp = requests.get(f"{BASE_URL}/api/officers/status", timeout=10)
        print_first_item("/api/officers/status", officers_resp)

        realtime_resp = requests.get(
            f"{BASE_URL}/api/realtime/incidents",
            params={"lat": 11.0168, "lon": 76.9558},
            timeout=10,
        )
        print_first_item("/api/realtime/incidents", realtime_resp)
    except requests.RequestException as exc:
        print(f"REST check failed: {exc}")


if __name__ == "__main__":
    main()

