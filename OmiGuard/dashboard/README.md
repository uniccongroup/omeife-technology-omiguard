# OmiGuard Live Dashboard

This static dashboard reads prediction data from Firebase:

```text
predictions/node_01/latest
predictions/node_01/history
```

It refreshes every 10 seconds. The prediction pipeline can still run every 90 seconds; the dashboard simply holds the current latest prediction until Firebase receives the next one.

## Run

Open directly:

```text
C:\Users\USER\Documents\grant\gas_ai_system\dashboard\index.html
```

Or serve locally:

```powershell
cd C:\Users\USER\Documents\grant\gas_ai_system
python -m http.server 5500 -d dashboard
```

Then open:

```text
http://127.0.0.1:5500
```

## Required Pipeline

Start the API:

```powershell
cd C:\Users\USER\Documents\grant\gas_ai_system
uvicorn src.api:app --host 0.0.0.0 --port 8000
```

Start the auto prediction pipeline:

```powershell
cd C:\Users\USER\Documents\grant\gas_ai_system
python src\auto_predict_pipeline.py
```

The dashboard will update after the pipeline writes the next prediction.
