import os
import json
import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FIREBASE_KEY_PATH = os.path.join(BASE_DIR, "firebase_key.json")

JSON_DIR = os.path.join(BASE_DIR, "data", "processed_json")
JSON_HISTORY_DIR = os.path.join(JSON_DIR, "history")
LATEST_JSON_PATH = os.path.join(JSON_DIR, "latest_payload.json")

DATABASE_URL = "https://streamlit-auth-9148c-default-rtdb.firebaseio.com/"
LATEST_PATH = "sensor_data/node_01/latest"
READINGS_PATH = "sensor_data/node_01/readings"

TIMESTAMP_FIELDS = (
    "timestamp",
    "sensor_timestamp",
    "created_at",
    "createdAt",
    "recorded_at",
    "recordedAt",
    "reading_time",
    "readingTime",
    "datetime",
    "date_time",
    "dateTime",
    "time",
)

SENSOR_FIELDS = {
    "co",
    "so2",
    "no2",
    "pm1_0",
    "pm2_5",
    "pm10",
    "temperature",
    "humidity",
}


MOLAR_VOLUME_L_PER_MOL = 24.45

# WHO 2021 short-term Air Quality Guideline levels.
# This script uses them as a screening index for each reading:
# 100 means the reading is at the WHO guideline level.
WHO_2021_24H_AQG = {
    "pm2_5": 15.0,  # ug/m3
    "pm10": 45.0,   # ug/m3
    "no2": 25.0,    # ug/m3
    "so2": 40.0,    # ug/m3
    "co": 4.0,      # mg/m3
}

MOLECULAR_WEIGHTS = {
    "co": 28.01,
    "no2": 46.0055,
    "so2": 64.066,
}


def init_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate(FIREBASE_KEY_PATH)
        firebase_admin.initialize_app(cred, {
            "databaseURL": DATABASE_URL
        })


def safe_float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (ValueError, TypeError):
        return default


def ppm_to_mg_m3(ppm, pollutant):
    return safe_float(ppm) * MOLECULAR_WEIGHTS[pollutant] / MOLAR_VOLUME_L_PER_MOL


def ppm_to_ug_m3(ppm, pollutant):
    return ppm_to_mg_m3(ppm, pollutant) * 1000


def compute_who_index(concentration, guideline):
    concentration = safe_float(concentration)
    if guideline <= 0:
        return 0.0
    return round((concentration / guideline) * 100, 2)


def aqi_category(index_value):
    if index_value <= 100:
        return "Safe"
    elif index_value <= 200:
        return "Moderate"
    elif index_value <= 400:
        return "Caution"
    else:
        return "Dangerous"


def risk_label_from_level(level):
    if level == 3:
        return "Dangerous"
    if level == 2:
        return "Caution"
    if level == 1:
        return "Moderate"
    return "Safe"


def risk_rank(label):
    ranks = {
        "Safe": 0,
        "Moderate": 1,
        "Caution": 2,
        "Dangerous": 3
    }
    return ranks.get(label, 0)


def higher_risk(label_a, label_b):
    return label_a if risk_rank(label_a) >= risk_rank(label_b) else label_b


def parse_datetime(timestamp):
    if timestamp is None or timestamp == "":
        return None

    try:
        if isinstance(timestamp, (int, float)):
            value = float(timestamp)
            if value > 10000000000:
                value = value / 1000
            return datetime.fromtimestamp(value)

        text = str(timestamp).strip()
        if text.isdigit():
            value = float(text)
            if value > 10000000000:
                value = value / 1000
            return datetime.fromtimestamp(value)

        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return dt
    except Exception:
        return None


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def parse_timestamp(timestamp):
    dt = parse_datetime(timestamp)
    if dt:
        return dt.hour, dt.weekday()

    now = datetime.now()
    return now.hour, now.weekday()


def has_sensor_values(record):
    return bool(SENSOR_FIELDS.intersection(record.keys()))


def record_datetime(record):
    if not isinstance(record, dict):
        return None

    for field in TIMESTAMP_FIELDS:
        dt = parse_datetime(record.get(field))
        if dt:
            return dt

    return parse_datetime(record.get("_firebase_key"))


def normalize_record(record, firebase_key=None):
    normalized = dict(record)
    if firebase_key is not None:
        normalized["_firebase_key"] = str(firebase_key)

    for field in TIMESTAMP_FIELDS:
        if normalized.get(field):
            normalized["timestamp"] = normalized[field]
            break

    return normalized


def flatten_sensor_records(node, firebase_key=None):
    if not isinstance(node, dict):
        return []

    records = []
    if has_sensor_values(node):
        records.append(normalize_record(node, firebase_key))

    for key, value in node.items():
        if isinstance(value, dict):
            records.extend(flatten_sensor_records(value, key))

    return records


def latest_record_from_readings(readings):
    if not isinstance(readings, dict):
        return None

    records = []
    for firebase_key, record in readings.items():
        records.extend(flatten_sensor_records(record, firebase_key))

    if not records:
        return None

    return max(
        records,
        key=lambda record: (
            record_datetime(record) or datetime.min,
            str(record.get("_firebase_key", ""))
        )
    )


def is_newer_record(candidate, current):
    if not isinstance(candidate, dict):
        return False
    if not isinstance(current, dict):
        return True

    candidate_time = record_datetime(candidate)
    current_time = record_datetime(current)

    if candidate_time and current_time:
        if candidate_time == current_time:
            return bool(candidate.get("_firebase_key"))
        return candidate_time > current_time
    return candidate_time is not None and current_time is None


def safe_filename(text):
    return (
        str(text)
        .replace(":", "-")
        .replace("/", "-")
        .replace("\\", "-")
        .replace(" ", "_")
    )


def dominant_pollutant(payload):
    pollutant_indexes = {
        "pm2_5": payload["aqi_pm2_5"],
        "pm10": payload["aqi_pm10"],
        "co": payload["aqi_co"],
        "no2": payload["aqi_no2"],
        "so2": payload["aqi_so2"],
    }
    return max(pollutant_indexes, key=pollutant_indexes.get)


def build_prediction_payload(latest):
    co = safe_float(latest.get("co", 0))
    so2 = safe_float(latest.get("so2", 0))
    no2 = safe_float(latest.get("no2", 0))
    pm1_0 = safe_float(latest.get("pm1_0", 0))
    pm2_5 = safe_float(latest.get("pm2_5", 0))
    pm10 = safe_float(latest.get("pm10", 0))
    temperature = safe_float(latest.get("temperature", 0))
    humidity = safe_float(latest.get("humidity", 0))

    device_id = latest.get("device_id", "node_01")
    device_timestamp = latest.get("timestamp")
    timestamp = now_iso()

    hour, day_of_week = parse_timestamp(timestamp)

    total_gas_load = co + so2 + no2
    total_pm_load = pm1_0 + pm2_5 + pm10

    co_mg_m3 = ppm_to_mg_m3(co, "co")
    no2_ug_m3 = ppm_to_ug_m3(no2, "no2")
    so2_ug_m3 = ppm_to_ug_m3(so2, "so2")

    aqi_pm2_5 = compute_who_index(pm2_5, WHO_2021_24H_AQG["pm2_5"])
    aqi_pm10 = compute_who_index(pm10, WHO_2021_24H_AQG["pm10"])
    aqi_co = compute_who_index(co_mg_m3, WHO_2021_24H_AQG["co"])
    aqi_no2 = compute_who_index(no2_ug_m3, WHO_2021_24H_AQG["no2"])
    aqi_so2 = compute_who_index(so2_ug_m3, WHO_2021_24H_AQG["so2"])

    aqi = max(aqi_pm2_5, aqi_pm10, aqi_co, aqi_no2, aqi_so2)
    aqi_cat = aqi_category(aqi)
    rule_risk_level = risk_rank(aqi_cat)
    final_rule_risk_class = aqi_cat

    payload = {
        "device_id": device_id,
        "timestamp": timestamp,
        "device_timestamp": device_timestamp,
        "processed_at": now_iso(),

        "co": co,
        "so2": so2,
        "no2": no2,
        "pm1_0": pm1_0,
        "pm2_5": pm2_5,
        "pm10": pm10,
        "temperature": temperature,
        "humidity": humidity,

        "hour": hour,
        "day_of_week": day_of_week,

        "total_gas_load": total_gas_load,
        "total_pm_load": total_pm_load,
        "co_so2_interaction": co * so2,
        "gas_pm_interaction": total_gas_load * total_pm_load,
        "temp_humidity_index": temperature * humidity,

        "heat_stress_flag": int(temperature >= 35),
        "high_humidity_flag": int(humidity >= 70),

        "pm2_5_pm10_ratio": pm2_5 / (pm10 + 1),
        "pm1_pm2_5_ratio": pm1_0 / (pm2_5 + 1),

        "child_exposure_score": (
            (co * 0.25) +
            (so2 * 0.20) +
            (no2 * 0.20) +
            (pm2_5 * 0.25) +
            (pm10 * 0.10) +
            (temperature * 0.05)
        ),

        "co_mg_m3": co_mg_m3,
        "no2_ug_m3": no2_ug_m3,
        "so2_ug_m3": so2_ug_m3,

        "aqi_pm2_5": aqi_pm2_5,
        "aqi_pm10": aqi_pm10,
        "aqi_co": aqi_co,
        "aqi_no2": aqi_no2,
        "aqi_so2": aqi_so2,
        "aqi": aqi,
        "aqi_category": aqi_cat,
        "who_aqg_exceedance_count": (
            int(aqi_pm2_5 > 100) +
            int(aqi_pm10 > 100) +
            int(aqi_co > 100) +
            int(aqi_no2 > 100) +
            int(aqi_so2 > 100)
        ),

        "rule_based_risk_level": rule_risk_level,
        "rule_based_risk_class": final_rule_risk_class
    }

    payload["who_dominant_pollutant"] = dominant_pollutant(payload)

    return payload


def save_payload_json(payload):
    os.makedirs(JSON_HISTORY_DIR, exist_ok=True)

    with open(LATEST_JSON_PATH, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=4)

    device_id = payload.get("device_id", "node_01")
    timestamp = safe_filename(payload.get("timestamp", datetime.now().isoformat()))

    history_file = os.path.join(
        JSON_HISTORY_DIR,
        f"{device_id}_{timestamp}.json"
    )

    if not os.path.exists(history_file):
        with open(history_file, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=4)

    return {
        "latest_json": LATEST_JSON_PATH,
        "history_json": history_file
    }


def get_latest_prepared_payload(save_json=True):
    init_firebase()

    latest = db.reference(LATEST_PATH).get()
    readings = db.reference(READINGS_PATH).get()
    latest_from_readings = latest_record_from_readings(readings)

    if is_newer_record(latest_from_readings, latest):
        latest = latest_from_readings

    if not latest:
        raise ValueError("No latest sensor data found in Firebase.")

    payload = build_prediction_payload(latest)

    if save_json:
        save_payload_json(payload)

    return payload


if __name__ == "__main__":
    payload = get_latest_prepared_payload(save_json=True)

    print("Prepared payload:")
    print(json.dumps(payload, indent=4))

    print("\nSaved latest JSON:")
    print(LATEST_JSON_PATH)

    print("\nSaved history folder:")
    print(JSON_HISTORY_DIR)
