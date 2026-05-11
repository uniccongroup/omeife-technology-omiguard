import argparse
import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv
from huggingface_hub import InferenceClient


load_dotenv(dotenv_path=Path(__file__).parent / ".env")

DEFAULT_API_URL = "http://127.0.0.1:8000/predict"
DEFAULT_MODEL = "microsoft/Phi-3-mini-4k-instruct:featherless-ai"

LABEL_GUIDANCE = {
    "Safe": {
        "risk_level": "Low",
        "action": "Continue normal monitoring.",
        "precautions": "Keep ventilation available, maintain the sensor, and review readings on the normal schedule.",
    },
    "Moderate": {
        "risk_level": "Moderate",
        "action": "Improve ventilation and continue monitoring.",
        "precautions": "Limit unnecessary exposure, watch for rising readings, and check the area again soon.",
    },
    "Caution": {
        "risk_level": "Elevated",
        "action": "Reduce exposure, improve ventilation, and monitor closely.",
        "precautions": "Keep children or vulnerable people away, inspect likely sources, and prepare to escalate if readings rise.",
    },
    "Dangerous": {
        "risk_level": "High",
        "action": "Move people away immediately, ventilate if it is safe to do so, and alert responsible personnel.",
        "precautions": "Avoid ignition sources, use appropriate PPE, and allow trained personnel to inspect before re-entry.",
    },
}


def read_json_file(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def get_latest_payload():
    from firebase_prepare_latest import get_latest_prepared_payload

    return get_latest_prepared_payload(save_json=True)


def get_prediction(payload, api_url):
    response = requests.post(api_url, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def summarize_sensor_data(payload):
    fields = [
        "co",
        "so2",
        "no2",
        "pm1_0",
        "pm2_5",
        "pm10",
        "temperature",
        "humidity",
        "aqi",
        "aqi_category",
        "who_dominant_pollutant",
        "child_exposure_score",
    ]
    return {field: payload.get(field) for field in fields if payload.get(field) is not None}


def build_prompt(prediction, payload):
    risk_class = prediction.get("risk_class", "Unknown")
    guidance = LABEL_GUIDANCE.get(risk_class, LABEL_GUIDANCE["Caution"])
    sensor_data = summarize_sensor_data(payload)

    return f"""
Prediction result from the gas AI model:
- Predicted label: {risk_class}
- Confidence score: {prediction.get("risk_score")}
- Anomaly flag: {prediction.get("anomaly_flag")}
- Model action recommendation: {prediction.get("action_recommendation")}

Label-specific recommendation that must be followed:
- Risk level: {guidance['risk_level']}
- Immediate action: {guidance['action']}
- Safety precautions: {guidance['precautions']}

Sensor data:
{json.dumps(sensor_data, indent=2)}

Write the recommendation using ONLY the predicted label above.
Do not change the risk level.
Do not introduce a different gas type, leak type, or prediction label.
If the label is Safe, do not recommend evacuation.

Provide:
1. Risk level
2. Immediate action
3. Safety precautions
"""


def generate_recommendation(prediction, payload, model=DEFAULT_MODEL):
    token = os.getenv("HF_TOKEN")
    if not token:
        raise ValueError("HF_TOKEN not found. Add it to gas_ai_system/src/.env")

    risk_class = prediction.get("risk_class", "Unknown")
    client = InferenceClient(api_key=token)

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an industrial harmful gas monitoring assistant. "
                    "Provide concise, practical safety recommendations. "
                    "Base the recommendation on the supplied predicted label only."
                ),
            },
            {
                "role": "user",
                "content": build_prompt(prediction, payload),
            },
        ],
        max_tokens=220,
        temperature=0.2,
    )

    return {
        "risk_class": risk_class,
        "risk_score": prediction.get("risk_score"),
        "anomaly_flag": prediction.get("anomaly_flag"),
        "recommendation": completion.choices[0].message.content.strip(),
    }


def recommendation_item(text, item_name, fallback=None):
    prefix = item_name.lower()

    for line in str(text or "").splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue

        normalized = cleaned.lstrip("0123456789.:-* ").strip()
        if normalized.lower().startswith(prefix):
            return normalized.split(":", 1)[-1].strip()

    return fallback or str(text or "").strip()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate an LLM safety recommendation from the real model prediction."
    )
    parser.add_argument(
        "--payload-json",
        help="Path to a prepared sensor payload JSON file. If omitted, the latest Firebase payload is used.",
    )
    parser.add_argument(
        "--prediction-json",
        help="Path to an existing prediction JSON file. If omitted, /predict is called with the payload.",
    )
    parser.add_argument(
        "--api-url",
        default=DEFAULT_API_URL,
        help=f"Prediction API URL. Default: {DEFAULT_API_URL}",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Hugging Face chat model. Default: {DEFAULT_MODEL}",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.payload_json:
        payload = read_json_file(args.payload_json)
    elif args.prediction_json:
        payload = {}
    else:
        payload = get_latest_payload()

    prediction = (
        read_json_file(args.prediction_json)
        if args.prediction_json
        else get_prediction(payload, args.api_url)
    )

    result = generate_recommendation(prediction, payload, args.model)

    print("Prediction used:")
    print(json.dumps({key: result[key] for key in ("risk_class", "risk_score", "anomaly_flag")}, indent=2))
    print("\nRecommendation:")
    print(result["recommendation"])


if __name__ == "__main__":
    main()
