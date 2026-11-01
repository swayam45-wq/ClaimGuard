"""
ClaimGuard Model Evaluation

Generates:
- Confusion matrix (raw + normalized)
- Precision/Recall/F1/PR-AUC on held-out shops
- Per-fraud-type recall table
- SHAP feature importance bar chart (top 20 features)

All outputs saved to models/artifacts/ and eval/outputs/
"""

from __future__ import annotations

import argparse
import json
import warnings
from datetime import date
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # non-interactive backend — must come before pyplot import
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
import xgboost as xgb
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
)
from sklearn.model_selection import GroupKFold

warnings.filterwarnings("ignore", category=UserWarning)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FRAUD_TYPES: list[str] = [
    "inflated_labor_hours",
    "part_price_markup",
    "duplicate_line_items",
    "unnecessary_operations",
    "phantom_parts",
    "labor_parts_mismatch",
]

THRESHOLD: float = 0.5
N_SPLITS: int = 5  # Must match train.py to produce the same last fold


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------


def load_model(artifacts_dir: Path) -> xgb.Booster:
    """Load the trained XGBoost booster from model.json.

    Args:
        artifacts_dir: Directory containing model.json.

    Returns:
        Loaded XGBoost Booster.
    """
    model_path = artifacts_dir / "model.json"
    booster = xgb.Booster()
    booster.load_model(str(model_path))
    return booster


def load_data(data_dir: Path) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Load feature matrix, labels, and groups from parquet files.

    Args:
        data_dir: Directory containing X.parquet, y.parquet, groups.parquet.

    Returns:
        (X, y, groups) as (DataFrame, Series, Series).
    """
    X: pd.DataFrame = pd.read_parquet(data_dir / "X.parquet")
    y: pd.Series = pd.read_parquet(data_dir / "y.parquet").squeeze()
    groups: pd.Series = pd.read_parquet(data_dir / "groups.parquet").squeeze()
    return X, y, groups


def load_estimates(data_dir: Path) -> dict[Any, list[str]]:
    """Load estimates.jsonl and build a mapping of estimate_id → fraud_types list.

    If estimates.jsonl is absent, returns an empty dict (evaluation degrades
    gracefully — per-fraud-type table will show N/A rows).

    Args:
        data_dir: Directory containing estimates.jsonl.

    Returns:
        Dict mapping estimate_id to list of fraud type strings.
    """
    jsonl_path = data_dir / "estimates.jsonl"
    if not jsonl_path.exists():
        warnings.warn(
            f"estimates.jsonl not found at {jsonl_path}. "
            "Per-fraud-type recall will not be computed.",
            stacklevel=2,
        )
        return {}

    id_to_fraud_types: dict[Any, list[str]] = {}
    with open(jsonl_path, encoding="utf-8") as fh:
        for line_idx, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            record: dict[str, Any] = json.loads(line)
            estimate_id = record.get("estimate_id", record.get("id"))
            fraud_types: list[str] = record.get("fraud_types", [])
            id_to_fraud_types[line_idx] = fraud_types
            if estimate_id is not None:
                id_to_fraud_types[estimate_id] = fraud_types
    return id_to_fraud_types


def load_feature_names(artifacts_dir: Path) -> list[str]:
    """Load the ordered feature name list saved during training.

    Args:
        artifacts_dir: Directory containing feature_names.json.

    Returns:
        List of feature column name strings.
    """
    with open(artifacts_dir / "feature_names.json", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Test-set extraction (last GroupKFold split — deterministic)
# ---------------------------------------------------------------------------


def get_test_split(
    X: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series,
    n_splits: int = N_SPLITS,
) -> tuple[pd.DataFrame, pd.Series, pd.Series, np.ndarray, np.ndarray]:
    """Return the held-out data from the *last* GroupKFold split.

    Uses the same GroupKFold(n_splits) as train.py to guarantee the identical
    deterministic partition (GroupKFold is order-based, not random).

    Args:
        X: Full feature matrix.
        y: Full label series.
        groups: Shop-ID series.
        n_splits: Number of folds (must match train.py).

    Returns:
        (X_test, y_test, groups_test, train_idx, test_idx)
    """
    gkf = GroupKFold(n_splits=n_splits)
    splits = list(gkf.split(X, y, groups))
    train_idx, test_idx = splits[-1]  # last fold → held-out test set
    return (
        X.iloc[test_idx],
        y.iloc[test_idx],
        groups.iloc[test_idx],
        train_idx,
        test_idx,
    )


# ---------------------------------------------------------------------------
# Shop feature augmentation (mirrors train.py — must be identical)
# ---------------------------------------------------------------------------


def augment_with_shop_features(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    groups_train: pd.Series,
    groups_test: pd.Series,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Add shop_fraud_rate and shop_avg_total_cost computed on train shops only.

    Mirrors the logic in train.py:compute_shop_features to ensure the test
    features are built identically to how they were during training.

    Args:
        X_train:      Training fold features.
        y_train:      Training fold labels.
        X_test:       Test fold features.
        groups_train: Shop IDs for training fold.
        groups_test:  Shop IDs for test fold.

    Returns:
        (X_train_aug, X_test_aug) with shop aggregate columns appended.
    """
    shop_df = pd.DataFrame(
        {"shop_id": groups_train.values, "label": y_train.values},
        index=X_train.index,
    )
    cost_col = (
        "total_billed"
        if "total_billed" in X_train.columns
        else ("total_cost" if "total_cost" in X_train.columns else None)
    )
    if cost_col:
        shop_df["total_cost"] = X_train[cost_col].values

    agg: dict[str, str] = {"label": "mean"}
    if cost_col:
        agg["total_cost"] = "mean"

    shop_stats = (
        shop_df.groupby("shop_id")
        .agg(agg)
        .rename(columns={"label": "shop_fraud_rate", "total_cost": "shop_avg_total_cost"})
    )
    global_fraud_rate = float(y_train.mean())
    global_avg_cost = float(X_train[cost_col].mean()) if cost_col else 0.0

    def _augment(X: pd.DataFrame, grp: pd.Series) -> pd.DataFrame:
        X_aug = X.copy()
        shop_ids = grp.values if hasattr(grp, "values") else np.array(grp)
        X_aug["shop_fraud_rate"] = [
            shop_stats["shop_fraud_rate"].get(s, global_fraud_rate) for s in shop_ids
        ]
        if "shop_avg_total_cost" in shop_stats.columns:
            X_aug["shop_avg_total_cost"] = [
                shop_stats["shop_avg_total_cost"].get(s, global_avg_cost) for s in shop_ids
            ]
        else:
            X_aug["shop_avg_total_cost"] = global_avg_cost
        return X_aug

    return _augment(X_train, groups_train), _augment(X_test, groups_test)


# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------


def predict(
    booster: xgb.Booster,
    X_test: pd.DataFrame,
    feature_names: list[str],
) -> np.ndarray:
    """Run inference and return raw probability scores.

    Args:
        booster:       Trained XGBoost booster.
        X_test:        Test feature matrix (columns must match feature_names).
        feature_names: Ordered list of feature names from training.

    Returns:
        1-D numpy array of fraud probabilities.
    """
    # Align columns to training order; fill any missing with 0
    X_aligned = X_test.reindex(columns=feature_names, fill_value=0.0)
    dtest = xgb.DMatrix(X_aligned, feature_names=feature_names)
    return booster.predict(dtest)


# ---------------------------------------------------------------------------
# Metrics computation
# ---------------------------------------------------------------------------


def compute_metrics(
    y_true: pd.Series,
    y_prob: np.ndarray,
    threshold: float = THRESHOLD,
) -> dict[str, float]:
    """Compute classification metrics at a given decision threshold.

    Args:
        y_true:    Ground-truth binary labels.
        y_prob:    Predicted fraud probabilities.
        threshold: Decision threshold for binarising probabilities.

    Returns:
        Dict with keys: precision, recall, f1, pr_auc.
    """
    y_pred = (y_prob >= threshold).astype(int)
    return {
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "pr_auc": float(average_precision_score(y_true, y_prob)),
    }


# ---------------------------------------------------------------------------
# Per-fraud-type recall
# ---------------------------------------------------------------------------


def compute_per_fraud_type_recall(
    y_true: pd.Series,
    y_prob: np.ndarray,
    test_index: pd.Index,
    id_to_fraud_types: dict[Any, list[str]],
    threshold: float = THRESHOLD,
) -> dict[str, dict[str, Any]]:
    """Compute recall for each fraud type on the test set.

    For each fraud type, we select test estimates whose fraud_types list
    contains that type, then measure what fraction the model flagged.

    Args:
        y_true:            Ground-truth labels for test set.
        y_prob:            Predicted probabilities for test set.
        test_index:        Original DataFrame index of the test rows (estimate IDs).
        id_to_fraud_types: Mapping from estimate_id → list[str] of fraud type tags.
        threshold:         Decision threshold for binarising predictions.

    Returns:
        Dict mapping fraud_type → {"recall": float, "count": int}.
    """
    y_pred = (y_prob >= threshold).astype(int)
    results: dict[str, dict[str, Any]] = {}

    for fraud_type in FRAUD_TYPES:
        # Identify test samples whose estimate contains this fraud type
        mask = np.array(
            [fraud_type in id_to_fraud_types.get(idx, []) for idx in test_index],
            dtype=bool,
        )
        count = int(mask.sum())
        if count == 0:
            results[fraud_type] = {"recall": float("nan"), "count": 0}
            continue

        recall = float(recall_score(y_true.values[mask], y_pred[mask], zero_division=0))
        results[fraud_type] = {"recall": recall, "count": count}

    return results


# ---------------------------------------------------------------------------
# Plot helpers
# ---------------------------------------------------------------------------


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def save_confusion_matrix_plot(
    y_true: pd.Series,
    y_prob: np.ndarray,
    out_dir: Path,
    threshold: float = THRESHOLD,
) -> None:
    """Save confusion matrix plots (raw counts + normalised) side by side.

    Args:
        y_true:    Ground-truth binary labels.
        y_prob:    Predicted fraud probabilities.
        out_dir:   Output directory.
        threshold: Decision threshold.
    """
    _ensure_dir(out_dir)
    y_pred = (y_prob >= threshold).astype(int)
    cm = confusion_matrix(y_true, y_pred)
    cm_norm = cm.astype(float) / cm.sum(axis=1, keepdims=True)

    labels = ["Legit", "Fraud"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    for ax, matrix, title, fmt in [
        (axes[0], cm, "Confusion Matrix (Counts)", "d"),
        (axes[1], cm_norm, "Confusion Matrix (Normalised)", ".2f"),
    ]:
        im = ax.imshow(matrix, interpolation="nearest", cmap="Blues")
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        ax.set(
            title=title,
            xticks=[0, 1],
            yticks=[0, 1],
            xticklabels=labels,
            yticklabels=labels,
            xlabel="Predicted label",
            ylabel="True label",
        )
        thresh = matrix.max() / 2.0
        for i in range(2):
            for j in range(2):
                val = matrix[i, j]
                text = f"{val:{fmt}}" if fmt != "d" else f"{int(val):,}"
                ax.text(
                    j,
                    i,
                    text,
                    ha="center",
                    va="center",
                    color="white" if val > thresh else "black",
                    fontsize=13,
                )

    fig.suptitle(f"ClaimGuard — threshold = {threshold}", fontsize=14, y=1.02)
    fig.tight_layout()
    save_path = out_dir / "confusion_matrix.png"
    fig.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {save_path}")


def save_pr_curve_plot(
    y_true: pd.Series,
    y_prob: np.ndarray,
    pr_auc: float,
    out_dir: Path,
) -> None:
    """Save precision-recall curve plot.

    Args:
        y_true:  Ground-truth binary labels.
        y_prob:  Predicted fraud probabilities.
        pr_auc:  Pre-computed PR-AUC value for display.
        out_dir: Output directory.
    """
    _ensure_dir(out_dir)
    precision_vals, recall_vals, _ = precision_recall_curve(y_true, y_prob)

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(recall_vals, precision_vals, lw=2, color="steelblue", label=f"PR-AUC = {pr_auc:.3f}")
    ax.axhline(
        y=float(y_true.mean()),
        color="gray",
        linestyle="--",
        label=f"Baseline (fraud rate = {y_true.mean():.3f})",
    )
    ax.set(
        xlabel="Recall",
        ylabel="Precision",
        title="ClaimGuard — Precision-Recall Curve (held-out shops)",
        xlim=[0.0, 1.0],
        ylim=[0.0, 1.05],
    )
    ax.legend(loc="lower left")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    save_path = out_dir / "pr_curve.png"
    fig.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {save_path}")


def save_shap_importance_plot(
    booster: xgb.Booster,
    X_test_aug: pd.DataFrame,
    feature_names: list[str],
    out_dir: Path,
    max_display: int = 20,
) -> None:
    """Compute SHAP values and save a bar-chart feature importance plot.

    Args:
        booster:       Trained XGBoost booster.
        X_test_aug:    Augmented test features (same columns as training).
        feature_names: Feature names in training order.
        out_dir:       Output directory.
        max_display:   Number of top features to show.
    """
    _ensure_dir(out_dir)
    X_aligned = X_test_aug.reindex(columns=feature_names, fill_value=0.0)

    explainer = shap.TreeExplainer(booster)
    shap_values = explainer.shap_values(X_aligned)

    fig, ax = plt.subplots(figsize=(10, 7))
    shap.summary_plot(
        shap_values,
        X_aligned,
        plot_type="bar",
        max_display=max_display,
        show=False,
    )
    plt.title(f"SHAP Feature Importance — Top {max_display} Features", fontsize=13)
    plt.tight_layout()
    save_path = out_dir / "shap_importance.png"
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close("all")
    print(f"  Saved: {save_path}")


# ---------------------------------------------------------------------------
# Metrics JSON persistence
# ---------------------------------------------------------------------------


def save_metrics_json(
    metrics: dict[str, float],
    per_fraud_type: dict[str, dict[str, Any]],
    cm: np.ndarray,
    groups_test: pd.Series,
    artifacts_dir: Path,
) -> None:
    """Serialise all evaluation metrics to artifacts/metrics.json.

    Args:
        metrics:        Overall precision/recall/f1/pr_auc dict.
        per_fraud_type: Per-fraud-type recall/count dict.
        cm:             2×2 confusion matrix (numpy array).
        groups_test:    Shop IDs of the test set.
        artifacts_dir:  Directory to write metrics.json into.
    """
    _ensure_dir(artifacts_dir)
    meta_path = artifacts_dir / "training_metadata.json"
    cv_pr_auc = None
    if meta_path.exists():
        try:
            with open(meta_path, encoding="utf-8") as fh:
                meta = json.load(fh)
                cv_pr_auc = meta.get("cv_pr_auc_mean")
        except (OSError, json.JSONDecodeError) as err:
            warnings.warn(f"Failed to read training metadata: {err}", stacklevel=2)

    payload: dict[str, Any] = {
        "precision": round(metrics["precision"], 6),
        "recall": round(metrics["recall"], 6),
        "f1": round(metrics["f1"], 6),
        "pr_auc": round(metrics["pr_auc"], 6),
        "cv_pr_auc": round(cv_pr_auc, 6) if cv_pr_auc is not None else None,
        "per_fraud_type": {
            ft: {
                "recall": (
                    round(v["recall"], 6)
                    if not (isinstance(v["recall"], float) and np.isnan(v["recall"]))
                    else None
                ),
                "count": v["count"],
            }
            for ft, v in per_fraud_type.items()
        },
        "confusion_matrix": cm.tolist(),
        "threshold": THRESHOLD,
        "test_shop_count": int(groups_test.nunique()),
        "test_sample_count": len(groups_test),
        "eval_date": date.today().isoformat(),
    }
    out_path = artifacts_dir / "metrics.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    print(f"  Saved: {out_path}")


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def print_summary(
    metrics: dict[str, float],
    per_fraud_type: dict[str, dict[str, Any]],
    groups_test: pd.Series,
    y_test: pd.Series,
) -> None:
    """Print a human-readable evaluation summary to stdout.

    Args:
        metrics:        Overall metric dict.
        per_fraud_type: Per-fraud-type recall dict.
        groups_test:    Test set shop IDs.
        y_test:         Test set ground-truth labels.
    """
    print("\n" + "=" * 60)
    print("ClaimGuard — Evaluation Results")
    print("=" * 60)
    print(f"  Test shops : {groups_test.nunique():,}")
    print(f"  Test samples: {len(y_test):,}  (fraud rate: {y_test.mean() * 100:.1f}%)")
    print()
    print(f"  Precision : {metrics['precision']:.3f}")
    print(f"  Recall    : {metrics['recall']:.3f}")
    print(f"  F1        : {metrics['f1']:.3f}")
    print(f"  PR-AUC    : {metrics['pr_auc']:.3f}")
    print()

    # F1 guard
    if metrics["f1"] < 0.80:
        print(
            "  ⚠ WARNING: F1 is below 0.80 target "
            f"(got {metrics['f1']:.3f}). "
            "Consider re-training or reviewing feature engineering."
        )

    # Per-fraud-type table
    print(f"  {'Fraud Type':<30} | {'Recall':>7} | {'Count':>7}")
    print(f"  {'-' * 30}-+-{'-' * 7}-+-{'-' * 7}")
    for ft, vals in per_fraud_type.items():
        recall_str = f"{vals['recall']:.3f}" if vals["count"] > 0 else "  N/A "
        print(f"  {ft:<30} | {recall_str:>7} | {vals['count']:>7,}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate the ClaimGuard XGBoost fraud classifier."
    )
    parser.add_argument(
        "--data",
        type=str,
        default="data/",
        help="Directory containing X.parquet, y.parquet, groups.parquet, estimates.jsonl",
    )
    parser.add_argument(
        "--artifacts",
        type=str,
        default="models/artifacts/",
        help="Directory containing model.json and feature_names.json",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="eval/outputs/",
        help="Output directory for plots and metrics",
    )
    parser.add_argument(
        "--n-splits",
        type=int,
        default=N_SPLITS,
        help="GroupKFold splits — must match the value used during training",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=THRESHOLD,
        help="Decision threshold for binary classification (default: 0.5)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    data_dir = Path(args.data)
    artifacts_dir = Path(args.artifacts)
    out_dir = Path(args.out)
    threshold = args.threshold

    print("=" * 60)
    print("ClaimGuard XGBoost Fraud Classifier — Evaluation")
    print("=" * 60)

    # ---- Load assets -------------------------------------------------------
    print("\nLoading model and data…")
    booster = load_model(artifacts_dir)
    X, y, groups = load_data(data_dir)
    feature_names = load_feature_names(artifacts_dir)
    id_to_fraud_types = load_estimates(data_dir)
    print(f"  Full dataset: {len(X):,} samples, {X.shape[1]:,} features")

    # ---- Test split (last GroupKFold fold) ---------------------------------
    print(f"\nExtracting held-out test set (last of {args.n_splits} GroupKFold folds)…")
    X_test, y_test, groups_test, train_idx, test_idx = get_test_split(
        X, y, groups, n_splits=args.n_splits
    )
    X_train = X.iloc[train_idx]
    y_train = y.iloc[train_idx]
    groups_train = groups.iloc[train_idx]
    print(f"  Train: {len(X_train):,}  |  Test: {len(X_test):,}")

    # ---- Augment test features (leak-safe) ---------------------------------
    _, X_test_aug = augment_with_shop_features(X_train, y_train, X_test, groups_train, groups_test)

    # ---- Predict -----------------------------------------------------------
    print("\nRunning inference…")
    y_prob = predict(booster, X_test_aug, feature_names)

    # ---- Overall metrics ---------------------------------------------------
    metrics = compute_metrics(y_test, y_prob, threshold=threshold)

    # ---- Per-fraud-type recall ---------------------------------------------
    per_fraud_type = compute_per_fraud_type_recall(
        y_test, y_prob, X_test.index, id_to_fraud_types, threshold=threshold
    )

    # ---- Print summary -----------------------------------------------------
    print_summary(metrics, per_fraud_type, groups_test, y_test)

    # ---- Confusion matrix --------------------------------------------------
    y_pred = (y_prob >= threshold).astype(int)
    cm = confusion_matrix(y_test, y_pred)

    # ---- Save plots --------------------------------------------------------
    print("\nSaving plots…")
    save_confusion_matrix_plot(y_test, y_prob, out_dir, threshold=threshold)
    save_pr_curve_plot(y_test, y_prob, metrics["pr_auc"], out_dir)
    save_shap_importance_plot(booster, X_test_aug, feature_names, out_dir)

    # ---- Save metrics JSON -------------------------------------------------
    print("\nSaving metrics JSON…")
    save_metrics_json(metrics, per_fraud_type, cm, groups_test, artifacts_dir)

    print("\n" + "=" * 60)
    print("Evaluation complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
