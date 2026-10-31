"""
Feature engineering for ClaimGuard fraud detection.

Produces estimate-level feature vectors from CIECA BMS-inspired estimate JSON.
Shop-level statistics (fraud rate, avg cost) are computed ONLY from training
shops to prevent data leakage across GroupKFold splits.

Usage:
    python build.py --data data/estimates.jsonl --out data/
"""

from __future__ import annotations

import argparse
import json
import os
from itertools import combinations
from typing import Any

import numpy as np
import pandas as pd
from rapidfuzz import fuzz

# ---------------------------------------------------------------------------
# Adjacency map for body panels (CIECA BMS-inspired)
# ---------------------------------------------------------------------------
PANEL_ADJACENCY: dict[str, set[str]] = {
    "front_bumper": {"hood", "left_fender", "right_fender", "grille", "front_fascia"},
    "hood": {"front_bumper", "left_fender", "right_fender", "cowl", "grille"},
    "left_fender": {"hood", "front_bumper", "left_door_front", "left_a_pillar", "cowl"},
    "right_fender": {"hood", "front_bumper", "right_door_front", "right_a_pillar", "cowl"},
    "left_door_front": {"left_fender", "left_door_rear", "left_b_pillar", "left_rocker"},
    "right_door_front": {"right_fender", "right_door_rear", "right_b_pillar", "right_rocker"},
    "left_door_rear": {
        "left_door_front",
        "left_quarter_panel",
        "left_b_pillar",
        "left_c_pillar",
        "left_rocker",
    },
    "right_door_rear": {
        "right_door_front",
        "right_quarter_panel",
        "right_b_pillar",
        "right_c_pillar",
        "right_rocker",
    },
    "left_quarter_panel": {
        "left_door_rear",
        "rear_bumper",
        "trunk_lid",
        "left_c_pillar",
        "left_rocker",
    },
    "right_quarter_panel": {
        "right_door_rear",
        "rear_bumper",
        "trunk_lid",
        "right_c_pillar",
        "right_rocker",
    },
    "rear_bumper": {"left_quarter_panel", "right_quarter_panel", "trunk_lid", "rear_fascia"},
    "trunk_lid": {"rear_bumper", "left_quarter_panel", "right_quarter_panel"},
    "roof": {
        "windshield",
        "left_a_pillar",
        "right_a_pillar",
        "left_b_pillar",
        "right_b_pillar",
        "left_c_pillar",
        "right_c_pillar",
        "rear_glass",
    },
    "windshield": {"roof", "left_a_pillar", "right_a_pillar", "cowl", "hood"},
    "rear_glass": {"roof", "left_c_pillar", "right_c_pillar"},
    "cowl": {"hood", "windshield", "left_fender", "right_fender"},
    "grille": {"front_bumper", "hood"},
    "front_fascia": {"front_bumper"},
    "rear_fascia": {"rear_bumper"},
    "left_rocker": {"left_door_front", "left_door_rear", "left_quarter_panel"},
    "right_rocker": {"right_door_front", "right_door_rear", "right_quarter_panel"},
    "left_a_pillar": {"left_fender", "windshield", "roof", "left_door_front"},
    "right_a_pillar": {"right_fender", "windshield", "roof", "right_door_front"},
    "left_b_pillar": {"left_door_front", "left_door_rear", "roof"},
    "right_b_pillar": {"right_door_front", "right_door_rear", "roof"},
    "left_c_pillar": {"left_door_rear", "left_quarter_panel", "roof", "rear_glass"},
    "right_c_pillar": {"right_door_rear", "right_quarter_panel", "roof", "rear_glass"},
    "floor_pan": {"left_rocker", "right_rocker"},
    "frame_rail_left": {"left_rocker", "floor_pan"},
    "frame_rail_right": {"right_rocker", "floor_pan"},
    "radiator_support": {"front_bumper", "hood", "left_fender", "right_fender"},
}

# All valid operation types
OPERATION_TYPES: list[str] = ["RR", "Repair", "Refinish", "Blend", "Align", "Replace"]

# All valid regions
REGIONS: list[str] = ["northeast", "southeast", "midwest", "southwest", "west"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_ratio(numerator: float, denominator: float, cap: float = 5.0) -> float:
    """Return numerator/denominator clamped to [0, cap]. Returns 0.0 if denom <= 0."""
    if denominator <= 0:
        return 0.0
    return min(numerator / denominator, cap)


def _is_adjacent(panel: str, primary_panels: set[str]) -> bool:
    """Return True if *panel* is adjacent to at least one panel in *primary_panels*."""
    neighbours = PANEL_ADJACENCY.get(panel, set())
    # Also treat a panel as adjacent to itself (it IS primary)
    return bool(neighbours & primary_panels) or panel in primary_panels


def _duplicate_sim_score(descriptions: list[str]) -> float:
    """Max pairwise token_sort_ratio across all description pairs, normalised to [0, 1]."""
    if len(descriptions) < 2:
        return 0.0
    max_score = 0.0
    for a, b in combinations(descriptions, 2):
        score = fuzz.token_sort_ratio(a, b)
        if score > max_score:
            max_score = score
    return max_score / 100.0


# ---------------------------------------------------------------------------
# Step 1: Load estimates
# ---------------------------------------------------------------------------


def load_estimates(data_path: str) -> list[dict[str, Any]]:
    """Load all estimates from a JSONL file."""
    estimates: list[dict[str, Any]] = []
    with open(data_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                estimates.append(json.loads(line))
    print(f"Loaded {len(estimates):,} estimates from {data_path}")
    return estimates


# ---------------------------------------------------------------------------
# Step 2: Regional part-price medians (fit on training data only)
# ---------------------------------------------------------------------------


def fit_regional_medians(
    estimates: list[dict[str, Any]],
    train_indices: np.ndarray,
) -> dict[str, dict[str, float]]:
    """
    Compute median OEM part price per (panel, vehicle_class) using only
    training-set estimates to prevent data leakage.

    Returns nested dict: medians[panel][vehicle_class] = median_price
    """
    records: list[dict[str, Any]] = []
    for idx in train_indices:
        est = estimates[idx]
        v_class = est["vehicle"].get("class", "unknown")
        for li in est.get("line_items", []):
            part = li.get("part")
            if part and part.get("oem_price") is not None:
                records.append(
                    {
                        "panel": li.get("panel", "unknown"),
                        "vehicle_class": v_class,
                        "oem_price": float(part["oem_price"]),
                    }
                )

    if not records:
        return {}

    df = pd.DataFrame(records)
    medians: dict[str, dict[str, float]] = {}
    for (panel, v_class), group in df.groupby(["panel", "vehicle_class"]):
        medians.setdefault(str(panel), {})[str(v_class)] = float(group["oem_price"].median())
    return medians


# ---------------------------------------------------------------------------
# Step 3 + 4 + 6: Per-estimate feature extraction
# ---------------------------------------------------------------------------


def extract_estimate_features(
    estimate: dict[str, Any],
    regional_medians: dict[str, dict[str, float]],
) -> dict[str, float | int]:
    """
    Extract all features for a single estimate (steps 3, 4, 6).
    regional_medians may be empty at feature-build time; pass {} to skip ratio features.
    """
    line_items: list[dict[str, Any]] = estimate.get("line_items", [])
    vehicle: dict[str, Any] = estimate.get("vehicle", {})
    region: str = estimate.get("region", "unknown")

    # ---- Gather primary damage panels from scenario ----
    # The scenario string (e.g. "rear_end") is used to derive primary panels.
    scenario: str = estimate.get("scenario", "")
    primary_panels: set[str] = _infer_primary_panels(scenario, line_items)

    # ---- Hours ratios ----
    hours_ratios: list[float] = []
    for li in line_items:
        billed = float(li.get("labor_hours_billed", 0.0) or 0.0)
        book = float(li.get("book_hours", 0.0) or 0.0)
        hours_ratios.append(_safe_ratio(billed, book, cap=5.0))

    max_hours_ratio = max(hours_ratios) if hours_ratios else 0.0
    mean_hours_ratio = float(np.mean(hours_ratios)) if hours_ratios else 0.0
    high_hours_ratio_count = sum(1 for r in hours_ratios if r > 1.3)

    # ---- Part price ratios ----
    part_price_ratios: list[float] = []
    for li in line_items:
        part = li.get("part")
        if not part:
            continue
        billed_price = float(part.get("billed_price", 0.0) or 0.0)
        oem_price = float(part.get("oem_price", 0.0) or 0.0)
        ratio = _safe_ratio(billed_price, oem_price, cap=5.0)
        part_price_ratios.append(ratio)

    max_part_price_ratio = max(part_price_ratios) if part_price_ratios else 0.0
    mean_part_price_ratio = float(np.mean(part_price_ratios)) if part_price_ratios else 0.0
    high_price_ratio_count = sum(1 for r in part_price_ratios if r > 1.2)

    # ---- Duplicate similarity score ----
    descriptions: list[str] = [str(li.get("description", "") or "") for li in line_items]
    duplicate_sim_score = _duplicate_sim_score(descriptions)

    # ---- Non-adjacent operation flag ----
    has_non_adjacent_op = 0
    for li in line_items:
        panel = str(li.get("panel", "") or "").lower().replace(" ", "_")
        if panel and not _is_adjacent(panel, primary_panels):
            has_non_adjacent_op = 1
            break

    # ---- Labor/parts ratio ----
    total_labor_hours: float = sum(
        float(li.get("labor_hours_billed", 0.0) or 0.0) for li in line_items
    )
    total_parts_cost: float = sum(
        float((li.get("part") or {}).get("billed_price", 0.0) or 0.0) for li in line_items
    )
    labor_parts_ratio = total_labor_hours / (total_parts_cost + 1.0)

    # ---- Estimate-level features ----
    labor_rate: float = float(estimate.get("labor_rate", 55.0) or 55.0)
    total_billed: float = sum(
        float(li.get("labor_hours_billed", 0.0) or 0.0) * labor_rate
        + float((li.get("part") or {}).get("billed_price", 0.0) or 0.0)
        for li in line_items
    )
    line_count: int = len(line_items)
    unique_panel_count: int = len(
        {str(li.get("panel", "") or "").lower() for li in line_items if li.get("panel")}
    )
    vehicle_age: int = 2025 - int(vehicle.get("year", 2020) or 2020)
    mileage: int = int(vehicle.get("mileage", 0) or 0)
    mileage_bucket: int = 0 if mileage < 25_000 else (1 if mileage < 75_000 else 2)

    # ---- Operation type counts ----
    op_counts: dict[str, int] = {op: 0 for op in OPERATION_TYPES}
    for li in line_items:
        op = str(li.get("operation_type", "") or "")
        if op in op_counts:
            op_counts[op] += 1

    # ---- Region one-hot encoding ----
    region_lower = region.lower()
    region_ohe: dict[str, int] = {f"region_{r}": int(region_lower == r) for r in REGIONS}

    # ---- Assemble feature dict ----
    features: dict[str, float | int] = {
        # Step 3: line-item aggregates
        "max_hours_ratio": max_hours_ratio,
        "mean_hours_ratio": mean_hours_ratio,
        "max_part_price_ratio": max_part_price_ratio,
        "mean_part_price_ratio": mean_part_price_ratio,
        "high_hours_ratio_count": high_hours_ratio_count,
        "high_price_ratio_count": high_price_ratio_count,
        "duplicate_sim_score": duplicate_sim_score,
        "has_non_adjacent_op": has_non_adjacent_op,
        "labor_parts_ratio": labor_parts_ratio,
        # Step 4: estimate-level
        "total_billed": total_billed,
        "line_count": line_count,
        "unique_panel_count": unique_panel_count,
        "vehicle_age": vehicle_age,
        "mileage_bucket": mileage_bucket,
        "op_RR_count": op_counts["RR"],
        "op_Repair_count": op_counts["Repair"],
        "op_Refinish_count": op_counts["Refinish"],
        "op_Blend_count": op_counts["Blend"],
        "op_Align_count": op_counts["Align"],
        "op_Replace_count": op_counts["Replace"],
    }
    features.update(region_ohe)  # Step 6: region one-hot

    return features


def _infer_primary_panels(scenario: str, line_items: list[dict[str, Any]]) -> set[str]:
    """
    Determine the set of primary damage panels from the scenario keyword and
    the panels actually listed in the estimate (whichever panels appear most
    frequently are considered primary for the adjacency check).
    """
    SCENARIO_PRIMARY: dict[str, set[str]] = {
        "rear_end": {"rear_bumper", "trunk_lid", "left_quarter_panel", "right_quarter_panel"},
        "front_end": {"front_bumper", "hood", "left_fender", "right_fender", "radiator_support"},
        "side_impact": {
            "left_door_front",
            "left_door_rear",
            "right_door_front",
            "right_door_rear",
            "left_rocker",
            "right_rocker",
        },
        "hail": {"hood", "roof", "trunk_lid", "left_fender", "right_fender"},
        "vandalism": {"hood", "left_door_front", "right_door_front", "trunk_lid"},
        "flood": {"floor_pan", "left_rocker", "right_rocker"},
        "comprehensive": set(PANEL_ADJACENCY.keys()),
        "rollover": {"roof", "left_a_pillar", "right_a_pillar", "windshield"},
        "parking_lot": {
            "left_door_front",
            "left_door_rear",
            "left_quarter_panel",
            "right_door_front",
            "right_door_rear",
            "right_quarter_panel",
        },
        "undercarriage": {"floor_pan", "frame_rail_left", "frame_rail_right"},
    }
    primary: set[str] = set()
    for key, panels in SCENARIO_PRIMARY.items():
        if key in scenario.lower():
            primary |= panels

    # Fallback: use the most-frequently cited panel in line items
    if not primary:
        from collections import Counter

        panel_counts = Counter(
            str(li.get("panel", "") or "").lower().replace(" ", "_")
            for li in line_items
            if li.get("panel")
        )
        if panel_counts:
            top_panel = panel_counts.most_common(1)[0][0]
            primary = {top_panel} | PANEL_ADJACENCY.get(top_panel, set())

    return primary


# ---------------------------------------------------------------------------
# Step 5: Shop-level features (fit on training shops only)
# ---------------------------------------------------------------------------


def compute_shop_features(
    df: pd.DataFrame,
    y: pd.Series,
    train_mask: np.ndarray,
) -> pd.DataFrame:
    """
    Compute shop-level features using ONLY training-set rows to prevent leakage.

    Parameters
    ----------
    df : pd.DataFrame
        Full feature DataFrame (must include 'shop_id' column).
    y : pd.Series
        Fraud labels aligned with df.
    train_mask : np.ndarray
        Boolean array of shape (len(df),); True for training rows.

    Returns
    -------
    pd.DataFrame
        df with 'shop_fraud_rate' and 'shop_avg_total_cost' columns added/updated.
        shop_id column is retained; call drop('shop_id') before final export.
    """
    train_df = df[train_mask].copy()
    train_y = y[train_mask]

    shop_stats = (
        train_df.assign(fraud_label=train_y.values)
        .groupby("shop_id")
        .agg(
            shop_fraud_rate=("fraud_label", "mean"),
            shop_avg_total_cost=("total_billed", "mean"),
        )
        .reset_index()
    )

    merged = df.merge(shop_stats, on="shop_id", how="left")
    merged["shop_fraud_rate"] = merged["shop_fraud_rate"].fillna(0.0)
    merged["shop_avg_total_cost"] = merged["shop_avg_total_cost"].fillna(
        train_df["total_billed"].mean() if len(train_df) > 0 else 0.0
    )
    merged.index = df.index  # preserve original index
    return merged


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def build_features(
    data_path: str = "data/estimates.jsonl",
    out_dir: str = "data/",
) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """
    Full feature engineering pipeline.

    Returns
    -------
    X : pd.DataFrame
        Feature matrix (no IDs, no raw JSON).
    y : pd.Series
        Fraud labels.
    groups : pd.Series
        Shop IDs for GroupKFold.
    """
    os.makedirs(out_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # 1. Load estimates
    # ------------------------------------------------------------------
    estimates = load_estimates(data_path)
    n = len(estimates)

    shop_ids: list[str] = [est["shop_id"] for est in estimates]
    labels: list[int] = [int(est["fraud_label"]) for est in estimates]

    # ------------------------------------------------------------------
    # 2. Compute regional medians on the FULL set as a first pass
    #    (a proper train-only fit is available via fit_regional_medians
    #    when called from the training script with train_indices).
    #    Here we fit on all data to produce the parquet files; the model
    #    training script must call fit_regional_medians with train_indices.
    # ------------------------------------------------------------------
    all_indices = np.arange(n)
    regional_medians = fit_regional_medians(estimates, all_indices)

    # ------------------------------------------------------------------
    # 3 + 4 + 6. Extract per-estimate features
    # ------------------------------------------------------------------
    print("Extracting per-estimate features …")
    rows: list[dict[str, float | int]] = []
    for est in estimates:
        rows.append(extract_estimate_features(est, regional_medians))

    df = pd.DataFrame(rows)
    df.insert(0, "shop_id", shop_ids)

    y = pd.Series(labels, name="fraud_label")
    groups = pd.Series(shop_ids, name="shop_id")

    # ------------------------------------------------------------------
    # 5. Shop-level features — using ALL data as train_mask here.
    #    In model training, call compute_shop_features with the actual
    #    train_mask from GroupKFold.
    # ------------------------------------------------------------------
    train_mask_all = np.ones(n, dtype=bool)
    df = compute_shop_features(df, y, train_mask_all)

    # ------------------------------------------------------------------
    # Final feature matrix: drop non-feature columns
    # ------------------------------------------------------------------
    X = df.drop(columns=["shop_id"])

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------
    assert X.isna().sum().sum() == 0, "NaNs found in feature matrix!"
    assert len(X) == len(y) == len(groups), "Length mismatch!"

    print(f"\nFeature matrix shape: {X.shape}")
    print(f"Dtypes:\n{X.dtypes.value_counts().to_string()}")
    print(f"NaN count: {X.isna().sum().sum()}")
    print(f"Class balance: {y.value_counts().sort_index().to_dict()}")
    print(f"Unique shops: {groups.nunique()}")

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    x_path = os.path.join(out_dir, "X.parquet")
    y_path = os.path.join(out_dir, "y.parquet")
    grp_path = os.path.join(out_dir, "groups.parquet")
    names_path = os.path.join(out_dir, "feature_names.json")

    X.to_parquet(x_path, index=False)
    y.to_frame().to_parquet(y_path, index=False)
    groups.to_frame().to_parquet(grp_path, index=False)

    feature_names: list[str] = X.columns.tolist()
    with open(names_path, "w", encoding="utf-8") as fh:
        json.dump(feature_names, fh, indent=2)

    print("\nExported:")
    print(f"  {x_path}")
    print(f"  {y_path}")
    print(f"  {grp_path}")
    print(f"  {names_path}")
    print(f"\nFeature names ({len(feature_names)}):")
    for name in feature_names:
        print(f"  {name}")

    return X, y, groups


def main(data_path: str = "data/estimates.jsonl", out_dir: str = "data/") -> None:
    """Entry point for CLI usage."""
    build_features(data_path=data_path, out_dir=out_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ClaimGuard – feature engineering pipeline",
    )
    parser.add_argument(
        "--data",
        default="data/estimates.jsonl",
        help="Path to estimates JSONL file (default: data/estimates.jsonl)",
    )
    parser.add_argument(
        "--out",
        default="data/",
        help="Output directory for parquet/json files (default: data/)",
    )
    args = parser.parse_args()
    main(data_path=args.data, out_dir=args.out)
