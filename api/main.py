"""
ClaimGuard Fraud Detection API

Provides REST endpoints for detecting fraud in auto repair estimates.
Model trained on CIECA BMS-inspired synthetic estimate data.

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
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import shap
import xgboost as xgb
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from rapidfuzz import fuzz

from .schemas import (
    BatchPredictionOut,
    EstimateIn,
    FlaggedLineOut,
    HealthOut,
    LineItemIn,
    ModelInfoOut,
    PredictionOut,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("claimguard.api")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ARTIFACTS_DIR = Path(os.getenv("ARTIFACTS_DIR", "models/artifacts"))
APP_VERSION = "1.0.0"

# Panel adjacency map – used to detect "unnecessary operations" fraud.
# Key = panel, value = set of panels considered adjacent / directly related.
PANEL_ADJACENCY: dict[str, set[str]] = {
    "hood": {"fender_lf", "fender_rf", "grille", "headlight_l", "headlight_r", "bumper_f"},
    "fender_lf": {"hood", "door_lf", "headlight_l", "bumper_f", "rocker_lf"},
    "fender_rf": {"hood", "door_rf", "headlight_r", "bumper_f", "rocker_rf"},
    "door_lf": {"fender_lf", "door_lr", "rocker_lf", "mirror_l", "a_pillar_l"},
    "door_rf": {"fender_rf", "door_rr", "rocker_rf", "mirror_r", "a_pillar_r"},
    "door_lr": {"door_lf", "quarter_l", "rocker_lf", "b_pillar_l", "c_pillar_l"},
    "door_rr": {"door_rf", "quarter_r", "rocker_rf", "b_pillar_r", "c_pillar_r"},
    "quarter_l": {"door_lr", "trunk_lid", "rocker_lf", "tail_light_l", "bumper_r"},
    "quarter_r": {"door_rr", "trunk_lid", "rocker_rf", "tail_light_r", "bumper_r"},
    "trunk_lid": {"quarter_l", "quarter_r", "bumper_r", "tail_light_l", "tail_light_r"},
    "bumper_f": {"hood", "fender_lf", "fender_rf", "grille", "headlight_l", "headlight_r"},
    "bumper_r": {"trunk_lid", "quarter_l", "quarter_r", "tail_light_l", "tail_light_r"},
    "roof": {"a_pillar_l", "a_pillar_r", "b_pillar_l", "b_pillar_r", "c_pillar_l", "c_pillar_r"},
    "rocker_lf": {"door_lf", "door_lr", "fender_lf", "quarter_l"},
    "rocker_rf": {"door_rf", "door_rr", "fender_rf", "quarter_r"},
    "grille": {"hood", "bumper_f", "headlight_l", "headlight_r"},
    "headlight_l": {"hood", "fender_lf", "bumper_f", "grille"},
    "headlight_r": {"hood", "fender_rf", "bumper_f", "grille"},
    "tail_light_l": {"quarter_l", "trunk_lid", "bumper_r"},
    "tail_light_r": {"quarter_r", "trunk_lid", "bumper_r"},
    "mirror_l": {"door_lf"},
    "mirror_r": {"door_rf"},
    "a_pillar_l": {"door_lf", "roof"},
    "a_pillar_r": {"door_rf", "roof"},
    "b_pillar_l": {"door_lf", "door_lr", "roof"},
    "b_pillar_r": {"door_rf", "door_rr", "roof"},
    "c_pillar_l": {"door_lr", "quarter_l", "roof"},
    "c_pillar_r": {"door_rr", "quarter_r", "roof"},
}

# Human-readable fraud explanation templates.
FRAUD_EXPLANATIONS: dict[str, str] = {
    "inflated_labor_hours": (
        "Labor hours billed ({billed:.1f}h) are {ratio:.1f}× the book rate ({book:.1f}h) "
        "for this operation."
    ),
    "part_price_markup": (
        "Part billed at ${billed:.2f}, which is {ratio:.0%} above the OEM reference price "
        "of ${median:.2f}."
    ),
    "duplicate_line_items": (
        "This line appears to be a near-duplicate of another line item "
        "(similarity: {score:.0%})."
    ),
    "unnecessary_operations": (
        "This {operation} operation is on a panel ({panel}) not adjacent to the "
        "primary damage area."
    ),
    "phantom_parts": (
        "Part '{part}' requires a vehicle feature not present on this trim ({trim})."
    ),
    "labor_parts_mismatch": (
        "Labor hours ({hours:.1f}h) are disproportionate to the minor part replaced ({part})."
    ),
}

# ---------------------------------------------------------------------------
# Lifespan – model loading
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
            logger.warning("Model artifact not found at %s – running in degraded mode.", model_path)
        else:
            model = xgb.Booster()
            model.load_model(str(model_path))
            logger.info("XGBoost model loaded from %s", model_path)

            # Build TreeExplainer once (expensive for large ensembles)
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
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ClaimGuard Fraud Detection API",
    description=(
        "REST API for detecting fraud in auto-repair estimates. "
        "Built on CIECA BMS-inspired data structures."
    ),
    version=APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # lock down via ALLOWED_ORIGINS env var in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

_CURRENT_YEAR = 2025  # training reference year


def _hours_ratio(li: LineItemIn) -> float:
    """Billed / book labor hours ratio; safe against zero book hours."""
    if li.labor_hours_book <= 0:
        return 1.0
    return li.labor_hours_billed / li.labor_hours_book


def _part_price_ratio(li: LineItemIn) -> float:
    """Billed / OEM price ratio for the part; 1.0 if no part."""
    if li.part is None or li.part.oem_price <= 0:
        return 1.0
    return li.part.billed_price / li.part.oem_price


def _max_pairwise_sim(descriptions: list[str]) -> float:
    """Return the maximum token-sort-ratio across all description pairs (0-1)."""
    if len(descriptions) < 2:
        return 0.0
    max_sim = 0.0
    for a, b in combinations(descriptions, 2):
        score = fuzz.token_sort_ratio(a, b) / 100.0
        if score > max_sim:
            max_sim = score
    return max_sim


def _has_non_adjacent_op(line_items: list[LineItemIn]) -> int:
    """
    Return 1 if any line item operates on a panel that is NOT adjacent to
    any other panel in the estimate (i.e., it looks isolated / unnecessary).
    """
    panels = [li.panel.lower().replace(" ", "_") for li in line_items]
    panel_set = set(panels)

    for panel in panel_set:
        adjacent = PANEL_ADJACENCY.get(panel, set())
        # If this panel has no neighbours in the estimate → suspicious
        if not adjacent.intersection(panel_set - {panel}):
            return 1
    return 0


def _mileage_bucket(mileage: int) -> int:
    """
    Encode mileage into ordered buckets matching training:
      0: <20k  1: 20-60k  2: 60-120k  3: 120-200k  4: ≥200k
    """
    if mileage < 20_000:
        return 0
    if mileage < 60_000:
        return 1
    if mileage < 120_000:
        return 2
    if mileage < 200_000:
        return 3
    return 4


def extract_features(estimate: EstimateIn, feature_names: list[str]) -> pd.DataFrame:
    """
    Derive the same feature set built by ``features/build.py`` from a live
    ``EstimateIn`` payload and return a single-row DataFrame whose columns
    match ``feature_names`` exactly (in order). Missing columns are filled 0.
    """
    items = estimate.line_items
    n = len(items)

    # --- Ratio features ---
    hours_ratios = [_hours_ratio(li) for li in items]
    price_ratios = [_part_price_ratio(li) for li in items]

    max_hours_ratio: float = max(hours_ratios)
    mean_hours_ratio: float = float(np.mean(hours_ratios))
    max_part_price_ratio: float = max(price_ratios)
    mean_part_price_ratio: float = float(np.mean(price_ratios))

    high_hours_ratio_count: int = sum(1 for r in hours_ratios if r > 1.3)
    high_price_ratio_count: int = sum(1 for r in price_ratios if r > 1.2)

    # --- Duplicate similarity ---
    descriptions = [li.description for li in items]
    duplicate_sim_score: float = _max_pairwise_sim(descriptions)

    # --- Non-adjacent operations ---
    has_non_adjacent: int = _has_non_adjacent_op(items)

    # --- Cost aggregates ---
    total_labor = sum(li.labor_hours_billed * li.labor_rate for li in items)
    total_parts = sum(
        (li.part.billed_price if li.part is not None else 0.0) for li in items
    )
    total_billed: float = total_labor + total_parts
    labor_parts_ratio: float = total_labor / max(total_parts, 1.0)

    # --- Structural counts ---
    line_count: int = n
    unique_panel_count: int = len({li.panel.lower() for li in items})

    # --- Vehicle features ---
    vehicle_age: int = _CURRENT_YEAR - estimate.vehicle.year
    mileage_bucket: int = _mileage_bucket(estimate.vehicle.mileage)

    # --- Operation counts ---
    op_counts: dict[str, int] = {
        "op_RR_count": 0,
        "op_Repair_count": 0,
        "op_Refinish_count": 0,
        "op_Blend_count": 0,
        "op_Align_count": 0,
        "op_Replace_count": 0,
    }
    _op_key_map = {
        "R&R": "op_RR_count",
        "Repair": "op_Repair_count",
        "Refinish": "op_Refinish_count",
        "Blend": "op_Blend_count",
        "Align": "op_Align_count",
        "Replace": "op_Replace_count",
    }
    for li in items:
        key = _op_key_map.get(li.operation)
        if key:
            op_counts[key] += 1

    # --- Region one-hot ---
    regions = ["northeast", "southeast", "midwest", "southwest", "west"]
    region_ohe = {f"region_{r}": int(estimate.region == r) for r in regions}

    # --- Shop-level features (default: no historical data at inference time) ---
    shop_fraud_rate: float = 0.05
    shop_avg_total_cost: float = 2500.0

    # --- Assemble raw feature dict ---
    raw: dict[str, float] = {
        "max_hours_ratio": max_hours_ratio,
        "mean_hours_ratio": mean_hours_ratio,
        "max_part_price_ratio": max_part_price_ratio,
        "mean_part_price_ratio": mean_part_price_ratio,
        "high_hours_ratio_count": float(high_hours_ratio_count),
        "high_price_ratio_count": float(high_price_ratio_count),
        "duplicate_sim_score": duplicate_sim_score,
        "has_non_adjacent_op": float(has_non_adjacent),
        "labor_parts_ratio": labor_parts_ratio,
        "total_billed": total_billed,
        "line_count": float(line_count),
        "unique_panel_count": float(unique_panel_count),
        "vehicle_age": float(vehicle_age),
        "mileage_bucket": float(mileage_bucket),
        "shop_fraud_rate": shop_fraud_rate,
        "shop_avg_total_cost": shop_avg_total_cost,
        **{k: float(v) for k, v in op_counts.items()},
        **{k: float(v) for k, v in region_ohe.items()},
    }

    # --- Build DataFrame aligned to training feature order ---
    if feature_names:
        row = {col: raw.get(col, 0.0) for col in feature_names}
    else:
        row = raw

    return pd.DataFrame([row])


# ---------------------------------------------------------------------------
# Per-line suspicion scoring & explanation
# ---------------------------------------------------------------------------

_HOURS_RATIO_THRESHOLD = 1.3
_PRICE_RATIO_THRESHOLD = 1.2
_DUP_SIM_THRESHOLD = 0.75
_LINE_SUSPICION_THRESHOLD = 0.4   # minimum score to flag a line


def _score_line(
    li: LineItemIn,
    hr: float,
    pr: float,
    dup_score: float,
    non_adjacent_panels: set[str],
) -> tuple[float, list[str]]:
    """
    Compute a suspicion score in [0, 1] for a single line item and return
    the list of fraud types detected.
    """
    score = 0.0
    fraud_types: list[str] = []

    # Inflated labor hours
    if hr > _HOURS_RATIO_THRESHOLD:
        weight = min((hr - 1.0) / 2.0, 1.0)   # saturates at 3× book
        score += 0.40 * weight
        fraud_types.append("inflated_labor_hours")

    # Part price markup
    if pr > _PRICE_RATIO_THRESHOLD:
        weight = min((pr - 1.0) / 1.5, 1.0)   # saturates at 2.5× OEM
        score += 0.30 * weight
        fraud_types.append("part_price_markup")

    # Duplicate line (shared across all lines in estimate)
    if dup_score >= _DUP_SIM_THRESHOLD:
        score += 0.20
        fraud_types.append("duplicate_line_items")

    # Non-adjacent operation
    panel_norm = li.panel.lower().replace(" ", "_")
    if panel_norm in non_adjacent_panels:
        score += 0.10
        fraud_types.append("unnecessary_operations")

    # Labor-parts mismatch: lots of hours for a cheap part
    if (
        li.part is not None
        and li.part.billed_price < 50.0
        and li.labor_hours_billed > 3.0
    ):
        score = min(score + 0.10, 1.0)
        if "labor_parts_mismatch" not in fraud_types:
            fraud_types.append("labor_parts_mismatch")

    return min(score, 1.0), fraud_types


def _build_explanation(li: LineItemIn, fraud_types: list[str], hr: float, pr: float, dup_score: float) -> str:
    """Render the most relevant fraud explanation template for this line."""
    if not fraud_types:
        return "No specific fraud pattern detected."

    primary = fraud_types[0]
    tpl = FRAUD_EXPLANATIONS.get(primary, "Suspicious activity detected.")

    try:
        if primary == "inflated_labor_hours":
            return tpl.format(
                billed=li.labor_hours_billed,
                ratio=hr,
                book=li.labor_hours_book,
            )
        if primary == "part_price_markup" and li.part is not None:
            return tpl.format(
                billed=li.part.billed_price,
                ratio=pr - 1.0,
                median=li.part.oem_price,
            )
        if primary == "duplicate_line_items":
            return tpl.format(score=dup_score)
        if primary == "unnecessary_operations":
            return tpl.format(operation=li.operation, panel=li.panel)
        if primary == "phantom_parts" and li.part is not None:
            return tpl.format(part=li.part.name, trim="unknown")
        if primary == "labor_parts_mismatch" and li.part is not None:
            return tpl.format(hours=li.labor_hours_billed, part=li.part.name)
    except (KeyError, ValueError):
        pass

    return tpl  # fallback: return raw template


def _identify_non_adjacent_panels(line_items: list[LineItemIn]) -> set[str]:
    """Return the set of panel names that are isolated (not adjacent to any other)."""
    panels = [li.panel.lower().replace(" ", "_") for li in line_items]
    panel_set = set(panels)
    isolated: set[str] = set()
    for panel in panel_set:
        adjacent = PANEL_ADJACENCY.get(panel, set())
        if not adjacent.intersection(panel_set - {panel}):
            isolated.add(panel)
    return isolated


def _flag_lines(
    estimate: EstimateIn,
    shap_values: np.ndarray,
    feature_names: list[str],
) -> list[FlaggedLineOut]:
    """
    Produce per-line fraud flags using a heuristic suspicion scorer weighted
    by SHAP feature importances for this estimate.
    """
    items = estimate.line_items
    dup_score = _max_pairwise_sim([li.description for li in items])
    non_adjacent = _identify_non_adjacent_panels(items)

    # SHAP-based feature importance weights (absolute values, normalised)
    shap_abs = np.abs(shap_values).flatten()
    if shap_abs.sum() > 0 and len(feature_names) == len(shap_abs):
        shap_weights = dict(zip(feature_names, shap_abs / shap_abs.sum()))
    else:
        shap_weights = {}

    # Weight boosts from SHAP
    hours_boost = shap_weights.get("max_hours_ratio", 0.0) + shap_weights.get("mean_hours_ratio", 0.0)
    price_boost = shap_weights.get("max_part_price_ratio", 0.0) + shap_weights.get("mean_part_price_ratio", 0.0)
    dup_boost = shap_weights.get("duplicate_sim_score", 0.0)

    flagged: list[FlaggedLineOut] = []

    for li in items:
        hr = _hours_ratio(li)
        pr = _part_price_ratio(li)

        base_score, fraud_types = _score_line(li, hr, pr, dup_score, non_adjacent)

        # Amplify score by SHAP weights for the matching features
        boosted = base_score
        if "inflated_labor_hours" in fraud_types:
            boosted += hours_boost * 0.3
        if "part_price_markup" in fraud_types:
            boosted += price_boost * 0.3
        if "duplicate_line_items" in fraud_types:
            boosted += dup_boost * 0.3

        confidence = min(boosted, 1.0)

        if confidence >= _LINE_SUSPICION_THRESHOLD:
            explanation = _build_explanation(li, fraud_types, hr, pr, dup_score)
            flagged.append(
                FlaggedLineOut(
                    line_id=li.line_id,
                    fraud_types=fraud_types,
                    confidence=round(confidence, 4),
                    explanation=explanation,
                )
            )

    return flagged


# ---------------------------------------------------------------------------
# Core prediction logic (shared by /predict and /predict/batch)
# ---------------------------------------------------------------------------


def _run_prediction(estimate: EstimateIn, app_state: Any) -> PredictionOut:
    """Run end-to-end fraud prediction for a single estimate."""
    t0 = time.perf_counter()

    model: xgb.Booster | None = app_state.model
    explainer: shap.TreeExplainer | None = app_state.explainer
    feature_names: list[str] = app_state.feature_names

    # 1. Feature extraction
    df = extract_features(estimate, feature_names)

    if model is None:
        logger.info("Using baseline feature-heuristic scorer (trained model artifact not loaded yet)")
        # Fallback scoring when model has not been trained yet
        max_hr = float(df["max_hours_ratio"].iloc[0]) if "max_hours_ratio" in df.columns else 1.0
        max_pr = float(df["max_part_price_ratio"].iloc[0]) if "max_part_price_ratio" in df.columns else 1.0
        dup_sim = float(df["duplicate_sim_score"].iloc[0]) if "duplicate_sim_score" in df.columns else 0.0
        non_adj = float(df["has_non_adjacent_op"].iloc[0]) if "has_non_adjacent_op" in df.columns else 0.0

        hours_score = max(0.0, min(1.0, (max_hr - 1.0) / 1.5))
        price_score = max(0.0, min(1.0, (max_pr - 1.0) / 0.6))
        prob = float(np.clip(0.04 + 0.40 * hours_score + 0.35 * price_score + 0.25 * dup_sim + 0.20 * non_adj, 0.01, 0.97))
        shap_row = np.zeros(len(feature_names))
    else:
        # 2. XGBoost inference
        dmatrix = xgb.DMatrix(df, feature_names=feature_names if feature_names else None)
        prob = float(model.predict(dmatrix)[0])

        # 4. SHAP values for this estimate
        try:
            shap_vals = explainer.shap_values(df)  # shape: (1, n_features) or (n_features,)
            if isinstance(shap_vals, list):
                shap_vals = shap_vals[0]
            shap_row = np.array(shap_vals).flatten()
        except Exception as exc:  # noqa: BLE001
            logger.warning("SHAP computation failed: %s", exc)
            shap_row = np.zeros(len(feature_names))

    # 3. Threshold & label
    threshold = float(os.getenv("FRAUD_THRESHOLD", "0.5"))
    is_fraud = prob > threshold

    if prob < 0.4:
        fraud_label = "clean"
    elif prob <= 0.7:
        fraud_label = "suspicious"
    else:
        fraud_label = "fraudulent"

    # 5. Per-line flagging
    flagged_lines = _flag_lines(estimate, shap_row, feature_names)

    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    return PredictionOut(
        estimate_id=estimate.estimate_id,
        fraud_probability=round(prob, 6),
        is_fraud=is_fraud,
        fraud_label=fraud_label,
        flagged_lines=flagged_lines,
        processing_time_ms=round(elapsed_ms, 2),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/predict", response_model=PredictionOut, summary="Score a single estimate")
async def predict(estimate: EstimateIn) -> PredictionOut:
    """
    Accept a single auto-repair estimate and return a fraud probability,
    categorical label, and per-line explanations.
    """
    return _run_prediction(estimate, app.state)


@app.post(
    "/predict/batch",
    response_model=BatchPredictionOut,
    summary="Score a batch of estimates",
)
async def predict_batch(estimates: list[EstimateIn]) -> BatchPredictionOut:
    """
    Accept a list of estimates (up to 500) and return aggregated results.
    Each estimate is scored independently.
    """
    if not estimates:
        raise HTTPException(status_code=422, detail="Batch must contain at least one estimate.")
    if len(estimates) > 500:
        raise HTTPException(status_code=422, detail="Batch size limit is 500 estimates.")

    t0 = time.perf_counter()
    results: list[PredictionOut] = []

    for est in estimates:
        result = _run_prediction(est, app.state)
        results.append(result)

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
