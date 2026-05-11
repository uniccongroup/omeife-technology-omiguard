# OmiGuard Auto Prediction Service

This folder runs automatic prediction without changing the training workflow.

Every 90 seconds, the worker:

1. pulls the latest Firebase reading with `src/firebase_prepare_latest.py`
2. prepares WHO-based features
3. calls the FastAPI `/predict` endpoint
4. saves prediction output to `data/predictions`
5. sleeps and repeats

## Run Without Docker

Open terminal 1:

```powershell
cd C:\Users\USER\Documents\grant\gas_ai_system
uvicorn src.api:app --host 0.0.0.0 --port 8000
```

Open terminal 2:

```powershell
cd C:\Users\USER\Documents\grant\gas_ai_system
$env:PREDICT_INTERVAL_SECONDS="90"
python prediction_service\auto_predict_latest.py
```

Run only one cycle for testing:

```powershell
python prediction_service\auto_predict_latest.py --once
```

## Run With Docker Compose

From this folder:

```powershell
cd C:\Users\USER\Documents\grant\gas_ai_system\prediction_service
docker compose up --build
```

This starts two services:

- `api`: runs `uvicorn src.api:app`
- `predictor`: runs the 90-second auto prediction loop

Stop both services:

```powershell
docker compose down
```

Run in the background:

```powershell
docker compose up --build -d
```

View logs:

```powershell
docker compose logs -f predictor
```

## Outputs

The worker saves:

```text
data/predictions/latest_prediction.json
data/predictions/prediction_history.csv
data/predictions/history/*.json
```

## Optional Firebase Prediction Writes

By default, predictions are saved locally only.

To also write predictions back to Firebase, set:

```powershell
$env:SAVE_PREDICTIONS_TO_FIREBASE="true"
```

For Docker, edit `docker-compose.yml`:

```yaml
SAVE_PREDICTIONS_TO_FIREBASE: "true"
```

Default Firebase output paths:

```text
sensor_data/node_01/predictions/latest
sensor_data/node_01/predictions/history
```
