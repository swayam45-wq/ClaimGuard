# data_gen

Synthetic estimate data pipeline for ClaimGuard.

Generates CIECA BMS-inspired auto repair estimates with ground-truth fraud labels.

## Files

- `pricing.py` — OEM part price tables, labor rates, book hours by (vehicle class × panel × operation), regional multipliers, trim feature map
- `scenarios.py` — 6 damage scenario templates (rear-end, front impact, side-swipe, hail, minor scrape, parking lot)
- `generator.py` — Builds clean estimates from scenarios + a 500-shop pool
- `fraud_injector.py` — Injects 6 fraud patterns with per-line ground-truth labels
- `run.py` — CLI to generate JSONL output

## Usage

```bash
pip install -r requirements.txt
python run.py --n 50000 --fraud-rate 0.10 --out ../data/ --seed 42
```

## Output

- `data/estimates.jsonl` — one JSON estimate per line
- `data/summary.json` — stats: fraud rate, pattern distribution, region/class breakdown

## Fraud Patterns

1. `inflated_labor_hours` — billed = 1.5–2.5× book hours
2. `part_price_markup` — billed price 25–60% above regional median
3. `duplicate_line_items` — cloned operation with reworded description
4. `unnecessary_operations` — blend/refinish on non-adjacent panel
5. `phantom_parts` — part incompatible with vehicle trim
6. `labor_parts_mismatch` — high hours (7–10h) with trivial part
