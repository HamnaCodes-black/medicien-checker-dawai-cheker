from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class CheckStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    UNKNOWN = "unknown"


class Verdict(str, Enum):
    CONSISTENT = "consistent"
    SUSPICIOUS = "suspicious"
    UNDETERMINED = "undetermined"


class Confidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class QualityStatus(str, Enum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"


class CheckResult(BaseModel):
    id: str
    status: CheckStatus
    title_key: str
    explanation_key: str
    explanation_en: str
    params: dict[str, Any] = Field(default_factory=dict)
    why_key: str
    confidence: float = Field(ge=0.0, le=1.0)
    weight: float
    risk_points: float
    metrics: dict[str, Any] = Field(default_factory=dict)


class ExtractedFields(BaseModel):
    product_name: str | None = None
    strength: str | None = None
    manufacturer: str | None = None
    registration_number: str | None = None
    batch_number: str | None = None
    manufacturing_date: str | None = None
    expiry_date: str | None = None
    barcode: str | None = None


class FieldOverrides(BaseModel):
    product_name: str | None = None
    strength: str | None = None
    manufacturer: str | None = None
    registration_number: str | None = None
    batch_number: str | None = None
    manufacturing_date: str | None = None
    expiry_date: str | None = None
    barcode: str | None = None


class QualityIssue(BaseModel):
    code: str
    severity: Literal["warn", "fail"]
    message_key: str
    params: dict[str, Any] = Field(default_factory=dict)


class ImageQuality(BaseModel):
    view: str
    width: int
    height: int
    status: QualityStatus
    blur_score: float
    brightness: float
    glare_ratio: float
    contrast: float
    issues: list[QualityIssue] = Field(default_factory=list)


class ReferenceSummary(BaseModel):
    id: str
    name: str
    strength: str | None = None
    manufacturer: str | None = None
    registration_number: str | None = None
    barcode: str | None = None
    barcode_prefix: str | None = None
    batch_regex: str | None = None
    color_hex: str | None = None
    demo: bool = True


class ReferenceMatch(BaseModel):
    matched_by: Literal["explicit", "barcode", "name", "none"]
    score: float
    label_key: str
    detail: str | None = None


class ComparisonRegion(BaseModel):
    label_key: str
    label_en: str
    bbox: list[int]
    severity: Literal["warn", "fail"]
    difference: float


class ViewComparison(BaseModel):
    view: str
    ssim: float
    orb_inliers: int
    color_distance: float
    phash_distance: int
    sharpness_ratio: float
    combined_similarity: float
    alignment: Literal["homography", "resize"]
    regions: list[ComparisonRegion] = Field(default_factory=list)
    images: dict[str, str] = Field(default_factory=dict)


class RegistrySummary(BaseModel):
    provider: str
    is_demo: bool
    available: bool
    notice_key: str


class Notice(BaseModel):
    key: str
    text_en: str
    params: dict[str, Any] = Field(default_factory=dict)
    tone: Literal["info", "warn", "danger"] = "info"


class AnalysisResult(BaseModel):
    analysis_id: str
    created_at: datetime
    verdict: Verdict
    risk_score: float
    confidence: Confidence
    confidence_reason_key: str
    confidence_reason_en: str
    reference: ReferenceSummary | None = None
    reference_match: ReferenceMatch | None = None
    fields: ExtractedFields
    checks: list[CheckResult]
    quality: dict[str, ImageQuality]
    quality_status: QualityStatus
    comparisons: dict[str, ViewComparison] = Field(default_factory=dict)
    registry: RegistrySummary
    notices: list[Notice] = Field(default_factory=list)
    ocr_engine: str
    ocr_confidence: float
    processing_ms: int
    scoring_version: str
    overrides_applied: list[str] = Field(default_factory=list)


class ReferencePublic(BaseModel):
    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    strength: str | None = None
    manufacturer: str | None = None
    registration_number: str | None = None
    batch_regex: str | None = None
    registration_regex: str | None = None
    barcode: str | None = None
    barcode_prefix: str | None = None
    color_hex: str | None = None
    demo: bool = True
    images: dict[str, str] = Field(default_factory=dict)


class RegistryRecordPublic(BaseModel):
    registration_number: str
    product_name: str
    manufacturer: str
    status: str
    note: str
    demo: bool = True


class HealthResponse(BaseModel):
    status: str
    version: str
    ocr_engine: str
    registry_provider: str
    reference_count: int
    demo_data: bool


class ScoringConfigPublic(BaseModel):
    version: str
    description: str
    weights: dict[str, float]
    status_factors: dict[str, float]
    thresholds: dict[str, float]
