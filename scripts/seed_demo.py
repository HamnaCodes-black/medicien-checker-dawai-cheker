"""Seed the demo reference image library and the local DEMO registry CSV."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.config import get_settings  # noqa: E402
from app.services.demo_registry import write_demo_registry  # noqa: E402
from app.services.reference_store import ReferenceStore, seed_demo_references  # noqa: E402


def main() -> None:
    settings = get_settings()
    if not settings.demo_manifest.exists():
        raise SystemExit(
            "demo_data/manifest.json not found. Run `python scripts/generate_demo_data.py` first."
        )
    if settings.refs_dir.exists() and any(settings.refs_dir.iterdir()):
        print(f"Reference store already populated: {settings.refs_dir}")
    count = seed_demo_references(settings)
    store = ReferenceStore(settings.refs_dir)
    registry_count = write_demo_registry(settings.demo_registry_csv, store.list())
    print(f"Seeded {count} demo references into {settings.refs_dir}")
    print(f"Wrote {registry_count} DEMO registry rows to {settings.demo_registry_csv}")
    print("DEMO DATA — fictional products and registrations only.")


if __name__ == "__main__":
    main()
