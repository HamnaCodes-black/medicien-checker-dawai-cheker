from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.services.checks import (
    check_barcode,
    check_batch_format,
    check_dates,
    check_expiry,
    check_photo_quality,
    check_print_quality,
    check_registration,
    check_spelling,
    check_visual,
)
from app.services.registry import RegistryRecord
from app.services.scoring import load_scoring_rules
from app.services.barcode import BarcodeScan, DetectedCode
from app.models import ExtractedFields
from app.services.visual import VisualAnalysis
from app.models import ImageQuality, QualityStatus
from app.services.checks import CheckContext, run_checks

RULES = load_scoring_rules(Path(__file__).resolve().parents[1] / "app" / "config" / "scoring.json")
TODAY = date(2026, 10, 19)

REFERENCE = {
    "id": "fevra-plus",
    "name": "Fevra+",
    "aliases": ["Fevra Plus"],
    "manufacturer": "Northstar Pharma (Pvt) Ltd",
    "reg_no": "DEMO-REG-1001",
    "reg_regex": r"^DEMO-REG-\d{4}$",
    "batch_regex": r"^DEMO-FV-\d{4}-[A-Z]\d{2}$",
    "barcode": "2001001000011",
    "barcode_prefix": "2001001",
    "demo": True,
}


class DemoRegistry:
    name = "test_demo"
    is_demo = True
    available = True

    def lookup(self, registration_number: str):
        if registration_number == "DEMO-REG-1001":
            return RegistryRecord(
                registration_number="DEMO-REG-1001",
                product_name="Fevra+",
                manufacturer="Northstar Pharma (Pvt) Ltd",
                status="Active (DEMO)",
                note="DEMO",
                demo=True,
            )
        return None


class UnavailableRegistry:
    name = "drap_unconfigured"
    is_demo = False
    available = False

    def lookup(self, registration_number: str):
        raise RuntimeError("not configured")


def barcode_scan(value="2001001000011", valid=True) -> BarcodeScan:
    code = DetectedCode(
        value=value,
        format="EAN13",
        valid=valid,
        view="back",
        normalized=value if len(value) == 13 else None,
    )
    return BarcodeScan(codes=[code], chosen=code, engine="test")


def quality(status=QualityStatus.OK, view="front") -> ImageQuality:
    return ImageQuality(
        view=view,
        width=1200,
        height=1600,
        status=status,
        blur_score=300.0,
        brightness=160.0,
        glare_ratio=0.1,
        contrast=60.0,
        issues=[],
    )


def visual(status="pass") -> VisualAnalysis:
    return VisualAnalysis(
        status=status,
        comparisons={},
        metrics={
            "status": status,
            "min_sharpness_ratio": 0.9 if status == "pass" else 0.1,
            "front_color_distance": 0.0,
            "front_ssim": 0.95 if status == "pass" else 0.4,
            "min_combined_similarity": 0.9 if status == "pass" else 0.4,
        },
    )


def test_expiry_pass_warn_fail_and_missing():
    assert check_expiry("2027-11", 0.9, RULES, TODAY).status.value == "pass"
    soon = check_expiry("2026-11", 0.9, RULES, TODAY)
    assert soon.status.value == "warn"
    assert soon.params["days_left"] <= 90
    assert check_expiry("2024-01", 0.9, RULES, TODAY).status.value == "fail"
    assert check_expiry(None, 0.9, RULES, TODAY).status.value == "fail"


def test_dates_order_shelf_life_and_missing():
    assert check_dates("2025-03", "2027-11", RULES).status.value == "pass"
    assert check_dates("2027-01", "2026-01", RULES).status.value == "fail"
    assert check_dates("2025-03", None, RULES).status.value == "unknown"
    assert check_dates(None, "2027-01", RULES).status.value == "warn"


def test_batch_format_match_ocr_correction_and_mismatch():
    assert check_batch_format("DEMO-FV-2025-A17", REFERENCE, RULES).status.value == "pass"
    corrected = check_batch_format("DEM0-FV-2025-A17", REFERENCE, RULES)
    assert corrected.status.value == "pass"
    assert corrected.metrics["ocr_corrected"] is True
    assert check_batch_format("FV2025A17", REFERENCE, RULES).status.value == "fail"
    assert check_batch_format(None, REFERENCE, RULES).status.value == "fail"


def test_barcode_valid_prefix_invalid_checksum_and_missing():
    assert check_barcode(barcode_scan(), None, REFERENCE, RULES).status.value == "pass"
    invalid = check_barcode(barcode_scan("2001001000012", False), None, REFERENCE, RULES)
    assert invalid.status.value == "fail"
    assert invalid.explanation_key.endswith("invalid_checksum")
    assert check_barcode(BarcodeScan(), None, REFERENCE, RULES).status.value == "warn"
    other = check_barcode(barcode_scan("2009999000013", True), None, REFERENCE, RULES)
    assert other.status.value == "fail"
    assert other.explanation_key.endswith("prefix_mismatch")


def test_registration_found_missing_not_found_and_unavailable():
    found = check_registration("DEMO-REG-1001", REFERENCE, DemoRegistry(), RULES)
    assert found.status.value == "pass"
    assert found.params["demo"] is True
    assert check_registration(None, REFERENCE, DemoRegistry(), RULES).status.value == "fail"
    assert check_registration("DEMO-REG-9999", REFERENCE, DemoRegistry(), RULES).status.value == "fail"
    unavailable = check_registration("DEMO-REG-1001", REFERENCE, UnavailableRegistry(), RULES)
    assert unavailable.status.value == "unknown"


def test_spelling_catches_typo_and_missing_reference():
    fields = ExtractedFields(
        product_name="Fevrraa+",
        manufacturer="Northstar Pharma (Pvt) Ltd",
    )
    result = check_spelling(fields, REFERENCE, 0.9, RULES)
    assert result.status.value == "fail"
    assert result.metrics["product_similarity"] < 0.82

    exact = check_spelling(
        ExtractedFields(product_name="Fevra+", manufacturer="Northstar Pharma (Pvt) Ltd"),
        REFERENCE,
        0.9,
        RULES,
    )
    assert exact.status.value == "pass"
    assert check_spelling(fields, None, 0.9, RULES).status.value == "unknown"


def test_visual_status_mapping_and_no_reference():
    assert check_visual(visual("pass"), REFERENCE, RULES).status.value == "pass"
    assert check_visual(visual("warn"), REFERENCE, RULES).status.value == "warn"
    assert check_visual(visual("fail"), REFERENCE, RULES).status.value == "fail"
    assert check_visual(None, None, RULES).status.value == "unknown"


def test_print_quality_never_fails():
    assert check_print_quality(visual("fail"), REFERENCE, RULES).status.value == "warn"
    assert check_print_quality(visual("pass"), REFERENCE, RULES).status.value == "pass"
    assert check_print_quality(None, None, RULES).status.value == "unknown"


def test_photo_quality_passes_failures_through():
    ok = check_photo_quality({"front": quality()}, QualityStatus.OK, RULES)
    assert ok.status.value == "pass"
    warn = check_photo_quality(
        {"front": quality(QualityStatus.WARN)}, QualityStatus.WARN, RULES
    )
    assert warn.status.value == "warn"
    failed = check_photo_quality(
        {"front": quality(QualityStatus.FAIL)}, QualityStatus.FAIL, RULES
    )
    assert failed.status.value == "fail"


def test_weights_sum_to_100_and_score_maps_to_checks():
    assert sum(RULES.weights.values()) == 100
    fields = ExtractedFields(
        product_name="Fevrraa+",
        strength="500 mg",
        manufacturer="Northstar Pharma (Pvt) Ltd",
        registration_number="DEMO-REG-1001",
        batch_number="DEMO-FV-2025-A17",
        manufacturing_date="2025-03",
        expiry_date="2027-11",
        barcode="2001001000011",
    )
    context = CheckContext(
        fields=fields,
        reference=REFERENCE,
        registry=DemoRegistry(),
        barcode=barcode_scan(),
        visual=visual("pass"),
        quality={"front": quality(), "back": quality(view="back"), "batch": quality(view="batch")},
        quality_status=QualityStatus.OK,
        ocr_confidence=0.9,
        today=TODAY,
    )
    checks = run_checks(context, RULES)
    spelling = next(check for check in checks if check.id == "spelling")
    assert spelling.status.value == "fail"
    assert spelling.risk_points == spelling.weight
    assert RULES.risk_score(checks) == sum(check.risk_points for check in checks)
    verdict = RULES.decide_verdict(checks, RULES.risk_score(checks), QualityStatus.OK, True)
    assert verdict.value == "suspicious"
