# DawaiCheck

DawaiCheck is a mobile-first, bilingual English/Urdu PWA that screens medicine **packaging photos** for warning signs. It checks selected details against a packaging reference, barcode validity, printed dates, OCR spelling, and visual similarity.

> **Safety notice:** DawaiCheck is a packaging screening aid, not a laboratory test. It cannot test chemical content, prove a medicine is genuine, or prove a medicine is safe. If you have any doubt, ask a licensed pharmacist or contact DRAP.

All bundled products, manufacturers, registration numbers, and images are fictional **DEMO DATA**. They are not real DRAP registrations and must not be used as evidence about any real medicine.

**[Read the full technical documentation →](docs/DOCUMENTATION.md)**

## Screenshots

| Home | Urdu / RTL | Result |
| --- | --- | --- |
| ![Home](docs/screenshots/home-mobile.png) | ![Urdu home](docs/screenshots/home-urdu.png) | ![Result](docs/screenshots/result-consistent.png) |

## Features

- Three mandatory photos (front, back, batch/expiry) with an optional blister/strip photo.
- On-device photo quality checks with retake guidance and a live camera preview when available.
- Server-side OCR, barcode/DataMatrix decoding, reference matching, packaging comparisons, and transparent risk scoring.
- Clear verdict states: **Looks consistent**, **Suspicious packaging**, or **Undetermined**. Never "safe" or "genuine".
- English and Urdu UI with RTL support, dark mode, 48px tap targets, and PWA install/offline shell support.
- Explicit consent before saving a result to local history; maximum 20 records in IndexedDB.
- Shareable text summary and English-only PDF report generated entirely in the browser.
- Hidden reference-admin screen for adding non-demo references when explicitly enabled.

## Architecture

```text
backend/    FastAPI API, OCR/barcode/visual analysis, scoring, demo reference store
frontend/   React + TypeScript + Vite PWA
demo_data/  Synthetic reference and tampered packaging images + manifest
scripts/    Dataset generation and evaluation helpers
docs/       Technical documentation, screenshots, evaluation results
```

The frontend talks to the backend through `/api`. In development Vite proxies `/api` to `http://127.0.0.1:8000`; in Docker Nginx proxies `/api` to the backend container.

## Local development

### Backend

Requirements: Python 3.12+ and, optionally, Tesseract OCR. RapidOCR is installed through the Python requirements and is used automatically.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

On Linux/macOS activate with `source .venv/bin/activate`. For Tesseract support install `tesseract-ocr` and the Urdu language pack (`tesseract-ocr-urd`), or set `OCR_ENGINE=rapidocr`.

### Frontend

Requires Node 22+.

```powershell
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173`. Camera access requires HTTPS or `localhost`. The live camera is optional; uploads and the device camera input work without it.

### Demo walkthrough

1. Open **How it works** to read the limitations and scoring explanation.
2. On the home screen, choose one of the four demo cases.
3. Review the photos, tap **Analyze photos**, and inspect the checks.
4. Save to history only after accepting the consent dialog.
5. Open **Report** to review and download the PDF.

Demo cases use the fictional `Fevra+` pack:

| Case | Expected result |
| --- | --- |
| Authentic demo pack | Looks consistent |
| Misspelled product name | Suspicious packaging |
| Expired date | Suspicious packaging |
| Wrong brand color | Suspicious packaging |

## Verification

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q

cd ..\frontend
npm run typecheck
npm run lint
npm run build
```

The backend E2E test requires an installed OCR engine and exercises the authentic and typo-name demo cases. The frontend build also generates the service worker and web manifest.

## Docker

```powershell
docker compose up --build
```

- App: `http://localhost:8080`
- API and docs: `http://localhost:8000/api/health`, `http://localhost:8000/docs`
- Persistent reference/admin data: named volume `backend_data`

Use `docker compose down` to stop. Add `-v` only when you intentionally want to delete stored admin-added references.

## Configuration

Copy `.env.example` to `.env` at the project root for backend settings. The frontend can use `frontend/.env` with `VITE_API_BASE_URL` when it is hosted separately from the API.

Important backend settings:

| Variable | Default | Purpose |
| --- | --- | --- |
| `OCR_ENGINE` | `auto` | `auto`, `rapidocr`, `tesseract`, or `none` |
| `OCR_LANGUAGES` | `eng+urd` | Tesseract language packs |
| `REGISTRY_PROVIDER` | `local_demo` | Local demo CSV; no real registry adapter is bundled |
| `SEED_DEMO_ON_STARTUP` | `true` | Seed five fictional references when the store is empty |
| `CORS_ORIGINS` | localhost dev origins | Comma-separated allowed browser origins |
| `VISION_LLM_ENABLED` | `false` | Optional vision fallback; disabled by default |
| `MAX_UPLOAD_MB` | `15` | Maximum size per uploaded photo |

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Service status, OCR engine, reference count, demo flag |
| `POST` | `/api/analyze` | Analyze `front`, `back`, `batch`, optional `blister`, `overrides`, `reference_id` |
| `GET` | `/api/references` | List packaging references |
| `POST` | `/api/references` | Add a reference with images |
| `GET` | `/api/references/{id}` | Get one reference |
| `GET` | `/api/references/{id}/image/{view}` | Reference image |
| `DELETE` | `/api/references/{id}` | Delete a non-demo reference |
| `GET` | `/api/scoring` | Public scoring weights and thresholds |
| `GET` | `/api/registry/lookup?number=...` | Demo registry lookup |

## Privacy and storage

- Photos are sent only to the configured API for analysis and are not written to server-side history by this project.
- Saved results and compressed photos stay in the browser's IndexedDB (`dawaicheck_history`).
- History is limited to 20 records. Deleting all records preserves language and theme preferences.
- No account, analytics, or third-party tracking is included.
- PDFs are generated locally. PDF output is English-only for font compatibility; the UI states this.

## Known limitations

- Packaging screening cannot detect counterfeit contents, wrong ingredients, substandard manufacturing, or storage problems.
- Results depend on photo quality, OCR, and the quality of the chosen reference.
- Registration lookup is demo-only by default and is not connected to DRAP.
- The bundled demo data is synthetic and is not suitable for regulatory or clinical decisions.
- This project is a prototype, not a medical device.
