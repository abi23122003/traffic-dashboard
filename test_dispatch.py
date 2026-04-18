"""Send a test dispatch to verify officer_update broadcast."""

import requests

URL = "http://localhost:5000/api/dispatch"
PAYLOAD = {
    "officer_id": 1,
    "incident_id": 1,
}


def main() -> None:
    try:
        response = requests.post(URL, json=PAYLOAD, timeout=10)
        print(f"Status code: {response.status_code}")

        try:
            body = response.json()
        except ValueError:
            print("Response was not JSON:")
            print(response.text)
            return

        officer_data = body.get("officer") if isinstance(body, dict) else None
        if officer_data is None and isinstance(body, dict):
            officer_data = body.get("data")

        print("Returned officer data:")
        print(officer_data)
    except requests.RequestException as exc:
        print(f"Request failed: {exc}")


if __name__ == "__main__":
    main()

