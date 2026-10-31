"""
ClaimGuard Inference & Feature Transformation Engine

Extracts features from CIECA BMS estimate payloads and computes SHAP-weighted
line-item fraud suspicion flags with natural language explanations.
"""

from __future__ import annotations

import logging
import os
import time
from itertools import combinations
from typing import Any

import numpy as np
import pandas as pd
try:
    import shap
except ImportError:
    shap = None

try:
    import xgboost as xgb
except ImportError:
    xgb = None

try:
    from rapidfuzz import fuzz

    def _fuzzy_score(a: str, b: str) -> float:
        return float(fuzz.token_sort_ratio(a, b))
except ImportError:
    from difflib import SequenceMatcher

    def _fuzzy_score(a: str, b: str) -> float:
        sa = " ".join(sorted(a.lower().split()))
        sb = " ".join(sorted(b.lower().split()))
        return SequenceMatcher(None, sa, sb).ratio() * 100.0


from .constants import (
    DUPLICATE_SIM_WARN,
    FRAUD_EXPLANATIONS,
    HOURS_RATIO_CRIT,
    HOURS_RATIO_WARN,
    LINE_SUSPICION_THRESHOLD,
    PANEL_ADJACENCY,
    PHANTOM_PART_TRIM_MAP,
    PRICE_RATIO_CRIT,
    PRICE_RATIO_WARN,
    REFINISH_BLEND_OPS,
)
from .schemas import EstimateIn, FlaggedLineOut, LineItemIn, PredictionOut

logger = logging.getLogger("claimguard.inference")


# ---------------------------------------------------------------------------
# Adjacency & Helper Functions
# ---------------------------------------------------------------------------


def _is_adjacent(panel_a: str, panel_b: str) -> bool:
    """Check if two body panels are adjacent or identical."""
    if panel_a == panel_b:
        return True
    return panel_b in PANEL_ADJACENCY.get(panel_a, set())


def _has_non_adjacent_operation(line_items: list[LineItemIn], primary_panel: str) -> bool:
    """Return True if any operation occurs on a panel disconnected from primary damage."""
    for li in line_items:
        if li.operation in REFINISH_BLEND_OPS and not _is_adjacent(primary_panel, li.panel):
            return True
    return False


def _compute_duplicate_sim(line_items: list[LineItemIn]) -> float:
    """Return the maximum pairwise fuzzy string similarity across line descriptions."""
    descriptions = [li.description.strip().lower() for li in line_items if li.description.strip()]
    if len(descriptions) < 2:
        return 0.0
    return max(_fuzzy_score(d1, d2) for d1, d2 in combinations(descriptions, 2)) / 100.0


def _find_max_duplicate_sim_for_line(target: LineItemIn, all_lines: list[LineItemIn]) -> float:
    """Compute the maximum similarity between this line and any other sibling line."""
    desc = target.description.strip().lower()
    if not desc:
        return 0.0
    scores = [
        _fuzzy_score(desc, other.description.strip().lower())
        for other in all_lines
        if other.line_id != target.line_id and other.description.strip()
    ]
    return max(scores, default=0) / 100.0


# ---------------------------------------------------------------------------
# Feature Extraction
# ---------------------------------------------------------------------------


def extract_features(estimate: EstimateIn, feature_names: list[str]) -> pd.DataFrame:
    """
    Extract the 27-dimensional feature vector matching features/build.py.
    """
    lines = estimate.line_items

    # 1. Labor hour ratios
    hours_ratios: list[float] = [
        min(li.labor_hours_billed / li.labor_hours_book, 5.0)
        for li in lines
        if li.labor_hours_book > 0
    ]
    max_hours_ratio = max(hours_ratios, default=1.0)
    mean_hours_ratio = float(np.mean(hours_ratios)) if hours_ratios else 1.0

    # 2. Part price ratios
    price_ratios: list[float] = [
        min(li.part.billed_price / li.part.oem_price, 5.0)
        for li in lines
        if li.part and li.part.oem_price > 0
    ]
    max_part_price_ratio = max(price_ratios, default=1.0)
    mean_part_price_ratio = float(np.mean(price_ratios)) if price_ratios else 1.0

    # 3. High-ratio counts
    high_hours_ratio_count = sum(1 for r in hours_ratios if r > HOURS_RATIO_WARN)
    high_price_ratio_count = sum(1 for r in price_ratios if r > PRICE_RATIO_WARN)

    # 4. Duplicate similarity score
    duplicate_sim_score = _compute_duplicate_sim(lines)

    # 5. Non-adjacent operations
    primary_panel = lines[0].panel if lines else "hood"
    has_non_adjacent_op = 1.0 if _has_non_adjacent_operation(lines, primary_panel) else 0.0

    # 6. Cost & labor aggregates
    total_labor_cost = sum(li.labor_hours_billed * li.labor_rate for li in lines)
    total_parts_cost = sum(li.part.billed_price for li in lines if li.part)
    total_billed = total_labor_cost + total_parts_cost
    total_labor_hours = sum(li.labor_hours_billed for li in lines)
    labor_parts_ratio = total_labor_hours / (total_parts_cost + 1.0)

    # 7. Metadata features
    line_count = float(len(lines))
    unique_panel_count = float(len({li.panel for li in lines}))
    vehicle_age = float(max(0, 2025 - estimate.vehicle.year))
    mileage = estimate.vehicle.mileage
    mileage_bucket = 0.0 if mileage < 25_000 else 1.0 if mileage < 75_000 else 2.0

    # 8. Operation counts
    op_counts = {
        "op_RR_count": float(sum(1 for li in lines if li.operation == "R&R")),
        "op_Repair_count": float(sum(1 for li in lines if li.operation == "Repair")),
        "op_Refinish_count": float(sum(1 for li in lines if li.operation == "Refinish")),
        "op_Blend_count": float(sum(1 for li in lines if li.operation == "Blend")),
        "op_Align_count": float(sum(1 for li in lines if li.operation == "Align")),
        "op_Replace_count": float(sum(1 for li in lines if li.operation == "Replace")),
    }

    # 9. Region one-hot
    region_dummies = {
        f"region_{r}": 1.0 if estimate.region == r else 0.0
        for r in ["northeast", "southeast", "midwest", "southwest", "west"]
    }

    raw: dict[str, float] = {
        "max_hours_ratio": max_hours_ratio,
        "mean_hours_ratio": mean_hours_ratio,
        "max_part_price_ratio": max_part_price_ratio,
        "mean_part_price_ratio": mean_part_price_ratio,
        "high_hours_ratio_count": float(high_hours_ratio_count),
        "high_price_ratio_count": float(high_price_ratio_count),
        "duplicate_sim_score": duplicate_sim_score,
        "has_non_adjacent_op": has_non_adjacent_op,
        "labor_parts_ratio": labor_parts_ratio,
        "total_billed": total_billed,
        "line_count": line_count,
        "unique_panel_count": unique_panel_count,
        "vehicle_age": vehicle_age,
        "mileage_bucket": mileage_bucket,
        **op_counts,
        **region_dummies,
        "shop_fraud_rate": 0.05,
        "shop_avg_total_cost": 2500.0,
    }

    row = {col: raw.get(col, 0.0) for col in feature_names} if feature_names else raw
    return pd.DataFrame([row])


# ---------------------------------------------------------------------------
# Line Flagging & Explanations
# ---------------------------------------------------------------------------


def _build_explanation(
    li: LineItemIn, fraud_types: list[str], hr: float, pr: float, dup_score: float
) -> str:
    """Render the primary fraud explanation template for a flagged line."""
    primary = fraud_types[0] if fraud_types else "unknown"
    tmpl = FRAUD_EXPLANATIONS.get(primary, "Line item deviates significantly from regional norms.")

    return tmpl.format(
        billed=li.labor_hours_billed
        if primary != "part_price_markup"
        else (li.part.billed_price if li.part else 0.0),
        book=li.labor_hours_book,
        ratio=hr
        if primary == "inflated_labor_hours"
        else (pr - 1.0 if primary == "part_price_markup" else hr),
        median=li.part.oem_price if li.part else 0.0,
        score=dup_score,
        operation=li.operation,
        panel=li.panel,
        part=li.part.name if li.part else "part",
        trim="Base",
        hours=li.labor_hours_billed,
    )


def flag_lines(
    estimate: EstimateIn,
    shap_values: np.ndarray,
    feature_names: list[str],
) -> list[FlaggedLineOut]:
    """Score individual line items and attach SHAP-weighted plain-English explanations."""
    lines = estimate.line_items
    primary_panel = lines[0].panel if lines else "hood"

    shap_abs = np.abs(shap_values).flatten()
    shap_weights: dict[str, float] = (
        dict(zip(feature_names, shap_abs / shap_abs.sum(), strict=False))
        if shap_abs.sum() > 0 and len(feature_names) == len(shap_abs)
        else {}
    )

    hours_boost = shap_weights.get("max_hours_ratio", 0.0) + shap_weights.get(
        "mean_hours_ratio", 0.0
    )
    price_boost = shap_weights.get("max_part_price_ratio", 0.0) + shap_weights.get(
        "mean_part_price_ratio", 0.0
    )
    dup_boost = shap_weights.get("duplicate_sim_score", 0.0)

    flagged: list[FlaggedLineOut] = []

    for li in lines:
        hr = li.labor_hours_billed / li.labor_hours_book if li.labor_hours_book > 0 else 1.0
        pr = (
            (li.part.billed_price / li.part.oem_price)
            if (li.part and li.part.oem_price > 0)
            else 1.0
        )
        dup_score = _find_max_duplicate_sim_for_line(li, lines)

        detected_types: list[str] = []
        scores: list[float] = []

        if hr > HOURS_RATIO_WARN:
            detected_types.append("inflated_labor_hours")
            scores.append(
                min(
                    1.0,
                    0.4
                    + (hr - HOURS_RATIO_WARN) / (HOURS_RATIO_CRIT - HOURS_RATIO_WARN) * 0.5
                    + hours_boost,
                )
            )

        if pr > PRICE_RATIO_WARN:
            detected_types.append("part_price_markup")
            scores.append(
                min(
                    1.0,
                    0.4
                    + (pr - PRICE_RATIO_WARN) / (PRICE_RATIO_CRIT - PRICE_RATIO_WARN) * 0.5
                    + price_boost,
                )
            )

        if dup_score >= DUPLICATE_SIM_WARN:
            detected_types.append("duplicate_line_items")
            scores.append(min(1.0, 0.4 + dup_score * 0.4 + dup_boost))

        if li.operation in REFINISH_BLEND_OPS and not _is_adjacent(primary_panel, li.panel):
            detected_types.append("unnecessary_operations")
            scores.append(0.72)

        if li.part:
            part_lower = li.part.name.lower()
            for kw in PHANTOM_PART_TRIM_MAP:
                if kw in part_lower and estimate.vehicle.trim.lower() in {"base", "lx", "se"}:
                    detected_types.append("phantom_parts")
                    scores.append(0.85)
                    break

        if li.labor_hours_billed >= 7.0 and (not li.part or li.part.oem_price < 50.0):
            detected_types.append("labor_parts_mismatch")
            scores.append(0.78)

        confidence = max(scores, default=0.0)
        if confidence >= LINE_SUSPICION_THRESHOLD:
            flagged.append(
                FlaggedLineOut(
                    line_id=li.line_id,
                    fraud_types=detected_types,
                    confidence=round(confidence, 4),
                    explanation=_build_explanation(li, detected_types, hr, pr, dup_score),
                )
            )

    return flagged


# ---------------------------------------------------------------------------
# Prediction Pipeline Coordinator
# ---------------------------------------------------------------------------


def run_prediction(estimate: EstimateIn, app_state: Any) -> PredictionOut:
    """Execute end-to-end inference and return a PredictionOut response."""
    t0 = time.perf_counter()

    model: xgb.Booster | None = getattr(app_state, "model", None)
    explainer: shap.TreeExplainer | None = getattr(app_state, "explainer", None)
    feature_names: list[str] = getattr(app_state, "feature_names", [])

    df = extract_features(estimate, feature_names)

    if model is None:
        max_hr = float(df["max_hours_ratio"].iloc[0]) if "max_hours_ratio" in df.columns else 1.0
        max_pr = (
            float(df["max_part_price_ratio"].iloc[0])
            if "max_part_price_ratio" in df.columns
            else 1.0
        )
        dup_sim = (
            float(df["duplicate_sim_score"].iloc[0]) if "duplicate_sim_score" in df.columns else 0.0
        )
        non_adj = (
            float(df["has_non_adjacent_op"].iloc[0]) if "has_non_adjacent_op" in df.columns else 0.0
        )

        hours_score = max(0.0, min(1.0, (max_hr - 1.0) / 1.5))
        price_score = max(0.0, min(1.0, (max_pr - 1.0) / 0.6))
        prob = float(
            np.clip(
                0.04 + 0.40 * hours_score + 0.35 * price_score + 0.25 * dup_sim + 0.20 * non_adj,
                0.01,
                0.97,
            )
        )
        shap_row = np.zeros(len(feature_names))
    else:
        dmatrix = xgb.DMatrix(df, feature_names=feature_names if feature_names else None)
        prob = float(model.predict(dmatrix)[0])
        try:
            shap_vals = explainer.shap_values(df) if explainer else []
            if isinstance(shap_vals, list):
                shap_vals = shap_vals[0]
            shap_row = np.array(shap_vals).flatten()
        except Exception as exc:
            logger.warning("SHAP calculation fallback: %s", exc)
            shap_row = np.zeros(len(feature_names))

    threshold = float(os.getenv("FRAUD_THRESHOLD", "0.5"))
    is_fraud = prob > threshold
    fraud_label = "clean" if prob < 0.4 else "suspicious" if prob <= 0.7 else "fraudulent"

    flagged_lines = flag_lines(estimate, shap_row, feature_names)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    return PredictionOut(
        estimate_id=estimate.estimate_id,
        fraud_probability=round(prob, 4),
        is_fraud=is_fraud,
        fraud_label=fraud_label,
        flagged_lines=flagged_lines,
        processing_time_ms=round(elapsed_ms, 2),
    )
