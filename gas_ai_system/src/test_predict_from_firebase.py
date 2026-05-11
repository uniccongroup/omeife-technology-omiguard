import json
import requests

from firebase_prepare_latest import get_latest_prepared_payload


API_URL = "http://127.0.0.1:8000/predict"


def main():
    payload = get_latest_prepared_payload(save_json=True)

    api_payload = payload.copy()

    # Remove fields not used by the ML model/API
    api_payload.pop("device_id", None)
    api_payload.pop("timestamp", None)
    api_payload.pop("rule_based_risk_level", None)
    api_payload.pop("rule_based_risk_class", None)

    print("Payload sent to API:")
    print(json.dumps(api_payload, indent=4))

    response = requests.post(API_URL, json=api_payload)

    print("\nStatus Code:", response.status_code)

    print("\nPrediction Response:")
    print(json.dumps(response.json(), indent=4))


if __name__ == "__main__":
    main()