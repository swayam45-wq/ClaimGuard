"""
Pydantic v2 schemas for ClaimGuard API.
Modeled on CIECA BMS (Business Message Suite) estimate structure.
See: https://www.cccsecureshare.com/Faq
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ---------------------------------------------------------------------------
# Input schemas
# ---------------------------------------------------------------------------


class VehicleIn(BaseModel):
    """Vehicle descriptor mirroring CIECA BMS VehicleInfo segment."""

    year: int = Field(..., ge=1990, le=2026)
    make: str
    model: str
    trim: str = "Base"
    mileage: int = Field(..., ge=0, le=500_000)
    # 'class' is a Python keyword – expose via alias
    class_: str = Field("compact", alias="class")  # compact/mid_size/luxury/truck/suv

    model_config = ConfigDict(populate_by_name=True)


class PartIn(BaseModel):
    """Single part line from a CIECA BMS PartDetail segment."""

    name: str
    oem_price: float = Field(..., ge=0)
    billed_price: float = Field(..., ge=0)
    source: Literal["OEM", "OEM_ALT", "AM", "LKQ", "RECON"] = "OEM"

    model_config = ConfigDict(populate_by_name=True)


class LineItemIn(BaseModel):
    """One estimate line item (operation + optional part)."""

    line_id: int
    operation: Literal["R&R", "Repair", "Refinish", "Blend", "Align", "Replace"]
    panel: str
    description: str = ""
    part: PartIn | None = None
    labor_hours_billed: float = Field(..., ge=0, le=50)
    labor_hours_book: float = Field(..., ge=0, le=50)
    labor_rate: float = Field(..., ge=20, le=300)

    model_config = ConfigDict(populate_by_name=True)


class EstimateIn(BaseModel):
    """Top-level estimate payload, analogous to a CIECA BMS EMS message."""

    estimate_id: str
    shop_id: str
    region: Literal["northeast", "southeast", "midwest", "southwest", "west"]
    vehicle: VehicleIn
    scenario: str = "unknown"
    line_items: list[LineItemIn] = Field(..., min_length=1)

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def validate_line_ids_unique(self) -> EstimateIn:
        ids = [li.line_id for li in self.line_items]
        if len(ids) != len(set(ids)):
            raise ValueError("line_id values must be unique within an estimate")
        return self


# ---------------------------------------------------------------------------
# Output schemas
# ---------------------------------------------------------------------------


class FlaggedLineOut(BaseModel):
    """Details about a single suspicious line item."""

    line_id: int
    fraud_types: list[str]
    confidence: float
    explanation: str

    model_config = ConfigDict(populate_by_name=True)


class PredictionOut(BaseModel):
    """Complete fraud prediction result for one estimate."""

    estimate_id: str
    fraud_probability: float
    is_fraud: bool
    # <0.4 → clean / 0.4-0.7 → suspicious / >0.7 → fraudulent
    fraud_label: Literal["clean", "suspicious", "fraudulent"]
    flagged_lines: list[FlaggedLineOut]
    processing_time_ms: float

    model_config = ConfigDict(populate_by_name=True)


class BatchPredictionOut(BaseModel):
    """Aggregate result for a batch of estimates."""

    results: list[PredictionOut]
    total: int
    fraud_count: int
    processing_time_ms: float

    model_config = ConfigDict(populate_by_name=True)


class HealthOut(BaseModel):
    """API health-check response."""

    status: Literal["ok", "degraded"]
    model_loaded: bool
    version: str

    model_config = ConfigDict(populate_by_name=True)


class ModelInfoOut(BaseModel):
    """Metadata about the currently loaded model."""

    model_version: str
    training_date: str
    n_features: int
    feature_names: list[str]
    metrics: dict  # precision, recall, f1, pr_auc
    best_params: dict

    model_config = ConfigDict(populate_by_name=True)
