from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.ocr import resolve_ocr_engine_name
from app.config import get_settings


ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "demo_data"


def _files(case_dir: Path) -> dict:
    return {
        view: (f"{view}.png", (case_dir / f"{view}.png").read_bytes(), "image/png")
        for view in ("front", "back", "batch")
    }


@pytest.mark.skipif(
    resolve_ocr_engine_name(get_settings()) == "none",
    reason="No OCR engine installed; install requirements or Tesseract to run the E2E test.",
)
def test_end_to_end_authentic_and_tampered():
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["reference_count"] >= 5

        authentic = client.post(
            "/api/analyze", files=_files(DEMO / "reference" / "fevra-plus")
        )
        assert authentic.status_code == 200, authentic.text
        authentic_data = authentic.json()
        assert authentic_data["verdict"] == "consistent"
        assert authentic_data["reference"]["demo"] is True
        assert authentic_data["fields"]["expiry_date"] == "2027-11"
        assert "front" in authentic_data["comparisons"]
        assert authentic_data["comparisons"]["front"]["images"]["reference"].startswith(
            "data:image/jpeg;base64,"
        )

        tampered = client.post(
            "/api/analyze", files=_files(DEMO / "tampered" / "fevra-plus__typo-name")
        )
        assert tampered.status_code == 200, tampered.text
        tampered_data = tampered.json()
        assert tampered_data["verdict"] == "suspicious"
        spelling = next(
            check for check in tampered_data["checks"] if check["id"] == "spelling"
        )
        assert spelling["status"] == "fail"
        assert "Fevrraa" in spelling["params"]["ocr_name"]


def test_health_endpoint_reports_demo_limitations():
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "ocr_engine" in data
