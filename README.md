# OmiGuard

OmiGuard is an AI-powered environmental monitoring system for harmful gas and air-quality risk prediction. It combines sensor data preparation, machine-learning inference, Firebase integration, an automated prediction pipeline, a responsive web dashboard, and an optional LLM assistant for safety recommendations.

## Features

- FastAPI prediction API for gas and particulate risk classification.
- Trained machine-learning models for risk scoring and anomaly detection.
- Firebase pipeline for reading live sensor data and writing prediction history.
- Responsive dashboard for live prediction status, pollutant readings, trends, and device state.
- Optional LLM-powered safety assistant using Hugging Face Inference API.
- Training scripts for regenerating AQI and no-AQI model variants.
- Docker-oriented prediction service scaffold for deployment workflows.

## Project Structure

```text
.
├── gas_ai_system/
│   ├── dashboard/              # Static OmiGuard dashboard
│   ├── data/                   # Sample and model-ready datasets
│   ├── models/                 # Trained model artifacts
│   ├── prediction_service/     # Docker service files
│   └── src/                    # API, training, Firebase, and pipeline code
├── llm/                        # Optional standalone chatbot service
├── .env.example                # Environment variable template
├── .gitignore
└── README.md
```

## System Requirements

- Python 3.10 or newer
- Firebase Realtime Database project
- Firebase service account JSON file
- Hugging Face token for the optional LLM recommendation/chat features

## Quick Start

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r gas_ai_system\src\requirements.txt
```

Create your local environment file:

```powershell
Copy-Item .env.example gas_ai_system\src\.env
```

Edit `gas_ai_system\src\.env` and add your real values.

Place your Firebase service account file here:

```text
gas_ai_system/firebase_key.json
```

Do not commit `firebase_key.json` or `.env`.

## Run the API

```powershell
.\.venv\Scripts\Activate.ps1
cd gas_ai_system\src
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

## Run the Auto Prediction Pipeline

Keep the API running in one terminal. In another terminal:

```powershell
cd gas_ai_system
..\.venv\Scripts\Activate.ps1
python src\auto_predict_pipeline.py
```

The pipeline reads the latest sensor payload from Firebase, sends it to the API, enriches the result with an LLM recommendation when needed, and writes:

```text
predictions/node_01/latest
predictions/node_01/history
```

## Run the Dashboard

```powershell
cd gas_ai_system
..\.venv\Scripts\Activate.ps1
python -m http.server 5500 -d dashboard
```

Open:

```text
http://127.0.0.1:5500
```

## Optional Standalone Chatbot

The main FastAPI API already exposes:

```text
POST /chat
```

If you want to run the standalone Flask chatbot service:

```powershell
cd llm
..\.venv\Scripts\Activate.ps1
python chatbot_api.py
```

## Training

Regenerate the main model:

```powershell
cd gas_ai_system
..\.venv\Scripts\Activate.ps1
python src\train.py
```

Regenerate the no-AQI model:

```powershell
cd gas_ai_system
..\.venv\Scripts\Activate.ps1
python src\train_no_aqi.py
```

The training scripts read from:

```text
gas_ai_system/data/model_ready_sensor_data.csv
gas_ai_system/data/model_ready_sensor_data_no_aqi.csv
```

and write model artifacts to:

```text
gas_ai_system/models/
gas_ai_system/models/no_aqi/
```

## Environment Variables

Copy `.env.example` to `gas_ai_system/src/.env` and configure:

```env
HF_TOKEN=your_hugging_face_token_here
```

Firebase credentials are loaded from:

```text
gas_ai_system/firebase_key.json
```

## Security Notes

This repository intentionally excludes secrets and runtime files:

- `.env`
- `firebase_key.json`
- Python cache files
- generated Firebase payload history
- local virtual environments
- backup folders and zip archives

Before pushing, run:

```powershell
git status
```

and confirm no private credential files are staged.

## Main API Endpoints

- `GET /` - health check and model metadata.
- `POST /predict` - returns risk class, confidence score, anomaly flag, and action recommendation.
- `POST /chat` - returns assistant guidance based on the current dashboard context.

## License

Add your preferred license before publishing publicly.
