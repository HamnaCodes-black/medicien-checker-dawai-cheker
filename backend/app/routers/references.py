from __future__ import annotations

import mimetypes

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from ..config import get_settings
from ..models import ReferencePublic
from ..services.demo_registry import append_demo_registry
from ..services.reference_store import ReferenceStore


router = APIRouter(prefix="/references", tags=["references"])


def _store(request: Request) -> ReferenceStore:
    return request.app.state.reference_store


@router.get("", response_model=list[ReferencePublic])
def list_references(request: Request) -> list[ReferencePublic]:
    store = _store(request)
    return [store.public(reference) for reference in store.list()]


@router.post("", response_model=ReferencePublic, status_code=201)
async def add_reference(
    request: Request,
    name: str = Form(...),
    manufacturer: str = Form(...),
    reg_no: str = Form(...),
    strength: str | None = Form(None),
    barcode: str | None = Form(None),
    barcode_prefix: str | None = Form(None),
    batch_regex: str | None = Form(None),
    reg_regex: str | None = Form(None),
    color_hex: str | None = Form(None),
    front: UploadFile = File(...),
    back: UploadFile = File(None),
    batch: UploadFile = File(None),
) -> ReferencePublic:
    store = _store(request)
    files = {
        view: upload
        for view, upload in (("front", front), ("back", back), ("batch", batch))
        if upload is not None
    }
    public = store.add(
        {
            "name": name,
            "manufacturer": manufacturer,
            "reg_no": reg_no,
            "strength": strength,
            "barcode": barcode,
            "barcode_prefix": barcode_prefix,
            "batch_regex": batch_regex,
            "reg_regex": reg_regex,
            "color_hex": color_hex,
        },
        files,
    )
    settings = get_settings()
    if settings.registry_provider.strip().lower() == "local_demo":
        append_demo_registry(
            settings.demo_registry_csv,
            registration=reg_no,
            product_name=name,
            manufacturer=manufacturer,
        )
    return public


@router.get("/{reference_id}", response_model=ReferencePublic)
def get_reference(reference_id: str, request: Request) -> ReferencePublic:
    store = _store(request)
    reference = store.get(reference_id)
    if not reference:
        raise HTTPException(status_code=404, detail="Reference not found")
    return store.public(reference)


@router.get("/{reference_id}/image/{view}")
def reference_image(reference_id: str, view: str, request: Request) -> FileResponse:
    if view not in {"front", "back", "batch"}:
        raise HTTPException(status_code=404, detail="Unknown image view")
    store = _store(request)
    reference = store.get(reference_id)
    if not reference:
        raise HTTPException(status_code=404, detail="Reference not found")
    path = store.image_path(reference, view)
    if not path:
        raise HTTPException(status_code=404, detail="Reference image not found")
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type, headers={"Cache-Control": "no-store"})


@router.delete("/{reference_id}", status_code=204)
def delete_reference(reference_id: str, request: Request) -> None:
    store = _store(request)
    reference = store.get(reference_id)
    if not reference:
        raise HTTPException(status_code=404, detail="Reference not found")
    if reference.get("demo", True):
        raise HTTPException(
            status_code=400,
            detail="Built-in demo references cannot be deleted. Run the seed script to reset.",
        )
    store.delete(reference_id)
