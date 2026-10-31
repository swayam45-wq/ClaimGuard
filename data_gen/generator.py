"""
generator.py — Clean (non-fraud) estimate generation for ClaimGuard.

Produces fully-populated estimate dicts that conform to the ClaimGuard
CIECA BMS-inspired schema.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from pricing import (
    LABOR_RATES,
    PART_BASE_PRICES,
    PANELS,
    REGIONS,
    VEHICLE_CLASSES,
    TRIM_FEATURES,
    get_regional_part_price,
    get_book_hours,
)
from scenarios import Scenario

# ---------------------------------------------------------------------------
# Vehicle pool
# ---------------------------------------------------------------------------

# (make, model, trim, vehicle_class)
_VEHICLE_POOL: list[tuple[str, str, str, str]] = [
    # compact
    ("Honda",  "Civic",   "EX",  "compact"),
    ("Toyota", "Corolla", "LE",  "compact"),
    ("Hyundai","Elantra", "SE",  "compact"),
    # mid_size
    ("Honda",   "Accord",  "EX-L", "mid_size"),
    ("Toyota",  "Camry",   "XSE",  "mid_size"),
    ("Nissan",  "Altima",  "SL",   "mid_size"),
    # luxury
    ("BMW",        "3-Series", "330i",        "luxury"),
    ("Audi",       "A4",       "Premium Plus","luxury"),
    ("Mercedes",   "C-Class",  "C300",        "luxury"),
    # truck
    ("Ford",    "F-150",    "XLT",      "truck"),
    ("Chevrolet","Silverado","LT",       "truck"),
    ("RAM",     "1500",     "Big Horn",  "truck"),
    # suv
    ("Toyota", "RAV4",    "XLE", "suv"),
    ("Honda",  "CR-V",    "EX",  "suv"),
    ("Ford",   "Explorer","XLT", "suv"),
]

_VEHICLE_BY_CLASS: dict[str, list[tuple[str, str, str, str]]] = {}
for _v in _VEHICLE_POOL:
    _VEHICLE_BY_CLASS.setdefault(_v[3], []).append(_v)


# ---------------------------------------------------------------------------
# Shop pool
# ---------------------------------------------------------------------------

def build_shop_pool() -> list[dict[str, Any]]:
    """
    Return a deterministic list of 500 shop dicts.

    Each shop has:
      - shop_id: str          "SHOP-001" … "SHOP-500"
      - region: str
      - preferred_class: str  vehicle class the shop most often sees
    """
    shops: list[dict[str, Any]] = []
    for i in range(1, 501):
        region_idx: int      = (i - 1) % len(REGIONS)
        class_idx:  int      = ((i - 1) // len(REGIONS)) % len(VEHICLE_CLASSES)
        shops.append(
            {
                "shop_id":         f"SHOP-{i:03d}",
                "region":          REGIONS[region_idx],
                "preferred_class": VEHICLE_CLASSES[class_idx],
            }
        )
    return shops


_SHOP_POOL: list[dict[str, Any]] = build_shop_pool()


def get_shop_pool() -> list[dict[str, Any]]:
    """Return the pre-built shop pool."""
    return _SHOP_POOL


# ---------------------------------------------------------------------------
# Panel → friendly part name mapping
# ---------------------------------------------------------------------------

_PART_NAME: dict[str, str] = {
    "front_bumper":        "bumper cover",
    "rear_bumper":         "bumper cover",
    "hood":                "hood panel",
    "left_door":           "door shell",
    "right_door":          "door shell",
    "left_fender":         "fender",
    "right_fender":        "fender",
    "left_quarter_panel":  "quarter panel",
    "right_quarter_panel": "quarter panel",
    "left_mirror":         "mirror assembly",
    "right_mirror":        "mirror assembly",
    "left_headlight":      "headlight assembly",
    "right_headlight":     "headlight assembly",
    "left_taillight":      "taillight assembly",
    "right_taillight":     "taillight assembly",
    "rocker_panel":        "rocker panel",
    "roof":                "roof panel",
    "windshield":          "windshield glass",
    "trunk_lid":           "trunk lid panel",
}

# Operations that always require a part
_OPERATIONS_WITH_PARTS: set[str] = {"R&R", "Replace"}

# Operations that never need a part (labor-only)
_OPERATIONS_NO_PART: set[str] = {"Repair", "Refinish", "Blend", "Align"}


# ---------------------------------------------------------------------------
# Core generation function
# ---------------------------------------------------------------------------

def generate_estimate(
    estimate_id: str,
    shop_id: str,
    region: str,
    vehicle_class: str,
    scenario: Scenario,
    rng: np.random.Generator,
) -> dict[str, Any]:
    """
    Generate a clean (non-fraudulent) repair estimate dict.

    Parameters
    ----------
    estimate_id   : unique identifier string, e.g. "EST-000001"
    shop_id       : shop identifier, e.g. "SHOP-042"
    region        : one of REGIONS
    vehicle_class : one of VEHICLE_CLASSES
    scenario      : Scenario object describing the damage type
    rng           : NumPy random Generator for reproducibility

    Returns
    -------
    dict conforming to the ClaimGuard estimate schema (fraud_label=0).
    """
    # --- Vehicle selection ---------------------------------------------------
    candidates = _VEHICLE_BY_CLASS.get(vehicle_class, _VEHICLE_BY_CLASS["compact"])
    make, model, trim, v_class = candidates[
        int(rng.integers(0, len(candidates)))
    ]
    year: int     = int(rng.integers(2018, 2025))        # 2018–2024 inclusive
    mileage: int  = int(rng.integers(5_000, 120_001))

    # --- Labor rate with ±10 % shop variance --------------------------------
    base_rate: float    = LABOR_RATES[region]
    labor_rate: float   = round(base_rate * rng.uniform(0.90, 1.10), 2)

    # --- Build line items from scenario operations --------------------------
    line_items: list[dict[str, Any]] = []
    line_id: int = 1

    for operation, panel in scenario.typical_operations:
        # Skip panels that don't exist in PART_BASE_PRICES (safety guard)
        if panel not in PART_BASE_PRICES.get(vehicle_class, {}):
            continue

        book_hours: float   = get_book_hours(operation, panel, rng)
        # ±15 % variance on billed hours (clean — no fraud)
        billed_hours: float = round(book_hours * rng.uniform(0.85, 1.15), 1)
        billed_hours        = max(0.1, billed_hours)

        description: str = f"{operation} {panel.replace('_', ' ')}"

        if operation in _OPERATIONS_WITH_PARTS:
            oem_price: float  = get_regional_part_price(panel, vehicle_class, region, rng)
            part_dict: dict[str, Any] = {
                "name":        _PART_NAME.get(panel, panel.replace("_", " ")),
                "oem_price":   oem_price,
                "billed_price": oem_price,        # clean: billed == OEM
                "source":      "OEM",
            }
        else:
            part_dict = None  # type: ignore[assignment]

        line: dict[str, Any] = {
            "line_id":            line_id,
            "operation":          operation,
            "panel":              panel,
            "description":        description,
            "part":               part_dict,
            "labor_hours_billed": billed_hours,
            "labor_hours_book":   book_hours,
            "labor_rate":         labor_rate,
            "fraud_flag":         0,
            "fraud_type":         None,
        }
        line_items.append(line)
        line_id += 1

    # Ensure at least one line item exists
    if not line_items:
        fallback_panel: str     = scenario.affected_panels[0]
        book_h: float           = get_book_hours("Repair", fallback_panel, rng)
        billed_h: float         = round(book_h * rng.uniform(0.85, 1.15), 1)
        line_items.append(
            {
                "line_id":            1,
                "operation":          "Repair",
                "panel":              fallback_panel,
                "description":        f"Repair {fallback_panel.replace('_', ' ')}",
                "part":               None,
                "labor_hours_billed": billed_h,
                "labor_hours_book":   book_h,
                "labor_rate":         labor_rate,
                "fraud_flag":         0,
                "fraud_type":         None,
            }
        )

    return {
        "estimate_id": estimate_id,
        "shop_id":     shop_id,
        "region":      region,
        "vehicle": {
            "year":    year,
            "make":    make,
            "model":   model,
            "trim":    trim,
            "mileage": mileage,
            "class":   v_class,
        },
        "scenario":    scenario.name,
        "line_items":  line_items,
        "fraud_label": 0,
        "fraud_types": [],
    }
