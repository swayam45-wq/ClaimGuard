# features

Feature engineering pipeline for ClaimGuard.

Reads `data/estimates.jsonl` and produces a feature matrix suitable for XGBoost training.

## Usage

```bash
pip install -r requirements.txt
python build.py --data ../data/estimates.jsonl --out ../data/
```

## Output

- `data/X.parquet` — 25-column feature matrix
- `data/y.parquet` — binary fraud labels
- `data/groups.parquet` — shop_id for GroupKFold
- `data/feature_names.json` — ordered feature list

## Critical: Shop Leakage Prevention

Shop-level features (`shop_fraud_rate`, `shop_avg_total_cost`) are computed **only from training-fold shops** via `compute_shop_features(df, y, train_mask)`. Test shops never influence training statistics.
