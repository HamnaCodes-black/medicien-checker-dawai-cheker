from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ..config import Settings


class RegistryUnavailable(RuntimeError):
    pass


@dataclass
class RegistryRecord:
    registration_number: str
    product_name: str
    manufacturer: str
    status: str
    note: str
    demo: bool


class RegistryAdapter(Protocol):
    name: str
    is_demo: bool
    available: bool

    def lookup(self, registration_number: str) -> RegistryRecord | None: ...


class LocalDemoRegistryAdapter:
    name = "local_demo_csv"
    is_demo = True
    available = True

    def __init__(self, csv_path: Path):
        self.csv_path = csv_path
        self._records: list[RegistryRecord] | None = None

    def _load(self) -> list[RegistryRecord]:
        if self._records is not None:
            return self._records
        records: list[RegistryRecord] = []
        if self.csv_path.exists():
            with self.csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    number = (row.get("registration_number") or "").strip()
                    if not number:
                        continue
                    records.append(
                        RegistryRecord(
                            registration_number=number,
                            product_name=(row.get("product_name") or "").strip(),
                            manufacturer=(row.get("manufacturer") or "").strip(),
                            status=(row.get("status") or "DEMO").strip(),
                            note=(row.get("note") or "DEMO DATA — not a real registration").strip(),
                            demo=True,
                        )
                    )
        self._records = records
        return records

    def lookup(self, registration_number: str) -> RegistryRecord | None:
        target = normalize_registration(registration_number)
        if not target:
            return None
        for record in self._load():
            if normalize_registration(record.registration_number) == target:
                return record
        return None


class UnconfiguredDrapRegistryAdapter:
    name = "drap_unconfigured"
    is_demo = False
    available = False

    def lookup(self, registration_number: str) -> RegistryRecord | None:
        raise RegistryUnavailable(
            "A real DRAP registry adapter is not configured. The team must verify an "
            "official DRAP integration before enabling this provider."
        )


def normalize_registration(value: str | None) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", (value or "")).upper()


def get_registry_adapter(settings: Settings) -> RegistryAdapter:
    provider = settings.registry_provider.strip().lower()
    if provider in {"drap", "drap_unconfigured"}:
        return UnconfiguredDrapRegistryAdapter()
    return LocalDemoRegistryAdapter(settings.demo_registry_csv)
