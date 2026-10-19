from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from ..models import CheckResult, CheckStatus, ExtractedFields, ImageQuality, QualityStatus
from .barcode import BarcodeScan, normalize_gtin, validate_gtin
from .field_parser import display_date, parse_date
from .registry import RegistryAdapter, RegistryUnavailable
from .scoring import ScoringRules
from .text import similarity
from .visual import VisualAnalysis, print_quality_status


def _iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        try:
            return date.fromisoformat(value + "-01")
        except ValueError:
            return parse_date(value)


def _last_day(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def _months_between(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month)


def check_photo_quality(
    quality: dict[str, ImageQuality],
    overall: QualityStatus,
    rules: ScoringRules,
) -> CheckResult:
    status = {
        QualityStatus.OK: CheckStatus.PASS,
        QualityStatus.WARN: CheckStatus.WARN,
        QualityStatus.FAIL: CheckStatus.FAIL,
    }[overall]
    issues = [
        {"view": view, "code": issue.code, "severity": issue.severity}
        for view, item in quality.items()
        for issue in item.issues
    ]
    failing_views = [view for view, item in quality.items() if item.status == QualityStatus.FAIL]
    warning_views = [view for view, item in quality.items() if item.status == QualityStatus.WARN]
    if status == CheckStatus.FAIL:
        explanation_key = "checks.photo_quality.failed"
        explanation_en = "One or more photos are too poor to analyse. Retake them with the specific tips below."
    elif status == CheckStatus.WARN:
        explanation_key = "checks.photo_quality.warnings"
        explanation_en = "Photos are usable, but some quality warnings may reduce confidence."
    else:
        explanation_key = "checks.photo_quality.passed"
        explanation_en = "Photos are sharp enough and well lit for packaging screening."
    return rules.make_check(
        "photo_quality",
        status,
        explanation_key,
        explanation_en,
        "checks.photo_quality.why",
        confidence=0.98,
        params={"failing_views": failing_views, "warning_views": warning_views},
        metrics={"issues": issues, "status": overall.value},
    )


def check_expiry(
    expiry_raw: str | None,
    ocr_confidence: float,
    rules: ScoringRules,
    today: date | None = None,
) -> CheckResult:
    today = today or date.today()
    expiring_days = int(rules.thresholds.get("expiring_soon_days", 90))
    if not expiry_raw:
        return rules.make_check(
            "expiry",
            CheckStatus.FAIL,
            "checks.expiry.missing",
            "No expiry date was found. A medicine carton without a readable expiry date should be verified.",
            "checks.expiry.why",
            confidence=0.75,
            metrics={"expiry_date": None},
        )
    expiry = _iso_date(expiry_raw)
    if not expiry:
        return rules.make_check(
            "expiry",
            CheckStatus.FAIL,
            "checks.expiry.unreadable",
            "An expiry date was found but it could not be parsed reliably.",
            "checks.expiry.why",
            confidence=0.55,
            params={"value": expiry_raw},
            metrics={"expiry_date": expiry_raw},
        )
    end_of_month = _last_day(expiry.year, expiry.month)
    days_left = (end_of_month - today).days
    display = display_date(expiry.isoformat())
    if days_left < 0:
        return rules.make_check(
            "expiry",
            CheckStatus.FAIL,
            "checks.expiry.expired",
            f"The printed expiry date ({display}) is in the past.",
            "checks.expiry.why",
            confidence=0.93,
            params={"date": display, "days_left": days_left},
            metrics={"expiry_date": expiry.isoformat(), "days_left": days_left},
        )
    if days_left <= expiring_days:
        return rules.make_check(
            "expiry",
            CheckStatus.WARN,
            "checks.expiry.expiring_soon",
            f"The printed expiry date ({display}) is close. Confirm the pack date with a pharmacist.",
            "checks.expiry.why",
            confidence=0.9,
            params={"date": display, "days_left": days_left},
            metrics={"expiry_date": expiry.isoformat(), "days_left": days_left},
        )
    return rules.make_check(
        "expiry",
        CheckStatus.PASS,
        "checks.expiry.valid",
        f"The printed expiry date ({display}) is in the future.",
        "checks.expiry.why",
        confidence=min(0.95, 0.7 + ocr_confidence * 0.25),
        params={"date": display, "days_left": days_left},
        metrics={"expiry_date": expiry.isoformat(), "days_left": days_left},
    )


def check_dates(
    mfg_raw: str | None,
    expiry_raw: str | None,
    rules: ScoringRules,
) -> CheckResult:
    if not mfg_raw:
        return rules.make_check(
            "dates",
            CheckStatus.WARN,
            "checks.dates.missing_mfg",
            "No manufacturing date was found, so the shelf life could not be checked.",
            "checks.dates.why",
            confidence=0.7,
            metrics={"manufacturing_date": None, "expiry_date": expiry_raw},
        )
    mfg = _iso_date(mfg_raw)
    expiry = _iso_date(expiry_raw)
    if not mfg:
        return rules.make_check(
            "dates",
            CheckStatus.WARN,
            "checks.dates.unreadable_mfg",
            "The manufacturing date could not be parsed reliably.",
            "checks.dates.why",
            confidence=0.55,
            params={"value": mfg_raw},
            metrics={"manufacturing_date": mfg_raw},
        )
    if not expiry:
        return rules.make_check(
            "dates",
            CheckStatus.UNKNOWN,
            "checks.dates.missing_exp",
            "The expiry date could not be parsed, so the manufacturing-to-expiry sequence was not checked.",
            "checks.dates.why",
            confidence=0.4,
            metrics={"manufacturing_date": mfg.isoformat(), "expiry_date": expiry_raw},
        )
    shelf_life = _months_between(mfg, expiry)
    min_months = int(rules.thresholds.get("min_shelf_life_months", 6))
    max_months = int(rules.thresholds.get("max_shelf_life_months", 60))
    metrics = {
        "manufacturing_date": mfg.isoformat(),
        "expiry_date": expiry.isoformat(),
        "shelf_life_months": shelf_life,
    }
    if mfg >= expiry:
        return rules.make_check(
            "dates",
            CheckStatus.FAIL,
            "checks.dates.order",
            "The manufacturing date is not before the expiry date.",
            "checks.dates.why",
            confidence=0.92,
            params={"mfg": display_date(mfg.isoformat()), "exp": display_date(expiry.isoformat())},
            metrics=metrics,
        )
    if shelf_life < min_months:
        return rules.make_check(
            "dates",
            CheckStatus.WARN,
            "checks.dates.short_shelf_life",
            f"The printed shelf life is unusually short ({shelf_life} months).",
            "checks.dates.why",
            confidence=0.8,
            params={"months": shelf_life},
            metrics=metrics,
        )
    if shelf_life > max_months:
        return rules.make_check(
            "dates",
            CheckStatus.WARN,
            "checks.dates.long_shelf_life",
            f"The printed shelf life is unusually long ({shelf_life} months).",
            "checks.dates.why",
            confidence=0.8,
            params={"months": shelf_life},
            metrics=metrics,
        )
    return rules.make_check(
        "dates",
        CheckStatus.PASS,
        "checks.dates.valid",
        f"The manufacturing and expiry dates are in a plausible order ({shelf_life}-month shelf life).",
        "checks.dates.why",
        confidence=0.85,
        params={"months": shelf_life},
        metrics=metrics,
    )


def _batch_variants(batch: str) -> set[str]:
    from itertools import product

    base = re.sub(r"\s+", "", batch.upper())
    substitutions = {
        "0": "O", "O": "0", "1": "I", "I": "1", "5": "S",
        "S": "5", "8": "B", "B": "8", "2": "Z", "Z": "2",
    }
    groups = [[char, substitutions[char]] if char in substitutions else [char] for char in base]
    total = 1
    for group in groups:
        total *= len(set(group))
    if total > 512:
        variants = {base}
        for old, new in substitutions.items():
            if old in base:
                variants.add(base.replace(old, new))
        return variants
    variants = set()
    for combination in product(*[sorted(set(group)) for group in groups]):
        variants.add("".join(combination))
    return variants


def check_batch_format(
    batch: str | None,
    reference: dict | None,
    rules: ScoringRules,
) -> CheckResult:
    if not batch:
        return rules.make_check(
            "batch_format",
            CheckStatus.FAIL,
            "checks.batch_format.missing",
            "No batch number was found on the packaging.",
            "checks.batch_format.why",
            confidence=0.8,
            metrics={"batch_number": None},
        )
    if reference and reference.get("batch_regex"):
        pattern = str(reference["batch_regex"])
        try:
            matches = any(re.fullmatch(pattern, variant, flags=re.IGNORECASE) for variant in _batch_variants(batch))
        except re.error:
            return rules.make_check(
                "batch_format",
                CheckStatus.UNKNOWN,
                "checks.batch_format.invalid_reference_rule",
                "The reference batch format rule is invalid, so this check could not run.",
                "checks.batch_format.why",
                confidence=0.3,
                metrics={"batch_number": batch},
            )
        if matches:
            corrected = not re.fullmatch(pattern, batch, flags=re.IGNORECASE)
            key = "checks.batch_format.matches_ocr" if corrected else "checks.batch_format.matches"
            text_en = (
                "The batch number matches the reference format after common OCR character corrections."
                if corrected
                else "The batch number matches the batch format recorded for this product."
            )
            return rules.make_check(
                "batch_format",
                CheckStatus.PASS,
                key,
                text_en,
                "checks.batch_format.why",
                confidence=0.82,
                params={"batch": batch, "pattern": pattern},
                metrics={"batch_number": batch, "pattern": pattern, "matches": True, "ocr_corrected": corrected},
            )
        return rules.make_check(
            "batch_format",
            CheckStatus.FAIL,
            "checks.batch_format.mismatch",
            "The printed batch number does not match the batch format recorded for this product.",
            "checks.batch_format.why",
            confidence=0.8,
            params={"batch": batch, "pattern": pattern},
            metrics={"batch_number": batch, "pattern": pattern, "matches": False},
        )
    plausible = bool(re.fullmatch(r"[A-Z0-9][A-Z0-9\-/.]{2,31}", batch.upper()))
    if plausible:
        return rules.make_check(
            "batch_format",
            CheckStatus.PASS,
            "checks.batch_format.plausible",
            "A batch number is present and looks plausible. No reference batch format is available for this product.",
            "checks.batch_format.why",
            confidence=0.55,
            params={"batch": batch},
            metrics={"batch_number": batch, "pattern": None, "matches": None},
        )
    return rules.make_check(
        "batch_format",
        CheckStatus.WARN,
        "checks.batch_format.unusual",
        "A batch number is present but its format looks unusual. No reference format is available.",
        "checks.batch_format.why",
        confidence=0.5,
        params={"batch": batch},
        metrics={"batch_number": batch, "pattern": None, "matches": None},
    )


def check_barcode(
    scan: BarcodeScan,
    ocr_barcode: str | None,
    reference: dict | None,
    rules: ScoringRules,
) -> CheckResult:
    chosen = scan.chosen
    fallback = normalize_gtin(ocr_barcode) if ocr_barcode else None
    if not chosen and not fallback:
        return rules.make_check(
            "barcode",
            CheckStatus.WARN,
            "checks.barcode.missing",
            "No barcode or DataMatrix was decoded from these photos.",
            "checks.barcode.why",
            confidence=0.65,
            metrics={"barcode": None},
        )

    if chosen:
        value = chosen.normalized or chosen.value
        valid = chosen.valid
        source = f"decoded ({chosen.format})"
        confidence = 0.92
    else:
        value = fallback
        valid = validate_gtin(fallback) if fallback else False
        source = "printed GTIN digits read by OCR"
        confidence = 0.62

    metrics: dict[str, Any] = {
        "barcode": value,
        "valid_checksum": valid,
        "decoded_codes": [
            {"value": code.value, "format": code.format, "valid": code.valid, "view": code.view}
            for code in scan.codes
        ],
        "source": source,
    }

    if value and len(re.sub(r"\D", "", value)) in {8, 12, 13, 14} and not valid:
        return rules.make_check(
            "barcode",
            CheckStatus.FAIL,
            "checks.barcode.invalid_checksum",
            "The barcode number is not valid: its GTIN check digit does not match.",
            "checks.barcode.why",
            confidence=confidence,
            params={"barcode": value},
            metrics=metrics,
        )

    if reference and reference.get("barcode_prefix") and value:
        expected = re.sub(r"\D", "", str(reference["barcode_prefix"]))
        actual = re.sub(r"\D", "", value)
        matches_prefix = actual.startswith(expected)
        metrics["prefix"] = actual[: max(7, len(expected))]
        metrics["expected_prefix"] = expected
        metrics["prefix_matches"] = matches_prefix
        if not matches_prefix:
            return rules.make_check(
                "barcode",
                CheckStatus.FAIL,
                "checks.barcode.prefix_mismatch",
                "The barcode company prefix does not match the reference packaging for this product.",
                "checks.barcode.why",
                confidence=confidence,
                params={"barcode": value, "expected": expected},
                metrics=metrics,
            )
        return rules.make_check(
            "barcode",
            CheckStatus.PASS,
            "checks.barcode.matches_reference",
            "The barcode check digit is valid and its company prefix matches the reference packaging.",
            "checks.barcode.why",
            confidence=confidence,
            params={"barcode": value},
            metrics=metrics,
        )

    if value and valid:
        return rules.make_check(
            "barcode",
            CheckStatus.PASS,
            "checks.barcode.valid_no_reference",
            "The barcode check digit is valid. No reference prefix is available to compare.",
            "checks.barcode.why",
            confidence=min(confidence, 0.75),
            params={"barcode": value},
            metrics=metrics,
        )
    return rules.make_check(
        "barcode",
        CheckStatus.WARN,
        "checks.barcode.non_gtin",
        "A code was decoded, but it is not a GTIN/EAN number that can be checksum-validated.",
        "checks.barcode.why",
        confidence=0.6,
        metrics=metrics,
    )


def check_registration(
    registration: str | None,
    reference: dict | None,
    registry: RegistryAdapter,
    rules: ScoringRules,
) -> CheckResult:
    metrics: dict[str, Any] = {
        "registration_number": registration,
        "registry_provider": registry.name,
        "registry_is_demo": registry.is_demo,
    }
    if not registration:
        return rules.make_check(
            "registration",
            CheckStatus.FAIL,
            "checks.registration.missing",
            "No registration number was found on the packaging.",
            "checks.registration.why",
            confidence=0.8,
            metrics=metrics,
        )
    if reference and reference.get("reg_regex"):
        pattern = str(reference["reg_regex"])
        try:
            format_ok = bool(re.fullmatch(pattern, registration, flags=re.IGNORECASE))
        except re.error:
            format_ok = True
        metrics["format_matches_reference"] = format_ok
    else:
        format_ok = True
        metrics["format_matches_reference"] = None

    if not registry.available:
        return rules.make_check(
            "registration",
            CheckStatus.UNKNOWN,
            "checks.registration.registry_unavailable",
            "The registration number is present, but no real registry adapter is configured.",
            "checks.registration.why",
            confidence=0.4,
            params={"registration": registration, "provider": registry.name},
            metrics=metrics,
        )
    try:
        record = registry.lookup(registration)
    except RegistryUnavailable as error:
        metrics["registry_error"] = str(error)
        return rules.make_check(
            "registration",
            CheckStatus.UNKNOWN,
            "checks.registration.registry_unavailable",
            "The registration number is present, but the registry could not be queried.",
            "checks.registration.why",
            confidence=0.35,
            params={"registration": registration, "provider": registry.name},
            metrics=metrics,
        )

    if not record:
        return rules.make_check(
            "registration",
            CheckStatus.FAIL,
            "checks.registration.not_found_demo" if registry.is_demo else "checks.registration.not_found",
            (
                "The registration number was not found in the local DEMO registry (which is not real DRAP data)."
                if registry.is_demo
                else "The registration number was not found in the configured registry."
            ),
            "checks.registration.why",
            confidence=0.7,
            params={"registration": registration, "demo": registry.is_demo},
            metrics=metrics,
        )

    metrics.update(
        {
            "registry_product": record.product_name,
            "registry_manufacturer": record.manufacturer,
            "registry_status": record.status,
            "registry_note": record.note,
        }
    )
    name_warning = False
    if reference:
        name_warning = similarity(record.product_name, reference.get("name")) < 0.72

    if not format_ok or name_warning:
        return rules.make_check(
            "registration",
            CheckStatus.WARN,
            "checks.registration.found_but_unexpected",
            (
                "The registration number was found, but its format or registered product name "
                "does not fully match this packaging."
            ),
            "checks.registration.why",
            confidence=0.72,
            params={
                "registration": registration,
                "registry_name": record.product_name,
                "demo": registry.is_demo,
            },
            metrics=metrics,
        )
    return rules.make_check(
        "registration",
        CheckStatus.PASS,
        "checks.registration.found_demo" if registry.is_demo else "checks.registration.found",
        (
            f"The registration number appears in the local DEMO registry (not real DRAP data) as {record.product_name}."
            if registry.is_demo
            else f"The registration number was found in the configured registry as {record.product_name}."
        ),
        "checks.registration.why",
        confidence=0.82 if registry.is_demo else 0.9,
        params={
            "registration": registration,
            "registry_name": record.product_name,
            "registry_manufacturer": record.manufacturer,
            "demo": registry.is_demo,
        },
        metrics=metrics,
    )


def check_spelling(
    fields: ExtractedFields,
    reference: dict | None,
    ocr_confidence: float,
    rules: ScoringRules,
) -> CheckResult:
    if not reference:
        return rules.make_check(
            "spelling",
            CheckStatus.UNKNOWN,
            "checks.spelling.no_reference",
            "No reference name is available, so product-name spelling could not be compared.",
            "checks.spelling.why",
            confidence=0.25,
            metrics={"product_similarity": None},
        )
    reference_name = reference.get("name") or ""
    aliases = list(reference.get("aliases") or [])
    product_name = fields.product_name
    product_similarity = max(
        [similarity(product_name, reference_name)]
        + [similarity(product_name, alias) for alias in aliases]
    ) if product_name else 0.0
    manufacturer_similarity = similarity(fields.manufacturer, reference.get("manufacturer")) if fields.manufacturer else None

    metrics = {
        "ocr_product_name": product_name,
        "reference_product_name": reference_name,
        "product_similarity": round(product_similarity, 4),
        "ocr_manufacturer": fields.manufacturer,
        "reference_manufacturer": reference.get("manufacturer"),
        "manufacturer_similarity": round(manufacturer_similarity, 4) if manufacturer_similarity is not None else None,
    }
    params = {
        "ocr_name": product_name or "—",
        "reference_name": reference_name,
        "similarity": int(round(product_similarity * 100)),
    }

    if not product_name:
        manufacturer_status = "pass"
        if manufacturer_similarity is not None and manufacturer_similarity < 0.8:
            manufacturer_status = "warn"
        return rules.make_check(
            "spelling",
            CheckStatus.WARN if manufacturer_status == "warn" else CheckStatus.UNKNOWN,
            "checks.spelling.product_missing",
            "The product name could not be read confidently, so spelling was not fully compared.",
            "checks.spelling.why",
            confidence=0.45,
            params=params,
            metrics=metrics,
        )

    if product_similarity >= 0.9 and (manufacturer_similarity is None or manufacturer_similarity >= 0.85):
        return rules.make_check(
            "spelling",
            CheckStatus.PASS,
            "checks.spelling.matches",
            "The product name and manufacturer closely match the reference packaging.",
            "checks.spelling.why",
            confidence=min(0.95, 0.6 + ocr_confidence * 0.35),
            params=params,
            metrics=metrics,
        )
    if product_similarity < 0.82:
        return rules.make_check(
            "spelling",
            CheckStatus.FAIL,
            "checks.spelling.product_mismatch",
            f'The printed name "{product_name}" is substantially different from the reference "{reference_name}".',
            "checks.spelling.why",
            confidence=min(0.92, 0.55 + ocr_confidence * 0.35),
            params=params,
            metrics=metrics,
        )
    if manufacturer_similarity is not None and manufacturer_similarity < 0.7:
        return rules.make_check(
            "spelling",
            CheckStatus.WARN,
            "checks.spelling.manufacturer_mismatch",
            "The manufacturer name differs noticeably from the reference packaging.",
            "checks.spelling.why",
            confidence=0.7,
            params={
                **params,
                "ocr_manufacturer": fields.manufacturer,
                "reference_manufacturer": reference.get("manufacturer"),
                "manufacturer_similarity": int(round(manufacturer_similarity * 100)),
            },
            metrics=metrics,
        )
    return rules.make_check(
        "spelling",
        CheckStatus.WARN,
        "checks.spelling.close_but_differs",
        f'The printed name "{product_name}" is close to, but not an exact match for, the reference "{reference_name}".',
        "checks.spelling.why",
        confidence=min(0.9, 0.5 + ocr_confidence * 0.35),
        params=params,
        metrics=metrics,
    )


def check_visual(
    visual: VisualAnalysis | None,
    reference: dict | None,
    rules: ScoringRules,
) -> CheckResult:
    if not reference:
        return rules.make_check(
            "visual",
            CheckStatus.UNKNOWN,
            "checks.visual.no_reference",
            "No reference packaging is available, so visual similarity could not be compared.",
            "checks.visual.why",
            confidence=0.2,
            metrics={"status": "unknown"},
        )
    if not visual:
        return rules.make_check(
            "visual",
            CheckStatus.UNKNOWN,
            "checks.visual.comparison_unavailable",
            "The visual comparison could not be completed for these photos.",
            "checks.visual.why",
            confidence=0.3,
            metrics={"status": "unknown"},
        )
    status = {
        "pass": CheckStatus.PASS,
        "warn": CheckStatus.WARN,
        "fail": CheckStatus.FAIL,
    }.get(visual.status, CheckStatus.UNKNOWN)
    front = visual.comparisons.get("front")
    similarity_value = front.combined_similarity if front else visual.metrics.get("min_combined_similarity", 0.0)
    region_count = sum(len(item.regions) for item in visual.comparisons.values())
    params = {
        "similarity": int(round(float(similarity_value or 0) * 100)),
        "regions": region_count,
    }
    if status == CheckStatus.FAIL:
        explanation_key = "checks.visual.fail"
        explanation_en = "The packaging artwork differs substantially from the reference image."
    elif status == CheckStatus.WARN:
        explanation_key = "checks.visual.warn"
        explanation_en = "The packaging mostly resembles the reference, but some visual elements differ."
    else:
        explanation_key = "checks.visual.pass"
        explanation_en = "The packaging artwork closely resembles the reference image."
    confidence = 0.82
    if front and front.alignment != "homography":
        confidence = 0.55
    return rules.make_check(
        "visual",
        status,
        explanation_key,
        explanation_en,
        "checks.visual.why",
        confidence=confidence,
        params=params,
        metrics=visual.metrics,
    )


def check_print_quality(
    visual: VisualAnalysis | None,
    reference: dict | None,
    rules: ScoringRules,
) -> CheckResult:
    if not reference:
        return rules.make_check(
            "print_quality",
            CheckStatus.UNKNOWN,
            "checks.print_quality.no_reference",
            "No reference packaging is available to compare print sharpness.",
            "checks.print_quality.why",
            confidence=0.25,
            metrics={},
        )
    status, metrics = print_quality_status(visual)
    if status == "unknown":
        return rules.make_check(
            "print_quality",
            CheckStatus.UNKNOWN,
            "checks.print_quality.unavailable",
            "Print sharpness could not be compared with the reference.",
            "checks.print_quality.why",
            confidence=0.3,
            metrics=metrics,
        )
    if status == "warn":
        return rules.make_check(
            "print_quality",
            CheckStatus.WARN,
            "checks.print_quality.warn",
            "Printed text looks less sharp than the reference. This is a warning only, not proof of tampering.",
            "checks.print_quality.why",
            confidence=0.65,
            params={"ratio": int(round(float(metrics.get("min_sharpness_ratio", 0)) * 100))},
            metrics=metrics,
        )
    return rules.make_check(
        "print_quality",
        CheckStatus.PASS,
        "checks.print_quality.pass",
        "Print sharpness is broadly similar to the reference packaging.",
        "checks.print_quality.why",
        confidence=0.7,
        params={"ratio": int(round(float(metrics.get("min_sharpness_ratio", 1)) * 100))},
        metrics=metrics,
    )


@dataclass
class CheckContext:
    fields: ExtractedFields
    reference: dict | None
    registry: RegistryAdapter
    barcode: BarcodeScan
    visual: VisualAnalysis | None
    quality: dict[str, ImageQuality]
    quality_status: QualityStatus
    ocr_confidence: float
    today: date


def run_checks(context: CheckContext, rules: ScoringRules) -> list[CheckResult]:
    return [
        check_photo_quality(context.quality, context.quality_status, rules),
        check_expiry(context.fields.expiry_date, context.ocr_confidence, rules, context.today),
        check_dates(
            context.fields.manufacturing_date,
            context.fields.expiry_date,
            rules,
        ),
        check_batch_format(context.fields.batch_number, context.reference, rules),
        check_barcode(
            context.barcode,
            context.fields.barcode,
            context.reference,
            rules,
        ),
        check_registration(
            context.fields.registration_number,
            context.reference,
            context.registry,
            rules,
        ),
        check_spelling(context.fields, context.reference, context.ocr_confidence, rules),
        check_visual(context.visual, context.reference, rules),
        check_print_quality(context.visual, context.reference, rules),
    ]
