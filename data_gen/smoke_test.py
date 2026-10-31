"""Quick smoke test for data_gen module."""
import sys
import os

# Ensure this directory is on the path
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np

# ---- pricing ----
from pricing import (
    PANELS, VEHICLE_CLASSES, REGIONS, LABOR_RATES,
    PART_BASE_PRICES, BOOK_HOURS, ADJACENT_PANELS,
    REGIONAL_PART_MULTIPLIER, TRIM_FEATURES, PHANTOM_PARTS,
    get_regional_part_price, get_book_hours,
)
assert len(PANELS) == 19, f"Expected 19 panels, got {len(PANELS)}"
assert set(VEHICLE_CLASSES) == {"compact", "mid_size", "luxury", "truck", "suv"}
assert set(REGIONS) == {"northeast", "southeast", "midwest", "southwest", "west"}
for vc in VEHICLE_CLASSES:
    assert set(PART_BASE_PRICES[vc].keys()) == set(PANELS), f"Missing panels for {vc}"
for op, panel_map in BOOK_HOURS.items():
    assert set(panel_map.keys()) == set(PANELS), f"Missing panels for operation {op}"
print("pricing        OK")

# ---- scenarios ----
from scenarios import SCENARIOS, get_random_scenario
assert len(SCENARIOS) == 6
names = [s.name for s in SCENARIOS]
expected_names = {"rear_end","front_impact","side_swipe","hail","minor_scrape","parking_lot"}
assert set(names) == expected_names, f"Got: {names}"
print("scenarios      OK — ", names)

# ---- generator ----
from generator import generate_estimate, get_shop_pool
shops = get_shop_pool()
assert len(shops) == 500
rng = np.random.default_rng(42)
est = generate_estimate("EST-000001", "SHOP-042", "midwest", "compact", SCENARIOS[0], rng)
required_keys = {"estimate_id","shop_id","region","vehicle","scenario","line_items","fraud_label","fraud_types"}
assert required_keys == set(est.keys()), f"Missing keys: {required_keys - set(est.keys())}"
assert est["fraud_label"] == 0
assert len(est["line_items"]) > 0
for li in est["line_items"]:
    for k in ("line_id","operation","panel","description","part","labor_hours_billed","labor_hours_book","labor_rate","fraud_flag","fraud_type"):
        assert k in li, f"line_item missing key: {k}"
print("generator      OK — estimate_id:", est["estimate_id"], "lines:", len(est["line_items"]))

# ---- fraud_injector ----
from fraud_injector import ALL_FRAUD_PATTERNS, inject_fraud, sample_fraud_patterns
assert len(ALL_FRAUD_PATTERNS) == 6
from pricing import PART_BASE_PRICES, REGIONAL_PART_MULTIPLIER
import numpy as np

regional_medians = {}
for vc, panels in PART_BASE_PRICES.items():
    for panel, base in panels.items():
        regional_medians.setdefault(panel, {})[vc] = base * 1.02

for pattern in ALL_FRAUD_PATTERNS:
    est2 = generate_estimate("EST-000002", "SHOP-001", "northeast", "luxury", SCENARIOS[1], rng)
    fraudulent = inject_fraud(est2, [pattern], rng, regional_medians)
    assert fraudulent["fraud_label"] == 1, f"fraud_label not set for {pattern}"
    assert pattern in fraudulent["fraud_types"]
    fraud_lines = [l for l in fraudulent["line_items"] if l["fraud_flag"] == 1]
    assert len(fraud_lines) >= 1, f"No fraud_flag=1 lines for pattern {pattern}"
    print(f"  fraud_injector [{pattern}] OK — {len(fraud_lines)} flagged line(s)")

print("\nAll smoke tests PASSED.")
