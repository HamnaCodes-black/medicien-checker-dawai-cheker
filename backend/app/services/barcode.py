from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from PIL import Image

try:
    import zxingcpp
except Exception:  # pragma: no cover - optional runtime dependency
    zxingcpp = None


GTIN_LENGTHS = {8, 12, 13, 14}


def gtin_check_digit(payload: str) -> str:
    total = 0
    for index, char in enumerate(reversed(payload)):
        total += int(char) * (3 if index % 2 == 0 else 1)
    return str((10 - total % 10) % 10)


def validate_gtin(value: str) -> bool:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) not in GTIN_LENGTHS:
        return False
    return gtin_check_digit(digits[:-1]) == digits[-1]


def normalize_gtin(value: str) -> str | None:
    if not value:
        return None
    text = value.strip()
    gs1 = re.search(r"\(01\)\s*(\d{14})", text)
    if gs1:
        text = gs1.group(1)
    digits = re.sub(r"\D", "", text)
    if len(digits) == 12:
        return "0" + digits
    if len(digits) == 8:
        return "0" * 5 + digits
    if len(digits) == 14:
        return digits[1:]
    if len(digits) == 13:
        return digits
    return None


@dataclass
class DetectedCode:
    value: str
    format: str
    valid: bool
    view: str
    normalized: str | None = None


@dataclass
class BarcodeScan:
    codes: list[DetectedCode] = field(default_factory=list)
    chosen: DetectedCode | None = None
    engine: str = "none"
    error: str | None = None

    @property
    def raw_value(self) -> str | None:
        return self.chosen.value if self.chosen else None

    @property
    def normalized(self) -> str | None:
        return self.chosen.normalized if self.chosen else None

    @property
    def is_valid(self) -> bool | None:
        if not self.chosen:
            return None
        return self.chosen.valid


def read_image_codes(image: Image.Image, view: str) -> list[DetectedCode]:
    if zxingcpp is None:
        return []
    array = image.convert("RGB")
    try:
        results = zxingcpp.read_barcodes(
            array,
            try_rotate=True,
            try_downscale=True,
            try_invert=True,
            return_errors=True,
        )
    except Exception:
        try:
            results = zxingcpp.read_barcodes(array)
        except Exception:
            return []
    codes: list[DetectedCode] = []
    for result in results:
        text = (getattr(result, "text", "") or "").strip()
        if not text:
            continue
        fmt = str(getattr(result, "format", "unknown")).split(".")[-1]
        normalized = normalize_gtin(text)
        own_valid: bool | None = None
        if normalized:
            own_valid = validate_gtin(normalized)
        zxing_valid = getattr(result, "valid", None)
        if own_valid is not None:
            valid = bool(own_valid)
        elif zxing_valid is not None:
            valid = bool(zxing_valid)
        else:
            valid = True
        codes.append(
            DetectedCode(
                value=text,
                format=fmt,
                valid=valid,
                view=view,
                normalized=normalized,
            )
        )
    return codes


def scan_barcodes(images: dict[str, Image.Image]) -> BarcodeScan:
    scan = BarcodeScan(engine="zxing-cpp")
    for view, image in images.items():
        codes = read_image_codes(image, view)
        scan.codes.extend(codes)
    if not scan.codes:
        scan.error = "no_barcode_found"
        return scan

    def rank(code: DetectedCode) -> tuple[int, int, int]:
        is_gtin = 1 if code.normalized else 0
        preferred_format = 1 if any(
            token in code.format.upper() for token in ("EAN", "UPC", "DATAMATRIX", "QR")
        ) else 0
        return (is_gtin, int(code.valid), preferred_format)

    scan.codes.sort(key=rank, reverse=True)
    scan.chosen = scan.codes[0]
    return scan


def barcode_prefix(value: str | None, length: int = 7) -> str:
    normalized = normalize_gtin(value or "")
    if not normalized:
        return ""
    digits = re.sub(r"\D", "", normalized)
    return digits[:length]


def codes_to_dict(scan: BarcodeScan) -> dict[str, Any]:
    return {
        "engine": scan.engine,
        "chosen": scan.raw_value,
        "normalized": scan.normalized,
        "valid_checksum": scan.is_valid,
        "codes": [
            {
                "value": code.value,
                "format": code.format,
                "valid": code.valid,
                "view": code.view,
            }
            for code in scan.codes
        ],
    }
