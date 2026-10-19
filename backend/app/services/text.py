from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFKD", value)
    value = value.replace("+", " plus ")
    value = re.sub(r"[^a-zA-Z0-9\u0600-\u06FF]+", " ", value)
    return re.sub(r"\s+", " ", value).strip().lower()


def compact_text(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current = [i]
        for j, char_b in enumerate(b, start=1):
            insert = current[j - 1] + 1
            delete = previous[j] + 1
            replace = previous[j - 1] + (char_a != char_b)
            current.append(min(insert, delete, replace))
        previous = current
    return previous[-1]


def similarity(a: str | None, b: str | None) -> float:
    left = compact_text(a)
    right = compact_text(b)
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    distance = levenshtein(left, right)
    return max(0.0, 1.0 - distance / max(len(left), len(right)))


def sequence_similarity(a: str | None, b: str | None) -> float:
    left = normalize_text(a)
    right = normalize_text(b)
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def contains_name(haystack: str | None, needle: str | None, threshold: float = 0.8) -> bool:
    if not haystack or not needle:
        return False
    hay = normalize_text(haystack)
    target = normalize_text(needle)
    if not target:
        return False
    if target in hay:
        return True
    words = hay.split()
    target_words = target.split()
    window = max(1, len(target_words))
    for start in range(0, max(1, len(words) - window + 1)):
        candidate = " ".join(words[start:start + window])
        if sequence_similarity(candidate, target) >= threshold:
            return True
    return False


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def percent(value: float) -> int:
    return int(round(clamp(value) * 100))
