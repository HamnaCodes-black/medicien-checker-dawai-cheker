from __future__ import annotations

import json
from io import BytesIO

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from ..config import Settings, get_settings
from ..models import AnalysisResult, FieldOverrides
from ..services.pipeline import analyze_package
from ..services.reference_store import ReferenceStore


Image.MAX_IMAGE_PIXELS = 60_000_000

router = APIRouter(tags=["analysis"])


async def _load_image(upload: UploadFile, settings: Settings, view: str) -> Image.Image:
    data = await upload.read()
    if not data:
        raise HTTPException(status_code=422, detail=f"{view} image is empty")
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"{view} image is larger than {settings.max_upload_mb} MB",
        )
    try:
        with Image.open(BytesIO(data)) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            if max(image.size) > settings.max_side_px:
                image.thumbnail((settings.max_side_px, settings.max_side_px), Image.Resampling.LANCZOS)
            return image.copy()
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise HTTPException(status_code=422, detail=f"{view} is not a usable image") from error


@router.post("/analyze", response_model=AnalysisResult)
async def analyze(
    request: Request,
    front: UploadFile = File(...),
    back: UploadFile = File(...),
    batch: UploadFile = File(...),
    blister: UploadFile | None = File(None),
    overrides: str | None = Form(None),
    reference_id: str | None = Form(None),
) -> AnalysisResult:
    settings = get_settings()
    store: ReferenceStore = request.app.state.reference_store
    images = {
        "front": await _load_image(front, settings, "front"),
        "back": await _load_image(back, settings, "back"),
        "batch": await _load_image(batch, settings, "batch"),
    }
    if blister is not None and blister.filename:
        images["blister"] = await _load_image(blister, settings, "blister")

    parsed_overrides: FieldOverrides | None = None
    if overrides:
        try:
            parsed_overrides = FieldOverrides.model_validate(json.loads(overrides))
        except (json.JSONDecodeError, ValueError) as error:
            raise HTTPException(status_code=422, detail="Invalid field overrides") from error

    try:
        return analyze_package(
            images,
            settings,
            store,
            overrides=parsed_overrides,
            explicit_reference_id=reference_id,
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail="Analysis failed. Please retake the photos or try again.",
        ) from error
