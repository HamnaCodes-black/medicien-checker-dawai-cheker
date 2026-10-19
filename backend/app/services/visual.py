from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

import cv2
import imagehash
import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity

from ..models import ComparisonRegion, ViewComparison


MAX_ANALYSIS_SIDE = 1100
MAX_COMPARE_WIDTH = 600
REGION_LABELS = {
    "brand": ("regions.brand_area", "Brand, logo or headline area"),
    "text": ("regions.text_area", "Printed text or layout area"),
    "regulatory": ("regions.regulatory_area", "Batch, expiry or regulatory area"),
}


@dataclass
class VisualAnalysis:
    status: str
    comparisons: dict[str, ViewComparison]
    metrics: dict[str, Any]


def _prepare(image: Image.Image) -> np.ndarray:
    array = np.array(image.convert("RGB"))
    height, width = array.shape[:2]
    scale = min(1.0, MAX_ANALYSIS_SIDE / max(height, width))
    if scale < 1.0:
        array = cv2.resize(
            array,
            (max(1, int(width * scale)), max(1, int(height * scale))),
            interpolation=cv2.INTER_AREA,
        )
    return array


def _to_gray(array: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(array, cv2.COLOR_RGB2GRAY)


def _laplacian_score(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _align(reference: np.ndarray, captured: np.ndarray) -> tuple[np.ndarray, str, int]:
    ref_gray = _to_gray(reference)
    cap_gray = _to_gray(captured)
    target_h, target_w = reference.shape[:2]
    if captured.shape[:2] != reference.shape[:2]:
        captured = cv2.resize(captured, (target_w, target_h), interpolation=cv2.INTER_AREA)
        cap_gray = _to_gray(captured)

    orb = cv2.ORB_create(nfeatures=1800, scaleFactor=1.2, nlevels=8, fastThreshold=12)
    keypoints_ref, descriptors_ref = orb.detectAndCompute(ref_gray, None)
    keypoints_cap, descriptors_cap = orb.detectAndCompute(cap_gray, None)
    if descriptors_ref is None or descriptors_cap is None or len(keypoints_ref) < 12 or len(keypoints_cap) < 12:
        return captured, "resize", 0

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
    knn = matcher.knnMatch(descriptors_cap, descriptors_ref, k=2)
    good = [pair for pair in knn if len(pair) == 2 and pair[0].distance < 0.78 * pair[1].distance]
    if len(good) < 12:
        return captured, "resize", len(good)

    src = np.float32([keypoints_cap[m[0].queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst = np.float32([keypoints_ref[m[0].trainIdx].pt for m in good]).reshape(-1, 1, 2)
    homography, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0, maxIters=2500, confidence=0.995)
    if homography is None:
        return captured, "resize", len(good)
    inliers = int(mask.sum()) if mask is not None else 0
    if inliers < 12:
        return captured, "resize", inliers

    corners = np.float32(
        [[0, 0], [captured.shape[1], 0], [captured.shape[1], captured.shape[0]], [0, captured.shape[0]]]
    ).reshape(-1, 1, 2)
    projected = cv2.perspectiveTransform(corners, homography).reshape(-1, 2)
    if not np.isfinite(projected).all():
        return captured, "resize", inliers
    if (
        projected[:, 0].min() < -target_w * 0.35
        or projected[:, 0].max() > target_w * 1.35
        or projected[:, 1].min() < -target_h * 0.35
        or projected[:, 1].max() > target_h * 1.35
        or abs(cv2.contourArea(projected.astype(np.float32))) < target_w * target_h * 0.15
    ):
        return captured, "resize", inliers

    aligned = cv2.warpPerspective(
        captured,
        homography,
        (target_w, target_h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return aligned, "homography", inliers


def _color_distance(reference: np.ndarray, captured: np.ndarray) -> float:
    ref_hsv = cv2.cvtColor(reference, cv2.COLOR_RGB2HSV)
    cap_hsv = cv2.cvtColor(captured, cv2.COLOR_RGB2HSV)
    ref_mask = ((ref_hsv[:, :, 1] > 90) & (ref_hsv[:, :, 2] > 40)).astype(np.uint8) * 255
    cap_mask = ((cap_hsv[:, :, 1] > 90) & (cap_hsv[:, :, 2] > 40)).astype(np.uint8) * 255
    if ref_mask.mean() < 1.0 or cap_mask.mean() < 1.0:
        ref_mask = None
        cap_mask = None
    hist_ref = cv2.calcHist([ref_hsv], [0, 1], ref_mask, [30, 32], [0, 180, 0, 256])
    hist_cap = cv2.calcHist([cap_hsv], [0, 1], cap_mask, [30, 32], [0, 180, 0, 256])
    cv2.normalize(hist_ref, hist_ref, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
    cv2.normalize(hist_cap, hist_cap, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
    correlation = float(cv2.compareHist(hist_ref, hist_cap, cv2.HISTCMP_CORREL))
    correlation = max(0.0, min(1.0, correlation))
    return round(1.0 - correlation, 4)


def _region_label(view: str, center_y: float, height: float) -> tuple[str, str]:
    position = center_y / max(1.0, height)
    if view == "front":
        if position < 0.36:
            key = "brand"
        elif position < 0.72:
            key = "text"
        else:
            key = "regulatory"
    else:
        if position < 0.3:
            key = "brand"
        elif position < 0.75:
            key = "text"
        else:
            key = "regulatory"
    return REGION_LABELS[key]


def _diff_regions(
    reference: np.ndarray,
    captured: np.ndarray,
    view: str,
) -> tuple[list[ComparisonRegion], np.ndarray]:
    height, width = reference.shape[:2]
    scale = min(1.0, 520.0 / max(height, width))
    if scale < 1.0:
        size = (max(1, int(width * scale)), max(1, int(height * scale)))
        ref_small = cv2.resize(reference, size, interpolation=cv2.INTER_AREA)
        cap_small = cv2.resize(captured, size, interpolation=cv2.INTER_AREA)
    else:
        ref_small, cap_small = reference, captured
    ref_gray = cv2.GaussianBlur(_to_gray(ref_small), (5, 5), 0)
    cap_gray = cv2.GaussianBlur(_to_gray(cap_small), (5, 5), 0)
    diff = cv2.absdiff(ref_gray, cap_gray)
    _, mask = cv2.threshold(diff, 38, 255, cv2.THRESH_BINARY)
    kernel = np.ones((7, 7), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.dilate(mask, kernel, iterations=1)
    component_count, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    regions: list[ComparisonRegion] = []
    min_area = ref_small.shape[0] * ref_small.shape[1] * 0.0016
    candidates: list[tuple[int, int, int, int, int]] = []
    for component in range(1, component_count):
        x, y, component_w, component_h, area = stats[component]
        if area < min_area:
            continue
        candidates.append((area, x, y, component_w, component_h))
    candidates.sort(reverse=True)
    for area, x, y, component_w, component_h in candidates[:4]:
        scaled_x = int(x / scale) if scale < 1.0 else x
        scaled_y = int(y / scale) if scale < 1.0 else y
        scaled_w = int(component_w / scale) if scale < 1.0 else component_w
        scaled_h = int(component_h / scale) if scale < 1.0 else component_h
        center_y = scaled_y + scaled_h / 2
        label_key, label_en = _region_label(view, center_y, height)
        severity = "fail" if area > ref_small.shape[0] * ref_small.shape[1] * 0.035 else "warn"
        regions.append(
            ComparisonRegion(
                label_key=label_key,
                label_en=label_en,
                bbox=[scaled_x, scaled_y, scaled_w, scaled_h],
                severity=severity,
                difference=round(float(area / (ref_small.shape[0] * ref_small.shape[1])), 4),
            )
        )

    heatmap = cv2.applyColorMap((diff * 2).clip(0, 255).astype(np.uint8), cv2.COLORMAP_JET)
    heatmap = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)
    if heatmap.shape[:2] != (height, width):
        heatmap = cv2.resize(heatmap, (width, height), interpolation=cv2.INTER_LINEAR)
    blended = cv2.addWeighted(reference, 0.55, heatmap, 0.45, 0)
    for region in regions:
        x, y, w, h = region.bbox
        color = (220, 38, 38) if region.severity == "fail" else (245, 158, 11)
        thickness = max(3, int(min(width, height) / 240))
        cv2.rectangle(blended, (x, y), (x + w, y + h), color, thickness)
    return regions, blended


def _encode_jpeg(array_rgb: np.ndarray, width: int = MAX_COMPARE_WIDTH) -> str:
    height = array_rgb.shape[0]
    current_width = array_rgb.shape[1]
    if current_width > width:
        new_height = max(1, int(height * width / current_width))
        array_rgb = cv2.resize(array_rgb, (width, new_height), interpolation=cv2.INTER_AREA)
    bgr = cv2.cvtColor(array_rgb, cv2.COLOR_RGB2BGR)
    ok, buffer = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
    if not ok:
        return ""
    encoded = base64.b64encode(buffer.tobytes()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _draw_regions(image: np.ndarray, regions: list[ComparisonRegion]) -> np.ndarray:
    annotated = image.copy()
    height, width = annotated.shape[:2]
    thickness = max(3, int(min(width, height) / 200))
    for region in regions:
        x, y, w, h = region.bbox
        color = (220, 38, 38) if region.severity == "fail" else (245, 158, 11)
        cv2.rectangle(annotated, (x, y), (x + w, y + h), color, thickness)
    return annotated


def compare_view(view: str, reference_image: Image.Image, captured_image: Image.Image) -> ViewComparison:
    reference = _prepare(reference_image)
    captured = _prepare(captured_image)
    aligned, alignment, inliers = _align(reference, captured)
    same_shape_captured = aligned

    ref_gray = _to_gray(reference)
    cap_gray = _to_gray(same_shape_captured)
    try:
        ssim_value = float(structural_similarity(ref_gray, cap_gray, data_range=255))
    except Exception:
        ssim_value = 0.0

    color_distance = _color_distance(reference, same_shape_captured)
    phash_ref = imagehash.phash(Image.fromarray(reference))
    phash_cap = imagehash.phash(Image.fromarray(same_shape_captured))
    phash_distance = int(phash_ref - phash_cap)

    ref_sharpness = max(1.0, _laplacian_score(ref_gray))
    cap_sharpness = _laplacian_score(cap_gray)
    sharpness_ratio = cap_sharpness / ref_sharpness

    ssim_score = max(0.0, min(1.0, ssim_value))
    color_score = max(0.0, 1.0 - color_distance)
    phash_score = max(0.0, 1.0 - min(1.0, phash_distance / 30.0))
    orb_score = max(0.0, min(1.0, inliers / 45.0))
    sharpness_score = max(0.0, min(1.0, sharpness_ratio))
    combined = (
        0.40 * ssim_score
        + 0.20 * color_score
        + 0.15 * phash_score
        + 0.15 * orb_score
        + 0.10 * sharpness_score
    )

    regions, overlay = _diff_regions(reference, same_shape_captured, view)
    annotated_ref = _draw_regions(reference, regions)
    annotated_cap = _draw_regions(same_shape_captured, regions)
    images = {
        "reference": _encode_jpeg(annotated_ref),
        "captured": _encode_jpeg(annotated_cap),
        "overlay": _encode_jpeg(overlay),
    }

    return ViewComparison(
        view=view,
        ssim=round(ssim_value, 4),
        orb_inliers=inliers,
        color_distance=color_distance,
        phash_distance=phash_distance,
        sharpness_ratio=round(sharpness_ratio, 4),
        combined_similarity=round(float(combined), 4),
        alignment=alignment,  # type: ignore[arg-type]
        regions=regions,
        images=images,
    )


def view_status(comparison: ViewComparison) -> str:
    if comparison.view == "front":
        if comparison.color_distance >= 0.5:
            return "fail"
        if comparison.ssim < 0.55 or comparison.combined_similarity < 0.6:
            return "fail"
        if (
            comparison.color_distance >= 0.25
            or comparison.ssim < 0.78
            or comparison.combined_similarity < 0.8
            or comparison.sharpness_ratio < 0.35
        ):
            return "warn"
        return "pass"
    if comparison.ssim < 0.62 or comparison.combined_similarity < 0.65:
        return "fail"
    if (
        comparison.ssim < 0.8
        or comparison.combined_similarity < 0.82
        or comparison.sharpness_ratio < 0.3
    ):
        return "warn"
    return "pass"


def analyze_visuals(
    captured: dict[str, Image.Image],
    reference_images: dict[str, Image.Image] | None,
) -> VisualAnalysis | None:
    if not reference_images:
        return None
    comparisons: dict[str, ViewComparison] = {}
    for view in ("front", "back", "batch"):
        if view in captured and view in reference_images:
            comparisons[view] = compare_view(view, reference_images[view], captured[view])
    if not comparisons:
        return None

    statuses = {view: view_status(comparison) for view, comparison in comparisons.items()}
    if "fail" in statuses.values():
        status = "fail"
    elif "warn" in statuses.values():
        status = "warn"
    else:
        status = "pass"

    front = comparisons.get("front")
    min_sharpness = min((item.sharpness_ratio for item in comparisons.values()), default=1.0)
    metrics = {
        "status": status,
        "view_statuses": statuses,
        "front_color_distance": front.color_distance if front else None,
        "front_ssim": front.ssim if front else None,
        "min_sharpness_ratio": round(min_sharpness, 4),
        "min_combined_similarity": round(
            min(item.combined_similarity for item in comparisons.values()), 4
        ),
        "max_phash_distance": max(item.phash_distance for item in comparisons.values()),
    }
    return VisualAnalysis(status=status, comparisons=comparisons, metrics=metrics)


def print_quality_status(visual: VisualAnalysis | None) -> tuple[str, dict[str, Any]]:
    if not visual:
        return "unknown", {}
    min_sharpness = float(visual.metrics.get("min_sharpness_ratio", 1.0))
    metrics = {
        "min_sharpness_ratio": round(min_sharpness, 4),
        "view_sharpness": {
            view: comparison.sharpness_ratio
            for view, comparison in visual.comparisons.items()
        },
    }
    if min_sharpness < 0.35:
        return "warn", metrics
    return "pass", metrics
