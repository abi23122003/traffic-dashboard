"""Send a test incident to verify incident_update broadcast."""

import requests

URL = "http://localhost:5000/api/incidents"
PAYLOAD = {
    "title": "Critical incident test - Live feed",
    "severity": "critical",
    "lat": 11.0168,
    "lng": 76.9558,
}


def main() -> None:
    try:
        response = requests.post(URL, json=PAYLOAD, timeout=10)
        print(f"Status code: {response.status_code}")
        try:
            print("Response JSON:")
            print(response.json())
        except ValueError:
            print("Response was not JSON:")
            print(response.text)
    except requests.RequestException as exc:
        print(f"Request failed: {exc}")


if __name__ == "__main__":
    main()


