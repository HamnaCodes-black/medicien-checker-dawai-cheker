"""Evaluate the packaging pipeline on the synthetic demo dataset.

Real-world accuracy is untested. These numbers only show that the plumbing works
on generated, fictional packaging images.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.services.pipeline import analyze_package  # noqa: E402
from app.services.reference_store import ReferenceStore  # noqa: E402


VERDICT_ORDER = ["consistent", "suspicious", "undetermined"]


def evaluate(limit: int | None, output_dir: Path) -> dict:
    manifest = json.loads((ROOT / "demo_data" / "manifest.json").read_text(encoding="utf-8"))
    cases = manifest["cases"]
    if limit:
        cases = cases[:limit]
    settings = get_settings()
    settings.seed_demo_on_startup = False
    store = ReferenceStore(settings.refs_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    started_all = time.time()
    for index, case in enumerate(cases, start=1):
        case_dir = ROOT / "demo_data"
        images = {
            view: Image.open(case_dir / relative).convert("RGB")
            for view, relative in case["images"].items()
        }
        started = time.time()
        result = analyze_package(images, settings, store)
        elapsed = time.time() - started
        rows.append(
            {
                "case_id": case["id"],
                "product_id": case["product_id"],
                "variant": case["variant"],
                "tamper_type": case["tamper_type"] or "",
                "expected": case["expected_verdict"],
                "predicted": result.verdict.value,
                "risk_score": result.risk_score,
                "confidence": result.confidence.value,
                "failed_checks": ";".join(
                    check.id for check in result.checks if check.status.value == "fail"
                ),
                "warn_checks": ";".join(
                    check.id for check in result.checks if check.status.value == "warn"
                ),
                "unknown_checks": ";".join(
                    check.id for check in result.checks if check.status.value == "unknown"
                ),
                "reference_matched": bool(result.reference),
                "ocr_engine": result.ocr_engine,
                "ocr_confidence": result.ocr_confidence,
                "processing_seconds": round(elapsed, 2),
            }
        )
        print(
            f"[{index:02d}/{len(cases)}] {case['id']:<44} "
            f"expected={case['expected_verdict']:<10} predicted={result.verdict.value:<13} "
            f"score={result.risk_score:>5} ({elapsed:.1f}s)"
        )

    tampered = [row for row in rows if row["expected"] == "suspicious"]
    authentic = [row for row in rows if row["expected"] == "consistent"]
    true_positive = sum(row["predicted"] == "suspicious" for row in tampered)
    false_negative = len(tampered) - true_positive
    false_positive = sum(row["predicted"] == "suspicious" for row in authentic)
    true_negative = len(authentic) - false_positive
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    accuracy = (true_positive + true_negative) / max(1, len(rows))

    matrix = {
        actual: {
            predicted: sum(
                row["expected"] == actual and row["predicted"] == predicted for row in rows
            )
            for predicted in VERDICT_ORDER
        }
        for actual in ["suspicious", "consistent"]
    }

    summary = {
        "dataset": "SYNTHETIC demo data only",
        "cases": len(rows),
        "tampered_cases": len(tampered),
        "authentic_cases": len(authentic),
        "true_positive": true_positive,
        "false_negative": false_negative,
        "false_positive": false_positive,
        "true_negative": true_negative,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy_detection": round(accuracy, 4),
        "authentic_looks_consistent_rate": round(true_negative / max(1, len(authentic)), 4),
        "verdict_matrix": matrix,
        "mean_processing_seconds": round(
            sum(row["processing_seconds"] for row in rows) / max(1, len(rows)), 2
        ),
        "total_seconds": round(time.time() - started_all, 1),
        "note": (
            "These results are on synthetic generated images. They say nothing about "
            "real-world accuracy. 'Undetermined' is counted as not flagged when computing recall."
        ),
    }

    with (output_dir / "results.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.2), gridspec_kw={"width_ratios": [1, 1.25]})
    matrix_values = np.array(
        [[matrix["suspicious"]["suspicious"], matrix["suspicious"]["consistent"]],
         [matrix["consistent"]["suspicious"], matrix["consistent"]["consistent"]]]
    )
    ax = axes[0]
    image = ax.imshow(matrix_values, cmap="YlOrRd")
    ax.set_xticks([0, 1], ["Flagged suspicious", "Not flagged"])
    ax.set_yticks([0, 1], ["Tampered", "Authentic"])
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Synthetic ground truth")
    ax.set_title("Screening confusion matrix")
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(matrix_values[i, j]), ha="center", va="center", fontsize=18)
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)

    ax = axes[1]
    for label, color, values in [
        ("Tampered", "#DC2626", [row["risk_score"] for row in tampered]),
        ("Authentic", "#0F766E", [row["risk_score"] for row in authentic]),
    ]:
        ax.hist(values, bins=np.arange(0, 105, 10), alpha=0.65, label=label, color=color)
    ax.axvline(float(settings_scoring_threshold()), color="#334155", linestyle="--", label="Suspicious threshold")
    ax.set_xlabel("Transparent risk score")
    ax.set_ylabel("Number of synthetic cases")
    ax.set_title("Risk score distribution")
    ax.legend()
    fig.suptitle("DawaiCheck evaluation — SYNTHETIC DEMO DATA ONLY", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(output_dir / "evaluation_chart.png", dpi=160)

    print("\n=== DawaiCheck synthetic demo evaluation ===")
    print(f"Cases: {len(rows)}  Tampered: {len(tampered)}  Authentic: {len(authentic)}")
    print(f"Precision: {precision:.2f}  Recall: {recall:.2f}  F1: {f1:.2f}")
    print(f"Authentic cases shown as 'Looks consistent': {true_negative}/{len(authentic)}")
    print("Verdict matrix (actual -> predicted):")
    for actual, values in matrix.items():
        print(f"  {actual}: {values}")
    print(f"Mean processing time: {summary['mean_processing_seconds']}s per case")
    print(f"Saved {output_dir / 'results.csv'}, summary.json and evaluation_chart.png")
    print("NOTE: synthetic images only — real-world accuracy is untested.")
    return summary


def settings_scoring_threshold() -> float:
    settings = get_settings()
    raw = json.loads(settings.scoring_file.read_text(encoding="utf-8"))
    return float(raw.get("thresholds", {}).get("suspicious_score", 15))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="Evaluate only the first N cases")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "eval_results",
        help="Directory for results.csv, summary.json and chart",
    )
    args = parser.parse_args()
    summary = evaluate(args.limit, args.output)
    if summary["recall"] < 0.6:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
