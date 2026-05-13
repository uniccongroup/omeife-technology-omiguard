import argparse
import json

from firebase_admin import db

from auto_predict_pipeline import (
    ALERT_HISTORY_PATH,
    DEVICE_ID,
    PREDICTION_HISTORY_PATH,
    save_alert_to_firebase,
)
from email_alerts import ALERT_RISK_CLASSES, send_risk_alert_if_needed
from firebase_prepare_latest import init_firebase


def load_records(path):
    data = db.reference(path).get() or {}
    if not isinstance(data, dict):
        return {}
    return data


def alert_keys(alerts):
    keys = set()
    for alert in alerts.values():
        if not isinstance(alert, dict):
            continue
        prediction_key = alert.get("prediction_history_key")
        prediction_time = alert.get("prediction_time")
        if prediction_key:
            keys.add(f"key:{prediction_key}")
        if prediction_time:
            keys.add(f"time:{prediction_time}")
    return keys


def missing_alert_predictions(limit):
    predictions = load_records(PREDICTION_HISTORY_PATH)
    alerts = load_records(ALERT_HISTORY_PATH)
    sent_keys = alert_keys(alerts)

    risky = []
    for key, prediction in predictions.items():
        if not isinstance(prediction, dict):
            continue
        if prediction.get("risk_class") not in ALERT_RISK_CLASSES:
            continue
        prediction_time = prediction.get("prediction_time")
        if f"key:{key}" in sent_keys or f"time:{prediction_time}" in sent_keys:
            continue
        record = prediction.copy()
        record["prediction_history_key"] = key
        risky.append(record)

    risky.sort(key=lambda item: item.get("prediction_time") or "")
    return risky[-limit:] if limit else risky


def main():
    parser = argparse.ArgumentParser(
        description="Send and record email alerts for risky predictions that do not have alert history records."
    )
    parser.add_argument("--limit", type=int, default=25, help="Maximum missing alerts to process. Use 0 for all.")
    parser.add_argument("--send", action="store_true", help="Actually send emails. Without this, only prints a dry run.")
    args = parser.parse_args()

    init_firebase()
    missing = missing_alert_predictions(args.limit)

    if not args.send:
        print(json.dumps({
            "device_id": DEVICE_ID,
            "mode": "dry_run",
            "missing_alerts": len(missing),
            "prediction_times": [item.get("prediction_time") for item in missing],
        }, indent=2))
        return

    sent = []
    failed = []
    for prediction in missing:
        alert_info = send_risk_alert_if_needed(prediction)
        if alert_info:
            save_alert_to_firebase(prediction, alert_info)
            sent.append(prediction.get("prediction_time"))
        else:
            failed.append(prediction.get("prediction_time"))

    print(json.dumps({
        "device_id": DEVICE_ID,
        "sent": len(sent),
        "failed": len(failed),
        "sent_prediction_times": sent,
        "failed_prediction_times": failed,
    }, indent=2))


if __name__ == "__main__":
    main()
