"""
scenarios.py — Damage scenario definitions for ClaimGuard data generation.

Each scenario captures a realistic collision/damage type with affected panels,
typical repair operations, and expected total cost ranges.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class Scenario:
    """Represents a real-world vehicle damage scenario."""

    name: str
    affected_panels: list[str]
    typical_operations: list[tuple[str, str]]  # (operation, panel)
    expected_cost_range: tuple[float, float]  # (min_total $, max_total $)
    description: str


# ---------------------------------------------------------------------------
# Individual scenario definitions
# ---------------------------------------------------------------------------

rear_end = Scenario(
    name="rear_end",
    affected_panels=[
        "rear_bumper",
        "trunk_lid",
        "left_taillight",
        "right_taillight",
    ],
    typical_operations=[
        ("R&R", "rear_bumper"),
        ("Repair", "trunk_lid"),
        ("Replace", "left_taillight"),
        ("Replace", "right_taillight"),
        ("Refinish", "rear_bumper"),
        ("Blend", "left_quarter_panel"),
    ],
    expected_cost_range=(800.0, 3500.0),
    description=(
        "Rear-end collision: rear bumper cover damage, trunk lid deformation, "
        "and taillight breakage. Common in stop-and-go traffic."
    ),
)

front_impact = Scenario(
    name="front_impact",
    affected_panels=[
        "front_bumper",
        "hood",
        "left_headlight",
        "right_headlight",
        "left_fender",
        "right_fender",
    ],
    typical_operations=[
        ("R&R", "front_bumper"),
        ("Repair", "hood"),
        ("Replace", "left_headlight"),
        ("Replace", "right_headlight"),
        ("Repair", "left_fender"),
        ("Repair", "right_fender"),
        ("Refinish", "hood"),
        ("Blend", "left_fender"),
        ("Blend", "right_fender"),
    ],
    expected_cost_range=(1500.0, 6500.0),
    description=(
        "Front-impact collision: bumper, hood, headlights, and both fenders "
        "damaged. Ranges from minor parking-speed impact to significant crash."
    ),
)

side_swipe = Scenario(
    name="side_swipe",
    affected_panels=[
        "left_door",
        "left_fender",
        "left_mirror",
    ],
    typical_operations=[
        ("R&R", "left_mirror"),
        ("Repair", "left_door"),
        ("Blend", "left_fender"),
        ("Refinish", "left_door"),
    ],
    expected_cost_range=(600.0, 2800.0),
    description=(
        "Side-swipe: mirror sheared off, door surface damage, fender scuff. "
        "Typically a glancing blow from an adjacent lane."
    ),
)

hail = Scenario(
    name="hail",
    affected_panels=[
        "hood",
        "roof",
        "trunk_lid",
    ],
    typical_operations=[
        ("Repair", "hood"),
        ("Repair", "roof"),
        ("Repair", "trunk_lid"),
        ("Refinish", "hood"),
        ("Refinish", "roof"),
        ("Refinish", "trunk_lid"),
    ],
    expected_cost_range=(1200.0, 5000.0),
    description=(
        "Hail damage: dent removal (PDR or conventional) on horizontal panels "
        "followed by refinishing. Severity depends on hail size and storm duration."
    ),
)

minor_scrape = Scenario(
    name="minor_scrape",
    affected_panels=[
        "front_bumper",
    ],
    typical_operations=[
        ("Repair", "front_bumper"),
        ("Refinish", "front_bumper"),
    ],
    expected_cost_range=(150.0, 800.0),
    description=(
        "Minor scrape: surface abrasion on front bumper cover only. "
        "Typically caused by low-speed contact with a fixed object."
    ),
)

parking_lot = Scenario(
    name="parking_lot",
    affected_panels=[
        "rear_bumper",
        "left_door",
    ],
    typical_operations=[
        ("R&R", "rear_bumper"),
        ("R&R", "left_door"),
        ("Refinish", "rear_bumper"),
        ("Refinish", "left_door"),
    ],
    expected_cost_range=(900.0, 3200.0),
    description=(
        "Parking-lot incident: rear bumper and door panel damage from "
        "low-speed collision with another vehicle or fixed object."
    ),
)

# ---------------------------------------------------------------------------
# Exported collection
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [
    rear_end,
    front_impact,
    side_swipe,
    hail,
    minor_scrape,
    parking_lot,
]

_SCENARIO_MAP: dict[str, Scenario] = {s.name: s for s in SCENARIOS}


def get_random_scenario(rng: random.Random | None = None) -> Scenario:
    """Return a uniformly random scenario."""
    if rng is not None:
        return rng.choice(SCENARIOS)
    return random.choice(SCENARIOS)


def get_scenario_by_name(name: str) -> Scenario:
    """Retrieve a scenario by its name string."""
    return _SCENARIO_MAP[name]
