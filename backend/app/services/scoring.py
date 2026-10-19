from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ..models import CheckResult, CheckStatus, Confidence, QualityStatus, Verdict


@dataclass(frozen=True)
class ScoringRules:
    version: str
    description: str
    weights: dict[str, float]
    status_factors: dict[str, float]
    thresholds: dict[str, float]

    def weight(self, check_id: str) -> float:
        return float(self.weights.get(check_id, 0.0))

    def risk_points(self, check_id: str, status: CheckStatus) -> float:
        factor = float(self.status_factors.get(status.value, 0.0))
        return round(self.weight(check_id) * factor, 2)

    def make_check(
        self,
        check_id: str,
        status: CheckStatus,
        explanation_key: str,
        explanation_en: str,
        why_key: str,
        confidence: float,
        params: dict | None = None,
        metrics: dict | None = None,
    ) -> CheckResult:
        return CheckResult(
            id=check_id,
            status=status,
            title_key=f"checks.{check_id}.title",
            explanation_key=explanation_key,
            explanation_en=explanation_en,
            params=params or {},
            why_key=why_key,
            confidence=round(max(0.0, min(1.0, confidence)), 3),
            weight=self.weight(check_id),
            risk_points=self.risk_points(check_id, status),
            metrics=metrics or {},
        )

    def risk_score(self, checks: list[CheckResult]) -> float:
        return round(min(100.0, sum(check.risk_points for check in checks)), 2)

    def decide_verdict(
        self,
        checks: list[CheckResult],
        risk_score: float,
        quality_status: QualityStatus,
        has_reference: bool,
    ) -> Verdict:
        if quality_status == QualityStatus.FAIL:
            return Verdict.UNDETERMINED
        if any(check.status == CheckStatus.FAIL for check in checks):
            return Verdict.SUSPICIOUS
        if risk_score >= float(self.thresholds.get("suspicious_score", 15.0)):
            return Verdict.SUSPICIOUS
        if not has_reference:
            return Verdict.UNDETERMINED
        return Verdict.CONSISTENT

    def decide_confidence(
        self,
        quality_status: QualityStatus,
        has_reference: bool,
        matched_by: str,
        ocr_confidence: float,
        unknown_count: int,
        quality_warn: bool,
    ) -> tuple[Confidence, str, str]:
        if quality_status == QualityStatus.FAIL:
            return (
                Confidence.LOW,
                "confidence.low.quality_failed",
                "Photos were too poor to screen reliably, so confidence is low.",
            )
        if not has_reference:
            return (
                Confidence.LOW,
                "confidence.low.no_reference",
                "No reference packaging matched this product, so the visual comparison is unavailable.",
            )
        if (
            matched_by in {"barcode", "explicit"}
            and ocr_confidence >= 0.55
            and quality_status == QualityStatus.OK
            and unknown_count <= 1
        ):
            return (
                Confidence.HIGH,
                "confidence.high.matched_reference",
                "A packaging reference was matched by barcode and the photos were clear.",
            )
        if quality_warn or unknown_count > 1 or matched_by == "name":
            reason_key = "confidence.medium.partial_evidence"
            reason_en = "Some checks could not be completed or the photos had minor quality issues."
        else:
            reason_key = "confidence.medium.some_uncertainty"
            reason_en = "The reference was matched, but some evidence is less certain."
        return Confidence.MEDIUM, reason_key, reason_en


def load_scoring_rules(path: Path) -> ScoringRules:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return ScoringRules(
        version=str(raw.get("version", "1.0.0")),
        description=str(raw.get("description", "")),
        weights={key: float(value) for key, value in raw.get("weights", {}).items()},
        status_factors={key: float(value) for key, value in raw.get("status_factors", {}).items()},
        thresholds={key: float(value) for key, value in raw.get("thresholds", {}).items()},
    )
