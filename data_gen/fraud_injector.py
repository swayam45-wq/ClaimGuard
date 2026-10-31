"""
fraud_injector.py — Injects realistic fraud patterns into clean estimates.

All 6 fraud patterns are implemented. Lines are labelled with
`fraud_flag=1` and `fraud_type=<pattern_name>` where the fraud occurs.
"""

from __future__ import annotations

import copy
from typing import Any

import numpy as np
from pricing import (
    ADJACENT_PANELS,
    PANELS,
    PHANTOM_PARTS,
    TRIM_FEATURES,
)

# ---------------------------------------------------------------------------
# Pattern registry
# ---------------------------------------------------------------------------

ALL_FRAUD_PATTERNS: list[str] = [
    "inflated_labor_hours",
    "part_price_markup",
    "duplicate_line_items",
    "unnecessary_operations",
    "phantom_parts",
    "labor_parts_mismatch",
]


def sample_fraud_patterns(
    fraud_rate: float,
    rng: np.random.Generator,
) -> list[str]:
    """
    Return a random subset of 1-3 fraud patterns with probability fraud_rate,
    or an empty list [] for a clean estimate.
    """
    if rng.uniform(0.0, 1.0) >= fraud_rate:
        return []
    n_patterns: int = int(rng.integers(1, 4))  # 1, 2, or 3
    return list(
        rng.choice(ALL_FRAUD_PATTERNS, size=n_patterns, replace=False)  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Individual fraud injectors (private helpers)
# ---------------------------------------------------------------------------


def _inflated_labor_hours(
    estimate: dict[str, Any],
    rng: np.random.Generator,
) -> None:
    """Pick one random line and inflate billed hours by 1.5×–2.5×."""
    lines: list[dict[str, Any]] = estimate["line_items"]
    if not lines:
        return
    idx: int = int(rng.integers(0, len(lines)))
    line = lines[idx]
    book: float = line["labor_hours_book"]
    line["labor_hours_billed"] = round(float(book) * rng.uniform(1.5, 2.5), 1)
    line["fraud_flag"] = 1
    line["fraud_type"] = "inflated_labor_hours"


def _part_price_markup(
    estimate: dict[str, Any],
    rng: np.random.Generator,
    regional_medians: dict[str, dict[str, float]],
) -> None:
    """
    Pick one line that has a part and mark up billed_price to
    regional_median * uniform(1.25, 1.60).
    """
    lines: list[dict[str, Any]] = estimate["line_items"]
    candidates = [item for item in lines if item.get("part") is not None]
    if not candidates:
        return
    idx: int = int(rng.integers(0, len(candidates)))
    line = candidates[idx]
    panel: str = line["panel"]
    v_class: str = estimate["vehicle"]["class"]

    median_price: float = regional_medians.get(panel, {}).get(v_class, line["part"]["oem_price"])
    inflated: float = round(float(median_price) * rng.uniform(1.25, 1.60), 2)
    line["part"]["billed_price"] = inflated
    line["fraud_flag"] = 1
    line["fraud_type"] = "part_price_markup"


def _duplicate_line_items(
    estimate: dict[str, Any],
    rng: np.random.Generator,
) -> None:
    """
    Clone a random line item, slightly alter the description, and append it.
    Both the original and clone are marked fraudulent.
    """
    lines: list[dict[str, Any]] = estimate["line_items"]
    if not lines:
        return
    idx: int = int(rng.integers(0, len(lines)))
    original = lines[idx]
    clone = copy.deepcopy(original)

    # Alter description slightly
    suffixes = [" - supplemental", " - additional", " (revised)"]
    suffix_idx: int = int(rng.integers(0, len(suffixes)))
    if rng.uniform(0, 1) < 0.5:
        clone["description"] = "Additional " + clone["description"]
    else:
        clone["description"] = clone["description"] + suffixes[suffix_idx]

    # Assign new line_id
    max_id: int = max(item["line_id"] for item in lines)
    clone["line_id"] = max_id + 1

    # Mark both
    original["fraud_flag"] = 1
    original["fraud_type"] = "duplicate_line_items"
    clone["fraud_flag"] = 1
    clone["fraud_type"] = "duplicate_line_items"

    lines.append(clone)


def _unnecessary_operations(
    estimate: dict[str, Any],
    rng: np.random.Generator,
) -> None:
    """
    Add a Blend or Refinish line item for a panel that is NOT adjacent to any
    primary damage panel in the scenario.
    """
    lines: list[dict[str, Any]] = estimate["line_items"]
    existing_panels: set[str] = {item["panel"] for item in lines}

    # Collect all panels adjacent to any already-damaged panel
    adjacent: set[str] = set()
    for panel in existing_panels:
        adjacent.update(ADJACENT_PANELS.get(panel, []))
    adjacent.update(existing_panels)  # also exclude the damaged panels themselves

    # Candidate panels: not damaged, not adjacent
    non_adjacent: list[str] = [p for p in PANELS if p not in adjacent]
    if not non_adjacent:
        # Fallback: pick any panel not already in estimate
        non_adjacent = [p for p in PANELS if p not in existing_panels]
    if not non_adjacent:
        return

    panel_idx: int = int(rng.integers(0, len(non_adjacent)))
    target_panel: str = non_adjacent[panel_idx]
    operation: str = "Blend" if rng.uniform(0, 1) < 0.5 else "Refinish"

    max_id: int = max((item["line_id"] for item in lines), default=0)
    labor_rate: float = lines[0]["labor_rate"] if lines else 78.0

    lines.append(
        {
            "line_id": max_id + 1,
            "operation": operation,
            "panel": target_panel,
            "description": f"{operation} {target_panel.replace('_', ' ')}",
            "part": None,
            "labor_hours_billed": round(rng.uniform(1.5, 2.5), 1),
            "labor_hours_book": round(rng.uniform(1.5, 2.5), 1),
            "labor_rate": labor_rate,
            "fraud_flag": 1,
            "fraud_type": "unnecessary_operations",
        }
    )


def _phantom_parts(
    estimate: dict[str, Any],
    rng: np.random.Generator,
) -> None:
    """
    Add a phantom part that requires a feature absent from the vehicle's trim.
    """
    trim: str = estimate["vehicle"]["trim"]
    trim_features: list[str] = TRIM_FEATURES.get(trim, [])

    # Find phantom parts whose required feature is NOT in trim_features
    eligible: list[tuple[str, str]] = [
        (part_name, required_feat)
        for part_name, required_feat in PHANTOM_PARTS.items()
        if required_feat not in trim_features
    ]
    if not eligible:
        return

    idx: int = int(rng.integers(0, len(eligible)))
    part_name, _required = eligible[idx]

    phantom_prices: dict[str, float] = {
        "parking_sensor_kit": 285.0,
        "sunroof_glass": 420.0,
        "HID_headlight_assembly": 580.0,
        "blind_spot_sensor": 195.0,
        "adaptive_cruise_module": 340.0,
    }
    oem_price: float = phantom_prices.get(part_name, 250.0)
    lines: list[dict[str, Any]] = estimate["line_items"]
    max_id: int = max((item["line_id"] for item in lines), default=0)
    labor_rate: float = lines[0]["labor_rate"] if lines else 78.0

    lines.append(
        {
            "line_id": max_id + 1,
            "operation": "Replace",
            "panel": "front_bumper",  # plausible mounting location
            "description": f"Replace {part_name.replace('_', ' ')}",
            "part": {
                "name": part_name.replace("_", " "),
                "oem_price": oem_price,
                "billed_price": oem_price,
                "source": "OEM",
            },
            "labor_hours_billed": 0.5,
            "labor_hours_book": 0.5,
            "labor_rate": labor_rate,
            "fraud_flag": 1,
            "fraud_type": "phantom_parts",
        }
    )


def _labor_parts_mismatch(
    estimate: dict[str, Any],
    rng: np.random.Generator,
) -> None:
    """
    Set one line's billed labor hours to a very high value (7–10 h) but
    assign it a trivial part (mirror cap, $35).
    """
    lines: list[dict[str, Any]] = estimate["line_items"]
    if not lines:
        return
    idx: int = int(rng.integers(0, len(lines)))
    line = lines[idx]

    line["labor_hours_billed"] = round(rng.uniform(7.0, 10.0), 1)
    line["part"] = {
        "name": "mirror cap",
        "oem_price": 35.0,
        "billed_price": 35.0,
        "source": "OEM",
    }
    line["fraud_flag"] = 1
    line["fraud_type"] = "labor_parts_mismatch"


# ---------------------------------------------------------------------------
# Public injection entry point
# ---------------------------------------------------------------------------


def inject_fraud(
    estimate: dict[str, Any],
    fraud_patterns: list[str],
    rng: np.random.Generator,
    regional_medians: dict[str, dict[str, float]],
) -> dict[str, Any]:
    """
    Apply the specified fraud patterns to a deep copy of *estimate* and
    return the modified estimate.

    Parameters
    ----------
    estimate         : clean estimate dict produced by generator.generate_estimate
    fraud_patterns   : list of pattern names to inject (subset of ALL_FRAUD_PATTERNS)
    rng              : NumPy random Generator for reproducibility
    regional_medians : panel → vehicle_class → median OEM price (for markup calc)

    Returns
    -------
    dict — modified estimate with fraud_label=1 and fraud_types populated.
    """
    result: dict[str, Any] = copy.deepcopy(estimate)

    for pattern in fraud_patterns:
        if pattern == "inflated_labor_hours":
            _inflated_labor_hours(result, rng)
        elif pattern == "part_price_markup":
            _part_price_markup(result, rng, regional_medians)
        elif pattern == "duplicate_line_items":
            _duplicate_line_items(result, rng)
        elif pattern == "unnecessary_operations":
            _unnecessary_operations(result, rng)
        elif pattern == "phantom_parts":
            _phantom_parts(result, rng)
        elif pattern == "labor_parts_mismatch":
            _labor_parts_mismatch(result, rng)

    result["fraud_label"] = 1
    result["fraud_types"] = list(fraud_patterns)
    return result
