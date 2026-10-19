from __future__ import annotations

from typing import Any

import cv2
import numpy as np
from PIL import Image

from ..models import ImageQuality, QualityIssue, QualityStatus


MIN_SHORT_SIDE = 480
BLUR_FAIL = 15.0
BLUR_WARN = 100.0
DARK_FAIL = 35.0
DARK_WARN = 60.0
BRIGHT_WARN = 232.0
BRIGHT_FAIL = 250.0
GLARE_WARN = 0.85
GLARE_FAIL = 0.97
CONTRAST_FAIL = 12.0
CONTRAST_WARN = 22.0


def _to_gray(image: Image.Image, max_side: int = 1000) -> np.ndarray:
    array = np.array(image.convert("RGB"))
    height, width = array.shape[:2]
    if max(height, width) > max_side:
        scale = max_side / max(height, width)
        array = cv2.resize(array, (int(width * scale), int(height * scale)))
    return cv2.cvtColor(array, cv2.COLOR_RGB2GRAY)


def measure_blur(gray: np.ndarray) -> float:
    if gray.size == 0:
        return 0.0
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def assess_image_quality(view: str, image: Image.Image) -> ImageQuality:
    width, height = image.size
    gray = _to_gray(image)
    blur = measure_blur(gray)
    brightness = float(gray.mean())
    contrast = float(gray.std())
    glare = float((gray >= 251).mean())

    issues: list[QualityIssue] = []
    short_side = min(width, height)
    if short_side < MIN_SHORT_SIDE:
        issues.append(
            QualityIssue(
                code="too_small",
                severity="fail",
                message_key="quality.issues.too_small",
                params={"min": MIN_SHORT_SIDE, "actual": short_side},
            )
        )
    if blur < BLUR_FAIL:
        issues.append(
            QualityIssue(
                code="too_blurry",
                severity="fail",
                message_key="quality.issues.too_blurry",
                params={"score": round(blur, 1)},
            )
        )
    elif blur < BLUR_WARN:
        issues.append(
            QualityIssue(
                code="slightly_blurry",
                severity="warn",
                message_key="quality.issues.slightly_blurry",
                params={"score": round(blur, 1)},
            )
        )
    if brightness < DARK_FAIL:
        issues.append(
            QualityIssue(
                code="too_dark",
                severity="fail",
                message_key="quality.issues.too_dark",
                params={"brightness": round(brightness, 1)},
            )
        )
    elif brightness < DARK_WARN:
        issues.append(
            QualityIssue(
                code="dark",
                severity="warn",
                message_key="quality.issues.dark",
                params={"brightness": round(brightness, 1)},
            )
        )
    if brightness > BRIGHT_FAIL:
        issues.append(
            QualityIssue(
                code="overexposed",
                severity="fail",
                message_key="quality.issues.overexposed",
                params={"brightness": round(brightness, 1)},
            )
        )
    elif brightness > BRIGHT_WARN:
        issues.append(
            QualityIssue(
                code="bright",
                severity="warn",
                message_key="quality.issues.bright",
                params={"brightness": round(brightness, 1)},
            )
        )
    if glare > GLARE_FAIL:
        issues.append(
            QualityIssue(
                code="glare",
                severity="fail",
                message_key="quality.issues.glare",
                params={"ratio": round(glare, 2)},
            )
        )
    elif glare > GLARE_WARN:
        issues.append(
            QualityIssue(
                code="glare_risk",
                severity="warn",
                message_key="quality.issues.glare_risk",
                params={"ratio": round(glare, 2)},
            )
        )
    if contrast < CONTRAST_FAIL:
        issues.append(
            QualityIssue(
                code="low_contrast",
                severity="fail",
                message_key="quality.issues.low_contrast",
                params={"contrast": round(contrast, 1)},
            )
        )
    elif contrast < CONTRAST_WARN:
        issues.append(
            QualityIssue(
                code="flat_contrast",
                severity="warn",
                message_key="quality.issues.flat_contrast",
                params={"contrast": round(contrast, 1)},
            )
        )

    if any(issue.severity == "fail" for issue in issues):
        status = QualityStatus.FAIL
    elif issues:
        status = QualityStatus.WARN
    else:
        status = QualityStatus.OK

    return ImageQuality(
        view=view,
        width=width,
        height=height,
        status=status,
        blur_score=round(blur, 2),
        brightness=round(brightness, 2),
        glare_ratio=round(glare, 3),
        contrast=round(contrast, 2),
        issues=issues,
    )


def assess_quality(images: dict[str, Image.Image]) -> dict[str, ImageQuality]:
    return {view: assess_image_quality(view, image) for view, image in images.items()}


def overall_quality_status(quality: dict[str, ImageQuality]) -> QualityStatus:
    statuses = [item.status for item in quality.values()]
    if QualityStatus.FAIL in statuses:
        return QualityStatus.FAIL
    if QualityStatus.WARN in statuses:
        return QualityStatus.WARN
    return QualityStatus.OK


def quality_to_metrics(quality: dict[str, ImageQuality]) -> dict[str, Any]:
    return {
        view: {
            "status": item.status.value,
            "blur_score": item.blur_score,
            "brightness": item.brightness,
            "glare_ratio": item.glare_ratio,
            "contrast": item.contrast,
            "width": item.width,
            "height": item.height,
            "issues": [issue.model_dump() for issue in item.issues],
        }
        for view, item in quality.items()
    }
