import os
import numpy as np
import joblib
import pandas as pd

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from chatbot_service import generate_chat_reply


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "models")

RISK_MODEL_PATH = os.path.join(MODELS_DIR, "risk_model.pkl")
ANOMALY_MODEL_PATH = os.path.join(MODELS_DIR, "anomaly_model.pkl")
LABEL_ENCODER_PATH = os.path.join(MODELS_DIR, "label_encoder.pkl")
FEATURE_COLS_PATH = os.path.join(MODELS_DIR, "feature_cols.pkl")


app = FastAPI(title="OmiGuard Lite Gas AI System API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


clf = joblib.load(RISK_MODEL_PATH)
iso = joblib.load(ANOMALY_MODEL_PATH)
le = joblib.load(LABEL_ENCODER_PATH)
feature_cols = joblib.load(FEATURE_COLS_PATH)


class SensorInput(BaseModel):
    co: float
    so2: float
    no2: float
    pm1_0: float
    pm2_5: float
    pm10: float
    temperature: float
    humidity: float

    hour: int
    day_of_week: int

    total_gas_load: float
    total_pm_load: float
    co_so2_interaction: float
    gas_pm_interaction: float
    temp_humidity_index: float

    heat_stress_flag: int
    high_humidity_flag: int

    pm2_5_pm10_ratio: float
    pm1_pm2_5_ratio: float
    child_exposure_score: float

    co_mg_m3: float = 0.0
    no2_ug_m3: float = 0.0
    so2_ug_m3: float = 0.0

    aqi_pm2_5: float
    aqi_pm10: float
    aqi_co: float = 0.0
    aqi_no2: float = 0.0
    aqi_so2: float = 0.0
    aqi: float
    who_aqg_exceedance_count: int = 0

    model_config = ConfigDict(extra="allow")


class ChatInput(BaseModel):
    message: str
    context: dict = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


def action_for(risk, anomaly):
    if anomaly:
        return "Abnormal reading detected. Inspect the device, verify the sensor reading, and check the environment immediately."

    if risk == "Dangerous":
        return "Dangerous air condition detected. Move children away immediately, improve ventilation, and alert responsible personnel."

    if risk == "Caution":
        return "Caution level detected. Reduce exposure, improve ventilation, and continue close monitoring."

    if risk == "Moderate":
        return "Moderate air quality concern. Continue monitoring and improve ventilation where possible."

    return "Safe conditions. Continue normal monitoring."


@app.get("/")
def home():
    return {
        "message": "OmiGuard Lite Gas AI System Running",
        "expected_features": feature_cols,
        "risk_classes": ["Safe", "Moderate", "Caution", "Dangerous"]
    }


@app.post("/predict")
def predict(data: SensorInput):
    data_dict = data.model_dump()

    values = pd.DataFrame([[data_dict.get(col, 0) for col in feature_cols]], columns=feature_cols)

    pred = clf.predict(values)[0]
    probs = clf.predict_proba(values)[0]

    risk_label = le.inverse_transform([pred])[0]
    anomaly = iso.predict(values)[0] == -1

    return {
        "risk_class": risk_label,
        "risk_score": round(float(np.max(probs)), 4),
        "anomaly_flag": bool(anomaly),
        "action_recommendation": action_for(risk_label, anomaly)
    }


@app.post("/chat")
def chat(data: ChatInput):
    try:
        reply = generate_chat_reply(data.message, data.context)
        return {"reply": reply}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
