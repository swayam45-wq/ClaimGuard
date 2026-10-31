"""
ClaimGuard API Constants & Templates

Defines panel adjacency models and plain-English SHAP explanation templates
conforming to the CIECA BMS standard.
"""

from __future__ import annotations

import os
from pathlib import Path

APP_VERSION: str = "1.0.0"
ARTIFACTS_DIR: Path = Path(os.getenv("ARTIFACTS_DIR", "models/artifacts"))

# Panel adjacency map – used to detect "unnecessary operations" fraud.
# Key = panel, value = set of panels considered adjacent / directly related.
PANEL_ADJACENCY: dict[str, set[str]] = {
    "hood": {"fender_lf", "fender_rf", "grille", "headlight_l", "headlight_r", "bumper_f"},
    "fender_lf": {"hood", "door_lf", "headlight_l", "bumper_f", "rocker_lf"},
    "fender_rf": {"hood", "door_rf", "headlight_r", "bumper_f", "rocker_rf"},
    "door_lf": {"fender_lf", "door_lr", "rocker_lf", "mirror_l", "a_pillar_l"},
    "door_rf": {"fender_rf", "door_rr", "rocker_rf", "mirror_r", "a_pillar_r"},
    "door_lr": {"door_lf", "quarter_l", "rocker_lf", "b_pillar_l", "c_pillar_l"},
    "door_rr": {"door_rf", "quarter_r", "rocker_rf", "b_pillar_r", "c_pillar_r"},
    "quarter_l": {"door_lr", "trunk_lid", "rocker_lf", "tail_light_l", "bumper_r"},
    "quarter_r": {"door_rr", "trunk_lid", "rocker_rf", "tail_light_r", "bumper_r"},
    "trunk_lid": {"quarter_l", "quarter_r", "bumper_r", "tail_light_l", "tail_light_r"},
    "bumper_f": {"hood", "fender_lf", "fender_rf", "grille", "headlight_l", "headlight_r"},
    "bumper_r": {"trunk_lid", "quarter_l", "quarter_r", "tail_light_l", "tail_light_r"},
    "roof": {"a_pillar_l", "a_pillar_r", "b_pillar_l", "b_pillar_r", "c_pillar_l", "c_pillar_r"},
    "rocker_lf": {"door_lf", "door_lr", "fender_lf", "quarter_l"},
    "rocker_rf": {"door_rf", "door_rr", "fender_rf", "quarter_r"},
    "grille": {"hood", "bumper_f", "headlight_l", "headlight_r"},
    "headlight_l": {"hood", "fender_lf", "bumper_f", "grille"},
    "headlight_r": {"hood", "fender_rf", "bumper_f", "grille"},
    "tail_light_l": {"quarter_l", "trunk_lid", "bumper_r"},
    "tail_light_r": {"quarter_r", "trunk_lid", "bumper_r"},
    "mirror_l": {"door_lf"},
    "mirror_r": {"door_rf"},
    "a_pillar_l": {"door_lf", "roof"},
    "a_pillar_r": {"door_rf", "roof"},
    "b_pillar_l": {"door_lf", "door_lr", "roof"},
    "b_pillar_r": {"door_rf", "door_rr", "roof"},
    "c_pillar_l": {"door_lr", "quarter_l", "roof"},
    "c_pillar_r": {"door_rr", "quarter_r", "roof"},
}

# Human-readable fraud explanation templates.
FRAUD_EXPLANATIONS: dict[str, str] = {
    "inflated_labor_hours": (
        "Labor hours billed ({billed:.1f}h) are {ratio:.1f}× the book rate ({book:.1f}h) "
        "for this operation."
    ),
    "part_price_markup": (
        "Part billed at ${billed:.2f}, which is {ratio:.0%} above the OEM reference price "
        "of ${median:.2f}."
    ),
    "duplicate_line_items": (
        "This line appears to be a near-duplicate of another line item (similarity: {score:.0%})."
    ),
    "unnecessary_operations": (
        "This {operation} operation is on a panel ({panel}) not adjacent to the "
        "primary damage area."
    ),
    "phantom_parts": (
        "Part '{part}' requires a vehicle feature not present on this trim ({trim})."
    ),
    "labor_parts_mismatch": (
        "Labor hours ({hours:.1f}h) are disproportionate to the minor part replaced ({part})."
    ),
}

# Known feature keywords corresponding to each phantom part
PHANTOM_PART_TRIM_MAP: dict[str, str] = {
    "parking_sensor": "parking_sensors",
    "sensor": "parking_sensors",
    "sunroof": "sunroof",
    "hid": "HID_headlights",
    "xenon": "HID_headlights",
    "blind_spot": "blind_spot",
    "adaptive_cruise": "adaptive_cruise",
}

# Operations that should be consistent with adjacent damage
REFINISH_BLEND_OPS: set[str] = {"Refinish", "Blend"}

# Thresholds for heuristic suspicion
HOURS_RATIO_WARN: float = 1.3
HOURS_RATIO_CRIT: float = 2.0
PRICE_RATIO_WARN: float = 1.2
PRICE_RATIO_CRIT: float = 1.4
DUPLICATE_SIM_WARN: float = 0.70
LINE_SUSPICION_THRESHOLD: float = 0.40
