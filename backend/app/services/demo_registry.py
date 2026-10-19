from __future__ import annotations

import csv
from pathlib import Path


HEADER = ["registration_number", "product_name", "manufacturer", "status", "note"]
DEMO_NOTE = "DEMO DATA — not a real DRAP registration"


def write_demo_registry(csv_path: Path, references: list[dict]) -> int:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for reference in references:
        registration = (reference.get("reg_no") or "").strip()
        if not registration:
            continue
        rows.append(
            {
                "registration_number": registration,
                "product_name": reference.get("name") or "",
                "manufacturer": reference.get("manufacturer") or "",
                "status": "Active (DEMO)",
                "note": DEMO_NOTE,
            }
        )
    rows.append(
        {
            "registration_number": "DEMO-REG-9001",
            "product_name": "Placebo Sample (fictional)",
            "manufacturer": "Demo Pharma (Pvt) Ltd",
            "status": "Active (DEMO)",
            "note": DEMO_NOTE,
        }
    )
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return len(rows)


def append_demo_registry(csv_path: Path, registration: str, product_name: str, manufacturer: str) -> None:
    if not registration:
        return
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    existing = False
    if csv_path.exists():
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if (row.get("registration_number") or "").strip().upper() == registration.strip().upper():
                    existing = True
                    break
    if existing:
        return
    new_file = not csv_path.exists()
    with csv_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADER)
        if new_file:
            writer.writeheader()
        writer.writerow(
            {
                "registration_number": registration,
                "product_name": product_name,
                "manufacturer": manufacturer,
                "status": "Active (DEMO)",
                "note": "DEMO DATA — added from the local admin screen; not a real DRAP registration",
            }
        )
