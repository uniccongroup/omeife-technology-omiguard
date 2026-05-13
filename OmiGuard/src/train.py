import json
import os

import joblib
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, IsolationForest
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "model_ready_sensor_data.csv")
MODELS_DIR = os.path.join(BASE_DIR, "models")
METRICS_PATH = os.path.join(MODELS_DIR, "metrics.txt")
REPORT_PATH = os.path.join(MODELS_DIR, "training_report.json")

FEATURE_COLS = [
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
    "who_aqg_exceedance_count",
]

TARGET_COL = "risk_class"
VALID_CLASSES = {"Safe", "Moderate", "Caution", "Dangerous"}


def load_training_data():
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(
            f"Model-ready dataset not found: {DATA_PATH}. "
            "Run src/manual_pull_build_dataset.py first."
        )

    df = pd.read_csv(DATA_PATH)

    missing = [col for col in FEATURE_COLS + [TARGET_COL] if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in model-ready dataset: {missing}")

    df[TARGET_COL] = df[TARGET_COL].astype(str).str.strip()
    invalid_labels = sorted(set(df[TARGET_COL]) - VALID_CLASSES)
    if invalid_labels:
        raise ValueError(
            f"Invalid {TARGET_COL} labels found: {invalid_labels}. "
            f"Expected only: {sorted(VALID_CLASSES)}"
        )

    for col in FEATURE_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=FEATURE_COLS + [TARGET_COL]).reset_index(drop=True)
    if df.empty:
        raise ValueError("No valid rows remain after cleaning the model-ready dataset.")

    return df


def main():
    os.makedirs(MODELS_DIR, exist_ok=True)

    df = load_training_data()
    X = df[FEATURE_COLS]
    y = df[TARGET_COL]

    label_encoder = LabelEncoder()
    y_encoded = label_encoder.fit_transform(y)

    class_counts = y.value_counts()
    use_stratify = len(class_counts) > 1 and class_counts.min() >= 2
    stratify = y_encoded if use_stratify else None

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y_encoded,
        test_size=0.2,
        random_state=42,
        stratify=stratify,
    )

    risk_model = GradientBoostingClassifier(random_state=42)
    risk_model.fit(X_train, y_train)

    predictions = risk_model.predict(X_test)
    accuracy = accuracy_score(y_test, predictions)
    macro_f1 = f1_score(y_test, predictions, average="macro", zero_division=0)

    contamination = min(0.1, max(1 / len(X), 0.05))
    anomaly_model = IsolationForest(contamination=contamination, random_state=42)
    anomaly_model.fit(X)

    joblib.dump(risk_model, os.path.join(MODELS_DIR, "risk_model.pkl"))
    joblib.dump(anomaly_model, os.path.join(MODELS_DIR, "anomaly_model.pkl"))
    joblib.dump(label_encoder, os.path.join(MODELS_DIR, "label_encoder.pkl"))
    joblib.dump(FEATURE_COLS, os.path.join(MODELS_DIR, "feature_cols.pkl"))

    with open(METRICS_PATH, "w", encoding="utf-8") as file:
        file.write("OmiGuard Lite Model Training Metrics\n")
        file.write("====================================\n")
        file.write(f"Rows: {len(df)}\n")
        file.write(f"Features: {len(FEATURE_COLS)}\n")
        file.write(f"Feature columns: {FEATURE_COLS}\n")
        file.write(f"Classes: {list(label_encoder.classes_)}\n")
        file.write(f"Accuracy: {accuracy:.4f}\n")
        file.write(f"Macro F1: {macro_f1:.4f}\n")

    report = {
        "rows": len(df),
        "features": FEATURE_COLS,
        "classes": list(label_encoder.classes_),
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "class_distribution": class_counts.to_dict(),
    }
    with open(REPORT_PATH, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=4)

    print(f"Rows: {len(df)}")
    print(f"Features: {len(FEATURE_COLS)}")
    print(f"Classes: {list(label_encoder.classes_)}")
    print(f"Accuracy: {accuracy:.4f}")
    print(f"Macro F1: {macro_f1:.4f}")
    print(f"Models saved to: {MODELS_DIR}")


if __name__ == "__main__":
    main()
