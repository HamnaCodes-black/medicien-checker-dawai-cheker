from __future__ import annotations

import shutil
import threading
from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np
from PIL import Image

from ..config import Settings


@dataclass
class TextBlock:
    text: str
    confidence: float
    bbox: list[float] = field(default_factory=list)


@dataclass
class OCRResult:
    engine: str
    blocks: list[TextBlock] = field(default_factory=list)
    avg_confidence: float = 0.0
    error: str | None = None

    @property
    def text(self) -> str:
        return "\n".join(block.text for block in self.blocks if block.text).strip()

    def blocks_as_dicts(self) -> list[dict[str, Any]]:
        return [
            {"text": block.text, "confidence": block.confidence, "bbox": block.bbox}
            for block in self.blocks
        ]


class OCRProvider(Protocol):
    name: str

    def available(self) -> bool: ...

    def read(self, image: Image.Image, languages: str) -> OCRResult: ...


def _bbox_from_points(points: Any) -> list[float]:
    try:
        xs = [float(point[0]) for point in points]
        ys = [float(point[1]) for point in points]
        return [min(xs), min(ys), max(xs), max(ys)]
    except Exception:
        return [0, 0, 0, 0]


class RapidOCRProvider:
    name = "rapidocr"
    _engine = None
    _lock = threading.Lock()

    def available(self) -> bool:
        try:
            import rapidocr_onnxruntime  # noqa: F401
            return True
        except Exception:
            return False

    def _get_engine(self):
        if RapidOCRProvider._engine is None:
            with RapidOCRProvider._lock:
                if RapidOCRProvider._engine is None:
                    from rapidocr_onnxruntime import RapidOCR
                    RapidOCRProvider._engine = RapidOCR()
        return RapidOCRProvider._engine

    def read(self, image: Image.Image, languages: str) -> OCRResult:
        engine = self._get_engine()
        array = np.array(image.convert("RGB"))
        with RapidOCRProvider._lock:
            result, _elapsed = engine(array)
        blocks: list[TextBlock] = []
        for item in result or []:
            try:
                points, text, score = item
            except Exception:
                continue
            text = str(text or "").strip()
            if not text:
                continue
            blocks.append(
                TextBlock(
                    text=text,
                    confidence=float(score or 0.0),
                    bbox=_bbox_from_points(points),
                )
            )
        return OCRResult(
            engine=self.name,
            blocks=blocks,
            avg_confidence=_average_confidence(blocks),
        )


class TesseractOCRProvider:
    name = "tesseract"

    def available(self) -> bool:
        try:
            import pytesseract
        except Exception:
            return False
        if shutil.which("tesseract"):
            return True
        try:
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def read(self, image: Image.Image, languages: str) -> OCRResult:
        import pytesseract
        from pytesseract import Output

        data = pytesseract.image_to_data(
            image,
            lang=languages,
            output_type=Output.DICT,
            config="--psm 3",
            timeout=45,
        )
        blocks: list[TextBlock] = []
        for index, text in enumerate(data.get("text", [])):
            text = str(text or "").strip()
            if not text:
                continue
            try:
                confidence = float(data["conf"][index]) / 100.0
            except (ValueError, IndexError, KeyError):
                confidence = 0.0
            if confidence < 0:
                confidence = 0.0
            left = float(data["left"][index])
            top = float(data["top"][index])
            width = float(data["width"][index])
            height = float(data["height"][index])
            blocks.append(
                TextBlock(
                    text=text,
                    confidence=confidence,
                    bbox=[left, top, left + width, top + height],
                )
            )
        blocks.sort(key=lambda block: (round(block.bbox[1] / 12), block.bbox[0]))
        return OCRResult(
            engine=self.name,
            blocks=blocks,
            avg_confidence=_average_confidence(blocks),
        )


class EasyOCRProvider:
    name = "easyocr"
    _readers: dict[str, Any] = {}
    _lock = threading.Lock()

    def available(self) -> bool:
        try:
            import easyocr  # noqa: F401
            return True
        except Exception:
            return False

    def read(self, image: Image.Image, languages: str) -> OCRResult:
        import easyocr

        lang_map = {
            "eng+urd": ["en", "ur"],
            "eng": ["en"],
            "urd": ["ur"],
            "en+ur": ["en", "ur"],
        }
        langs = lang_map.get(languages, ["en", "ur"] if "ur" in languages else ["en"])
        key = ",".join(langs)
        with EasyOCRProvider._lock:
            reader = EasyOCRProvider._readers.get(key)
            if reader is None:
                reader = easyocr.Reader(langs, gpu=False, verbose=False)
                EasyOCRProvider._readers[key] = reader
            results = reader.readtext(np.array(image.convert("RGB")), detail=1, paragraph=False)
        blocks: list[TextBlock] = []
        for bbox_points, text, score in results:
            text = str(text or "").strip()
            if not text:
                continue
            blocks.append(
                TextBlock(
                    text=text,
                    confidence=float(score or 0.0),
                    bbox=_bbox_from_points(bbox_points),
                )
            )
        blocks.sort(key=lambda block: (round(block.bbox[1] / 12), block.bbox[0]))
        return OCRResult(
            engine=self.name,
            blocks=blocks,
            avg_confidence=_average_confidence(blocks),
        )


class NullOCRProvider:
    name = "none"
    available = lambda self: True  # type: ignore[assignment]

    def read(self, image: Image.Image, languages: str) -> OCRResult:
        return OCRResult(engine=self.name, blocks=[], error="ocr_unavailable")


def _average_confidence(blocks: list[TextBlock]) -> float:
    usable = [block.confidence for block in blocks if block.text.strip()]
    if not usable:
        return 0.0
    return round(sum(usable) / len(usable), 4)


TESSERACT = TesseractOCRProvider()
RAPID = RapidOCRProvider()
EASY = EasyOCRProvider()
NULL = NullOCRProvider()


def _provider_chain(preference: str) -> list[OCRProvider]:
    preference = (preference or "auto").lower()
    named: dict[str, OCRProvider] = {
        "tesseract": TESSERACT,
        "rapidocr": RAPID,
        "easyocr": EASY,
        "none": NULL,
    }
    if preference in named:
        primary = [named[preference]]
    else:
        primary = [TESSERACT, RAPID, EASY, NULL]
    chain = [provider for provider in primary if provider.available()]
    for provider in (RAPID, TESSERACT, EASY, NULL):
        if provider not in chain and provider.available():
            chain.append(provider)
    return chain


class OCRService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.chain = _provider_chain(settings.ocr_engine)
        self.last_engine = self.chain[0].name if self.chain else "none"

    @property
    def engine_name(self) -> str:
        return self.last_engine

    def read(self, image: Image.Image) -> OCRResult:
        errors: list[str] = []
        for provider in self.chain:
            try:
                result = provider.read(image, self.settings.ocr_languages)
            except Exception as error:
                errors.append(f"{provider.name}: {error}")
                continue
            if result.blocks or provider.name == "none":
                self.last_engine = provider.name
                return result
            errors.append(f"{provider.name}: no text")
        self.last_engine = "none"
        return OCRResult(
            engine="none",
            blocks=[],
            error="; ".join(errors) or "ocr_unavailable",
        )


def resolve_ocr_engine_name(settings: Settings) -> str:
    chain = _provider_chain(settings.ocr_engine)
    return chain[0].name if chain else "none"

