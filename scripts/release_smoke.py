"""Release smoke benchmark for emlint (the automated tier).

Generates a small, deterministic set of Stim built-in DEMs plus three
text-level mutations of each, runs the emlint check battery on every case,
and records the outcomes under results/raw/release-smoke/<emlint-version>/
plus one append-only row in results/RUN_LOG.jsonl.

This is the record-only tier: it never adjudicates findings and never edits
historical results. Exit code follows the emlint contract:
0 = all checks passed, 1 = any error-severity failure, 2 = warnings only.

Run:
    python scripts/release_smoke.py --emlint-version 0.2.2
Self-test (writes nowhere persistent):
    python scripts/release_smoke.py --emlint-version 0.0.0 --no-log \
        --output-dir /tmp/release-smoke-selftest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import stim

import emlint

ROOT = Path(__file__).resolve().parent.parent

NOISE = {
    "after_clifford_depolarization": 0.001,
    "before_measure_flip_probability": 0.001,
    "after_reset_flip_probability": 0.001,
}

CASES = [
    ("repetition_d3_r3", "repetition_code:memory", 3, 3),
    ("rotated_surface_z_d3_r3", "surface_code:rotated_memory_z", 3, 3),
    ("rotated_surface_x_d3_r3", "surface_code:rotated_memory_x", 3, 3),
]

PAYLOADS = {
    "zero_probability": "error(0) D0",
    "logical_without_syndrome": "error(0.1) L0",
    "high_probability": "error(0.75) D0",
}


def _dem_text(generator: str, distance: int, rounds: int) -> str:
    circuit = stim.Circuit.generated(
        generator, distance=distance, rounds=rounds, **NOISE
    )
    return str(circuit.detector_error_model(decompose_errors=True))


def _findings(report: emlint.Report) -> list[dict[str, object]]:
    return [
        {
            "name": result.name,
            "passed": result.passed,
            "severity": result.severity,
            "message": result.message,
        }
        for result in report.results
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emlint-version", required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--no-log", action="store_true")
    args = parser.parse_args()

    started = time.perf_counter()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    out_dir = args.output_dir or (
        ROOT / "results" / "raw" / "release-smoke" / args.emlint_version
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    environment = {
        "python": platform.python_version(),
        "stim": stim.__version__,
        "emlint": args.emlint_version,
        "platform": platform.platform(),
    }

    runlog_rows: list[dict[str, object]] = []
    worst_severity = 0  # 0 pass, 2 warnings, 1 error
    checked = 0

    for case_name, generator, distance, rounds in CASES:
        base_text = _dem_text(generator, distance, rounds)
        variants = [("__baseline", base_text)]
        variants += [
            (f"__{mutation}", f"{base_text}\n{payload}\n")
            for mutation, payload in PAYLOADS.items()
        ]
        for variant_name, text in variants:
            report = emlint.check(text)
            findings = _findings(report)
            case_id = f"{case_name}{variant_name}"
            digest = hashlib.sha256(text.encode()).hexdigest()
            record = {
                "id": case_id,
                "emlint_version": args.emlint_version,
                "environment": environment,
                "input_sha256": digest,
                "findings": findings,
                "exit_code": 1
                if any(f["severity"] == "error" and not f["passed"] for f in findings)
                else (2 if any(not f["passed"] for f in findings) else 0),
            }
            (out_dir / f"{case_id}.emlint.json").write_text(
                json.dumps(record, indent=2) + "\n", encoding="utf-8"
            )
            runlog_rows.append(
                {
                    "id": f"release-smoke-{args.emlint_version}-{case_id}",
                    "command": f"emlint.check(<{case_id} DEM>)",
                    "environment": environment,
                    "input_hashes": {"dem": digest},
                    "exit_code": record["exit_code"],
                    "timestamp": stamp,
                    "complete": True,
                }
            )
            checked += 1
            for finding in findings:
                if finding["passed"]:
                    continue
                worst_severity = (
                    1 if finding["severity"] == "error" else max(worst_severity, 2)
                )

    if not args.no_log:
        with (ROOT / "results" / "RUN_LOG.jsonl").open("a", encoding="utf-8") as handle:
            for row in runlog_rows:
                handle.write(json.dumps(row) + "\n")

    elapsed = time.perf_counter() - started
    print(
        json.dumps(
            {
                "emlint_version": args.emlint_version,
                "cases_checked": checked,
                "worst_severity": worst_severity,
                "results_dir": str(out_dir),
                "duration_seconds": round(elapsed, 3),
            }
        )
    )
    return worst_severity


if __name__ == "__main__":
    sys.exit(main())
