# ClaimGuard

**AI-powered fraud detection for auto repair estimates in the P&C insurance economy.**

ClaimGuard detects fraudulent and inflated line items in auto repair estimates using a trained XGBoost classifier with SHAP explainability. It is modeled on the real-world domain of [CCC Intelligent Solutions](https://www.cccis.com) and the CIECA BMS electronic data standard.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         ClaimGuard Monorepo                             │
│                                                                         │
│  data_gen/          features/         models/          api/             │
│  ┌──────────┐       ┌──────────┐      ┌──────────┐    ┌──────────────┐ │
│  │ Synthetic│──────▶│ Feature  │─────▶│ XGBoost  │───▶│   FastAPI    │ │
│  │ Pipeline │       │ Engineer │      │  +SHAP   │    │  :8000       │ │
│  │ 50k est. │       │ 25 feats │      │ PR-AUC 0.97  │    │  /predict    │ │
│  └──────────┘       └──────────┘      └──────────┘    └──────┬───────┘ │
│       6 fraud                                                 │         │
│       patterns                                       ┌────────▼───────┐ │
│                                                      │   Next.js 14   │ │
│                                                      │   :3000        │ │
│                                                      │   /  /results  │ │
│                                                      │   /metrics     │ │
│                                                      └────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                     Docker Compose (api + web)
```

---

## Quick Start

### Prerequisites
- Docker Desktop
- Python 3.11+ (for local training)
- Node.js 20+ (for local frontend dev)

### 1. Clone & configure

```bash
git clone https://github.com/patelswayam88/ClaimGuard.git
cd ClaimGuard
cp .env.example .env            # edit if needed
cp api/.env.example api/.env
cp web/.env.example web/.env
```

### 2. Generate synthetic data & train the model

```bash
# Install data_gen deps
pip install -r data_gen/requirements.txt

# Generate 50,000 synthetic estimates (10% fraud rate)
cd data_gen
python run.py --n 50000 --fraud-rate 0.10 --out ../data/ --seed 42
cd ..

# Build feature matrix
pip install -r features/requirements.txt
python features/build.py --data data/estimates.jsonl --out data/

# Train XGBoost model (GroupKFold by shop_id)
pip install -r models/requirements.txt
python models/train.py --data data/ --artifacts models/artifacts/

# Evaluate & generate plots
python models/evaluate.py --data data/ --artifacts models/artifacts/ --out eval/outputs/
```

### 3. Run with Docker Compose

```bash
docker compose up --build
```

- API: http://localhost:8000
- Dashboard: http://localhost:3000
- API docs: http://localhost:8000/docs

---

## Repository Structure

```
ClaimGuard/
├── docker-compose.yml
├── README.md
├── data_gen/
│   ├── requirements.txt
│   ├── pricing.py          # CIECA BMS-inspired parts/labor price tables
│   ├── scenarios.py        # Damage scenario templates
│   ├── generator.py        # Clean estimate builder
│   ├── fraud_injector.py   # 6-pattern fraud injection with ground-truth labels
│   └── run.py              # CLI: python run.py --n 50000 --fraud-rate 0.10
├── features/
│   ├── requirements.txt
│   └── build.py            # Feature engineering (25 features, GroupKFold-safe)
├── models/
│   ├── requirements.txt
│   ├── train.py            # XGBoost + GroupKFold grid search
│   ├── evaluate.py         # Precision/recall, PR curves, confusion matrix
│   └── artifacts/          # model.json, shap_explainer.pkl (gitignored)
├── api/
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── main.py             # FastAPI: /predict, /predict/batch, /health, /model-info
│   └── schemas.py          # Pydantic v2 request/response models
├── web/
│   ├── Dockerfile
│   ├── app/                # Next.js App Router pages
│   │   ├── page.tsx        # / — estimate intake
│   │   ├── results/[id]/   # /results — verdict + line table
│   │   └── metrics/        # /metrics — PR curve, confusion matrix, SHAP
│   └── components/         # VerdictBanner, FlaggedLine, ConfidenceBar
├── eval/
│   ├── report.py           # Generates metrics + SHAP plots, patches README
│   └── outputs/            # PNG outputs (gitignored)
└── tests/
    └── test_pipeline.py    # End-to-end: generate → featurize → predict
```

---

## API Reference

### POST /predict

Submit one estimate for fraud analysis.

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "estimate_id": "EST-DEMO-001",
    "shop_id": "SHOP-042",
    "region": "midwest",
    "vehicle": {"year": 2021, "make": "Honda", "model": "Civic", "trim": "EX", "mileage": 45000, "class": "compact"},
    "scenario": "rear_end",
    "line_items": [
      {
        "line_id": 1,
        "operation": "R&R",
        "panel": "rear_bumper",
        "description": "R&R rear bumper cover",
        "part": {"name": "bumper cover", "oem_price": 285.00, "billed_price": 285.00, "source": "OEM"},
        "labor_hours_billed": 9.5,
        "labor_hours_book": 2.5,
        "labor_rate": 78.00
      }
    ]
  }'
```

**Response:**
```json
{
  "estimate_id": "EST-DEMO-001",
  "fraud_probability": 0.923,
  "is_fraud": true,
  "fraud_label": "fraudulent",
  "flagged_lines": [
    {
      "line_id": 1,
      "fraud_types": ["inflated_labor_hours"],
      "confidence": 0.91,
      "explanation": "Labor hours billed (9.5h) are 3.8× the book rate (2.5h) for this operation."
    }
  ],
  "processing_time_ms": 18.4
}
```

### POST /predict/batch

Submit up to 500 estimates in one call.

```bash
curl -X POST http://localhost:8000/predict/batch \
  -H "Content-Type: application/json" \
  -d '[<estimate1>, <estimate2>, ...]'
```

### GET /health

```bash
curl http://localhost:8000/health
# {"status":"ok","model_loaded":true,"version":"1.0.0"}
```

### GET /model-info

```bash
curl http://localhost:8000/model-info
```

---

## Fraud Taxonomy

ClaimGuard detects six fraud patterns (implemented in `data_gen/fraud_injector.py`):

| # | Pattern | Description |
|---|---------|-------------|
| 1 | **Inflated Labor Hours** | Billed hours = 1.5×–2.5× book hours |
| 2 | **Part Price Markup** | Billed part price exceeds regional median by 25–60% |
| 3 | **Duplicate Line Items** | Cloned operation with slightly reworded description |
| 4 | **Unnecessary Operations** | Blend/refinish on panels not adjacent to damage |
| 5 | **Phantom Parts** | Parts incompatible with vehicle trim |
| 6 | **Labor/Parts Mismatch** | High labor hours with trivial part (e.g. mirror cap) |

---

## Feature Engineering

25 features per estimate (see `features/build.py`):

**Line-item aggregates:**
- `max_hours_ratio`, `mean_hours_ratio` — billed vs. book hours
- `max_part_price_ratio`, `mean_part_price_ratio` — billed vs. OEM price
- `high_hours_ratio_count`, `high_price_ratio_count`
- `duplicate_sim_score` — max pairwise RapidFuzz similarity across line descriptions
- `has_non_adjacent_op` — operation on non-adjacent panel flag
- `labor_parts_ratio` — total labor hours / total parts cost

**Estimate-level:**
- `total_billed`, `line_count`, `unique_panel_count`
- `vehicle_age`, `mileage_bucket`
- `op_*_count` (6 operation types)
- `region_*` (5 one-hot region columns)

**Shop-level (training only):**
- `shop_fraud_rate` — historical fraud rate (fitted on training shops only)
- `shop_avg_total_cost`

> **Leakage prevention:** Shop-level features are fitted exclusively on training-fold shops in each GroupKFold split. Test shops never influence training statistics.

---

## Model Card

### Training Data
- **Source:** 100% synthetic (see Synthetic Data section)
- **Size:** 50,000 estimates, 500 unique shops, 6 scenario types
- **Fraud rate:** 10% (5,000 fraudulent estimates)
- **Fraud patterns:** All 6 patterns represented
- **Regions:** northeast, southeast, midwest, southwest, west (balanced)
- **Vehicle classes:** compact, mid-size, luxury, truck, SUV

### Model
- **Algorithm:** XGBoost binary classifier
- **Split strategy:** GroupKFold (n_splits=5) by shop_id — no shop leaks across folds
- **Hyperparameter search:** Grid over max_depth ∈ {4,6,8}, learning_rate ∈ {0.05,0.1}, n_estimators ∈ {200,400}, subsample ∈ {0.8,1.0}
- **Class imbalance:** Handled via `scale_pos_weight = neg_count / pos_count`
- **Explainability:** SHAP TreeExplainer, per-estimate values, top-feature explanations

### Target Metrics (on held-out shops)

<!-- METRICS_START -->
### Latest Model Metrics (auto-generated 2026-11-01)

| Metric | Value |
|--------|-------|
| Precision | 1.000 |
| Recall | 0.966 |
| F1 Score | 0.983 |
| PR-AUC | 0.983 |
| Threshold | 0.5 |
<!-- METRICS_END -->

### Limitations

1. **Synthetic data only.** The training data is procedurally generated. No real claims data was used. Model performance on actual insurance claims will differ significantly and requires re-calibration on real data.
2. **No temporal dynamics.** The synthetic data has no time dimension. Real fraud evolves; the model would need periodic retraining.
3. **No claims history.** Real fraud detection leverages multi-claim shop/claimant history. This model only sees one estimate at a time.
4. **Threshold sensitivity.** The default threshold (0.5) is a reasonable starting point but should be calibrated to the cost ratio of false positives vs. false negatives in a real deployment.
5. **Region generalization.** Part prices and labor rates use simplified regional tables. Real-world variance within regions is much higher.
6. **No OCR or photo analysis.** Real solutions like CCC Smart Estimate use computer vision on damage photos. This system only processes structured JSON estimates.

---

## Synthetic Data Methodology

The data pipeline (`data_gen/`) works in three stages:

### 1. Pricing Tables (`pricing.py`)
CIECA BMS-inspired price tables define realistic OEM part prices and book hours for each combination of (vehicle class × panel × operation). Regional multipliers reflect real cost-of-living differences. All values are illustrative approximations based on public collision repair data, not licensed CCC data.

### 2. Clean Estimate Generation (`generator.py`)
Each estimate is drawn from one of 6 damage scenarios (rear-end, front impact, side-swipe, hail, minor scrape, parking lot). A vehicle (year 2018–2024, 5 classes, realistic makes/models/trims) is assigned to a shop. Book hours and OEM prices are pulled from the pricing tables with ±15% and ±10% noise respectively to simulate natural variation.

### 3. Fraud Injection (`fraud_injector.py`)
10% of estimates are randomly selected for fraud. 1–3 fraud patterns are randomly applied. Each injected fraud records `fraud_flag=1` on the affected line item(s) and logs the pattern name in `fraud_types` on the estimate. Ground-truth labels are deterministic and reproducible via the `--seed` parameter.

### Limitations of the Synthetic Data
- Vehicle makes/models are real but prices are approximated
- Fraud patterns are simpler than real-world fraud (no collusion, no staged accidents)
- Shop behavior is random, not modeled on real shop behavioral patterns
- No claim lifecycle data (supplements, re-inspections, approvals)

---

## Running Tests

```bash
pip install pytest
cd ClaimGuard

# Unit + schema tests (no server needed)
pytest tests/test_pipeline.py -v -k "not Integration"

# Integration tests (requires running API)
API_URL=http://localhost:8000 pytest tests/test_pipeline.py -v -k "Integration"

# All tests
pytest tests/ -v
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ARTIFACTS_DIR` | `models/artifacts` | Path to model artifacts (api) |
| `PORT` | `8000` | API server port |
| `FRAUD_THRESHOLD` | `0.5` | Probability threshold for is_fraud |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | API URL for frontend |

---

## References

- [CCC Intelligent Solutions](https://www.cccis.com) — Cloud platform for the P&C insurance economy
- [CCC Secure Share Developer Program](https://www.cccsecureshare.com/Developers) — RESTful API network for third-party repair/insurance apps
- [CCC Secure Share FAQ](https://www.cccsecureshare.com/Faq) — API model, CIECA BMS standard documentation
- [CCC Intelligent Estimating (PDF)](https://cdn.prod.website-files.com/699ddfbb66862c762774fcbf/699ddfbb66862c762775008a_90b79736741e823235a82af5e97ab686_Intelligent%20Estimating.pdf) — CCC ONE Estimate, Smart Estimate, Quick Estimate REST API, Mobile Appraiser Pro
- [CIECA](https://www.cieca.com) — Collision Industry Electronic Commerce Association, maintainers of the BMS (Business Message Suite) standard referenced by CCC Secure Share
- [ShopAutomate](https://www.shopautomate.ai/support.html) — Example third-party app built on CCC Secure Share

---

## License

This is a portfolio project for educational and demonstration purposes. Not affiliated with or endorsed by CCC Intelligent Solutions, Inc. or CIECA. All pricing data is synthetic and approximated.
