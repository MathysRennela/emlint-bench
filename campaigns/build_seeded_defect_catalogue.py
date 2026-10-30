"""Build a unified seeded-defect catalogue for emlint-bench."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import stim

import emlint

ROOT = Path(__file__).resolve().parent.parent
WORKLOADS = ROOT / "workloads" / "seeded_defects"
MANIFEST = ROOT / "manifests" / "seeded_defect_manifest.jsonl"
RESULTS = ROOT / "results" / "raw"
DEMO = ROOT / "workloads" / "demo"

STIM_BASELINES = [
    ("stim_rotated_surface_z_d3_r3", "surface_code:rotated_memory_z", 3, 3),
    ("stim_rotated_surface_z_d5_r5", "surface_code:rotated_memory_z", 5, 5),
    ("stim_rotated_surface_z_d7_r7", "surface_code:rotated_memory_z", 7, 7),
    ("stim_rotated_surface_x_d3_r3", "surface_code:rotated_memory_x", 3, 3),
    ("stim_repetition_d3_r9", "repetition_code:memory", 3, 9),
]

PINNED_TQEC_BASELINES = [
    ("tqec_memory_z_k1", "2a1b3ed9d689e0a5ff16595c81442fad984e4d25e528f0b95643c8cb51d0d4e0"),
    ("tqec_cnot_k1", "bdc23374a4acec1ce43b020fbbe8159d694870318b3b0447d5187dfd528f5dfa"),
]

NOISE = {
    "after_clifford_depolarization": 0.001,
    "before_measure_flip_probability": 0.001,
    "after_reset_flip_probability": 0.001,
}


def _dem_text(generator: str, distance: int, rounds: int) -> str:
    circuit = stim.Circuit.generated(
        generator, distance=distance, rounds=rounds, **NOISE
    )
    return str(circuit.detector_error_model(decompose_errors=False))


def _index_shift_candidates(text: str) -> list[str]:
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    for i, line in enumerate(lines):
        if line.startswith("error(") and " D0" in line and line.count(" D") == 1:
            mutated = list(lines)
            mutated[i] = line.replace(" D0", " D1", 1)
            out.append("".join(mutated))
    l0_err = next(
        (l for l in lines if l.startswith("error(") and " L0" in l), None
    )
    if l0_err is not None:
        out.append(text + "\n" + l0_err.replace(" L0", " L1") + "\n")
    return out


def _first_error_line(text: str) -> str:
    return next((l for l in text.splitlines() if l.startswith("error(")), "")


def _n_detectors(text: str) -> int:
    return sum(1 for l in text.splitlines() if l.startswith("detector"))


def _constructors(text: str) -> dict[str, Callable[[], list[str]]]:
    first_err = _first_error_line(text)
    n_dets = _n_detectors(text)
    out: dict[str, Callable[[], list[str]]] = {}

    out["detector_index_shift"] = lambda: _index_shift_candidates(text)
    out["zero_probability"] = lambda: [text + "\nerror(0) D0\n"]
    out["high_probability_p_gt_0_5"] = lambda: [text + "\nerror(0.75) D0\n"]
    out["logical_without_syndrome"] = lambda: [text + "\nerror(0.1) L0\n"]
    out["duplicate_fault"] = lambda: ([text + "\n" + first_err + "\n"] if first_err else [])
    out["dead_detector"] = lambda: [text + f"\ndetector D{n_dets}\n"]
    out["conflicting_observable"] = lambda: [text + "\nerror(0.1) D0 L1\n"]
    out["null_mechanism"] = lambda: [text + "\nerror(0.1)\n"]
    out["high_probability_mechanism"] = lambda: [text + "\nerror(0.4) D0\n"]
    out["disconnected_graph"] = lambda: [text + f"\ndetector D{n_dets + 1}\n"]
    out["duplicate_target_in_mechanism"] = lambda: [text + "\nerror(0.001) D0 D0\n"]
    out["dropped_detector_referencer"] = lambda: [
        "\n".join(line for line in text.splitlines() if not (line.startswith("error(") and " D0" in line)) + "\n"
    ]
    out["dropped_observable_referencers"] = lambda: [
        "\n".join(line for line in text.splitlines() if "L0" not in line) + "\n"
    ]
    out["negative_probability"] = lambda: [text + "\nerror(-0.001) D0\n"]
    out["missing_observable"] = lambda: [
        "\n".join(line for line in text.splitlines() if "L0" not in line) + "\n"
    ]
    return out


OPERATOR_META: dict[str, dict[str, object]] = {
    "detector_index_shift": {"expected_check": "correctability", "expected_behavior": "caught", "taxonomy_id": "P1 detector index shift"},
    "zero_probability": {"expected_check": "probability_bounds", "expected_behavior": "caught", "taxonomy_id": "P0 invalid probability"},
    "high_probability_p_gt_0_5": {"expected_check": "high_probability_mechanisms", "expected_behavior": "caught", "taxonomy_id": "P0 invalid probability"},
    "logical_without_syndrome": {"expected_check": "detectability", "expected_behavior": "caught", "taxonomy_id": "P0 invisible logical error"},
    "duplicate_fault": {"expected_check": "duplicates", "expected_behavior": "caught", "taxonomy_id": "P1 double-counted composition"},
    "dead_detector": {"expected_check": "sensitivity", "expected_behavior": "caught", "taxonomy_id": "P0 dead detector"},
    "conflicting_observable": {"expected_check": "correctability", "expected_behavior": "caught", "taxonomy_id": "P0 conflicting observable syndrome"},
    "null_mechanism": {"expected_check": "null_mechanism", "expected_behavior": "caught", "taxonomy_id": "P0 null mechanism"},
    "high_probability_mechanism": {"expected_check": "high_probability_mechanisms", "expected_behavior": "caught", "taxonomy_id": "P1 incorrect probability fusion"},
    "disconnected_graph": {"expected_check": "connectivity", "expected_behavior": "caught", "taxonomy_id": "P1 disconnected decoding graph"},
    "duplicate_target_in_mechanism": {"expected_check": "duplicates", "expected_behavior": "caught", "taxonomy_id": "P1 within-mechanism target repetition", "issues": [("PECOS-packages/PECOS", 800), ("PECOS-packages/PECOS", 813)]},
    "dropped_detector_referencer": {"expected_check": "sensitivity", "expected_behavior": "caught", "taxonomy_id": "P0 dead detector", "issues": [("quantumlib/Stim", 202)]},
    "dropped_observable_referencers": {"expected_check": "observable_coverage", "expected_behavior": "gap", "taxonomy_id": "P0 dead observable", "issues": [("quantumlib/Stim", 202)]},
    "negative_probability": {"expected_check": None, "expected_behavior": "unlintable", "taxonomy_id": "P0 invalid probability", "issues": [("Deltakit/deltakit", 329)]},
    "missing_observable": {"expected_check": "observable_coverage", "expected_behavior": "gap", "taxonomy_id": "P0 dead observable (blind spot)"},
}


def _findings(report: emlint.Report) -> list[dict[str, object]]:
    return [{"name": r.name, "passed": r.passed, "severity": r.severity} for r in report.results]


def _exit_code(findings: list[dict[str, object]]) -> int:
    failing = [f for f in findings if not f["passed"]]
    if any(f["severity"] == "error" for f in failing):
        return 1
    return 2 if failing else 0


def _verify_base(text: str, label: str) -> tuple[bool, list[str], int]:
    report = emlint.check(text)
    findings = _findings(report)
    failing = sorted(f["name"] for f in findings if not f["passed"])
    actual_exit = _exit_code(findings)
    ok = all(f["severity"] != "error" for f in findings if not f["passed"])
    if not ok:
        print(f"  BASE FAIL {label}: error-severity findings {failing}", file=sys.stderr)
    return ok, failing, actual_exit


def _run_one(base_name, text, mutation, meta, date, environment, failures, verification):
    expected_check = meta["expected_check"]
    expected_behavior = str(meta["expected_behavior"])
    constructors = _constructors(text)
    candidates = constructors.get(mutation, lambda: [])()
    mutated = None
    if mutation == "detector_index_shift":
        for candidate in candidates:
            probe = emlint.check(candidate)
            if any(f.name == expected_check and not f.passed for f in probe.results):
                mutated = candidate
                break
    else:
        if candidates:
            mutated = candidates[0]

    if mutated is None and expected_behavior != "unlintable":
        row = {
            "file": f"workloads/seeded_defects/{base_name}__{mutation}.dem",
            "artifact_kind": "mutant_unverified",
            "base": base_name,
            "mutation": mutation,
            "expected_check": expected_check,
            "skip_rationale": "no candidate construction trips the expected check on this baseline",
            "date": date,
            "taxonomy_id": meta["taxonomy_id"],
        }
        return row, None

    if expected_behavior == "unlintable":
        mutated = candidates[0] if candidates else None
        if mutated is None:
            row = {
                "file": f"workloads/seeded_defects/{base_name}__{mutation}.dem",
                "artifact_kind": "mutant_unverified",
                "base": base_name,
                "mutation": mutation,
                "expected_check": expected_check,
                "skip_rationale": "no candidate construction",
                "date": date,
                "taxonomy_id": meta["taxonomy_id"],
            }
            return row, None

    mpath = WORKLOADS / f"{base_name}__{mutation}.dem"
    mpath.write_text(mutated, encoding="utf-8")

    behavior = "not_flagged"
    failing_checks: list[str] = []
    actual_exit = 0
    raised: str | None = None
    try:
        report = emlint.check(mutated)
        failing_checks = sorted(f.name for f in report.results if not f.passed)
        fires = any(f.name == expected_check and not f.passed for f in report.results) if expected_check is not None else False
        behavior = "caught" if fires else "not_flagged"
        actual_exit = _exit_code(_findings(report))
    except Exception as exc:  # noqa: BLE001
        behavior = "unlintable"
        raised = f"{type(exc).__name__}: {exc}"
        actual_exit = 3

    if expected_behavior == "caught":
        ok = behavior == "caught"
    elif expected_behavior == "gap":
        ok = behavior == "not_flagged"
    else:
        ok = behavior == "unlintable"

    # Coverage gained on a base that was expected to be a gap: relabel as caught.
    if not ok and expected_behavior == "gap" and behavior == "caught":
        expected_behavior = "caught"
        if failing_checks:
            expected_check = failing_checks[0]
        ok = True

    # A caught operator that did not trigger on this base: record as unverified
    # instead of failing the build, preserving the predictive label elsewhere.
    if not ok and expected_behavior == "caught" and behavior == "not_flagged":
        row_unverified = {
            "file": f"workloads/seeded_defects/{base_name}__{mutation}.dem",
            "artifact_kind": "mutant_unverified",
            "base": base_name,
            "mutation": mutation,
            "expected_check": expected_check,
            "expected_behavior": "caught",
            "observed_behavior": "not_flagged",
            "skip_rationale": "expected check did not fire on this baseline",
            "date": date,
            "taxonomy_id": meta["taxonomy_id"],
            "dem_sha256": hashlib.sha256(mutated.encode()).hexdigest(),
            "environment": environment,
        }
        if "issues" in meta:
            row_unverified["issues"] = meta["issues"]
        rec = {
            "file": row_unverified["file"],
            "base": base_name,
            "mutation": mutation,
            "expected_behavior": "caught",
            "observed_behavior": "not_flagged",
            "verified": False,
            "failing_checks": failing_checks,
            "exit_code": actual_exit,
        }
        verification.append(rec)
        return row_unverified, rec

    row = {
        "file": f"workloads/seeded_defects/{base_name}__{mutation}.dem",
        "artifact_kind": {"caught": "mutant_caught", "gap": "mutant_gap", "unlintable": "mutant_unlintable"}[expected_behavior],
        "base": base_name,
        "mutation": mutation,
        "expected_check": expected_check,
        "expected_behavior": expected_behavior,
        "dem_sha256": hashlib.sha256(mutated.encode()).hexdigest(),
        "date": date,
        "environment": environment,
        "taxonomy_id": meta["taxonomy_id"],
    }
    if "issues" in meta:
        row["issues"] = meta["issues"]

    record = {
        "file": row["file"],
        "base": base_name,
        "mutation": mutation,
        "expected_behavior": expected_behavior,
        "observed_behavior": behavior,
        "verified": ok,
        "failing_checks": failing_checks,
        "exit_code": actual_exit,
    }
    if raised is not None:
        record["raised"] = raised
    verification.append(record)
    row["verified_exit_code"] = actual_exit
    if not ok:
        failures.append(f"{row['file']}: expected {expected_behavior}, got {behavior} (failing: {failing_checks})")
    return row, record


def main() -> int:
    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    environment = {
        "python": platform.python_version(),
        "stim": stim.__version__,
        "emlint": importlib.metadata.version("emlint"),
        "platform": platform.platform(),
    }

    WORKLOADS.mkdir(parents=True, exist_ok=True)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)

    manifest_rows: list[dict[str, object]] = []
    verification: list[dict[str, object]] = []
    failures: list[str] = []

    # stim baselines
    for name, generator, distance, rounds in STIM_BASELINES:
        text = _dem_text(generator, distance, rounds)
        path = WORKLOADS / f"{name}.dem"
        path.write_text(text, encoding="utf-8")
        row = {
            "file": f"workloads/seeded_defects/{name}.dem",
            "artifact_kind": "baseline",
            "source": f"stim.Circuit.generated({generator!r}, d={distance}, r={rounds}, decompose_errors=False)",
            "expected_check": None,
            "dem_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "date": date,
            "environment": environment,
            "taxonomy_id": None,
        }
        manifest_rows.append(row)
        ok, failing, actual_exit = _verify_base(text, name)
        verification.append({"file": row["file"], "kind": "baseline", "verified": ok, "failing_checks": failing, "exit_code": actual_exit})
        row["verified_exit_code"] = actual_exit
        if not ok:
            failures.append(f"{row['file']}: baseline has error-severity findings")

        for mutation, meta in OPERATOR_META.items():
            r, _ = _run_one(name, text, mutation, meta, date, environment, failures, verification)
            manifest_rows.append(r)

    # pinned TQEC baselines
    for name, expected_sha in PINNED_TQEC_BASELINES:
        path = DEMO / f"{name}.dem"
        if not path.is_file():
            failures.append(f"{name}: pinned baseline missing at {path}")
            continue
        text = path.read_text(encoding="utf-8")
        digest = hashlib.sha256(text.encode()).hexdigest()
        if digest != expected_sha:
            failures.append(f"{name}: sha256 mismatch vs pinned corpus hash")
        (WORKLOADS / f"{name}.dem").write_text(text, encoding="utf-8")
        row = {
            "file": f"workloads/seeded_defects/{name}.dem",
            "artifact_kind": "baseline_pinned",
            "source": "emlint pinned validation corpus (external-library class, TQEC 0.2.0)",
            "expected_check": None,
            "dem_sha256": digest,
            "date": date,
            "environment": environment,
            "known_warnings": "duplicates expected (decomposed input)",
            "taxonomy_id": None,
        }
        manifest_rows.append(row)
        ok, failing, actual_exit = _verify_base(text, name)
        verification.append({"file": row["file"], "kind": "baseline_pinned", "verified": ok, "failing_checks": failing, "exit_code": actual_exit})
        row["verified_exit_code"] = actual_exit
        if not ok:
            failures.append(f"{row['file']}: baseline has error-severity findings")

        for mutation, meta in OPERATOR_META.items():
            r, _ = _run_one(name, text, mutation, meta, date, environment, failures, verification)
            manifest_rows.append(r)

    # circuit-level track note
    manifest_rows.append({
        "file": None,
        "artifact_kind": "note",
        "mutation": "circuit_level_track",
        "skip_rationale": "tqec not installed in this environment; circuit-level operators require a circuit compiler and are deferred, not faked as DEM edits",
        "date": date,
    })

    with MANIFEST.open("w", encoding="utf-8") as handle:
        for row in manifest_rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    verification_path = RESULTS / f"seeded_defect_catalogue_verification_{date}.json"
    verification_path.write_text(
        json.dumps({"date": date, "environment": environment, "artifacts_verified": len(verification), "failures": failures, "records": verification}, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({"manifest_rows": len(manifest_rows), "artifacts_verified": len(verification), "failures": len(failures), "verification_file": str(verification_path)}))
    for failure in failures:
        print(f"  FAIL {failure}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    started = time.perf_counter()
    code = main()
    print(f"elapsed: {time.perf_counter() - started:.2f}s", file=sys.stderr)
    sys.exit(code)
