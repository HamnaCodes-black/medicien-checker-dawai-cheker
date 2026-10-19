from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps

from ..config import Settings
from ..models import ReferencePublic, ReferenceSummary
from .barcode import barcode_prefix, normalize_gtin
from .text import contains_name, sequence_similarity, similarity


DEMO_NOTICE = "DEMO DATA — not real medicine registrations"


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:50] or "reference"


class ReferenceStore:
    def __init__(self, root: Path):
        self.root = root
        self.index_path = root / "index.json"

    def _read(self) -> dict:
        if not self.index_path.exists():
            return {"demo": True, "notice": DEMO_NOTICE, "references": []}
        try:
            return json.loads(self.index_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"demo": True, "notice": DEMO_NOTICE, "references": []}

    def _write(self, data: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.index_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        temporary.replace(self.index_path)

    def list(self) -> list[dict]:
        return list(self._read().get("references", []))

    def get(self, reference_id: str) -> dict | None:
        for reference in self.list():
            if reference.get("id") == reference_id:
                return reference
        return None

    def image_path(self, reference: dict, view: str) -> Path | None:
        relative = (reference.get("images") or {}).get(view)
        if not relative:
            return None
        candidate = (self.root / relative).resolve()
        try:
            candidate.relative_to(self.root.resolve())
        except ValueError:
            return None
        return candidate if candidate.exists() else None

    def summary(self, reference: dict) -> ReferenceSummary:
        return ReferenceSummary(
            id=reference.get("id", ""),
            name=reference.get("name", ""),
            strength=reference.get("strength"),
            manufacturer=reference.get("manufacturer"),
            registration_number=reference.get("reg_no"),
            barcode=reference.get("barcode"),
            barcode_prefix=reference.get("barcode_prefix"),
            batch_regex=reference.get("batch_regex"),
            color_hex=reference.get("color_hex"),
            demo=bool(reference.get("demo", True)),
        )

    def public(self, reference: dict) -> ReferencePublic:
        images = {
            view: f"/api/references/{reference.get('id')}/image/{view}"
            for view in ("front", "back", "batch")
            if view in (reference.get("images") or {})
        }
        return ReferencePublic(
            id=reference.get("id", ""),
            name=reference.get("name", ""),
            aliases=list(reference.get("aliases") or []),
            strength=reference.get("strength"),
            manufacturer=reference.get("manufacturer"),
            registration_number=reference.get("reg_no"),
            batch_regex=reference.get("batch_regex"),
            registration_regex=reference.get("reg_regex"),
            barcode=reference.get("barcode"),
            barcode_prefix=reference.get("barcode_prefix"),
            color_hex=reference.get("color_hex"),
            demo=bool(reference.get("demo", True)),
            images=images,
        )

    def by_barcode(self, value: str | None) -> tuple[dict, float] | None:
        normalized = normalize_gtin(value or "")
        if not normalized:
            return None
        prefix = barcode_prefix(normalized)
        for reference in self.list():
            reference_barcode = normalize_gtin(reference.get("barcode") or "")
            if reference_barcode and reference_barcode == normalized:
                return reference, 1.0
            reference_prefix = re.sub(r"\D", "", str(reference.get("barcode_prefix") or ""))
            if reference_prefix and prefix[: len(reference_prefix)] == reference_prefix:
                return reference, 0.9
        return None

    def by_name(
        self,
        text: str | None,
        product_name: str | None = None,
    ) -> tuple[dict, float] | None:
        best: tuple[dict, float] | None = None
        for reference in self.list():
            names = [reference.get("name", ""), *(reference.get("aliases") or [])]
            for name in names:
                if not name:
                    continue
                score = 0.0
                if text and contains_name(text, name, threshold=0.7):
                    score = 0.9
                if product_name:
                    score = max(
                        score,
                        sequence_similarity(product_name, name),
                        similarity(product_name, name),
                    )
                if best is None or score > best[1]:
                    best = (reference, score)
        if best and best[1] >= 0.68:
            return best
        return None

    def add(self, form: dict, files: dict[str, UploadFile]) -> ReferencePublic:
        required = ["name", "manufacturer", "reg_no"]
        for field in required:
            if not str(form.get(field) or "").strip():
                raise HTTPException(status_code=422, detail=f"Missing required field: {field}")
        name = str(form["name"]).strip()
        manufacturer = str(form["manufacturer"]).strip()
        reg_no = str(form["reg_no"]).strip()
        batch_regex = str(form.get("batch_regex") or "").strip() or None
        reg_regex = str(form.get("reg_regex") or "").strip() or None
        if batch_regex:
            try:
                re.compile(batch_regex)
            except re.error as error:
                raise HTTPException(status_code=422, detail=f"Invalid batch regex: {error}") from error
        if reg_regex:
            try:
                re.compile(reg_regex)
            except re.error as error:
                raise HTTPException(status_code=422, detail=f"Invalid registration regex: {error}") from error

        barcode = normalize_gtin(str(form.get("barcode") or ""))
        reference_id = _slug(name)
        data = self._read()
        existing_ids = {item.get("id") for item in data.get("references", [])}
        if reference_id in existing_ids:
            reference_id = f"{reference_id}-{int(datetime.now().timestamp())}"

        folder = self.root / "user" / reference_id
        folder.mkdir(parents=True, exist_ok=True)
        images: dict[str, str] = {}
        for view in ("front", "back", "batch"):
            upload = files.get(view)
            if upload is None:
                continue
            content = upload.file.read()
            if not content:
                continue
            if len(content) > 15 * 1024 * 1024:
                raise HTTPException(status_code=413, detail=f"{view} image is too large")
            try:
                with Image.open(BytesIO(content)) as source:
                    normalized = ImageOps.exif_transpose(source).convert("RGB")
                    normalized.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
                    buffer = BytesIO()
                    normalized.save(buffer, format="JPEG", quality=88)
            except Exception as error:
                raise HTTPException(status_code=422, detail=f"{view} is not a usable image") from error
            filename = f"{view}.jpg"
            (folder / filename).write_bytes(buffer.getvalue())
            images[view] = str((folder / filename).relative_to(self.root)).replace("\\", "/")

        if "front" not in images:
            raise HTTPException(status_code=422, detail="An authentic front-of-pack image is required")

        reference = {
            "id": reference_id,
            "name": name,
            "aliases": [],
            "strength": str(form.get("strength") or "").strip() or None,
            "manufacturer": manufacturer,
            "reg_no": reg_no,
            "reg_regex": reg_regex,
            "batch_regex": batch_regex,
            "barcode": barcode,
            "barcode_prefix": barcode_prefix(barcode) if barcode else None,
            "color_hex": str(form.get("color_hex") or "").strip() or None,
            "demo": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "images": images,
        }
        data.setdefault("references", []).append(reference)
        self._write(data)
        return self.public(reference)

    def delete(self, reference_id: str) -> bool:
        data = self._read()
        references = data.get("references", [])
        target = next((item for item in references if item.get("id") == reference_id), None)
        if not target:
            return False
        data["references"] = [item for item in references if item.get("id") != reference_id]
        self._write(data)
        for relative in (target.get("images") or {}).values():
            path = (self.root / relative).resolve()
            try:
                path.relative_to(self.root.resolve())
            except ValueError:
                continue
            path.unlink(missing_ok=True)
        return True


def seed_demo_references(settings: Settings) -> int:
    store = ReferenceStore(settings.refs_dir)
    if store.list():
        return len(store.list())
    manifest_path = settings.demo_manifest
    if not manifest_path.exists():
        return 0
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0
    demo_root = manifest_path.parent
    root = settings.refs_dir
    root.mkdir(parents=True, exist_ok=True)
    seeded = []
    for item in manifest.get("references", []):
        reference_id = _slug(item.get("id") or item.get("name", "reference"))
        destination = root / "demo" / reference_id
        images: dict[str, str] = {}
        for view, relative in (item.get("images") or {}).items():
            source = demo_root / relative
            if not source.exists():
                continue
            destination.mkdir(parents=True, exist_ok=True)
            target = destination / f"{view}{source.suffix}"
            shutil.copyfile(source, target)
            images[view] = str(target.relative_to(root)).replace("\\", "/")
        if not images:
            continue
        seeded.append(
            {
                **{key: value for key, value in item.items() if key != "images"},
                "id": reference_id,
                "demo": True,
                "images": images,
                "seeded_from": "demo_data/manifest.json",
            }
        )
    store._write(
        {
            "demo": True,
            "notice": DEMO_NOTICE,
            "seeded_at": datetime.now(timezone.utc).isoformat(),
            "references": seeded,
        }
    )
    return len(seeded)
