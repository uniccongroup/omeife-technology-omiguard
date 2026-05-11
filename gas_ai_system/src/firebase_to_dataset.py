import os
import csv
import firebase_admin
from firebase_admin import credentials, db


# =============================
# PROJECT PATHS
# =============================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FIREBASE_KEY_PATH = os.path.join(BASE_DIR, "firebase_key.json")
OUTPUT_CSV = os.path.join(BASE_DIR, "data", "real_sensor_data.csv")

# hidden tracking file (for deduplication)
ID_TRACK_FILE = os.path.join(BASE_DIR, "data", "processed_ids.txt")


# =============================
# FIREBASE CONFIG
# =============================
DATABASE_URL = "https://streamlit-auth-9148c-default-rtdb.firebaseio.com/"
SENSOR_PATH = "sensor_data/node_01/readings"


# =============================
# FIREBASE INIT
# =============================
if not firebase_admin._apps:
    cred = credentials.Certificate(FIREBASE_KEY_PATH)
    firebase_admin.initialize_app(cred, {
        "databaseURL": DATABASE_URL
    })


# CSV fields (NO firebase_id)
FIELDNAMES = [
    "device_id",
    "timestamp",
    "co",
    "so2",
    "no2",
    "pm1_0",
    "pm2_5",
    "pm10",
    "temperature",
    "humidity"
]


# =============================
# LOAD SAVED IDS
# =============================
def load_processed_ids():
    if not os.path.exists(ID_TRACK_FILE):
        return set()

    with open(ID_TRACK_FILE, "r") as f:
        return set(line.strip() for line in f.readlines())


# =============================
# SAVE NEW IDS
# =============================
def save_processed_ids(new_ids):
    with open(ID_TRACK_FILE, "a") as f:
        for _id in new_ids:
            f.write(_id + "\n")


# =============================
# FORMAT DATA (NO firebase_id)
# =============================
def normalize_record(record):
    return {
        "device_id": record.get("device_id", "node_01"),
        "timestamp": record.get("timestamp", ""),
        "co": record.get("co", 0),
        "so2": record.get("so2", 0),
        "no2": record.get("no2", 0),
        "pm1_0": record.get("pm1_0", 0),
        "pm2_5": record.get("pm2_5", 0),
        "pm10": record.get("pm10", 0),
        "temperature": record.get("temperature", 0),
        "humidity": record.get("humidity", 0)
    }


# =============================
# MAIN FUNCTION
# =============================
def append_new_records():
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)

    processed_ids = load_processed_ids()

    ref = db.reference(SENSOR_PATH)
    firebase_data = ref.get()

    if not firebase_data:
        print("No Firebase data found.")
        return

    new_rows = []
    new_ids = []

    for firebase_id, record in firebase_data.items():
        if firebase_id not in processed_ids:
            new_rows.append(normalize_record(record))
            new_ids.append(firebase_id)

    if not new_rows:
        print("No new records to append.")
        return

    file_exists = os.path.exists(OUTPUT_CSV)

    with open(OUTPUT_CSV, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)

        if not file_exists:
            writer.writeheader()

        writer.writerows(new_rows)

    save_processed_ids(new_ids)

    print(f"Appended {len(new_rows)} new records.")
    print(f"CSV updated: {OUTPUT_CSV}")


# =============================
# RUN
# =============================
if __name__ == "__main__":
    append_new_records()