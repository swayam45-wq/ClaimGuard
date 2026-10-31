"""
pricing.py — Parts/labor price tables for ClaimGuard data generation.

All prices are in USD and represent realistic OEM market values as of 2024.
"""

from __future__ import annotations

import random

import numpy as np

# ---------------------------------------------------------------------------
# Taxonomy constants
# ---------------------------------------------------------------------------

VEHICLE_CLASSES: list[str] = ["compact", "mid_size", "luxury", "truck", "suv"]

REGIONS: list[str] = ["northeast", "southeast", "midwest", "southwest", "west"]

PANELS: list[str] = [
    "front_bumper",
    "rear_bumper",
    "hood",
    "left_door",
    "right_door",
    "left_fender",
    "right_fender",
    "left_quarter_panel",
    "right_quarter_panel",
    "left_mirror",
    "right_mirror",
    "left_headlight",
    "right_headlight",
    "left_taillight",
    "right_taillight",
    "rocker_panel",
    "roof",
    "windshield",
    "trunk_lid",
]

OPERATIONS: list[str] = ["R&R", "Repair", "Refinish", "Blend", "Align", "Replace"]

# ---------------------------------------------------------------------------
# Regional labor rates ($/hr base)
# ---------------------------------------------------------------------------

LABOR_RATES: dict[str, float] = {
    "northeast": 95.0,
    "southeast": 72.0,
    "midwest": 78.0,
    "southwest": 75.0,
    "west": 105.0,
}

# ---------------------------------------------------------------------------
# Regional parts price multipliers
# ---------------------------------------------------------------------------

REGIONAL_PART_MULTIPLIER: dict[str, float] = {
    "northeast": 1.08,
    "southeast": 0.95,
    "midwest": 1.00,
    "southwest": 0.97,
    "west": 1.12,
}

# ---------------------------------------------------------------------------
# OEM part base prices  (vehicle_class → panel → price USD)
# ---------------------------------------------------------------------------

PART_BASE_PRICES: dict[str, dict[str, float]] = {
    "compact": {
        "front_bumper": 245.0,
        "rear_bumper": 220.0,
        "hood": 380.0,
        "left_door": 525.0,
        "right_door": 525.0,
        "left_fender": 195.0,
        "right_fender": 195.0,
        "left_quarter_panel": 310.0,
        "right_quarter_panel": 310.0,
        "left_mirror": 145.0,
        "right_mirror": 145.0,
        "left_headlight": 285.0,
        "right_headlight": 285.0,
        "left_taillight": 180.0,
        "right_taillight": 180.0,
        "rocker_panel": 165.0,
        "roof": 620.0,
        "windshield": 290.0,
        "trunk_lid": 340.0,
    },
    "mid_size": {
        "front_bumper": 310.0,
        "rear_bumper": 290.0,
        "hood": 465.0,
        "left_door": 680.0,
        "right_door": 680.0,
        "left_fender": 255.0,
        "right_fender": 255.0,
        "left_quarter_panel": 395.0,
        "right_quarter_panel": 395.0,
        "left_mirror": 195.0,
        "right_mirror": 195.0,
        "left_headlight": 365.0,
        "right_headlight": 365.0,
        "left_taillight": 240.0,
        "right_taillight": 240.0,
        "rocker_panel": 210.0,
        "roof": 780.0,
        "windshield": 360.0,
        "trunk_lid": 435.0,
    },
    "luxury": {
        "front_bumper": 680.0,
        "rear_bumper": 625.0,
        "hood": 920.0,
        "left_door": 1350.0,
        "right_door": 1350.0,
        "left_fender": 540.0,
        "right_fender": 540.0,
        "left_quarter_panel": 780.0,
        "right_quarter_panel": 780.0,
        "left_mirror": 480.0,
        "right_mirror": 480.0,
        "left_headlight": 895.0,
        "right_headlight": 895.0,
        "left_taillight": 610.0,
        "right_taillight": 610.0,
        "rocker_panel": 420.0,
        "roof": 1580.0,
        "windshield": 720.0,
        "trunk_lid": 870.0,
    },
    "truck": {
        "front_bumper": 420.0,
        "rear_bumper": 390.0,
        "hood": 520.0,
        "left_door": 890.0,
        "right_door": 890.0,
        "left_fender": 340.0,
        "right_fender": 340.0,
        "left_quarter_panel": 510.0,
        "right_quarter_panel": 510.0,
        "left_mirror": 265.0,
        "right_mirror": 265.0,
        "left_headlight": 420.0,
        "right_headlight": 420.0,
        "left_taillight": 310.0,
        "right_taillight": 310.0,
        "rocker_panel": 285.0,
        "roof": 940.0,
        "windshield": 410.0,
        "trunk_lid": 580.0,
    },
    "suv": {
        "front_bumper": 365.0,
        "rear_bumper": 340.0,
        "hood": 490.0,
        "left_door": 760.0,
        "right_door": 760.0,
        "left_fender": 295.0,
        "right_fender": 295.0,
        "left_quarter_panel": 450.0,
        "right_quarter_panel": 450.0,
        "left_mirror": 230.0,
        "right_mirror": 230.0,
        "left_headlight": 395.0,
        "right_headlight": 395.0,
        "left_taillight": 275.0,
        "right_taillight": 275.0,
        "rocker_panel": 240.0,
        "roof": 870.0,
        "windshield": 385.0,
        "trunk_lid": 510.0,
    },
}

# ---------------------------------------------------------------------------
# Book hours  (operation → panel → hours)
# ---------------------------------------------------------------------------
# For operations that are panel-agnostic we provide a single representative
# value; for granular ones we key by panel.

BOOK_HOURS: dict[str, dict[str, float]] = {
    "R&R": {
        "front_bumper": 2.5,
        "rear_bumper": 2.3,
        "hood": 1.8,
        "left_door": 3.5,
        "right_door": 3.5,
        "left_fender": 2.0,
        "right_fender": 2.0,
        "left_quarter_panel": 4.5,
        "right_quarter_panel": 4.5,
        "left_mirror": 0.8,
        "right_mirror": 0.8,
        "left_headlight": 1.2,
        "right_headlight": 1.2,
        "left_taillight": 0.9,
        "right_taillight": 0.9,
        "rocker_panel": 3.0,
        "roof": 5.0,
        "windshield": 2.0,
        "trunk_lid": 2.2,
    },
    "Repair": {
        "front_bumper": 2.0,
        "rear_bumper": 1.8,
        "hood": 3.0,
        "left_door": 3.5,
        "right_door": 3.5,
        "left_fender": 2.5,
        "right_fender": 2.5,
        "left_quarter_panel": 4.0,
        "right_quarter_panel": 4.0,
        "left_mirror": 0.5,
        "right_mirror": 0.5,
        "left_headlight": 0.8,
        "right_headlight": 0.8,
        "left_taillight": 0.6,
        "right_taillight": 0.6,
        "rocker_panel": 2.5,
        "roof": 4.5,
        "windshield": 1.5,
        "trunk_lid": 2.5,
    },
    "Refinish": {
        "front_bumper": 2.2,
        "rear_bumper": 2.0,
        "hood": 2.5,
        "left_door": 2.0,
        "right_door": 2.0,
        "left_fender": 1.8,
        "right_fender": 1.8,
        "left_quarter_panel": 2.5,
        "right_quarter_panel": 2.5,
        "left_mirror": 0.8,
        "right_mirror": 0.8,
        "left_headlight": 0.5,
        "right_headlight": 0.5,
        "left_taillight": 0.5,
        "right_taillight": 0.5,
        "rocker_panel": 1.5,
        "roof": 3.0,
        "windshield": 0.5,
        "trunk_lid": 2.0,
    },
    "Blend": {
        "front_bumper": 1.5,
        "rear_bumper": 1.5,
        "hood": 1.8,
        "left_door": 1.5,
        "right_door": 1.5,
        "left_fender": 1.5,
        "right_fender": 1.5,
        "left_quarter_panel": 1.8,
        "right_quarter_panel": 1.8,
        "left_mirror": 0.5,
        "right_mirror": 0.5,
        "left_headlight": 0.3,
        "right_headlight": 0.3,
        "left_taillight": 0.3,
        "right_taillight": 0.3,
        "rocker_panel": 1.2,
        "roof": 2.0,
        "windshield": 0.3,
        "trunk_lid": 1.5,
    },
    "Align": {
        "front_bumper": 2.0,
        "rear_bumper": 2.0,
        "hood": 1.5,
        "left_door": 2.0,
        "right_door": 2.0,
        "left_fender": 1.5,
        "right_fender": 1.5,
        "left_quarter_panel": 2.5,
        "right_quarter_panel": 2.5,
        "left_mirror": 0.5,
        "right_mirror": 0.5,
        "left_headlight": 0.5,
        "right_headlight": 0.5,
        "left_taillight": 0.5,
        "right_taillight": 0.5,
        "rocker_panel": 1.5,
        "roof": 2.0,
        "windshield": 0.5,
        "trunk_lid": 1.5,
    },
    "Replace": {
        "front_bumper": 1.0,
        "rear_bumper": 1.0,
        "hood": 1.2,
        "left_door": 1.5,
        "right_door": 1.5,
        "left_fender": 1.0,
        "right_fender": 1.0,
        "left_quarter_panel": 2.0,
        "right_quarter_panel": 2.0,
        "left_mirror": 0.5,
        "right_mirror": 0.5,
        "left_headlight": 0.8,
        "right_headlight": 0.8,
        "left_taillight": 0.6,
        "right_taillight": 0.6,
        "rocker_panel": 1.0,
        "roof": 3.0,
        "windshield": 1.5,
        "trunk_lid": 1.0,
    },
}

# ---------------------------------------------------------------------------
# Adjacent panels
# ---------------------------------------------------------------------------

ADJACENT_PANELS: dict[str, list[str]] = {
    "front_bumper": ["hood", "left_fender", "right_fender", "left_headlight", "right_headlight"],
    "rear_bumper": [
        "trunk_lid",
        "left_quarter_panel",
        "right_quarter_panel",
        "left_taillight",
        "right_taillight",
    ],
    "hood": ["front_bumper", "left_fender", "right_fender", "windshield"],
    "left_door": ["left_fender", "left_quarter_panel", "left_mirror", "rocker_panel"],
    "right_door": ["right_fender", "right_quarter_panel", "right_mirror", "rocker_panel"],
    "left_fender": ["front_bumper", "hood", "left_door", "left_headlight"],
    "right_fender": ["front_bumper", "hood", "right_door", "right_headlight"],
    "left_quarter_panel": ["left_door", "rear_bumper", "left_taillight", "rocker_panel", "roof"],
    "right_quarter_panel": ["right_door", "rear_bumper", "right_taillight", "rocker_panel", "roof"],
    "left_mirror": ["left_door", "left_fender"],
    "right_mirror": ["right_door", "right_fender"],
    "left_headlight": ["front_bumper", "left_fender", "hood"],
    "right_headlight": ["front_bumper", "right_fender", "hood"],
    "left_taillight": ["rear_bumper", "left_quarter_panel", "trunk_lid"],
    "right_taillight": ["rear_bumper", "right_quarter_panel", "trunk_lid"],
    "rocker_panel": ["left_door", "right_door", "left_quarter_panel", "right_quarter_panel"],
    "roof": ["windshield", "left_quarter_panel", "right_quarter_panel", "trunk_lid"],
    "windshield": ["hood", "roof"],
    "trunk_lid": ["rear_bumper", "left_taillight", "right_taillight", "roof"],
}

# ---------------------------------------------------------------------------
# Trim features
# ---------------------------------------------------------------------------

TRIM_FEATURES: dict[str, list[str]] = {
    "base": [],
    "LX": ["backup_camera"],
    "LE": ["backup_camera"],
    "SE": ["backup_camera"],
    "EX": ["backup_camera", "heated_seats"],
    "XLE": ["backup_camera", "heated_seats"],
    "SL": ["backup_camera", "heated_seats"],
    "EX-L": ["backup_camera", "heated_seats", "sunroof"],
    "XSE": ["backup_camera", "heated_seats", "sunroof"],
    "XLT": ["backup_camera", "heated_seats"],
    "LT": ["backup_camera", "heated_seats"],
    "Touring": ["backup_camera", "heated_seats", "sunroof", "parking_sensors", "HID_headlights"],
    "330i": [
        "backup_camera",
        "heated_seats",
        "sunroof",
        "parking_sensors",
        "HID_headlights",
        "blind_spot",
        "adaptive_cruise",
    ],
    "Premium Plus": [
        "backup_camera",
        "heated_seats",
        "sunroof",
        "parking_sensors",
        "HID_headlights",
        "blind_spot",
        "adaptive_cruise",
    ],
    "C300": [
        "backup_camera",
        "heated_seats",
        "sunroof",
        "parking_sensors",
        "HID_headlights",
        "blind_spot",
        "adaptive_cruise",
    ],
    "Big Horn": ["backup_camera", "heated_seats"],
}

# ---------------------------------------------------------------------------
# Phantom parts — require a feature NOT present on base/low trims
# ---------------------------------------------------------------------------

PHANTOM_PARTS: dict[str, str] = {
    "parking_sensor_kit": "parking_sensors",
    "sunroof_glass": "sunroof",
    "HID_headlight_assembly": "HID_headlights",
    "blind_spot_sensor": "blind_spot",
    "adaptive_cruise_module": "adaptive_cruise",
}

# ---------------------------------------------------------------------------
# Pricing utility functions
# ---------------------------------------------------------------------------


def get_regional_part_price(
    panel: str,
    vehicle_class: str,
    region: str,
    rng: np.random.Generator | None = None,
) -> float:
    """Return OEM part price adjusted for region with ±5 % noise."""
    base: float = PART_BASE_PRICES[vehicle_class][panel]
    multiplier: float = REGIONAL_PART_MULTIPLIER[region]
    price: float = base * multiplier
    if rng is not None:
        noise: float = rng.uniform(-0.05, 0.05)
    else:
        noise = random.uniform(-0.05, 0.05)
    return round(price * (1.0 + noise), 2)


def get_book_hours(
    operation: str,
    panel: str,
    rng: np.random.Generator | None = None,
) -> float:
    """Return book hours for an operation/panel with ±10 % noise."""
    hours: float = BOOK_HOURS[operation][panel]
    if rng is not None:
        noise: float = rng.uniform(-0.10, 0.10)
    else:
        noise = random.uniform(-0.10, 0.10)
    return round(hours * (1.0 + noise), 1)
