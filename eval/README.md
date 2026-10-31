# eval

ClaimGuard evaluation reports and visual artifacts.

## Generating Reports

```bash
python eval/report.py --data data/ --artifacts models/artifacts/ --out eval/outputs/
```

This generates:
- `eval/outputs/confusion_matrix.png`
- `eval/outputs/pr_curve.png`
- `eval/outputs/shap_importance.png`
- `eval/outputs/per_fraud_type_recall.png`
- Updates the metric table in `README.md`
