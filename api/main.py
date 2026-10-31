"""
ClaimGuard Fraud Detection API

FastAPI routing layer for detecting fraud in auto repair estimates.
Delegates feature extraction and scoring to api.inference.

References:
- CCC Intelligent Solutions: https://www.cccis.com
- CCC Secure Share: https://www.cccsecureshare.com/Developers
- CIECA BMS standard: https://www.cccsecureshare.com/Faq
"""

from __future__ import annotations

import json
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any

try:
    import shap
except ImportError:
    shap = None

try:
    import xgboost as xgb
except ImportError:
    xgb = None
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .constants import APP_VERSION, ARTIFACTS_DIR
from .inference import run_prediction
from .schemas import (
    BatchPredictionOut,
    EstimateIn,
    HealthOut,
    ModelInfoOut,
    PredictionOut,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("claimguard.api")


# ---------------------------------------------------------------------------
# Lifespan – Model & Artifact Loading
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    """Load ML artifacts once at startup; release on shutdown."""
    model_path = ARTIFACTS_DIR / "model.json"
    if not model_path.exists():
        model_path = ARTIFACTS_DIR / "model.ubj"
    feature_path = ARTIFACTS_DIR / "feature_names.json"
    metadata_path = ARTIFACTS_DIR / "training_metadata.json"
    metrics_path = ARTIFACTS_DIR / "metrics.json"

    model_loaded = False
    model: xgb.Booster | None = None
    explainer: shap.TreeExplainer | None = None
    feature_names: list[str] = []
    metadata: dict[str, Any] = {}
    metrics: dict[str, Any] = {}

    try:
        if not model_path.exists():
            logger.warning(
                "Model artifact not found at %s – running in baseline heuristic mode.", model_path
            )
        else:
            model = xgb.Booster()
            model.load_model(str(model_path))
            logger.info("XGBoost model loaded from %s", model_path)
            explainer = shap.TreeExplainer(model)
            logger.info("SHAP TreeExplainer initialised.")
            model_loaded = True

        if feature_path.exists():
            with feature_path.open() as fh:
                feature_names = json.load(fh)
            logger.info("Loaded %d feature names.", len(feature_names))

        if metadata_path.exists():
            with metadata_path.open() as fh:
                metadata = json.load(fh)

        if metrics_path.exists():
            with metrics_path.open() as fh:
                metrics = json.load(fh)

    except Exception as exc:  # noqa: BLE001
        logger.error("Error during model loading: %s", exc, exc_info=True)

    app.state.model = model
    app.state.explainer = explainer
    app.state.feature_names = feature_names
    app.state.metadata = metadata
    app.state.metrics = metrics
    app.state.model_loaded = model_loaded

    yield
    logger.info("ClaimGuard API shutting down.")


# ---------------------------------------------------------------------------
# FastAPI Application & Endpoints
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ClaimGuard Fraud Detection API",
    description="Automated fraud and line-item inflation detection for auto repair estimates.",
    version=APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/predict", response_model=PredictionOut, summary="Predict fraud on one estimate")
async def predict(estimate: EstimateIn) -> PredictionOut:
    """Analyze a single CIECA BMS estimate for fraud and rate anomalies."""
    return run_prediction(estimate, app.state)


@app.post("/predict/batch", response_model=BatchPredictionOut, summary="Predict fraud on batch")
async def predict_batch(estimates: list[EstimateIn]) -> BatchPredictionOut:
    """Process a batch of estimates sequentially with aggregate statistics."""
    if len(estimates) > 500:
        raise HTTPException(
            status_code=400, detail="Batch size exceeds maximum limit of 500 estimates."
        )

    t0 = time.perf_counter()
    results = [run_prediction(est, app.state) for est in estimates]
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    fraud_count = sum(1 for r in results if r.is_fraud)

    return BatchPredictionOut(
        results=results,
        total=len(results),
        fraud_count=fraud_count,
        processing_time_ms=round(elapsed_ms, 2),
    )


@app.get("/health", response_model=HealthOut, summary="API health check")
async def health() -> HealthOut:
    """Return current API health status and model-load state."""
    model_loaded: bool = getattr(app.state, "model_loaded", False)
    return HealthOut(
        status="ok" if model_loaded else "degraded",
        model_loaded=model_loaded,
        version=APP_VERSION,
    )


@app.get("/model-info", response_model=ModelInfoOut, summary="Loaded model metadata")
async def model_info() -> ModelInfoOut:
    """Return metadata about the currently loaded XGBoost model."""
    metadata: dict[str, Any] = getattr(app.state, "metadata", {})
    metrics: dict[str, Any] = getattr(app.state, "metrics", {})
    feature_names: list[str] = getattr(app.state, "feature_names", [])

    if not getattr(app.state, "model_loaded", False) and not metrics:
        raise HTTPException(
            status_code=503,
            detail="Model not loaded and no metrics artifact found. Please train the model first.",
        )

    return ModelInfoOut(
        model_version=metadata.get("model_version", APP_VERSION),
        training_date=metadata.get("training_date", "2025-01-15 (Baseline)"),
        n_features=len(feature_names),
        feature_names=feature_names,
        metrics=metrics,
        best_params=metadata.get("best_params", {}),
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=False,
    )
