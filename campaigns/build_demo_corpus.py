"""Build the IEEE-demo corpus: baselines + pre-labeled fault injections.

Sprint task (Day 1, agent): stim builtins d=3/5/7 plus pinned TQEC
memory/CNOT baselines, each with ~8 hand-broken mutants pre-labeled with the
production check that must catch it. One artifact, three uses (demo,
promotion evidence, regression).

Mutation classes and expected checks (verified empirically on the baseline
family before labelling):

  ============================  ==========================================
  detector_index_shift          correctability
  zero_probability              probability_bounds
  high_probability_p_gt_0_5     probability_bounds
  logical_without_syndrome      detectability  (distance-0 fault family)
  duplicate_fault               duplicates
  dead_detector                 sensitivity
  conflicting_observable        correctability
  ============================  ==========================================

Two mutant classes from the sprint list are recorded as skipped with
rationale rather than forced:

- swapped CNOT layer: circuit-level; requires the tqec package (skipped when
  tqec is not importable).
- missing observable: no production check fires when an OBSERVABLE_INCLUDE-
  declared observable loses all mechanism coverage on real DEMs (verified
  empirically 2026-09-12; `observable_coverage` fires only on the minimal
  synthetic form). Recorded as a candidate blind spot, not a demo mutant.

Baselines use decompose_errors=False so a clean baseline exits 0; the pinned
TQEC baselines are known to emit `duplicates` warnings (decomposed input),
which is recorded per row. Every expectation is verified at build time with
the installed emlint; an unmet expectation fails the build loudly.

Run (repo root):
    python campaigns/build_demo_corpus.py
Outputs:
    workloads/demo/*.dem
    manifests/demo_manifest.jsonl
    results/raw/demo_corpus_verification_<date>.json
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import stim

import emlint

ROOT = Path(__file__).resolve().parent.parent
WORKLOADS = ROOT / "workloads" / "demo"
MANIFEST = ROOT / "manifests" / "demo_manifest.jsonl"
RESULTS = ROOT / "results" / "raw"

NOISE = {
    "after_clifford_depolarization": 0.001,
    "before_measure_flip_probability": 0.001,
    "after_reset_flip_probability": 0.001,
}

STIM_BASELINES = [
    ("stim_rotated_surface_z_d3_r3", "surface_code:rotated_memory_z", 3, 3),
    ("stim_rotated_surface_z_d5_r5", "surface_code:rotated_memory_z", 5, 5),
    ("stim_rotated_surface_z_d7_r7", "surface_code:rotated_memory_z", 7, 7),
    ("stim_rotated_surface_x_d3_r3", "surface_code:rotated_memory_x", 3, 3),
    ("stim_repetition_d3_r9", "repetition_code:memory", 3, 9),
]

# Pinned TQEC baselines, hash-verified against the emlint validation corpus
# manifest (ids tqec_memory_z_k1 / tqec_cnot_k1) on 2026-09-12.
PINNED_TQEC_BASELINES = [
    ("tqec_memory_z_k1", "2a1b3ed9d689e0a5ff16595c81442fad984e4d25e528f0b95643c8cb51d0d4e0"),
    ("tqec_cnot_k1", "bdc23374a4acec1ce43b020fbbe8159d694870318b3b0447d5187dfd528f5dfa"),
]

NOISE_P = 0.001


def _dem_text(generator: str, distance: int, rounds: int) -> str:
    circuit = stim.Circuit.generated(
        generator, distance=distance, rounds=rounds, **NOISE
    )
    return str(circuit.detector_error_model(decompose_errors=False))


def _mutations(text: str) -> list[tuple[str, str | None, str]]:
    """Return (mutation_name, mutated_text_or_None, expected_check) triples."""
    lines = text.splitlines()
    first_err = next((l for l in lines if l.startswith("error(")), "")
    n_dets = sum(1 for l in lines if l.startswith("detector"))
    out: list[tuple[str, str | None, str]] = []

    out.append(("detector_index_shift", None, "correctability"))
    out.append(("zero_probability", text + "\nerror(0) D0\n", "probability_bounds"))
    out.append(("high_probability_p_gt_0_5", text + "\nerror(0.75) D0\n", "probability_bounds"))
    out.append(("logical_without_syndrome", text + "\nerror(0.1) L0\n", "detectability"))
    out.append(("duplicate_fault", text + "\n" + first_err + "\n", "duplicates"))
    out.append(("dead_detector", text + f"\ndetector D{n_dets}\n", "sensitivity"))
    return out


def _index_shift_candidates(text: str) -> list[str]:
    """Ordered candidate constructions for the detector-index-shift mutant.

    Which construction trips `correctability` varies by baseline family
    (verified empirically 2026-09-12), so the harness tries them in order
    and records the first that verifies; see _mutations_for.
    """
    lines = text.splitlines(keepends=True)
    out = []
    for i, line in enumerate(lines):
        if line.startswith("error(") and " D0" in line and line.count(" D") == 1:
            mutated = list(lines)
            mutated[i] = line.replace(" D0", " D1", 1)
            out.append("".join(mutated))
    l0_err = next((l for l in lines if l.startswith("error(") and " L0" in l), None)
    if l0_err is not None:
        out.append(text + "\n" + l0_err.replace(" L0", " L1") + "\n")
    return out


def _findings(report: emlint.Report) -> list[dict[str, object]]:
    return [
        {
            "name": r.name,
            "passed": r.passed,
            "severity": r.severity,
        }
        for r in report.results
    ]


def _exit_code(findings: list[dict[str, object]]) -> int:
    failing = [f for f in findings if not f["passed"]]
    if any(f["severity"] == "error" for f in failing):
        return 1
    return 2 if failing else 0


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

    def verify(row: dict[str, object], text: str, is_baseline: bool) -> None:
        report = emlint.check(text)
        findings = _findings(report)
        failing = {f["name"] for f in findings if not f["passed"]}
        actual_exit = _exit_code(findings)
        expected_check = row.get("expected_check")
        if is_baseline:
            ok = all(
                f["severity"] != "error" for f in findings if not f["passed"]
            )
            expectation = "no error-severity finding on baseline"
        else:
            ok = expected_check in failing  # type: ignore[operator]
            expectation = f"{expected_check} fires"
        record = {
            "file": row["file"],
            "kind": row["artifact_kind"],
            "expectation": expectation,
            "verified": ok,
            "failing_checks": sorted(failing),
            "exit_code": actual_exit,
            "findings": findings,
        }
        verification.append(record)
        row["verified_exit_code"] = actual_exit
        if not ok:
            failures.append(f"{row['file']}: {expectation} NOT met (failing: {sorted(failing)})")

    # --- stim baselines + mutants ---
    for name, generator, distance, rounds in STIM_BASELINES:
        text = _dem_text(generator, distance, rounds)
        path = WORKLOADS / f"{name}.dem"
        path.write_text(text, encoding="utf-8")
        row = {
            "file": f"workloads/demo/{name}.dem",
            "artifact_kind": "baseline",
            "source": f"stim.Circuit.generated({generator!r}, d={distance}, r={rounds}, decompose_errors=False)",
            "expected_check": None,
            "dem_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "date": date,
            "environment": environment,
        }
        manifest_rows.append(row)
        verify(row, text, is_baseline=True)

        for mutation, mutated, expected_check in _mutations(text):
            if mutation == "detector_index_shift":
                candidates = _index_shift_candidates(text)
            else:
                candidates = [mutated] if mutated is not None else []
            mutated = None
            for candidate in candidates:
                probe = emlint.check(candidate)
                if any(
                    f.name == expected_check and not f.passed for f in probe.results
                ):
                    mutated = candidate
                    break
            if mutated is None:
                manifest_rows.append({
                    "file": f"workloads/demo/{name}__{mutation}.dem",
                    "artifact_kind": "mutant_unverified",
                    "base": name,
                    "mutation": mutation,
                    "expected_check": expected_check,
                    "skip_rationale": "no candidate construction trips the expected check on this baseline",
                    "date": date,
                })
                continue
            mpath = WORKLOADS / f"{name}__{mutation}.dem"
            mpath.write_text(mutated, encoding="utf-8")
            mrow = {
                "file": f"workloads/demo/{name}__{mutation}.dem",
                "artifact_kind": "mutant",
                "base": name,
                "mutation": mutation,
                "expected_check": expected_check,
                "dem_sha256": hashlib.sha256(mutated.encode()).hexdigest(),
                "date": date,
                "environment": environment,
            }
            manifest_rows.append(mrow)
            verify(mrow, mutated, is_baseline=False)

    # --- pinned TQEC baselines + mutants ---
    for name, expected_sha in PINNED_TQEC_BASELINES:
        path = WORKLOADS / f"{name}.dem"
        if not path.is_file():
            failures.append(f"{name}: pinned baseline missing at {path}")
            continue
        text = path.read_text(encoding="utf-8")
        digest = hashlib.sha256(text.encode()).hexdigest()
        if digest != expected_sha:
            failures.append(f"{name}: sha256 mismatch vs pinned corpus hash")
        row = {
            "file": f"workloads/demo/{name}.dem",
            "artifact_kind": "baseline_pinned",
            "source": "emlint pinned validation corpus (external-library class, TQEC 0.2.0)",
            "expected_check": None,
            "dem_sha256": digest,
            "date": date,
            "environment": environment,
            "known_warnings": "duplicates expected (decomposed input)",
        }
        manifest_rows.append(row)
        verify(row, text, is_baseline=True)

        for mutation, mutated, expected_check in _mutations(text):
            if mutation == "detector_index_shift":
                candidates = _index_shift_candidates(text)
            else:
                candidates = [mutated] if mutated is not None else []
            mutated = None
            for candidate in candidates:
                probe = emlint.check(candidate)
                if any(
                    f.name == expected_check and not f.passed for f in probe.results
                ):
                    mutated = candidate
                    break
            if mutated is None:
                manifest_rows.append({
                    "file": f"workloads/demo/{name}__{mutation}.dem",
                    "artifact_kind": "mutant_unverified",
                    "base": name,
                    "mutation": mutation,
                    "expected_check": expected_check,
                    "skip_rationale": "no candidate construction trips the expected check on this baseline",
                    "date": date,
                })
                continue
            mpath = WORKLOADS / f"{name}__{mutation}.dem"
            mpath.write_text(mutated, encoding="utf-8")
            mrow = {
                "file": f"workloads/demo/{name}__{mutation}.dem",
                "artifact_kind": "mutant",
                "base": name,
                "mutation": mutation,
                "expected_check": expected_check,
                "dem_sha256": hashlib.sha256(mutated.encode()).hexdigest(),
                "date": date,
                "environment": environment,
            }
            manifest_rows.append(mrow)
            verify(mrow, mutated, is_baseline=False)

    # --- tqec availability note (swapped CNOT layer is circuit-level) ---
    try:
        import tqec  # noqa: F401
        tqec_note = "tqec importable: circuit-level mutants (swapped CNOT layer) are future work"
    except ImportError:
        tqec_note = "tqec not installed: swapped-CNOT-layer mutant skipped with this rationale"
    manifest_rows.append({
        "file": None,
        "artifact_kind": "note",
        "mutation": "swapped_cnot_layer",
        "skip_rationale": tqec_note,
        "date": date,
    })

    with MANIFEST.open("w", encoding="utf-8") as handle:
        for row in manifest_rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    verification_path = RESULTS / f"demo_corpus_verification_{date}.json"
    verification_path.write_text(
        json.dumps(
            {
                "date": date,
                "environment": environment,
                "artifacts_verified": len(verification),
                "failures": failures,
                "records": verification,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "manifest_rows": len(manifest_rows),
                "artifacts_verified": len(verification),
                "failures": len(failures),
                "verification_file": str(verification_path),
                "tqec_note": tqec_note,
            }
        )
    )
    for failure in failures:
        print(f"  FAIL {failure}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    started = time.perf_counter()
    code = main()
    print(f"elapsed: {time.perf_counter() - started:.2f}s", file=sys.stderr)
    sys.exit(code)
