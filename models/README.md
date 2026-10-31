# models

XGBoost fraud classifier training and evaluation for ClaimGuard.

## Usage

```bash
pip install -r requirements.txt

# Train
python train.py --data ../data/ --artifacts artifacts/

# Evaluate
python evaluate.py --data ../data/ --artifacts artifacts/ --out ../eval/outputs/
```

## Artifacts (gitignored)

- `artifacts/model.json` — XGBoost booster (binary format)
- `artifacts/shap_explainer.pkl` — SHAP TreeExplainer
- `artifacts/feature_names.json` — ordered feature list
- `artifacts/training_metadata.json` — params, CV scores, training date
- `artifacts/metrics.json` — precision/recall/F1/PR-AUC + per-fraud-type recall

## Design

- **GroupKFold(n_splits=5)** by `shop_id` — shops never leak across train/test
- **scale_pos_weight** set from class balance to handle 10% fraud rate
- Grid search: 24 combinations of max_depth × learning_rate × n_estimators × subsample
- Target: F1 ≥ 0.85 on held-out shops
