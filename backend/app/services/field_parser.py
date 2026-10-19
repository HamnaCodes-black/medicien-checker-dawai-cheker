from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from .text import normalize_text


MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}

DATE_TOKEN = (
    r"(?:20\d{2}[-/.]\d{1,2}(?:[-/.]\d{1,2})?"
    r"|\d{1,2}[-/.]\d{1,2}[-/.]20\d{2}"
    r"|\d{1,2}[-/.]20\d{2}"
    r"|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*[\s,./-]*20\d{2}"
    r"|20\d{2})"
)

MFG_LABELS = r"(?:mfg\.?\s*(?:date)?|mfd\.?\s*(?:date)?|manufactured(?:\s*on)?|date\s*of\s*manufacture|manufacturing\s*date)"
EXP_LABELS = r"(?:exp(?:iry)?\.?\s*(?:date)?|expires?(?:\s*on)?|use\s*before|best\s*before)"

BATCH_LABELS = r"(?:batch|b\.?\s*no|lot|lot\.?\s*no)\.?\s*(?:no\.?|number|#)?"
REG_LABELS = r"(?:reg(?:istration)?\.?\s*(?:no\.?|number|#)?|drap\s*(?:reg\.?\s*no\.?)?)"


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    raw = value.strip().replace(",", " ")
    raw = re.sub(r"\s+", " ", raw)
    token_match = re.search(DATE_TOKEN, raw, flags=re.IGNORECASE)
    token = token_match.group(0) if token_match else raw
    token = re.sub(r"\s+", "", token)

    match = re.fullmatch(r"(20\d{2})[-/.](\d{1,2})(?:[-/.](\d{1,2}))?", token)
    if match:
        year, month = int(match.group(1)), int(match.group(2))
        day = int(match.group(3) or 1)
        return _safe_date(year, month, day)

    match = re.fullmatch(r"(\d{1,2})[-/.](\d{1,2})[-/.](20\d{2})", token)
    if match:
        first, second, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
        if first > 12:
            day, month = first, second
        else:
            day, month = second, first
        return _safe_date(year, month, day)

    match = re.fullmatch(r"(\d{1,2})[-/.](20\d{2})", token)
    if match:
        return _safe_date(int(match.group(2)), int(match.group(1)), 1)

    match = re.fullmatch(r"([A-Za-z]+)[-/. ]*(20\d{2})", token)
    if match:
        month = MONTHS.get(match.group(1).lower()[:4]) or MONTHS.get(match.group(1).lower()[:3])
        if month:
            return _safe_date(int(match.group(2)), month, 1)

    return None


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        try:
            return date(year, month, 1)
        except ValueError:
            return None


def date_to_iso(value: date | None) -> str | None:
    if not value:
        return None
    if value.day == 1:
        return value.strftime("%Y-%m")
    return value.strftime("%Y-%m-%d")


def _label_date(text: str, labels: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    label_re = re.compile(labels, flags=re.IGNORECASE)
    date_re = re.compile(DATE_TOKEN, flags=re.IGNORECASE)
    for index, line in enumerate(lines):
        label_match = label_re.search(line)
        if not label_match:
            continue
        tail = line[label_match.end():]
        match = date_re.search(tail)
        if not match and index + 1 < len(lines):
            match = date_re.search(lines[index + 1])
        if match:
            parsed = parse_date(match.group(0))
            if parsed:
                return date_to_iso(parsed)
    flat = re.sub(r"\s+", " ", text)
    for label_match in label_re.finditer(flat):
        tail = flat[label_match.end():label_match.end() + 30]
        match = date_re.search(tail)
        if match:
            parsed = parse_date(match.group(0))
            if parsed:
                return date_to_iso(parsed)
    return None


def _line_pair_value(
    lines: list[str],
    label_pattern: str,
    cleaner,
) -> Any | None:
    for index, line in enumerate(lines):
        if not re.search(label_pattern, line, flags=re.IGNORECASE):
            continue
        remainder = re.sub(
            r"^.*?" + label_pattern + r"[\s:.\-]*",
            "",
            line,
            flags=re.IGNORECASE,
        ).strip(" :.-")
        if remainder and not _is_placeholder(remainder):
            cleaned = cleaner(remainder)
            if cleaned:
                return cleaned
        if index + 1 < len(lines):
            candidate = lines[index + 1].strip(" :.-")
            if candidate and not _is_placeholder(candidate):
                cleaned = cleaner(candidate)
                if cleaned:
                    return cleaned
    return None


def _is_placeholder(value: str) -> bool:
    lowered = value.lower().strip(" .:-")
    return lowered in {"", "no", "number", "n/a", "na", "-", "—", "not printed"}


def _clean_batch(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip().strip(".,;:")
    candidate = re.sub(r"\s{2,}.*$", "", candidate)
    candidate = candidate.split()[0] if " " in candidate else candidate
    candidate = candidate.replace(" ", "")
    if len(candidate) < 3 or len(candidate) > 32:
        return None
    if not re.search(r"[A-Za-z]", candidate) or not re.search(r"\d", candidate):
        return None
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9\-/.]{2,31}", candidate):
        return None
    return candidate.upper()


def _clean_registration(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip().strip(".,;:")
    candidate = candidate.split()[0] if " " in candidate else candidate
    candidate = re.sub(r"[^A-Za-z0-9\-/]", "", candidate)
    if len(candidate) < 5 or len(candidate) > 40:
        return None
    if not re.search(r"\d", candidate):
        return None
    return candidate.upper()


def _clean_text_value(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip(" .:-")
    return cleaned or None


def extract_strength(text: str) -> str | None:
    patterns = [
        r"(\d{1,4}(?:[.,]\d{1,2})?)\s*(mg|mcg|g|ml|iu)\b",
        r"(\d{1,4}(?:[.,]\d{1,2})?)\s*/\s*(?:5\s*)?(ml|mg)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            number = match.group(1).replace(",", ".")
            unit = match.group(2).lower()
            if unit == "g" and float(number) >= 100:
                continue
            return f"{number} {unit}"
    number_only = re.search(r"(?m)^\s*(\d{1,4}(?:[.,]\d{1,2})?)\s*$", text)
    if number_only:
        following = text[number_only.end():]
        unit = re.match(r"\s*(mg|mcg|g|ml|iu)\b", following, flags=re.IGNORECASE)
        if unit:
            return f"{number_only.group(1).replace(',', '.')} {unit.group(1).lower()}"
    return None


def extract_manufacturer(lines: list[str]) -> str | None:
    company_tokens = re.compile(
        r"(pharma|pharmaceutical|labs?|laborator|healthcare|formulations|biotech|bio\s*pharma|industries)",
        re.IGNORECASE,
    )
    for index, line in enumerate(lines):
        if re.search(r"manufactured\s+by|marketed\s+by", line, flags=re.IGNORECASE):
            remainder = re.sub(
                r".*?(?:manufactured|marketed)\s+by[\s:.\-]*",
                "",
                line,
                flags=re.IGNORECASE,
            ).strip()
            if remainder and company_tokens.search(remainder):
                return _clean_text_value(remainder)
            if index + 1 < len(lines) and company_tokens.search(lines[index + 1]):
                return _clean_text_value(lines[index + 1])
    for line in lines:
        if (
            company_tokens.search(line)
            and "dawaicheck" not in line.lower()
            and "fictional" not in line.lower()
            and len(line) < 80
        ):
            return _clean_text_value(line)
    return None


GENERIC_NAME_BITS = {
    "dawai", "demo", "demodata", "fictional", "pharmacy", "prescription",
    "tablets", "tablet", "syrup", "capsule", "capsules", "suspension",
    "sample", "pack", "not for sale", "software", "testing", "product",
    "information", "directions", "batch", "expiry", "mfg", "reg", "made in",
    "pakistan", "drap", "close up", "strength", "dosage", "photograph",
    "printed", "panel", "clearly",
}


def _flat_bbox(bbox: Any) -> list[float]:
    if not bbox:
        return [0, 0, 0, 0]
    if len(bbox) == 4 and not isinstance(bbox[0], (list, tuple)):
        return [float(value) for value in bbox]
    xs = [float(point[0]) for point in bbox]
    ys = [float(point[1]) for point in bbox]
    return [min(xs), min(ys), max(xs), max(ys)]


def guess_product_name(
    text: str,
    blocks: list[dict[str, Any]] | None = None,
    reference_names: list[str] | None = None,
) -> str | None:
    reference_names = reference_names or []
    candidates: list[tuple[float, str]] = []
    for block in blocks or []:
        block_text = _clean_text_value(str(block.get("text", "")))
        if not block_text:
            continue
        lowered = block_text.lower()
        bbox = _flat_bbox(block.get("bbox"))
        height = max(1.0, bbox[3] - bbox[1])
        width = max(1.0, bbox[2] - bbox[0])
        if not (2 < len(block_text) <= 42):
            continue
        if re.fullmatch(r"[\d\s.,+/-]+", block_text):
            continue
        if re.fullmatch(r"\d+(?:[.,]\d+)?\s*(?:mg|mcg|g|ml|iu)", block_text, flags=re.IGNORECASE):
            continue
        if any(bit in lowered for bit in GENERIC_NAME_BITS):
            continue
        if not re.search(r"[A-Za-z]{3}", block_text):
            continue
        score = height * (min(len(block_text), 18) ** 0.5)
        candidates.append((score, block_text))

    if candidates:
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    helpful_lines = [
        _clean_text_value(line)
        for line in text.splitlines()
        if _clean_text_value(line)
        and re.search(r"[A-Za-z]{3}", line)
        and not any(bit in line.lower() for bit in GENERIC_NAME_BITS)
        and not re.fullmatch(r"\d+(?:[.,]\d+)?\s*(?:mg|mcg|g|ml|iu)", line.strip(), flags=re.IGNORECASE)
    ]
    for line in helpful_lines:
        if 2 < len(line) <= 42:
            return line
    return None


def extract_fields_from_text(text: str, blocks: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    merged = "\n".join(lines)
    flat = re.sub(r"\s+", " ", merged)

    mfg_iso = _label_date(flat, MFG_LABELS)
    exp_iso = _label_date(flat, EXP_LABELS)

    batch = _line_pair_value(lines, BATCH_LABELS, _clean_batch)
    if not batch:
        match = re.search(BATCH_LABELS + r"[\s:.\-]*([A-Za-z0-9][A-Za-z0-9\-/.]{2,31})", flat, flags=re.IGNORECASE)
        batch = _clean_batch(match.group(1)) if match else None

    registration = _line_pair_value(lines, REG_LABELS, _clean_registration)
    if not registration:
        match = re.search(REG_LABELS + r"[\s:.\-]*([A-Za-z0-9][A-Za-z0-9\-/]{4,39})", flat, flags=re.IGNORECASE)
        registration = _clean_registration(match.group(1)) if match else None

    barcode_match = re.search(
        r"(?:gtin|ean(?:-?13)?|upc)\s*[:.\-]?\s*(\d{8,14})",
        flat,
        flags=re.IGNORECASE,
    )
    barcode = barcode_match.group(1) if barcode_match else None

    return {
        "product_name": guess_product_name(merged, blocks),
        "strength": extract_strength(flat),
        "manufacturer": extract_manufacturer(lines),
        "registration_number": registration,
        "batch_number": batch,
        "manufacturing_date": mfg_iso,
        "expiry_date": exp_iso,
        "barcode": barcode,
    }


def merge_view_fields(view_fields: dict[str, dict[str, Any]]) -> dict[str, Any]:
    priorities = {
        "product_name": ["front", "back", "batch"],
        "strength": ["front", "back", "batch"],
        "manufacturer": ["front", "back", "batch"],
        "registration_number": ["batch", "back", "front"],
        "batch_number": ["batch", "back", "front"],
        "manufacturing_date": ["batch", "back", "front"],
        "expiry_date": ["batch", "back", "front"],
        "barcode": ["back", "batch", "front"],
    }
    merged: dict[str, Any] = {}
    for field, order in priorities.items():
        value = None
        for view in order:
            candidate = view_fields.get(view, {}).get(field)
            if candidate:
                value = candidate
                break
        merged[field] = value
    return merged


def display_date(value: str | None) -> str:
    if not value:
        return ""
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        try:
            parsed = datetime.strptime(value + "-01", "%Y-%m-%d").date()
        except ValueError:
            return value
    return parsed.strftime("%m/%Y") if parsed.day == 1 else parsed.strftime("%d/%m/%Y")
