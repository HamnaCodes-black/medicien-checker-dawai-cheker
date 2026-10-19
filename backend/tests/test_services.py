from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import get_settings
from app.services.image_quality import assess_image_quality
from app.services.reference_store import ReferenceStore, seed_demo_references
from app.services.visual import analyze_visuals, view_status
from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "demo_data"


@pytest.fixture()
def temp_settings(tmp_path):
    settings = get_settings().model_copy(deep=True)
    settings.reference_dir = tmp_path / "references"
    settings.registry_csv = tmp_path / "registry.csv"
    settings.demo_manifest = DEMO / "manifest.json"
    count = seed_demo_references(settings)
    assert count == 5
    return settings


def test_reference_store_seeds_and_matches_barcode(temp_settings):
    store = ReferenceStore(temp_settings.refs_dir)
    assert len(store.list()) == 5
    match = store.by_barcode("2001001000011")
    assert match is not None
    assert match[0]["name"] == "Fevra+"
    name_match = store.by_name("Fevrraa+ 500 mg", "Fevrraa+")
    assert name_match is not None


def test_visual_comparison_identical_and_wrong_colour():
    reference = Image.open(DEMO / "reference" / "fevra-plus" / "front.png").convert("RGB")
    tampered = Image.open(DEMO / "tampered" / "fevra-plus__wrong-color" / "front.png").convert("RGB")
    authentic = analyze_visuals({"front": reference}, {"front": reference})
    assert authentic is not None
    assert authentic.status == "pass"
    assert authentic.comparisons["front"].combined_similarity > 0.9
    wrong = analyze_visuals({"front": tampered}, {"front": reference})
    assert wrong is not None
    assert wrong.status == "fail"
    assert view_status(wrong.comparisons["front"]) == "fail"


def test_quality_gate_flags_severe_blur_and_tiny_images():
    image = Image.open(DEMO / "reference" / "fevra-plus" / "front.png").convert("RGB")
    sharp = assess_image_quality("front", image)
    assert sharp.status.value == "ok"
    blurred = assess_image_quality("front", image.filter(ImageFilter.GaussianBlur(14)))
    assert blurred.status.value == "fail"
    assert any(issue.code == "too_blurry" for issue in blurred.issues)
    tiny = assess_image_quality("front", image.resize((300, 420)))
    assert tiny.status.value == "fail"
    assert any(issue.code == "too_small" for issue in tiny.issues)


def test_scoring_config_is_valid_and_transparent():
    settings = get_settings()
    raw = json.loads(settings.scoring_file.read_text(encoding="utf-8"))
    assert sum(raw["weights"].values()) == 100
    assert raw["weights"]["photo_quality"] == 0
    assert set(raw["status_factors"]) == {"pass", "warn", "fail", "unknown"}
