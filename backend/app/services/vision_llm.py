from __future__ import annotations

import base64
import json
import re
from io import BytesIO

import httpx
from PIL import Image

from ..config import Settings
from ..models import ExtractedFields


SYSTEM_PROMPT = (
    "You extract printed packaging fields from medicine carton photos for a "
    "packaging-screening app. Return ONLY a JSON object with the keys "
    "product_name, strength, manufacturer, registration_number, batch_number, "
    "manufacturing_date, expiry_date, barcode. Use null when unreadable. "
    "Do not guess. Never comment on whether the medicine is genuine or safe."
)


def _encode(image: Image.Image, max_side: int = 1200) -> str:
    working = image.convert("RGB")
    if max(working.size) > max_side:
        ratio = max_side / max(working.size)
        working = working.resize(
            (max(1, int(working.width * ratio)), max(1, int(working.height * ratio))),
            Image.Resampling.LANCZOS,
        )
    buffer = BytesIO()
    working.save(buffer, format="JPEG", quality=84)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def _parse_json_content(content: str) -> dict:
    cleaned = content.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def refine_fields_with_vision_llm(
    settings: Settings,
    images: dict[str, Image.Image],
    fields: ExtractedFields,
    ocr_confidence: float,
) -> tuple[ExtractedFields, str | None]:
    if not settings.vision_llm_enabled:
        return fields, None
    if not settings.vision_llm_api_key:
        return fields, "vision_llm_missing_api_key"
    if ocr_confidence >= 0.62 and all(
        [
            fields.product_name,
            fields.registration_number,
            fields.batch_number,
            fields.expiry_date,
        ]
    ):
        return fields, None

    content: list[dict] = [
        {
            "type": "text",
            "text": (
                "Photos: front of pack, back/side of pack, and batch/expiry close-up. "
                "Current OCR text is unreliable. Extract the packaging fields."
            ),
        }
    ]
    for view in ("front", "back", "batch"):
        if view in images:
            content.append({"type": "text", "text": f"{view}:"})
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": _encode(images[view])},
                }
            )
    payload = {
        "model": settings.vision_llm_model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
    }
    headers = {
        "Authorization": f"Bearer {settings.vision_llm_api_key}",
        "Content-Type": "application/json",
    }
    url = settings.vision_llm_base_url.rstrip("/") + "/chat/completions"
    try:
        with httpx.Client(timeout=settings.vision_llm_timeout_seconds) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()
        content_text = body["choices"][0]["message"]["content"]
        extracted = _parse_json_content(content_text)
    except Exception as error:
        return fields, f"vision_llm_failed: {type(error).__name__}"

    if not extracted:
        return fields, "vision_llm_no_fields"
    updates = fields.model_dump()
    filled = False
    for key in updates:
        if updates[key]:
            continue
        value = extracted.get(key)
        if isinstance(value, str) and value.strip():
            updates[key] = value.strip()
            filled = True
    if not filled:
        return fields, "vision_llm_no_new_fields"
    return ExtractedFields(**updates), "vision_llm_used"
