from __future__ import annotations

import time
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from PIL import Image

from ..config import Settings
from ..models import (
    AnalysisResult,
    CheckStatus,
    Confidence,
    ExtractedFields,
    FieldOverrides,
    Notice,
    QualityStatus,
    ReferenceMatch,
    RegistrySummary,
    Verdict,
)
from .barcode import BarcodeScan, DetectedCode, normalize_gtin, scan_barcodes, validate_gtin
from .checks import CheckContext, run_checks
from .field_parser import extract_fields_from_text, merge_view_fields
from .image_quality import assess_quality, overall_quality_status, quality_to_metrics
from .ocr import OCRResult, OCRService
from .reference_store import ReferenceStore
from .registry import RegistryAdapter, get_registry_adapter
from .scoring import ScoringRules, load_scoring_rules
from .text import normalize_text
from .vision_llm import refine_fields_with_vision_llm
from .visual import analyze_visuals


MANDATORY_VIEWS = ("front", "back", "batch")
ALL_VIEWS = ("front", "back", "batch", "blister")


def _combined_ocr_confidence(results: list[OCRResult]) -> float:
    blocks = [block for result in results for block in result.blocks if block.text.strip()]
    if not blocks:
        return 0.0
    return round(sum(block.confidence for block in blocks) / len(blocks), 4)


def _ocr_text(results: dict[str, OCRResult]) -> str:
    return "\n".join(result.text for result in results.values() if result.text)


def _parse_views(results: dict[str, OCRResult]) -> dict[str, dict]:
    return {
        view: extract_fields_from_text(result.text, result.blocks_as_dicts())
        for view, result in results.items()
    }


def _merge_fields(results: dict[str, OCRResult]) -> ExtractedFields:
    parsed = _parse_views(results)
    merged = merge_view_fields(parsed)
    return ExtractedFields(**merged)


def _apply_overrides(
    fields: ExtractedFields,
    overrides: FieldOverrides | None,
) -> tuple[ExtractedFields, list[str]]:
    if overrides is None:
        return fields, []
    updated = fields.model_copy()
    applied: list[str] = []
    for field_name in overrides.model_fields_set:
        value = getattr(overrides, field_name)
        if isinstance(value, str):
            value = value.strip() or None
        setattr(updated, field_name, value)
        applied.append(field_name)
    return updated, applied


def _resolve_reference(
    store: ReferenceStore,
    fields: ExtractedFields,
    scan: BarcodeScan,
    ocr_text: str,
    explicit_reference_id: str | None,
) -> tuple[dict | None, ReferenceMatch | None]:
    if explicit_reference_id:
        reference = store.get(explicit_reference_id)
        if reference:
            return reference, ReferenceMatch(
                matched_by="explicit",
                score=1.0,
                label_key="reference.match.explicit",
                detail=reference.get("name"),
            )
    barcode_candidate = fields.barcode or scan.normalized or scan.raw_value
    barcode_match = store.by_barcode(barcode_candidate)
    if barcode_match:
        reference, score = barcode_match
        return reference, ReferenceMatch(
            matched_by="barcode",
            score=round(score, 2),
            label_key="reference.match.barcode",
            detail=reference.get("name"),
        )
    name_match = store.by_name(ocr_text, fields.product_name)
    if name_match:
        reference, score = name_match
        return reference, ReferenceMatch(
            matched_by="name",
            score=round(score, 2),
            label_key="reference.match.name",
            detail=reference.get("name"),
        )
    return None, ReferenceMatch(
        matched_by="none",
        score=0.0,
        label_key="reference.match.none",
        detail=None,
    )


def _load_reference_images(store: ReferenceStore, reference: dict | None) -> dict[str, Image.Image]:
    if not reference:
        return {}
    images: dict[str, Image.Image] = {}
    for view in MANDATORY_VIEWS:
        path = store.image_path(reference, view)
        if path:
            try:
                with Image.open(path) as handle:
                    images[view] = handle.convert("RGB").copy()
            except Exception:
                continue
    return images


def _registry_summary(registry: RegistryAdapter) -> RegistrySummary:
    if registry.is_demo:
        notice_key = "notices.demo_registry"
    elif not registry.available:
        notice_key = "notices.registry_unavailable"
    else:
        notice_key = "notices.registry_configured"
    return RegistrySummary(
        provider=registry.name,
        is_demo=registry.is_demo,
        available=registry.available,
        notice_key=notice_key,
    )


def _base_notices(
    reference: dict | None,
    registry: RegistryAdapter,
    overrides_applied: list[str],
    vision_status: str | None,
) -> list[Notice]:
    notices: list[Notice] = []
    if reference and reference.get("demo", True):
        notices.append(
            Notice(
                key="notices.demo_reference",
                text_en=(
                    "Reference library: DEMO DATA — these are fictional packages, "
                    "not real medicine registrations."
                ),
                tone="info",
            )
        )
    if registry.is_demo:
        notices.append(
            Notice(
                key="notices.demo_registry",
                text_en=(
                    "Registration lookup uses a local DEMO CSV. It is not connected to "
                    "DRAP and must not be treated as a real registration check."
                ),
                tone="info",
            )
        )
    elif not registry.available:
        notices.append(
            Notice(
                key="notices.registry_unavailable",
                text_en="No real registry adapter is configured, so registration lookup is unavailable.",
                tone="warn",
            )
        )
    if reference is None:
        notices.append(
            Notice(
                key="notices.no_reference",
                text_en=(
                    "No reference packaging matched this product. Visual identity and "
                    "spelling checks are limited; confidence is lower."
                ),
                tone="warn",
            )
        )
    if overrides_applied:
        notices.append(
            Notice(
                key="notices.overrides_applied",
                text_en="Your corrected fields were used for this re-check.",
                params={"fields": overrides_applied},
                tone="info",
            )
        )
    if vision_status == "vision_llm_used":
        notices.append(
            Notice(
                key="notices.vision_llm_used",
                text_en="Low-confidence OCR fields were supplemented by the optional vision model.",
                tone="info",
            )
        )
    elif vision_status and vision_status.startswith("vision_llm_failed"):
        notices.append(
            Notice(
                key="notices.vision_llm_failed",
                text_en="The optional vision model was unavailable; on-device OCR results were used.",
                tone="warn",
            )
        )
    return notices


def _skipped_checks(
    rules: ScoringRules,
    explanation_key: str,
    explanation_en: str,
    check_ids: list[str],
) -> list:
    return [
        rules.make_check(
            check_id,
            CheckStatus.UNKNOWN,
            explanation_key,
            explanation_en,
            f"checks.{check_id}.why",
            confidence=0.0,
            metrics={"skipped": True},
        )
        for check_id in check_ids
    ]


def _quality_failure_result(
    *,
    started: float,
    rules: ScoringRules,
    images: dict[str, Image.Image],
    quality,
    quality_status: QualityStatus,
    reference: dict | None,
    reference_match: ReferenceMatch | None,
    store: ReferenceStore,
    registry: RegistryAdapter,
    barcode: BarcodeScan,
    fields: ExtractedFields,
    settings: Settings,
) -> AnalysisResult:
    checks = [run_checks_quality_only(quality, quality_status, rules)]
    checks.extend(
        _skipped_checks(
            rules,
            "checks.common.quality_retake",
            "Not evaluated because the photos did not pass the image quality gate.",
            [
                "expiry",
                "dates",
                "batch_format",
                "barcode",
                "registration",
                "spelling",
                "visual",
                "print_quality",
            ],
        )
    )
    notices = _base_notices(reference, registry, [], None)
    notices.insert(
        0,
        Notice(
            key="notices.quality_failed",
            text_en="The photos were too poor to screen. Retake them using the tips on each capture step.",
            tone="danger",
        ),
    )
    return AnalysisResult(
        analysis_id=uuid.uuid4().hex[:12],
        created_at=datetime.now(timezone.utc),
        verdict=Verdict.UNDETERMINED,
        risk_score=0.0,
        confidence=Confidence.LOW,
        confidence_reason_key="confidence.low.quality_failed",
        confidence_reason_en="Photos were too poor to screen reliably, so confidence is low.",
        reference=store.summary(reference) if reference else None,
        reference_match=reference_match,
        fields=fields,
        checks=checks,
        quality=quality,
        quality_status=quality_status,
        comparisons={},
        registry=_registry_summary(registry),
        notices=notices,
        ocr_engine="not_run",
        ocr_confidence=0.0,
        processing_ms=int((time.perf_counter() - started) * 1000),
        scoring_version=rules.version,
    )


def run_checks_quality_only(quality, quality_status: QualityStatus, rules: ScoringRules):
    from .checks import check_photo_quality

    return check_photo_quality(quality, quality_status, rules)


def analyze_package(
    images: dict[str, Image.Image],
    settings: Settings,
    store: ReferenceStore,
    registry: RegistryAdapter | None = None,
    ocr_service: OCRService | None = None,
    overrides: FieldOverrides | None = None,
    explicit_reference_id: str | None = None,
    today: date | None = None,
) -> AnalysisResult:
    started = time.perf_counter()
    rules = load_scoring_rules(settings.scoring_file)
    registry = registry or get_registry_adapter(settings)
    ocr_service = ocr_service or OCRService(settings)

    quality = assess_quality({view: images[view] for view in images})
    mandatory_quality = {view: quality[view] for view in MANDATORY_VIEWS if view in quality}
    quality_status = overall_quality_status(mandatory_quality)

    barcode_scan = scan_barcodes({view: images[view] for view in MANDATORY_VIEWS if view in images})
    fields = ExtractedFields()
    if barcode_scan.normalized:
        fields.barcode = barcode_scan.normalized
    elif barcode_scan.chosen and barcode_scan.chosen.value:
        fields.barcode = barcode_scan.chosen.value

    if quality_status == QualityStatus.FAIL:
        reference, match = _resolve_reference(store, fields, barcode_scan, "", explicit_reference_id)
        return _quality_failure_result(
            started=started,
            rules=rules,
            images=images,
            quality=quality,
            quality_status=quality_status,
            reference=reference,
            reference_match=match,
            store=store,
            registry=registry,
            barcode=barcode_scan,
            fields=fields,
            settings=settings,
        )

    view_ocr: dict[str, OCRResult] = {}
    for view in ("front", "back"):
        if view in images:
            view_ocr[view] = ocr_service.read(images[view])

    fields = _merge_fields(view_ocr)
    if barcode_scan.normalized:
        fields.barcode = barcode_scan.normalized
    elif barcode_scan.chosen and barcode_scan.chosen.value:
        fields.barcode = barcode_scan.chosen.value

    ocr_text = _ocr_text(view_ocr)
    reference, reference_match = _resolve_reference(
        store, fields, barcode_scan, ocr_text, explicit_reference_id
    )

    missing_critical = not all(
        [fields.expiry_date, fields.batch_number, fields.registration_number]
    )
    front_or_back_empty = not any(result.blocks for result in view_ocr.values())
    if "batch" in images and (
        missing_critical
        or reference is None
        or front_or_back_empty
    ):
        batch_result = ocr_service.read(images["batch"])
        view_ocr["batch"] = batch_result
        fields = _merge_fields(view_ocr)
        if barcode_scan.normalized:
            fields.barcode = barcode_scan.normalized
        elif barcode_scan.chosen and barcode_scan.chosen.value:
            fields.barcode = barcode_scan.chosen.value
        ocr_text = _ocr_text(view_ocr)
        reference, reference_match = _resolve_reference(
            store, fields, barcode_scan, ocr_text, explicit_reference_id
        )

    ocr_confidence = _combined_ocr_confidence(list(view_ocr.values()))
    vision_status: str | None = None
    if not overrides:
        fields, vision_status = refine_fields_with_vision_llm(
            settings, images, fields, ocr_confidence
        )
        if vision_status == "vision_llm_used":
            ocr_text = ocr_text + "\n" + " ".join(
                value for value in fields.model_dump().values() if isinstance(value, str)
            )

    fields, overrides_applied = _apply_overrides(fields, overrides)
    if "barcode" in overrides_applied:
        barcode_value = fields.barcode
        normalized = normalize_gtin(barcode_value) if barcode_value else None
        synthetic = DetectedCode(
            value=barcode_value or "",
            format="user_override",
            valid=validate_gtin(normalized) if normalized else False,
            view="manual",
            normalized=normalized,
        )
        barcode_scan = BarcodeScan(codes=[synthetic], chosen=synthetic, engine="user_override")
    reference, reference_match = _resolve_reference(
        store, fields, barcode_scan, ocr_text, explicit_reference_id
    )

    reference_images = _load_reference_images(store, reference)
    visual = analyze_visuals(images, reference_images)

    ocr_failed = not any(result.blocks for result in view_ocr.values())
    registry_summary = _registry_summary(registry)
    notices = _base_notices(reference, registry, overrides_applied, vision_status)

    if ocr_failed:
        views_without_text = [result.engine for result in view_ocr.values()]
        notices.insert(
            0,
            Notice(
                key="notices.ocr_failed",
                text_en="Text could not be read from these photos. Retake them in good light and hold the camera steady.",
                params={"engines": views_without_text},
                tone="danger",
            ),
        )
        checks = [run_checks_quality_only(quality, quality_status, rules)]
        checks.extend(
            _skipped_checks(
                rules,
                "checks.common.ocr_failed",
                "Not evaluated because printed text could not be read.",
                ["expiry", "dates", "batch_format", "registration", "spelling"],
            )
        )
        from .checks import check_barcode, check_print_quality, check_visual

        checks.append(check_barcode(barcode_scan, fields.barcode, reference, rules))
        checks.append(check_visual(visual, reference, rules))
        checks.append(check_print_quality(visual, reference, rules))
        checks.sort(key=lambda check: [
            "photo_quality", "expiry", "dates", "batch_format", "barcode",
            "registration", "spelling", "visual", "print_quality",
        ].index(check.id))
        fields.product_name = fields.product_name or None
        return AnalysisResult(
            analysis_id=uuid.uuid4().hex[:12],
            created_at=datetime.now(timezone.utc),
            verdict=Verdict.UNDETERMINED,
            risk_score=rules.risk_score(checks),
            confidence=Confidence.LOW,
            confidence_reason_key="confidence.low.ocr_failed",
            confidence_reason_en="Printed text could not be read reliably, so confidence is low.",
            reference=store.summary(reference) if reference else None,
            reference_match=reference_match,
            fields=fields,
            checks=checks,
            quality=quality,
            quality_status=quality_status,
            comparisons={view: item for view, item in (visual.comparisons.items() if visual else [])},
            registry=registry_summary,
            notices=notices,
            ocr_engine=ocr_service.engine_name,
            ocr_confidence=ocr_confidence,
            processing_ms=int((time.perf_counter() - started) * 1000),
            scoring_version=rules.version,
            overrides_applied=overrides_applied,
        )

    context = CheckContext(
        fields=fields,
        reference=reference,
        registry=registry,
        barcode=barcode_scan,
        visual=visual,
        quality=quality,
        quality_status=quality_status,
        ocr_confidence=ocr_confidence,
        today=today or date.today(),
    )
    checks = run_checks(context, rules)
    risk_score = rules.risk_score(checks)
    verdict = rules.decide_verdict(
        checks,
        risk_score,
        quality_status,
        has_reference=reference is not None,
    )
    unknown_count = sum(1 for check in checks if check.status == CheckStatus.UNKNOWN)
    confidence, reason_key, reason_en = rules.decide_confidence(
        quality_status=quality_status,
        has_reference=reference is not None,
        matched_by=reference_match.matched_by if reference_match else "none",
        ocr_confidence=ocr_confidence,
        unknown_count=unknown_count,
        quality_warn=quality_status == QualityStatus.WARN,
    )

    if quality_status == QualityStatus.WARN:
        notices.insert(
            0,
            Notice(
                key="notices.quality_warnings",
                text_en="Some photos had quality warnings. Results are usable but confidence may be lower.",
                tone="warn",
            )
        )

    return AnalysisResult(
        analysis_id=uuid.uuid4().hex[:12],
        created_at=datetime.now(timezone.utc),
        verdict=verdict,
        risk_score=risk_score,
        confidence=confidence,
        confidence_reason_key=reason_key,
        confidence_reason_en=reason_en,
        reference=store.summary(reference) if reference else None,
        reference_match=reference_match,
        fields=fields,
        checks=checks,
        quality=quality,
        quality_status=quality_status,
        comparisons=visual.comparisons if visual else {},
        registry=registry_summary,
        notices=notices,
        ocr_engine=ocr_service.engine_name,
        ocr_confidence=ocr_confidence,
        processing_ms=int((time.perf_counter() - started) * 1000),
        scoring_version=rules.version,
        overrides_applied=overrides_applied,
    )
