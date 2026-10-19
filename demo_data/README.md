# DawaiCheck synthetic demo dataset

**DEMO DATA — not real registrations.** All product names, manufacturers, registration numbers, batches and dates are fictional. The packaging images were generated with PIL specifically for this prototype.

- `reference/` — 5 fictional authentic reference packages
- `tampered/` — 15 intentionally tampered variants
- `manifest.json` — metadata and expected labels
- `labels.csv` — labels used by the evaluation script

Regenerate with `python scripts/generate_demo_data.py`.
These images must not be used as evidence that any real product is safe or unsafe.
