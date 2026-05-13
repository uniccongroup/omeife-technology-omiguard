import time
import json
import requests
from datetime import datetime

import firebase_admin
from firebase_admin import db

from firebase_prepare_latest import get_latest_prepared_payload, init_firebase
from LLM_recommend import generate_recommendation, recommendation_item
from email_alerts import send_risk_alert_if_needed


# =============================
# CONFIG
# =============================
API_URL = "http://127.0.0.1:8000/predict"

INTERVAL_SECONDS = 90

DEVICE_ID = "node_01"

PREDICTION_LATEST_PATH = f"predictions/{DEVICE_ID}/latest"
PREDICTION_HISTORY_PATH = f"predictions/{DEVICE_ID}/history"
ALERT_LATEST_PATH = f"alerts/{DEVICE_ID}/latest"
ALERT_HISTORY_PATH = f"alerts/{DEVICE_ID}/history"


# =============================
# TIME HELPER
# =============================
def now_iso():
    return datetime.now().isoformat(timespec="seconds")


# =============================
# API CALL
# =============================
def send_to_prediction_api(payload):
    response = requests.post(API_URL, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def add_llm_recommendation(payload, prediction):
    risk_class = prediction.get("risk_class")
    if risk_class in {"Safe", "Moderate"}:
        return prediction

    try:
        llm_result = generate_recommendation(prediction, payload)
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
        print("LLM recommendation error:", str(exc))
        return prediction


# =============================
# CLEAN SENSOR DATA FOR DASHBOARD
# =============================
def extract_sensor_data(payload):
    return {
        "co": payload.get("co"),
        "so2": payload.get("so2"),
        "no2": payload.get("no2"),
        "pm1_0": payload.get("pm1_0"),
        "pm2_5": payload.get("pm2_5"),
        "pm10": payload.get("pm10"),
        "temperature": payload.get("temperature"),
        "humidity": payload.get("humidity"),
        "aqi": payload.get("aqi"),
        "aqi_pm2_5": payload.get("aqi_pm2_5"),
        "aqi_pm10": payload.get("aqi_pm10"),
        "aqi_category": payload.get("aqi_category"),
        "child_exposure_score": payload.get("child_exposure_score"),
        "rule_based_risk_class": payload.get("rule_based_risk_class")
    }


# =============================
# PREPARED FEATURES FOR RECORD
# =============================
def extract_prepared_features(payload):
    return {
        "hour": payload.get("hour"),
        "day_of_week": payload.get("day_of_week"),
        "total_gas_load": payload.get("total_gas_load"),
        "total_pm_load": payload.get("total_pm_load"),
        "co_so2_interaction": payload.get("co_so2_interaction"),
        "gas_pm_interaction": payload.get("gas_pm_interaction"),
        "temp_humidity_index": payload.get("temp_humidity_index"),
        "heat_stress_flag": payload.get("heat_stress_flag"),
        "high_humidity_flag": payload.get("high_humidity_flag"),
        "pm2_5_pm10_ratio": payload.get("pm2_5_pm10_ratio"),
        "pm1_pm2_5_ratio": payload.get("pm1_pm2_5_ratio"),
        "aqi": payload.get("aqi"),
        "aqi_pm2_5": payload.get("aqi_pm2_5"),
        "aqi_pm10": payload.get("aqi_pm10"),
        "child_exposure_score": payload.get("child_exposure_score")
    }


# =============================
# SAVE TO FIREBASE
# =============================
def save_prediction_to_firebase(payload, prediction):
    prediction_time = now_iso()

    result = {
        "device_id": payload.get("device_id", DEVICE_ID),

        # actual time prediction was made
        "prediction_time": prediction_time,

        # time from ESP32 sensor reading
        "sensor_timestamp": payload.get("timestamp"),

        "risk_class": prediction.get("risk_class"),
        "risk_score": prediction.get("risk_score"),
        "anomaly_flag": prediction.get("anomaly_flag"),
        "action_recommendation": prediction.get("action_recommendation"),
        "base_action_recommendation": prediction.get("base_action_recommendation"),
        "llm_action_recommendation": prediction.get("llm_action_recommendation"),
        "llm_recommendation": prediction.get("llm_recommendation"),

        "sensor_data": extract_sensor_data(payload),
        "prepared_features": extract_prepared_features(payload)
    }

    # Replace current/latest prediction
    db.reference(PREDICTION_LATEST_PATH).set(result)

    # Keep permanent history
    history_ref = db.reference(PREDICTION_HISTORY_PATH).push(result)
    result["prediction_history_key"] = history_ref.key
    db.reference(PREDICTION_LATEST_PATH).update({"prediction_history_key": history_ref.key})

    return result


def save_alert_to_firebase(prediction_result, alert_info):
    alert_record = {
        "device_id": prediction_result.get("device_id", DEVICE_ID),
        "risk_class": prediction_result.get("risk_class"),
        "risk_score": prediction_result.get("risk_score"),
        "anomaly_flag": prediction_result.get("anomaly_flag"),
        "prediction_time": prediction_result.get("prediction_time"),
        "prediction_history_key": prediction_result.get("prediction_history_key"),
        "sensor_timestamp": prediction_result.get("sensor_timestamp"),
        "sent_at": alert_info.get("sent_at"),
        "subject": alert_info.get("subject"),
        "from_name": alert_info.get("from_name"),
        "from_email": alert_info.get("from_email"),
        "to_emails": alert_info.get("to_emails", []),
        "llm_action_recommendation": prediction_result.get("llm_action_recommendation"),
        "llm_recommendation": prediction_result.get("llm_recommendation"),
        "action_recommendation": prediction_result.get("action_recommendation"),
        "sensor_data": prediction_result.get("sensor_data", {}),
    }

    db.reference(ALERT_LATEST_PATH).set(alert_record)
    db.reference(ALERT_HISTORY_PATH).push(alert_record)
    return alert_record


# =============================
# ONE PREDICTION CYCLE
# =============================
def run_once():
    payload = get_latest_prepared_payload(save_json=True)

    prediction = send_to_prediction_api(payload)
    prediction = add_llm_recommendation(payload, prediction)

    saved_result = save_prediction_to_firebase(payload, prediction)
    alert_info = send_risk_alert_if_needed(saved_result)
    if alert_info:
        save_alert_to_firebase(saved_result, alert_info)

    return saved_result


# =============================
# AUTO LOOP
# =============================
def run_forever():
    init_firebase()

    print("OmiGuard Auto Prediction Pipeline Started")
    print(f"API URL: {API_URL}")
    print(f"Device ID: {DEVICE_ID}")
    print(f"Interval: {INTERVAL_SECONDS} seconds")
    print(f"Latest path: {PREDICTION_LATEST_PATH}")
    print(f"History path: {PREDICTION_HISTORY_PATH}")
    print(f"Alert history path: {ALERT_HISTORY_PATH}")
    print("-" * 60)

    while True:
        try:
            result = run_once()

            print("Prediction saved successfully")
            print(json.dumps({
                "prediction_time": result.get("prediction_time"),
                "sensor_timestamp": result.get("sensor_timestamp"),
                "risk_class": result.get("risk_class"),
                "risk_score": result.get("risk_score"),
                "anomaly_flag": result.get("anomaly_flag")
            }, indent=4))

        except Exception as e:
            print("Pipeline error:", str(e))

        print("-" * 60)
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    run_forever()
