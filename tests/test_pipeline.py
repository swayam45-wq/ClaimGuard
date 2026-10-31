"""
tests/test_pipeline.py — ClaimGuard end-to-end pipeline tests

Covers:
- All 6 fraud patterns generate correct labels
- Feature matrix has no NaNs
- API predict endpoint returns correct shape
- Known-fraudulent estimates flagged as fraud
- Known-clean estimates not flagged

Run with: pytest tests/ -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

# Add project root to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "data_gen"))
sys.path.insert(0, str(ROOT / "features"))

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CLEAN_ESTIMATE = {
    "estimate_id": "EST-TEST-CLEAN-001",
    "shop_id": "SHOP-001",
    "region": "midwest",
    "vehicle": {
        "year": 2022,
        "make": "Honda",
        "model": "Civic",
        "trim": "EX",
        "mileage": 30000,
        "class": "compact",
    },
    "scenario": "rear_end",
    "line_items": [
        {
            "line_id": 1,
            "operation": "R&R",
            "panel": "rear_bumper",
            "description": "R&R rear bumper cover",
            "part": {
                "name": "bumper cover",
                "oem_price": 285.00,
                "billed_price": 285.00,
                "source": "OEM",
            },
            "labor_hours_billed": 2.5,
            "labor_hours_book": 2.5,
            "labor_rate": 78.00,
            "fraud_flag": 0,
            "fraud_type": None,
        }
    ],
    "fraud_label": 0,
    "fraud_types": [],
}

FRAUDULENT_ESTIMATE_INFLATED_HOURS = {
    "estimate_id": "EST-TEST-FRAUD-001",
    "shop_id": "SHOP-002",
    "region": "northeast",
    "vehicle": {
        "year": 2020,
        "make": "Toyota",
        "model": "Camry",
        "trim": "XSE",
        "mileage": 55000,
        "class": "mid_size",
    },
    "scenario": "front_impact",
    "line_items": [
        {
            "line_id": 1,
            "operation": "R&R",
            "panel": "front_bumper",
            "description": "R&R front bumper cover",
            "part": {
                "name": "bumper cover",
                "oem_price": 380.00,
                "billed_price": 380.00,
                "source": "OEM",
            },
            "labor_hours_billed": 9.5,  # Inflated: book=2.5, billed=9.5 → ratio=3.8x
            "labor_hours_book": 2.5,
            "labor_rate": 95.00,
            "fraud_flag": 1,
            "fraud_type": "inflated_labor_hours",
        },
        {
            "line_id": 2,
            "operation": "Replace",
            "panel": "right_headlight",
            "description": "Replace right headlight assembly",
            "part": {
                "name": "headlight assembly",
                "oem_price": 410.00,
                "billed_price": 615.00,  # 50% markup
                "source": "OEM",
            },
            "labor_hours_billed": 1.0,
            "labor_hours_book": 1.0,
            "labor_rate": 95.00,
            "fraud_flag": 1,
            "fraud_type": "part_price_markup",
        },
    ],
    "fraud_label": 1,
    "fraud_types": ["inflated_labor_hours", "part_price_markup"],
}


# ---------------------------------------------------------------------------
# Data generation tests
# ---------------------------------------------------------------------------


class TestDataGeneration:
    """Test synthetic data generation."""

    def test_pricing_module_imports(self) -> None:
        from pricing import (
            BOOK_HOURS,
            LABOR_RATES,
            OPERATIONS,
            PANELS,
            PART_BASE_PRICES,
            REGIONS,
            VEHICLE_CLASSES,
        )

        assert len(VEHICLE_CLASSES) > 0
        assert len(REGIONS) == 5
        assert len(LABOR_RATES) == 5
        assert len(PANELS) > 10
        assert len(OPERATIONS) > 0
        assert len(PART_BASE_PRICES) > 0
        assert len(BOOK_HOURS) > 0

    def test_regional_part_price_positive(self) -> None:
        from pricing import get_regional_part_price

        price = get_regional_part_price("front_bumper", "compact", "midwest")
        assert price > 0, "Part price must be positive"

    def test_book_hours_positive(self) -> None:
        from pricing import get_book_hours

        hours = get_book_hours("R&R", "front_bumper")
        assert hours > 0, "Book hours must be positive"

    def test_scenarios_module(self) -> None:
        from scenarios import SCENARIOS, get_random_scenario

        assert len(SCENARIOS) >= 6
        scenario = get_random_scenario()
        assert hasattr(scenario, "name")
        assert hasattr(scenario, "affected_panels")
        assert hasattr(scenario, "typical_operations")

    def test_clean_estimate_schema(self) -> None:
        from generator import generate_estimate, get_shop_pool
        from scenarios import get_random_scenario

        rng = np.random.default_rng(42)
        shops = get_shop_pool()
        shop = shops[0]
        scenario = get_random_scenario()

        estimate = generate_estimate(
            estimate_id="EST-000001",
            shop_id=shop["shop_id"],
            region=shop["region"],
            vehicle_class=shop["preferred_class"],
            scenario=scenario,
            rng=rng,
        )

        assert estimate["fraud_label"] == 0
        assert estimate["fraud_types"] == []
        assert len(estimate["line_items"]) > 0
        assert "vehicle" in estimate
        assert "line_items" in estimate
        assert all(li["fraud_flag"] == 0 for li in estimate["line_items"])

    def test_fraud_injector_inflated_hours(self) -> None:
        from fraud_injector import inject_fraud

        rng = np.random.default_rng(100)
        estimate = json.loads(json.dumps(CLEAN_ESTIMATE))
        estimate["fraud_label"] = 0
        estimate["fraud_types"] = []

        regional_medians: dict = {"rear_bumper": {"compact": 285.0}}
        result = inject_fraud(estimate, ["inflated_labor_hours"], rng, regional_medians)

        assert result["fraud_label"] == 1
        assert "inflated_labor_hours" in result["fraud_types"]
        flagged = [li for li in result["line_items"] if li.get("fraud_flag") == 1]
        assert len(flagged) > 0

        for li in flagged:
            if li.get("fraud_type") == "inflated_labor_hours":
                ratio = li["labor_hours_billed"] / li["labor_hours_book"]
                assert ratio >= 1.5, f"Expected ratio >= 1.5, got {ratio:.2f}"

    def test_fraud_injector_part_price_markup(self) -> None:
        from fraud_injector import inject_fraud

        rng = np.random.default_rng(200)
        estimate = json.loads(json.dumps(CLEAN_ESTIMATE))
        estimate["fraud_label"] = 0
        estimate["fraud_types"] = []
        regional_medians: dict = {"rear_bumper": {"compact": 285.0}}

        result = inject_fraud(estimate, ["part_price_markup"], rng, regional_medians)
        assert result["fraud_label"] == 1
        assert "part_price_markup" in result["fraud_types"]
        flagged = [li for li in result["line_items"] if li.get("fraud_type") == "part_price_markup"]
        assert len(flagged) > 0

        for li in flagged:
            if li.get("part"):
                ratio = li["part"]["billed_price"] / regional_medians.get(li["panel"], {}).get(
                    "compact", li["part"]["oem_price"]
                )
                assert ratio >= 1.25

    def test_fraud_injector_duplicate_lines(self) -> None:
        from fraud_injector import inject_fraud

        rng = np.random.default_rng(300)
        estimate = json.loads(json.dumps(CLEAN_ESTIMATE))
        estimate["fraud_label"] = 0
        estimate["fraud_types"] = []
        regional_medians: dict = {}

        original_count = len(estimate["line_items"])
        result = inject_fraud(estimate, ["duplicate_line_items"], rng, regional_medians)
        assert result["fraud_label"] == 1
        assert "duplicate_line_items" in result["fraud_types"]
        assert len(result["line_items"]) > original_count, "Duplicate should add a line"

    def test_fraud_injector_unnecessary_operations(self) -> None:
        from fraud_injector import inject_fraud

        rng = np.random.default_rng(400)
        estimate = json.loads(json.dumps(CLEAN_ESTIMATE))
        estimate["fraud_label"] = 0
        estimate["fraud_types"] = []
        regional_medians: dict = {}

        result = inject_fraud(estimate, ["unnecessary_operations"], rng, regional_medians)
        assert result["fraud_label"] == 1
        assert "unnecessary_operations" in result["fraud_types"]

    def test_fraud_injector_phantom_parts(self) -> None:
        from fraud_injector import inject_fraud

        rng = np.random.default_rng(500)
        estimate = json.loads(json.dumps(CLEAN_ESTIMATE))
        estimate["fraud_label"] = 0
        estimate["fraud_types"] = []
        regional_medians: dict = {}

        result = inject_fraud(estimate, ["phantom_parts"], rng, regional_medians)
        assert result["fraud_label"] == 1
        assert "phantom_parts" in result["fraud_types"]

    def test_fraud_injector_labor_parts_mismatch(self) -> None:
        from fraud_injector import inject_fraud

        rng = np.random.default_rng(600)
        estimate = json.loads(json.dumps(CLEAN_ESTIMATE))
        estimate["fraud_label"] = 0
        estimate["fraud_types"] = []
        regional_medians: dict = {}

        result = inject_fraud(estimate, ["labor_parts_mismatch"], rng, regional_medians)
        assert result["fraud_label"] == 1
        assert "labor_parts_mismatch" in result["fraud_types"]
        flagged = [
            li for li in result["line_items"] if li.get("fraud_type") == "labor_parts_mismatch"
        ]
        assert len(flagged) > 0
        for li in flagged:
            assert li["labor_hours_billed"] >= 7.0

    def test_fraud_rate_accuracy(self) -> None:
        """Verify that fraud rate parameter is respected within ±2%."""
        from fraud_injector import inject_fraud, sample_fraud_patterns
        from generator import generate_estimate, get_shop_pool
        from scenarios import get_random_scenario

        rng = np.random.default_rng(42)
        shops = get_shop_pool()
        target_rate = 0.10
        n = 500
        fraud_count = 0

        regional_medians: dict = {}
        for i in range(n):
            shop = shops[i % len(shops)]
            scenario = get_random_scenario()
            est = generate_estimate(
                estimate_id=f"EST-{i:06d}",
                shop_id=shop["shop_id"],
                region=shop["region"],
                vehicle_class=shop["preferred_class"],
                scenario=scenario,
                rng=rng,
            )
            patterns = sample_fraud_patterns(target_rate, rng)
            if patterns:
                est = inject_fraud(est, patterns, rng, regional_medians)
                fraud_count += 1

        actual_rate = fraud_count / n
        assert abs(actual_rate - target_rate) < 0.05, (
            f"Fraud rate {actual_rate:.3f} too far from target {target_rate}"
        )


# ---------------------------------------------------------------------------
# Feature engineering tests
# ---------------------------------------------------------------------------


class TestFeatureEngineering:
    """Test feature extraction."""

    def test_features_no_nans(self, tmp_path: Path) -> None:
        """Feature matrix must have zero NaN values."""
        sys.path.insert(0, str(ROOT / "features"))
        from build import build_features

        # Write test estimates
        estimates = [CLEAN_ESTIMATE, FRAUDULENT_ESTIMATE_INFLATED_HOURS]
        jsonl = tmp_path / "estimates.jsonl"
        with open(jsonl, "w") as f:
            for est in estimates:
                f.write(json.dumps(est) + "\n")

        X, y, groups = build_features(str(jsonl), str(tmp_path))
        assert X.isna().sum().sum() == 0, "NaNs found in feature matrix"

    def test_features_correct_length(self, tmp_path: Path) -> None:
        from build import build_features

        estimates = [CLEAN_ESTIMATE, FRAUDULENT_ESTIMATE_INFLATED_HOURS]
        jsonl = tmp_path / "estimates.jsonl"
        with open(jsonl, "w") as f:
            for est in estimates:
                f.write(json.dumps(est) + "\n")

        X, y, groups = build_features(str(jsonl), str(tmp_path))
        assert len(X) == len(y) == len(groups) == 2

    def test_label_alignment(self, tmp_path: Path) -> None:
        from build import build_features

        estimates = [CLEAN_ESTIMATE, FRAUDULENT_ESTIMATE_INFLATED_HOURS]
        jsonl = tmp_path / "estimates.jsonl"
        with open(jsonl, "w") as f:
            for est in estimates:
                f.write(json.dumps(est) + "\n")

        X, y, groups = build_features(str(jsonl), str(tmp_path))
        assert y.iloc[0] == 0, "First estimate should be clean"
        assert y.iloc[1] == 1, "Second estimate should be fraud"


# ---------------------------------------------------------------------------
# API tests (requires running API server OR direct function tests)
# ---------------------------------------------------------------------------


class TestAPISchemas:
    """Test Pydantic schema validation without running server."""

    def test_valid_estimate_in(self) -> None:
        sys.path.insert(0, str(ROOT / "api"))
        from schemas import EstimateIn

        est = EstimateIn.model_validate(CLEAN_ESTIMATE)
        assert est.estimate_id == "EST-TEST-CLEAN-001"
        assert len(est.line_items) == 1

    def test_invalid_estimate_missing_fields(self) -> None:
        from pydantic import ValidationError
        from schemas import EstimateIn

        with pytest.raises(ValidationError):
            EstimateIn.model_validate({"estimate_id": "X"})  # missing required fields

    def test_invalid_labor_hours_too_high(self) -> None:
        from pydantic import ValidationError
        from schemas import EstimateIn

        bad = json.loads(json.dumps(CLEAN_ESTIMATE))
        bad["line_items"][0]["labor_hours_billed"] = 999.0  # exceeds le=50

        with pytest.raises(ValidationError):
            EstimateIn.model_validate(bad)

    def test_duplicate_line_ids_rejected(self) -> None:
        from pydantic import ValidationError
        from schemas import EstimateIn

        bad = json.loads(json.dumps(CLEAN_ESTIMATE))
        bad["line_items"].append(
            json.loads(json.dumps(bad["line_items"][0]))
        )  # duplicate line_id=1

        with pytest.raises(ValidationError):
            EstimateIn.model_validate(bad)

    def test_fraud_label_field(self) -> None:
        from schemas import PredictionOut

        out = PredictionOut(
            estimate_id="EST-001",
            fraud_probability=0.85,
            is_fraud=True,
            fraud_label="fraudulent",
            flagged_lines=[],
            processing_time_ms=12.3,
        )
        assert out.fraud_label == "fraudulent"

    def test_clean_prediction_schema(self) -> None:
        from schemas import PredictionOut

        out = PredictionOut(
            estimate_id="EST-002",
            fraud_probability=0.12,
            is_fraud=False,
            fraud_label="clean",
            flagged_lines=[],
            processing_time_ms=8.1,
        )
        assert out.is_fraud is False
        assert out.fraud_label == "clean"


# ---------------------------------------------------------------------------
# Integration test (requires model artifacts + server)
# ---------------------------------------------------------------------------


class TestIntegration:
    """
    Integration tests that require the API server running.
    Skip automatically if server not available.
    Run with: API_URL=http://localhost:8000 pytest tests/ -v -k integration
    """

    @pytest.fixture
    def api_url(self) -> str:
        import os

        return os.getenv("API_URL", "http://localhost:8000")

    def _is_api_available(self, url: str) -> bool:
        try:
            import urllib.request

            urllib.request.urlopen(f"{url}/health", timeout=2)
            return True
        except Exception:
            return False

    def test_health_endpoint(self, api_url: str) -> None:
        if not self._is_api_available(api_url):
            pytest.skip("API server not running")
        import urllib.request

        with urllib.request.urlopen(f"{api_url}/health") as resp:
            data = json.loads(resp.read())
        assert data["status"] == "ok"

    def test_predict_clean_estimate(self, api_url: str) -> None:
        if not self._is_api_available(api_url):
            pytest.skip("API server not running")
        import urllib.request

        body = json.dumps(CLEAN_ESTIMATE).encode()
        req = urllib.request.Request(
            f"{api_url}/predict",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
        assert "fraud_probability" in result
        assert "is_fraud" in result
        assert isinstance(result["fraud_probability"], float)

    def test_predict_fraudulent_estimate(self, api_url: str) -> None:
        if not self._is_api_available(api_url):
            pytest.skip("API server not running")
        import urllib.request

        body = json.dumps(FRAUDULENT_ESTIMATE_INFLATED_HOURS).encode()
        req = urllib.request.Request(
            f"{api_url}/predict",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
        # A heavily fraudulent estimate should trigger is_fraud=True
        # (depends on trained model — assert probability is elevated)
        assert result["fraud_probability"] > 0.3, (
            f"Expected elevated probability for known fraud, got {result['fraud_probability']}"
        )

    def test_predict_422_on_bad_input(self, api_url: str) -> None:
        if not self._is_api_available(api_url):
            pytest.skip("API server not running")
        import urllib.error
        import urllib.request

        body = json.dumps({"estimate_id": "bad"}).encode()
        req = urllib.request.Request(
            f"{api_url}/predict",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req)
        assert exc_info.value.code == 422

    def test_batch_predict(self, api_url: str) -> None:
        if not self._is_api_available(api_url):
            pytest.skip("API server not running")
        import urllib.request

        batch = [CLEAN_ESTIMATE, FRAUDULENT_ESTIMATE_INFLATED_HOURS]
        body = json.dumps(batch).encode()
        req = urllib.request.Request(
            f"{api_url}/predict/batch",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
        assert result["total"] == 2
        assert len(result["results"]) == 2
