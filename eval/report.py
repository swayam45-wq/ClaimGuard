"""
eval/report.py — ClaimGuard Evaluation Report Generator

Loads the trained model, runs it against the test split, generates all
metric outputs (confusion matrix, PR curve, SHAP importance), and patches
the README metrics section with up-to-date numbers.

Usage:
    python eval/report.py --data data/ --artifacts models/artifacts/ --out eval/outputs/
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent
DEFAULT_DATA = ROOT / "data"
DEFAULT_ARTIFACTS = ROOT / "models" / "artifacts"
DEFAULT_OUT = ROOT / "eval" / "outputs"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_artifacts(artifacts_dir: Path) -> tuple[xgb.Booster, list[str], dict, dict]:
    model = xgb.Booster()
    model.load_model(str(artifacts_dir / "model.json"))

    with open(artifacts_dir / "feature_names.json") as f:
        feature_names: list[str] = json.load(f)

    metadata: dict = {}
    meta_path = artifacts_dir / "training_metadata.json"
    if meta_path.exists():
        with open(meta_path) as f:
            metadata = json.load(f)

    metrics: dict = {}
    metrics_path = artifacts_dir / "metrics.json"
    if metrics_path.exists():
        with open(metrics_path) as f:
            metrics = json.load(f)

    return model, feature_names, metadata, metrics


def load_test_data(
    data_dir: Path, feature_names: list[str]
) -> tuple[pd.DataFrame, pd.Series, pd.Series, list[dict]]:
    X = pd.read_parquet(data_dir / "X.parquet")[feature_names]
    y = pd.read_parquet(data_dir / "y.parquet").squeeze()
    groups = pd.read_parquet(data_dir / "groups.parquet").squeeze()

    estimates: list[dict] = []
    jsonl_path = data_dir / "estimates.jsonl"
    if jsonl_path.exists():
        with open(jsonl_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    estimates.append(json.loads(line))

    return X, y, groups, estimates


def get_test_indices(groups: pd.Series, seed: int = 42) -> np.ndarray:
    """Reproduce the last-fold test split from training (deterministic)."""
    from sklearn.model_selection import GroupKFold

    gkf = GroupKFold(n_splits=5)
    splits = list(gkf.split(np.zeros(len(groups)), np.zeros(len(groups)), groups))
    _, test_idx = splits[-1]  # last fold = held-out test
    return test_idx


# ---------------------------------------------------------------------------
# Plot helpers
# ---------------------------------------------------------------------------


def plot_confusion_matrix(cm: np.ndarray, out_path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.patch.set_facecolor("#0f172a")

    labels = ["Clean", "Fraud"]

    for ax, data, title in [
        (axes[0], cm, "Raw Counts"),
        (axes[1], cm.astype(float) / cm.sum(axis=1, keepdims=True), "Normalized"),
    ]:
        ax.set_facecolor("#1e293b")
        ax.imshow(data, cmap="RdYlGn", vmin=0, vmax=1 if "Norm" in title else None)
        ax.set_xticks([0, 1])
        ax.set_yticks([0, 1])
        ax.set_xticklabels(labels, color="white")
        ax.set_yticklabels(labels, color="white")
        ax.set_xlabel("Predicted", color="white")
        ax.set_ylabel("Actual", color="white")
        ax.set_title(title, color="white")
        ax.tick_params(colors="white")
        for spine in ax.spines.values():
            spine.set_edgecolor("#334155")
        for i in range(2):
            for j in range(2):
                val = data[i, j]
                txt = f"{val:.2f}" if "Norm" in title else str(val)
                ax.text(
                    j,
                    i,
                    txt,
                    ha="center",
                    va="center",
                    color="white",
                    fontsize=14,
                    fontweight="bold",
                )

    plt.suptitle("ClaimGuard — Confusion Matrix", color="white", fontsize=14)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"  Saved: {out_path}")


def plot_pr_curve(y_test: np.ndarray, y_prob: np.ndarray, pr_auc: float, out_path: Path) -> None:
    precision, recall, _ = precision_recall_curve(y_test, y_prob)

    fig, ax = plt.subplots(figsize=(8, 6))
    fig.patch.set_facecolor("#0f172a")
    ax.set_facecolor("#1e293b")

    ax.plot(recall, precision, color="#3b5bdb", linewidth=2.5, label=f"PR-AUC = {pr_auc:.3f}")
    ax.axhline(
        y=y_test.mean(), color="#94a3b8", linestyle="--", linewidth=1, label="Baseline (class freq)"
    )
    ax.set_xlabel("Recall", color="white")
    ax.set_ylabel("Precision", color="white")
    ax.set_title("ClaimGuard — Precision-Recall Curve", color="white")
    ax.tick_params(colors="white")
    ax.legend(facecolor="#1e293b", labelcolor="white")
    for spine in ax.spines.values():
        spine.set_edgecolor("#334155")
    ax.set_xlim([0, 1])
    ax.set_ylim([0, 1.05])
    ax.grid(color="#334155", linewidth=0.5)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"  Saved: {out_path}")


def plot_shap_importance(
    model: xgb.Booster, X_test: pd.DataFrame, out_path: Path, top_n: int = 20
) -> None:
    try:
        import shap

        explainer = shap.TreeExplainer(model)
        sample = X_test.sample(min(500, len(X_test)), random_state=42)
        shap_values = explainer.shap_values(sample)
        mean_abs = np.abs(shap_values).mean(axis=0)
        importance_df = pd.DataFrame({"feature": X_test.columns, "importance": mean_abs})
        importance_df = importance_df.nlargest(top_n, "importance").sort_values("importance")

        fig, ax = plt.subplots(figsize=(10, max(6, top_n * 0.35)))
        fig.patch.set_facecolor("#0f172a")
        ax.set_facecolor("#1e293b")

        ax.barh(importance_df["feature"], importance_df["importance"], color="#3b5bdb")
        ax.set_xlabel("Mean |SHAP Value|", color="white")
        ax.set_title(f"ClaimGuard — Top {top_n} Feature Importances (SHAP)", color="white")
        ax.tick_params(colors="white")
        for spine in ax.spines.values():
            spine.set_edgecolor("#334155")
        ax.grid(axis="x", color="#334155", linewidth=0.5)

        plt.tight_layout()
        plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close()
        print(f"  Saved: {out_path}")
    except Exception as exc:
        print(f"  SHAP plot failed: {exc}")


def plot_per_fraud_type_recall(per_fraud_type: dict[str, dict], out_path: Path) -> None:
    if not per_fraud_type:
        print("  No per-fraud-type data available, skipping chart.")
        return

    names = list(per_fraud_type.keys())
    recalls = [per_fraud_type[n].get("recall", 0.0) for n in names]
    pretty = [n.replace("_", " ").title() for n in names]

    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor("#0f172a")
    ax.set_facecolor("#1e293b")

    colors = ["#2f9e44" if r >= 0.85 else "#f59f00" if r >= 0.70 else "#e03131" for r in recalls]
    ax.bar(pretty, recalls, color=colors)
    ax.set_ylabel("Recall", color="white")
    ax.set_title("ClaimGuard — Per-Fraud-Type Recall", color="white")
    ax.set_ylim([0, 1.1])
    ax.tick_params(colors="white")
    ax.tick_params(axis="x", rotation=25)
    for spine in ax.spines.values():
        spine.set_edgecolor("#334155")
    ax.axhline(y=0.85, color="#94a3b8", linestyle="--", linewidth=1, label="Target 0.85")
    ax.legend(facecolor="#1e293b", labelcolor="white")
    ax.grid(axis="y", color="#334155", linewidth=0.5)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"  Saved: {out_path}")


# ---------------------------------------------------------------------------
# Per-fraud-type recall computation
# ---------------------------------------------------------------------------

FRAUD_PATTERNS = [
    "inflated_labor_hours",
    "part_price_markup",
    "duplicate_line_items",
    "unnecessary_operations",
    "phantom_parts",
    "labor_parts_mismatch",
]


def compute_per_fraud_recall(
    test_indices: np.ndarray,
    estimates: list[dict],
    y_pred: np.ndarray,
) -> dict[str, dict]:
    results: dict[str, dict] = {}
    for pattern in FRAUD_PATTERNS:
        pattern_indices = [
            i
            for i in test_indices
            if i < len(estimates) and pattern in estimates[i].get("fraud_types", [])
        ]
        if not pattern_indices:
            results[pattern] = {"recall": 0.0, "count": 0}
            continue
        y_pred_pattern = y_pred[
            [list(test_indices).index(i) for i in pattern_indices if i in test_indices]
        ]
        recall = float(np.mean(y_pred_pattern)) if len(y_pred_pattern) > 0 else 0.0
        results[pattern] = {"recall": round(recall, 4), "count": len(pattern_indices)}
    return results


# ---------------------------------------------------------------------------
# README patcher
# ---------------------------------------------------------------------------

METRICS_MARKER_START = "<!-- METRICS_START -->"
METRICS_MARKER_END = "<!-- METRICS_END -->"


def patch_readme(metrics: dict, readme_path: Path) -> None:
    if not readme_path.exists():
        print("  README not found, skipping patch.")
        return

    content = readme_path.read_text(encoding="utf-8")
    block = f"""{METRICS_MARKER_START}
### Latest Model Metrics (auto-generated {datetime.now().strftime("%Y-%m-%d")})

| Metric | Value |
|--------|-------|
| Precision | {metrics.get("precision", "N/A"):.3f} |
| Recall | {metrics.get("recall", "N/A"):.3f} |
| F1 Score | {metrics.get("f1", "N/A"):.3f} |
| PR-AUC | {metrics.get("pr_auc", "N/A"):.3f} |
| Threshold | {metrics.get("threshold", 0.5)} |
{METRICS_MARKER_END}"""

    if METRICS_MARKER_START in content and METRICS_MARKER_END in content:
        start = content.index(METRICS_MARKER_START)
        end = content.index(METRICS_MARKER_END) + len(METRICS_MARKER_END)
        content = content[:start] + block + content[end:]
    else:
        content += f"\n\n{block}\n"

    readme_path.write_text(content, encoding="utf-8")
    print(f"  README patched: {readme_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate ClaimGuard evaluation report")
    parser.add_argument("--data", default=str(DEFAULT_DATA), help="Path to data directory")
    parser.add_argument(
        "--artifacts", default=str(DEFAULT_ARTIFACTS), help="Path to model artifacts"
    )
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output directory for plots")
    args = parser.parse_args()

    data_dir = Path(args.data)
    artifacts_dir = Path(args.artifacts)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("ClaimGuard — Evaluation Report")
    print("=" * 60)

    # Load
    print("\n[1/6] Loading model and artifacts...")
    model, feature_names, metadata, _ = load_artifacts(artifacts_dir)

    print("[2/6] Loading test data...")
    X, y, groups, estimates = load_test_data(data_dir, feature_names)

    test_idx = get_test_indices(groups)
    X_test = X.iloc[test_idx]
    y_test = y.iloc[test_idx].values

    # Predict
    print("[3/6] Running predictions...")
    dmatrix = xgb.DMatrix(X_test, feature_names=feature_names)
    y_prob = model.predict(dmatrix)
    threshold = float(os.getenv("FRAUD_THRESHOLD", "0.5"))
    y_pred = (y_prob >= threshold).astype(int)

    # Metrics
    print("[4/6] Computing metrics...")
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    pr_auc = average_precision_score(y_test, y_prob)
    cm = confusion_matrix(y_test, y_pred)
    per_fraud = compute_per_fraud_recall(test_idx, estimates, y_pred)

    print(f"\n  Precision : {precision:.4f}")
    print(f"  Recall    : {recall:.4f}")
    print(f"  F1        : {f1:.4f}")
    print(f"  PR-AUC    : {pr_auc:.4f}")

    print("\n  Per-fraud-type recall:")
    print(f"  {'Pattern':<30} {'Recall':>8} {'Count':>8}")
    print("  " + "-" * 50)
    for pattern, vals in per_fraud.items():
        print(f"  {pattern:<30} {vals['recall']:>8.3f} {vals['count']:>8}")

    if f1 < 0.80:
        print(f"\n  WARNING: F1={f1:.4f} is below 0.80 target. Consider retraining with more data.")
    else:
        print(f"\n  ✓ F1={f1:.4f} meets quality bar.")

    # Save metrics JSON
    metrics_out: dict = {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "pr_auc": round(pr_auc, 4),
        "threshold": threshold,
        "per_fraud_type": per_fraud,
        "confusion_matrix": cm.tolist(),
        "test_shop_count": int(groups.iloc[test_idx].nunique()),
        "test_sample_count": int(len(y_test)),
        "eval_date": datetime.now(UTC).strftime("%Y-%m-%d"),
    }
    metrics_path = artifacts_dir / "metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics_out, f, indent=2)
    print(f"\n  Saved metrics: {metrics_path}")

    # Plots
    print("\n[5/6] Generating plots...")
    plot_confusion_matrix(cm, out_dir / "confusion_matrix.png")
    plot_pr_curve(y_test, y_prob, pr_auc, out_dir / "pr_curve.png")
    plot_shap_importance(model, X_test, out_dir / "shap_importance.png")
    plot_per_fraud_type_recall(per_fraud, out_dir / "per_fraud_type_recall.png")

    # Patch README
    print("\n[6/6] Patching README...")
    patch_readme(metrics_out, ROOT / "README.md")

    print("\n" + "=" * 60)
    print("Report complete.")
    print(f"Plots saved to: {out_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
