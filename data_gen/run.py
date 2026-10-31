"""
run.py — CLI entrypoint for ClaimGuard synthetic data generation.

Usage:
    python run.py --n 50000 --fraud-rate 0.10 --out data/ --seed 42

Output:
    {out}/estimates.jsonl  — one JSON estimate per line
    {out}/summary.json     — statistics and sample fraudulent records
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Local imports — ensure data_gen directory is on sys.path so imports work
# whether run directly or as python data_gen/run.py
# ---------------------------------------------------------------------------
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from pricing import (
    PART_BASE_PRICES,
    REGIONAL_PART_MULTIPLIER,
    REGIONS,
    VEHICLE_CLASSES,
)
from scenarios import SCENARIOS, get_random_scenario
from generator import generate_estimate, get_shop_pool
from fraud_injector import (
    ALL_FRAUD_PATTERNS,
    inject_fraud,
    sample_fraud_patterns,
)


# ---------------------------------------------------------------------------
# Regional median computation
# ---------------------------------------------------------------------------

def compute_regional_medians() -> dict[str, dict[str, float]]:
    """
    Compute regional-median OEM prices for each (panel, vehicle_class) pair.

    Returns:  panel → vehicle_class → median price (float)

    We take the mean across all regions (weighted by regional multiplier) as a
    simple approximation for the "expected" price that a fraudster would exceed.
    """
    medians: dict[str, dict[str, float]] = {}
    for v_class, panels in PART_BASE_PRICES.items():
        for panel, base_price in panels.items():
            if panel not in medians:
                medians[panel] = {}
            # Mean of all regional adjusted prices
            regional_prices = [
                base_price * REGIONAL_PART_MULTIPLIER[r] for r in REGIONS
            ]
            medians[panel][v_class] = float(np.mean(regional_prices))
    return medians


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="run.py",
        description="Generate synthetic ClaimGuard auto-repair estimates.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """
            Examples:
              python run.py --n 50000 --fraud-rate 0.10 --out data/ --seed 42
              python run.py --n 1000  --fraud-rate 0.20 --out out/  --seed 7
            """
        ),
    )
    parser.add_argument(
        "--n",
        type=int,
        default=50_000,
        help="Total number of estimates to generate (default: 50000).",
    )
    parser.add_argument(
        "--fraud-rate",
        type=float,
        default=0.10,
        help="Fraction of estimates that are fraudulent (default: 0.10).",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="data/",
        help="Output directory (created if absent, default: data/).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42).",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Main generation loop
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    n: int                 = args.n
    fraud_rate: float      = args.fraud_rate
    out_dir: Path          = Path(args.out)
    seed: int              = args.seed

    if not 0.0 <= fraud_rate <= 1.0:
        print("ERROR: --fraud-rate must be between 0.0 and 1.0", file=sys.stderr)
        sys.exit(1)
    if n < 1:
        print("ERROR: --n must be at least 1", file=sys.stderr)
        sys.exit(1)

    out_dir.mkdir(parents=True, exist_ok=True)
    estimates_path: Path = out_dir / "estimates.jsonl"
    summary_path:   Path = out_dir / "summary.json"

    rng: np.random.Generator = np.random.default_rng(seed)
    shop_pool = get_shop_pool()                       # 500 shops
    regional_medians = compute_regional_medians()     # panel→class→median

    # -----------------------------------------------------------------------
    # Counters / accumulators for summary
    # -----------------------------------------------------------------------
    fraud_count:  int = 0
    clean_count:  int = 0
    pattern_counts: dict[str, int]       = {p: 0 for p in ALL_FRAUD_PATTERNS}
    region_dist:    dict[str, int]       = defaultdict(int)
    class_dist:     dict[str, int]       = defaultdict(int)
    sample_fraudulent: list[dict[str, Any]] = []

    t_start = time.monotonic()

    print(f"\n{'='*60}")
    print(f"  ClaimGuard — Synthetic Data Generator")
    print(f"{'='*60}")
    print(f"  n={n:,}  fraud_rate={fraud_rate:.1%}  seed={seed}")
    print(f"  Output → {estimates_path.resolve()}")
    print(f"{'='*60}\n")

    with open(estimates_path, "w", encoding="utf-8") as fh:
        for i in range(n):
            # --- Pick a shop ------------------------------------------------
            shop_idx: int         = int(rng.integers(0, len(shop_pool)))
            shop: dict[str, Any]  = shop_pool[shop_idx]
            region: str           = shop["region"]
            v_class: str          = shop["preferred_class"]

            # --- Pick a scenario --------------------------------------------
            scenario_idx: int = int(rng.integers(0, len(SCENARIOS)))
            scenario = SCENARIOS[scenario_idx]

            # --- Generate clean estimate ------------------------------------
            estimate_id: str = f"EST-{i + 1:06d}"
            est: dict[str, Any] = generate_estimate(
                estimate_id=estimate_id,
                shop_id=shop["shop_id"],
                region=region,
                vehicle_class=v_class,
                scenario=scenario,
                rng=rng,
            )

            # --- Inject fraud with probability fraud_rate -------------------
            is_fraud: bool = bool(rng.uniform(0.0, 1.0) < fraud_rate)
            if is_fraud:
                patterns: list[str] = sample_fraud_patterns(fraud_rate, rng)
                est = inject_fraud(est, patterns, rng, regional_medians)
                fraud_count += 1
                for p in patterns:
                    pattern_counts[p] = pattern_counts.get(p, 0) + 1
                if len(sample_fraudulent) < 3:
                    sample_fraudulent.append(est)
            else:
                clean_count += 1

            region_dist[region] += 1
            class_dist[v_class] += 1

            # --- Write JSONL ------------------------------------------------
            fh.write(json.dumps(est, default=str) + "\n")

            # Progress feedback every 5 000 records
            if (i + 1) % 5_000 == 0:
                elapsed = time.monotonic() - t_start
                rate    = (i + 1) / elapsed
                eta     = (n - (i + 1)) / rate if rate > 0 else 0
                print(
                    f"  [{i + 1:>8,} / {n:,}]  "
                    f"fraud={fraud_count:,}  "
                    f"elapsed={elapsed:.1f}s  "
                    f"ETA={eta:.0f}s"
                )

    elapsed_total = time.monotonic() - t_start
    fraud_rate_actual: float = fraud_count / n if n > 0 else 0.0

    # -----------------------------------------------------------------------
    # Write summary.json
    # -----------------------------------------------------------------------
    summary: dict[str, Any] = {
        "total_estimates":       n,
        "fraud_count":           fraud_count,
        "clean_count":           clean_count,
        "fraud_rate_actual":     round(fraud_rate_actual, 6),
        "pattern_counts":        pattern_counts,
        "region_distribution":   dict(region_dist),
        "vehicle_class_distribution": dict(class_dist),
        "sample_fraudulent":     sample_fraudulent,
        "generation_params": {
            "n":          n,
            "fraud_rate": fraud_rate,
            "seed":       seed,
            "out":        str(out_dir.resolve()),
        },
    }
    with open(summary_path, "w", encoding="utf-8") as sf:
        json.dump(summary, sf, indent=2, default=str)

    # -----------------------------------------------------------------------
    # Print summary table
    # -----------------------------------------------------------------------
    print(f"\n{'='*60}")
    print(f"  Generation complete in {elapsed_total:.1f}s")
    print(f"{'='*60}")
    print(f"  {'Total estimates':<28} {n:>10,}")
    print(f"  {'Fraud estimates':<28} {fraud_count:>10,}  ({fraud_rate_actual:.2%})")
    print(f"  {'Clean estimates':<28} {clean_count:>10,}")
    print()
    print(f"  {'Fraud pattern':<35} {'Count':>8}")
    print(f"  {'-'*44}")
    for pat, cnt in sorted(pattern_counts.items(), key=lambda x: -x[1]):
        print(f"  {pat:<35} {cnt:>8,}")
    print()
    print(f"  {'Region':<20} {'Count':>8}")
    print(f"  {'-'*29}")
    for reg, cnt in sorted(region_dist.items()):
        print(f"  {reg:<20} {cnt:>8,}")
    print()
    print(f"  {'Vehicle class':<20} {'Count':>8}")
    print(f"  {'-'*29}")
    for vc, cnt in sorted(class_dist.items()):
        print(f"  {vc:<20} {cnt:>8,}")
    print(f"{'='*60}")
    print(f"  Estimates  → {estimates_path.resolve()}")
    print(f"  Summary    → {summary_path.resolve()}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
