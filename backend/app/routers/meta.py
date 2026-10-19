from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query, Request

from ..config import get_settings
from ..models import HealthResponse, RegistryRecordPublic, ScoringConfigPublic
from ..services.ocr import resolve_ocr_engine_name
from ..services.reference_store import ReferenceStore
from ..services.registry import RegistryUnavailable, get_registry_adapter


router = APIRouter(tags=["meta"])


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    settings = get_settings()
    store: ReferenceStore = request.app.state.reference_store
    data = store._read()
    registry = get_registry_adapter(settings)
    return HealthResponse(
        status="ok",
        version="0.1.0",
        ocr_engine=resolve_ocr_engine_name(settings),
        registry_provider=registry.name,
        reference_count=len(store.list()),
        demo_data=bool(data.get("demo", True)),
    )


@router.get("/scoring", response_model=ScoringConfigPublic)
def scoring() -> ScoringConfigPublic:
    settings = get_settings()
    try:
        raw = json.loads(settings.scoring_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=500, detail="Scoring config unavailable") from error
    return ScoringConfigPublic(
        version=str(raw.get("version", "1.0.0")),
        description=str(raw.get("description", "")),
        weights={key: float(value) for key, value in raw.get("weights", {}).items()},
        status_factors={key: float(value) for key, value in raw.get("status_factors", {}).items()},
        thresholds={key: float(value) for key, value in raw.get("thresholds", {}).items()},
    )


@router.get("/registry/lookup", response_model=RegistryRecordPublic)
def registry_lookup(number: str = Query(..., min_length=3, max_length=40)) -> RegistryRecordPublic:
    settings = get_settings()
    registry = get_registry_adapter(settings)
    if not registry.available:
        raise HTTPException(
            status_code=503,
            detail="A real registry adapter is not configured. Local demo mode uses CSV data.",
        )
    try:
        record = registry.lookup(number)
    except RegistryUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    if not record:
        raise HTTPException(status_code=404, detail="Registration not found in the local DEMO registry")
    return RegistryRecordPublic(
        registration_number=record.registration_number,
        product_name=record.product_name,
        manufacturer=record.manufacturer,
        status=record.status,
        note=record.note,
        demo=record.demo,
    )
