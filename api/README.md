# api

ClaimGuard FastAPI Inference Service.

Provides high-throughput REST endpoints for detecting fraudulent and inflated auto-repair estimates modeled on the CIECA BMS standard.

## Endpoints

- `POST /predict` — Analyzes a single estimate JSON, returns fraud probability, classification verdict, and line-level flags with SHAP explanations.
- `POST /predict/batch` — Batched prediction for multiple estimates (up to 500 per call).
- `GET /health` — Service health and model status.
- `GET /model-info` — Loaded model version, training timestamp, hyperparameters, and test evaluation metrics.

## Running Locally

```bash
pip install -r requirements.txt
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive OpenAPI docs will be available at [http://localhost:8000/docs](http://localhost:8000/docs).
