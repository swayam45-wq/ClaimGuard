"""
ClaimGuard XGBoost Fraud Classifier Training

Uses GroupKFold by shop_id to prevent data leakage.
Saves model JSON, SHAP explainer, and feature list to models/artifacts/.
"""

from __future__ import annotations

import argparse
import json
import pickle
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import shap
import xgboost as xgb
from sklearn.metrics import average_precision_score
from sklearn.model_selection import GroupKFold, ParameterGrid

warnings.filterwarnings("ignore", category=UserWarning)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_data(data_dir: str = "data/") -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Load feature matrix, labels, and group (shop_id) series from parquet files.

    Args:
        data_dir: Directory containing X.parquet, y.parquet, groups.parquet.

    Returns:
        Tuple of (X, y, groups) as (DataFrame, Series, Series).
    """
    data_path = Path(data_dir)
    X: pd.DataFrame = pd.read_parquet(data_path / "X.parquet")
    y: pd.Series = pd.read_parquet(data_path / "y.parquet").squeeze()
    groups: pd.Series = pd.read_parquet(data_path / "groups.parquet").squeeze()
    return X, y, groups


# ---------------------------------------------------------------------------
# Shop-level aggregate feature engineering (leak-safe)
# ---------------------------------------------------------------------------


def compute_shop_features(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_eval: pd.DataFrame,
    groups_train: pd.Series,
    groups_eval: pd.Series,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compute shop_fraud_rate and shop_avg_total_cost on training shops only,
    then left-join onto both train and eval sets to avoid leakage.

    Args:
        X_train: Feature matrix for training fold.
        y_train: Labels for training fold.
        X_eval:  Feature matrix for evaluation fold.
        groups_train: Shop IDs aligned with X_train / y_train.
        groups_eval:  Shop IDs aligned with X_eval.

    Returns:
        (X_train_aug, X_eval_aug) with two new columns appended.
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

    agg: dict[str, Any] = {"label": "mean"}
    if cost_col:
        agg["total_cost"] = "mean"

    shop_stats = (
        shop_df.groupby("shop_id")
        .agg(agg)
        .rename(columns={"label": "shop_fraud_rate", "total_cost": "shop_avg_total_cost"})
    )
    # Global fallbacks for unseen shops in eval
    global_fraud_rate: float = float(y_train.mean())
    global_avg_cost: float = float(X_train[cost_col].mean()) if cost_col else 0.0

    def _augment(X: pd.DataFrame, grp: pd.Series) -> pd.DataFrame:
        X_aug = X.copy()
        shop_series = grp.values if hasattr(grp, "values") else np.array(grp)
        fraud_rates = np.array(
            [shop_stats["shop_fraud_rate"].get(s, global_fraud_rate) for s in shop_series],
            dtype=np.float64,
        )
        X_aug["shop_fraud_rate"] = fraud_rates
        if "shop_avg_total_cost" in shop_stats.columns:
            avg_costs = np.array(
                [shop_stats["shop_avg_total_cost"].get(s, global_avg_cost) for s in shop_series],
                dtype=np.float64,
            )
        else:
            avg_costs = np.full(len(X_aug), global_avg_cost, dtype=np.float64)
        X_aug["shop_avg_total_cost"] = avg_costs
        return X_aug

    return _augment(X_train, groups_train), _augment(X_eval, groups_eval)


# ---------------------------------------------------------------------------
# Cross-validation
# ---------------------------------------------------------------------------

FIXED_PARAMS: dict[str, Any] = {
    "objective": "binary:logistic",
    "eval_metric": "aucpr",
    "tree_method": "hist",
    "random_state": 42,
    "verbosity": 0,
}

PARAM_GRID: dict[str, list[Any]] = {
    "max_depth": [4, 6, 8],
    "learning_rate": [0.05, 0.1],
    "n_estimators": [200, 400],
    "subsample": [0.8, 1.0],
}


def _train_single_fold(
    params: dict[str, Any],
    X_tr: pd.DataFrame,
    y_tr: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    scale_pos_weight: float,
) -> float:
    """Train one XGBoost model and return PR-AUC on validation fold."""
    full_params = {**FIXED_PARAMS, **params, "scale_pos_weight": scale_pos_weight}
    n_estimators: int = full_params.pop("n_estimators")

    dtrain = xgb.DMatrix(X_tr, label=y_tr, feature_names=list(X_tr.columns))
    dval = xgb.DMatrix(X_val, label=y_val, feature_names=list(X_val.columns))

    booster = xgb.train(
        params=full_params,
        dtrain=dtrain,
        num_boost_round=n_estimators,
        evals=[(dval, "val")],
        verbose_eval=False,
    )
    preds: np.ndarray = booster.predict(dval)
    return float(average_precision_score(y_val.values, preds))


def cross_validate(
    X: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series,
    n_splits: int = 5,
) -> tuple[dict[str, Any], list[float], list[tuple[np.ndarray, np.ndarray]]]:
    """Run GroupKFold CV over the full param grid.

    Args:
        X: Full feature matrix.
        y: Full label series.
        groups: Shop-ID series (same index as X and y).
        n_splits: Number of GroupKFold splits.

    Returns:
        Tuple of (best_params, best_fold_scores, cv_splits)
        where cv_splits is a list of (train_idx, val_idx) numpy arrays.
    """
    scale_pos_weight: float = float((y == 0).sum()) / float((y == 1).sum())
    gkf = GroupKFold(n_splits=n_splits)

    # Materialise all splits up-front so we can reuse them deterministically.
    cv_splits: list[tuple[np.ndarray, np.ndarray]] = list(gkf.split(X, y, groups))

    param_combinations = list(ParameterGrid(PARAM_GRID))
    print(f"Running CV over {len(param_combinations)} parameter combos × {n_splits} folds…")

    best_score: float = -1.0
    best_params: dict[str, Any] = param_combinations[0]
    best_fold_scores: list[float] = []

    for combo_idx, params in enumerate(param_combinations, start=1):
        fold_scores: list[float] = []
        for _fold_idx, (train_idx, val_idx) in enumerate(cv_splits):
            X_tr, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_tr, y_val = y.iloc[train_idx], y.iloc[val_idx]
            grp_tr, grp_val = groups.iloc[train_idx], groups.iloc[val_idx]

            X_tr_aug, X_val_aug = compute_shop_features(X_tr, y_tr, X_val, grp_tr, grp_val)

            score = _train_single_fold(params, X_tr_aug, y_tr, X_val_aug, y_val, scale_pos_weight)
            fold_scores.append(score)

        mean_score = float(np.mean(fold_scores))
        print(
            f"  [{combo_idx:>3}/{len(param_combinations)}] "
            f"params={params}  mean_PR-AUC={mean_score:.4f}"
        )
        if mean_score > best_score:
            best_score = mean_score
            best_params = dict(params)
            best_fold_scores = fold_scores

    return best_params, best_fold_scores, cv_splits


# ---------------------------------------------------------------------------
# Final model training
# ---------------------------------------------------------------------------


def train_final_model(
    X: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series,
    best_params: dict[str, Any],
) -> tuple[xgb.Booster, list[str]]:
    """Retrain best params on ALL data and return (booster, feature_names).

    Args:
        X: Full feature matrix (will have shop features added).
        y: Full label series.
        groups: Shop-ID series.
        best_params: Best hyperparameters from CV.

    Returns:
        Trained XGBoost Booster and the list of feature column names.
    """
    scale_pos_weight: float = float((y == 0).sum()) / float((y == 1).sum())

    # Compute shop features on the full dataset (no leakage concern on full train)
    X_aug, _ = compute_shop_features(X, y, X.iloc[:0], groups, groups.iloc[:0])
    feature_names: list[str] = list(X_aug.columns)

    full_params = {
        **FIXED_PARAMS,
        **best_params,
        "scale_pos_weight": scale_pos_weight,
    }
    n_estimators: int = full_params.pop("n_estimators")

    dtrain = xgb.DMatrix(X_aug, label=y, feature_names=feature_names)
    booster = xgb.train(
        params=full_params,
        dtrain=dtrain,
        num_boost_round=n_estimators,
        verbose_eval=False,
    )
    return booster, feature_names


# ---------------------------------------------------------------------------
# Artifact saving
# ---------------------------------------------------------------------------


def save_artifacts(
    booster: xgb.Booster,
    feature_names: list[str],
    best_params: dict[str, Any],
    fold_scores: list[float],
    y: pd.Series,
    artifacts_dir: str = "models/artifacts/",
) -> None:
    """Persist all training artifacts to disk.

    Args:
        booster:       Trained XGBoost booster.
        feature_names: Ordered list of feature column names used during training.
        best_params:   Best hyperparameters from CV.
        fold_scores:   Per-fold PR-AUC scores from best param set.
        y:             Full label series (to derive fraud rate).
        artifacts_dir: Output directory for artifacts.
    """
    out = Path(artifacts_dir)
    out.mkdir(parents=True, exist_ok=True)

    # 1. Model JSON
    model_path = out / "model.json"
    booster.save_model(str(model_path))

    # 2. SHAP explainer — build a DMatrix-compatible explainer
    explainer = shap.TreeExplainer(booster)
    explainer_path = out / "shap_explainer.pkl"
    with open(explainer_path, "wb") as fh:
        pickle.dump(explainer, fh, protocol=pickle.HIGHEST_PROTOCOL)

    # 3. Feature names JSON
    feature_path = out / "feature_names.json"
    with open(feature_path, "w", encoding="utf-8") as fh:
        json.dump(feature_names, fh, indent=2)

    # 4. Training metadata JSON
    mean_score = float(np.mean(fold_scores))
    std_score = float(np.std(fold_scores))
    metadata: dict[str, Any] = {
        "training_date": datetime.now(UTC).isoformat(),
        "best_params": best_params,
        "cv_pr_auc_mean": round(mean_score, 6),
        "cv_pr_auc_std": round(std_score, 6),
        "cv_fold_scores": [round(s, 6) for s in fold_scores],
        "n_train": int(len(y)),
        "fraud_rate": round(float(y.mean()), 6),
        "fixed_params": {k: v for k, v in FIXED_PARAMS.items() if k != "verbosity"},
    }
    metadata_path = out / "training_metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as fh:
        json.dump(metadata, fh, indent=2)

    print(f"\nArtifacts saved to {out}/")
    print(f"  {model_path.name}")
    print(f"  {explainer_path.name}")
    print(f"  {feature_path.name}")
    print(f"  {metadata_path.name}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train ClaimGuard XGBoost fraud classifier.")
    parser.add_argument(
        "--data",
        type=str,
        default="data/",
        help="Directory containing X.parquet, y.parquet, groups.parquet",
    )
    parser.add_argument(
        "--artifacts",
        type=str,
        default="models/artifacts/",
        help="Output directory for model artifacts",
    )
    parser.add_argument(
        "--n-splits",
        type=int,
        default=5,
        help="Number of GroupKFold splits (default: 5)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print("=" * 60)
    print("ClaimGuard XGBoost Fraud Classifier — Training")
    print("=" * 60)

    # ---- Load data -------------------------------------------------------
    print(f"\nLoading data from: {args.data}")
    X, y, groups = load_data(args.data)
    print(f"  Samples : {len(X):,}")
    print(f"  Features: {X.shape[1]:,}")
    print(f"  Fraud %  : {y.mean() * 100:.2f}%")
    print(f"  Shops   : {groups.nunique():,}")

    # ---- Cross-validation ------------------------------------------------
    print(f"\nRunning {args.n_splits}-fold GroupKFold CV…")
    best_params, fold_scores, cv_splits = cross_validate(X, y, groups, n_splits=args.n_splits)

    mean_pr_auc = float(np.mean(fold_scores))
    std_pr_auc = float(np.std(fold_scores))
    print(f"\nBest params: {best_params}")
    print(f"CV PR-AUC (OOF across folds): {mean_pr_auc:.4f} ± {std_pr_auc:.4f}")

    # ---- Final model training on held-out train split --------------------
    # Model is trained strictly on training shops (fold 1-4) with fold 5 held out
    train_idx, test_idx = cv_splits[-1]
    X_train, y_train, groups_train = X.iloc[train_idx], y.iloc[train_idx], groups.iloc[train_idx]
    print(
        f"\nTraining final model on training shops only "
        f"({len(X_train):,} estimates, {groups_train.nunique()} shops; "
        f"{len(test_idx):,} estimates held out)…",
        end=" ",
        flush=True,
    )
    booster, feature_names = train_final_model(X_train, y_train, groups_train, best_params)
    print("Done.")

    # ---- Save artifacts --------------------------------------------------
    save_artifacts(booster, feature_names, best_params, fold_scores, y_train, args.artifacts)

    print("\n" + "=" * 60)
    print("Training complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
