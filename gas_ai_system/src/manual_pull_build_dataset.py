import os
import csv
import firebase_admin
import pandas as pd
from firebase_admin import credentials, db


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FIREBASE_KEY_PATH = os.path.join(BASE_DIR, "firebase_key.json")

DATABASE_URL = "https://streamlit-auth-9148c-default-rtdb.firebaseio.com/"
SENSOR_PATH = "sensor_data/node_01/readings"

DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_CSV = os.path.join(DATA_DIR, "real_sensor_data.csv")
MODEL_READY_CSV = os.path.join(DATA_DIR, "model_ready_sensor_data.csv")
ID_TRACK_FILE = os.path.join(DATA_DIR, "processed_ids.txt")


RAW_FIELDS = [
    "device_id",
    "timestamp",
    "co",
    "so2",
    "no2",
    "pm1_0",
    "pm2_5",
    "pm10",
    "temperature",
    "humidity",
]


MOLAR_VOLUME_L_PER_MOL = 24.45

# Gas readings arrive as ppm. PM readings arrive as ug/m3.
# These WHO values are used as screening indexes: 100 means at guideline level.
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
    return "Dangerous"


def dominant_pollutant(row):
    pollutant_indexes = {
        "pm2_5": row["aqi_pm2_5"],
        "pm10": row["aqi_pm10"],
        "co": row["aqi_co"],
        "no2": row["aqi_no2"],
        "so2": row["aqi_so2"],
    }
    return max(pollutant_indexes, key=pollutant_indexes.get)


def load_processed_ids():
    if not os.path.exists(ID_TRACK_FILE):
        return set()

    with open(ID_TRACK_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def save_processed_ids(ids):
    os.makedirs(DATA_DIR, exist_ok=True)

    with open(ID_TRACK_FILE, "a", encoding="utf-8") as f:
        for item in ids:
            f.write(item + "\n")


def normalize_record(record):
    return {
        "device_id": record.get("device_id", "node_01"),
        "timestamp": record.get("timestamp", ""),
        "co": safe_float(record.get("co", 0)),
        "so2": safe_float(record.get("so2", 0)),
        "no2": safe_float(record.get("no2", 0)),
        "pm1_0": safe_float(record.get("pm1_0", 0)),
        "pm2_5": safe_float(record.get("pm2_5", 0)),
        "pm10": safe_float(record.get("pm10", 0)),
        "temperature": safe_float(record.get("temperature", 0)),
        "humidity": safe_float(record.get("humidity", 0)),
    }


def pull_new_records():
    os.makedirs(DATA_DIR, exist_ok=True)

    processed_ids = load_processed_ids()
    ref = db.reference(SENSOR_PATH)
    firebase_data = ref.get()

    if not firebase_data:
        print("No Firebase data found.")
        return 0

    new_rows = []
    new_ids = []

    for firebase_id, record in firebase_data.items():
        if firebase_id not in processed_ids and isinstance(record, dict):
            new_rows.append(normalize_record(record))
            new_ids.append(firebase_id)

    if not new_rows:
        print("No new records to append.")
        return 0

    file_exists = os.path.exists(RAW_CSV) and os.path.getsize(RAW_CSV) > 0

    with open(RAW_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RAW_FIELDS)

        if not file_exists:
            writer.writeheader()

        writer.writerows(new_rows)

    save_processed_ids(new_ids)

    print(f"Appended {len(new_rows)} new records to raw CSV.")
    return len(new_rows)


def build_features():
    if not os.path.exists(RAW_CSV) or os.path.getsize(RAW_CSV) == 0:
        print("Raw CSV does not exist or is empty.")
        return None

    df = pd.read_csv(RAW_CSV)

    if df.empty:
        print("Raw CSV is empty.")
        return None

    for col in RAW_FIELDS:
        if col not in df.columns:
            df[col] = "" if col in ("device_id", "timestamp") else 0

    numeric_cols = [
        "co",
        "so2",
        "no2",
        "pm1_0",
        "pm2_5",
        "pm10",
        "temperature",
        "humidity",
    ]

    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df = df[RAW_FIELDS].drop_duplicates().reset_index(drop=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.sort_values("timestamp", na_position="last").reset_index(drop=True)

    df["hour"] = df["timestamp"].dt.hour.fillna(0).astype(int)
    df["day_of_week"] = df["timestamp"].dt.dayofweek.fillna(0).astype(int)

    df["total_gas_load"] = df["co"] + df["so2"] + df["no2"]
    df["total_pm_load"] = df["pm1_0"] + df["pm2_5"] + df["pm10"]

    df["co_so2_interaction"] = df["co"] * df["so2"]
    df["gas_pm_interaction"] = df["total_gas_load"] * df["total_pm_load"]

    df["temp_humidity_index"] = df["temperature"] * df["humidity"]
    df["heat_stress_flag"] = (df["temperature"] >= 35).astype(int)
    df["high_humidity_flag"] = (df["humidity"] >= 70).astype(int)

    df["pm2_5_pm10_ratio"] = df["pm2_5"] / (df["pm10"] + 1)
    df["pm1_pm2_5_ratio"] = df["pm1_0"] / (df["pm2_5"] + 1)

    df["child_exposure_score"] = (
        (df["co"] * 0.25) +
        (df["so2"] * 0.20) +
        (df["no2"] * 0.20) +
        (df["pm2_5"] * 0.25) +
        (df["pm10"] * 0.10) +
        (df["temperature"] * 0.05)
    )

    df["co_mg_m3"] = df["co"].apply(lambda x: ppm_to_mg_m3(x, "co"))
    df["no2_ug_m3"] = df["no2"].apply(lambda x: ppm_to_ug_m3(x, "no2"))
    df["so2_ug_m3"] = df["so2"].apply(lambda x: ppm_to_ug_m3(x, "so2"))

    df["aqi_pm2_5"] = df["pm2_5"].apply(
        lambda x: compute_who_index(x, WHO_2021_24H_AQG["pm2_5"])
    )
    df["aqi_pm10"] = df["pm10"].apply(
        lambda x: compute_who_index(x, WHO_2021_24H_AQG["pm10"])
    )
    df["aqi_co"] = df["co_mg_m3"].apply(
        lambda x: compute_who_index(x, WHO_2021_24H_AQG["co"])
    )
    df["aqi_no2"] = df["no2_ug_m3"].apply(
        lambda x: compute_who_index(x, WHO_2021_24H_AQG["no2"])
    )
    df["aqi_so2"] = df["so2_ug_m3"].apply(
        lambda x: compute_who_index(x, WHO_2021_24H_AQG["so2"])
    )
    df["aqi"] = df[
        ["aqi_pm2_5", "aqi_pm10", "aqi_co", "aqi_no2", "aqi_so2"]
    ].max(axis=1)
    df["aqi_category"] = df["aqi"].apply(aqi_category)

    df["who_aqg_exceedance_count"] = (
        (df["aqi_pm2_5"] > 100).astype(int) +
        (df["aqi_pm10"] > 100).astype(int) +
        (df["aqi_co"] > 100).astype(int) +
        (df["aqi_no2"] > 100).astype(int) +
        (df["aqi_so2"] > 100).astype(int)
    )
    df["who_dominant_pollutant"] = df.apply(dominant_pollutant, axis=1)
    df["rule_based_risk_class"] = df["aqi_category"]
    df["risk_class"] = df["aqi_category"]

    df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S").fillna("")

    output_columns = [
        "device_id",
        "timestamp",
        "co",
        "so2",
        "no2",
        "pm1_0",
        "pm2_5",
        "pm10",
        "temperature",
        "humidity",
        "hour",
        "day_of_week",
        "total_gas_load",
        "total_pm_load",
        "co_so2_interaction",
        "gas_pm_interaction",
        "temp_humidity_index",
        "heat_stress_flag",
        "high_humidity_flag",
        "pm2_5_pm10_ratio",
        "pm1_pm2_5_ratio",
        "child_exposure_score",
        "co_mg_m3",
        "no2_ug_m3",
        "so2_ug_m3",
        "aqi_pm2_5",
        "aqi_pm10",
        "aqi_co",
        "aqi_no2",
        "aqi_so2",
        "aqi",
        "aqi_category",
        "who_aqg_exceedance_count",
        "who_dominant_pollutant",
        "rule_based_risk_class",
        "risk_class",
    ]

    df = df[output_columns]
    df.to_csv(MODEL_READY_CSV, index=False, encoding="utf-8")

    print(f"Model-ready dataset saved to: {MODEL_READY_CSV}")
    print("Risk distribution:")
    print(df["risk_class"].value_counts())
    print("\nFinal columns saved:")
    print(df.columns.tolist())

    return df


def main():
    try:
        init_firebase()
        pull_new_records()
    except Exception as exc:
        print(f"Firebase pull skipped: {exc}")

    df = build_features()
    if df is None:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
