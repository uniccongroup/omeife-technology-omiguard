import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests


PROJECT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from firebase_prepare_latest import get_latest_prepared_payload  # noqa: E402
from LLM_recommend import generate_recommendation, recommendation_item  # noqa: E402


DEFAULT_INTERVAL_SECONDS = 90
DEFAULT_API_URL = "http://127.0.0.1:8000/predict"
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "data" / "predictions"

PREDICTION_HISTORY_FIELDS = [
    "prediction_timestamp",
    "device_id",
    "sensor_timestamp",
    "risk_class",
    "risk_score",
    "anomaly_flag",
    "action_recommendation",
    "base_action_recommendation",
    "llm_action_recommendation",
    "llm_recommendation",
    "aqi",
    "aqi_category",
    "who_dominant_pollutant",
    "who_aqg_exceedance_count",
    "co",
    "so2",
    "no2",
    "pm2_5",
    "pm10",
    "temperature",
    "humidity",
]


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def env_float(name, default):
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def timestamp_now():
    return datetime.now().isoformat(timespec="seconds")


def safe_filename(value):
    return (
        str(value)
        .replace(":", "-")
        .replace("/", "-")
        .replace("\\", "-")
        .replace(" ", "_")
    )


def build_api_payload(prepared_payload):
    api_payload = prepared_payload.copy()

    # These are useful metadata fields, but they are not model inputs.
    api_payload.pop("device_id", None)
    api_payload.pop("timestamp", None)
    api_payload.pop("rule_based_risk_level", None)
    api_payload.pop("rule_based_risk_class", None)

    return api_payload


def post_prediction(api_url, prepared_payload, timeout_seconds):
    response = requests.post(
        api_url,
        json=build_api_payload(prepared_payload),
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    return response.json()


def add_llm_recommendation(prepared_payload, prediction):
    risk_class = prediction.get("risk_class")
    if risk_class in {"Safe", "Moderate"}:
        return prediction

    try:
        llm_result = generate_recommendation(prediction, prepared_payload)
        llm_text = llm_result.get("recommendation", "").strip()
        if not llm_text:
            return prediction

        enriched_prediction = prediction.copy()
        enriched_prediction["base_action_recommendation"] = prediction.get("action_recommendation")
        enriched_prediction["llm_recommendation"] = llm_text
        enriched_prediction["llm_action_recommendation"] = recommendation_item(
            llm_text,
            "Immediate action",
            fallback=prediction.get("action_recommendation"),
        )
        enriched_prediction["action_recommendation"] = enriched_prediction["llm_action_recommendation"]
        return enriched_prediction
    except Exception as exc:
        print(f"[{timestamp_now()}] LLM recommendation failed: {exc}", flush=True)
        return prediction


def build_prediction_record(prepared_payload, prediction, api_url):
    return {
        "prediction_timestamp": timestamp_now(),
        "api_url": api_url,
        "device_id": prepared_payload.get("device_id"),
        "sensor_timestamp": prepared_payload.get("timestamp"),
        "risk_class": prediction.get("risk_class"),
        "risk_score": prediction.get("risk_score"),
        "anomaly_flag": prediction.get("anomaly_flag"),
        "action_recommendation": prediction.get("action_recommendation"),
        "base_action_recommendation": prediction.get("base_action_recommendation"),
        "llm_action_recommendation": prediction.get("llm_action_recommendation"),
        "llm_recommendation": prediction.get("llm_recommendation"),
        "aqi": prepared_payload.get("aqi"),
        "aqi_category": prepared_payload.get("aqi_category"),
        "who_dominant_pollutant": prepared_payload.get("who_dominant_pollutant"),
        "who_aqg_exceedance_count": prepared_payload.get("who_aqg_exceedance_count"),
        "co": prepared_payload.get("co"),
        "so2": prepared_payload.get("so2"),
        "no2": prepared_payload.get("no2"),
        "pm2_5": prepared_payload.get("pm2_5"),
        "pm10": prepared_payload.get("pm10"),
        "temperature": prepared_payload.get("temperature"),
        "humidity": prepared_payload.get("humidity"),
        "prepared_payload": prepared_payload,
        "prediction": prediction,
    }


def save_prediction_files(record, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)

    latest_path = output_dir / "latest_prediction.json"
    history_dir = output_dir / "history"
    history_dir.mkdir(parents=True, exist_ok=True)

    history_name = (
        f"{safe_filename(record.get('device_id', 'node_01'))}_"
        f"{safe_filename(record.get('sensor_timestamp', record['prediction_timestamp']))}.json"
    )
    history_json_path = history_dir / history_name
    history_csv_path = output_dir / "prediction_history.csv"

    with latest_path.open("w", encoding="utf-8") as file:
        json.dump(record, file, indent=4)

    with history_json_path.open("w", encoding="utf-8") as file:
        json.dump(record, file, indent=4)

    csv_row = {field: record.get(field) for field in PREDICTION_HISTORY_FIELDS}
    write_header = not history_csv_path.exists() or history_csv_path.stat().st_size == 0

    with history_csv_path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=PREDICTION_HISTORY_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(csv_row)

    return {
        "latest_json": str(latest_path),
        "history_json": str(history_json_path),
        "history_csv": str(history_csv_path),
    }


def save_prediction_to_firebase(record):
    from firebase_admin import db

    latest_path = os.getenv(
        "PREDICTION_FIREBASE_LATEST_PATH",
        "sensor_data/node_01/predictions/latest",
    )
    history_path = os.getenv(
        "PREDICTION_FIREBASE_HISTORY_PATH",
        "sensor_data/node_01/predictions/history",
    )

    db.reference(latest_path).set(record)
    db.reference(history_path).push(record)


def run_once(api_url, output_dir, timeout_seconds, save_to_firebase=False):
    prepared_payload = get_latest_prepared_payload(save_json=True)
    prediction = post_prediction(api_url, prepared_payload, timeout_seconds)
    prediction = add_llm_recommendation(prepared_payload, prediction)
    record = build_prediction_record(prepared_payload, prediction, api_url)
    saved_paths = save_prediction_files(record, output_dir)

    if save_to_firebase:
        save_prediction_to_firebase(record)

    print(
        "[{time}] {device} {sensor_time} -> {risk} "
        "(score={score}, anomaly={anomaly})".format(
            time=record["prediction_timestamp"],
            device=record.get("device_id"),
            sensor_time=record.get("sensor_timestamp"),
            risk=record.get("risk_class"),
            score=record.get("risk_score"),
            anomaly=record.get("anomaly_flag"),
        ),
        flush=True,
    )
    print(f"Saved latest prediction: {saved_paths['latest_json']}", flush=True)

    return record


def run_forever(api_url, output_dir, interval_seconds, timeout_seconds, save_to_firebase):
    print("OmiGuard auto prediction worker started.", flush=True)
    print(f"API URL: {api_url}", flush=True)
    print(f"Interval: {interval_seconds} seconds", flush=True)
    print(f"Output directory: {output_dir}", flush=True)
    print(f"Save predictions to Firebase: {save_to_firebase}", flush=True)

    while True:
        started = time.monotonic()

        try:
            run_once(
                api_url=api_url,
                output_dir=output_dir,
                timeout_seconds=timeout_seconds,
                save_to_firebase=save_to_firebase,
            )
        except Exception as exc:
            print(f"[{timestamp_now()}] Prediction cycle failed: {exc}", flush=True)

        elapsed = time.monotonic() - started
        sleep_for = max(0, interval_seconds - elapsed)
        print(f"Sleeping for {sleep_for:.1f} seconds.", flush=True)
        print("-" * 60, flush=True)
        time.sleep(sleep_for)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Pull latest Firebase reading and run prediction repeatedly."
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single prediction cycle and exit.",
    )
    parser.add_argument(
        "--api-url",
        default=os.getenv("PREDICT_API_URL", DEFAULT_API_URL),
        help="FastAPI /predict endpoint.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=env_float("PREDICT_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS),
        help="Seconds between prediction cycles. Default is 90 seconds.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=env_float("PREDICT_TIMEOUT_SECONDS", 20),
        help="HTTP timeout for the prediction API request.",
    )
    parser.add_argument(
        "--output-dir",
        default=os.getenv("PREDICT_OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR)),
        help="Directory where latest/history prediction files are saved.",
    )
    parser.add_argument(
        "--save-to-firebase",
        action="store_true",
        default=env_bool("SAVE_PREDICTIONS_TO_FIREBASE", False),
        help="Also write prediction results back to Firebase.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)

    if args.once:
        run_once(
            api_url=args.api_url,
            output_dir=output_dir,
            timeout_seconds=args.timeout,
            save_to_firebase=args.save_to_firebase,
        )
        return

    run_forever(
        api_url=args.api_url,
        output_dir=output_dir,
        interval_seconds=args.interval,
        timeout_seconds=args.timeout,
        save_to_firebase=args.save_to_firebase,
    )


if __name__ == "__main__":
    main()
