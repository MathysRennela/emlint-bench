"""Build the upstream-issue fixture corpus (strong tier of the ecosystem survey).

One fixture per strong-tier finding of notes/ecosystem/UPSTREAM_ISSUE_SURVEY.md
(emlint-dev), each anchored to the upstream issue that exposed the failure
mode. Unlike the demo corpus (which proves checks fire), this corpus deliberately
includes *gap* fixtures: artifacts where the predicate class applies but the
current emlint build does NOT flag them. A gap fixture that starts failing
means emlint gained coverage — the build then fails loudly so the label can be
flipped from `gap` to `caught`.

Fixture matrix (all built on the demo baseline
workloads/demo/stim_rotated_surface_z_d3_r3.dem, which is duplicates-clean):

  ==========================================  =========================  ==========
  mutation                                    upstream issue             behavior
  ==========================================  =========================  ==========
  duplicate_target_in_mechanism               PECOS#800, PECOS#813       gap
  same_syndrome_disagreeing_observables       PECOS#780                  caught
  zero_probability                            Deltakit#329               caught
  negative_probability                        Deltakit#329               unlintable
  dropped_detector_referencer                 Stim#202                   caught
  dropped_observable_referencers              Stim#202                   gap
  ==========================================  =========================  ==========

Behaviors (verified empirically 2026-09-26, emlint 0.2.2 / stim 1.16.0):

- `caught`      — the expected check fires; expectation verified at build time.
- `gap`         — the expected check does NOT fire; recorded as the benchmark
                  gap. The build fails loudly if this changes.
- `unlintable`  — the DEM text is rejected by the frontend (exit-3 contract):
                  negative probabilities cannot exist in a parseable DEM, so
                  the out-of-range half of Deltakit#329 is loud, not silent.

Gap rationale (why these are representation gaps, not missing predicates):

- duplicate_target_in_mechanism: `ErrorMechanism.detectors` is a
  frozenset, so target multiplicity inside one instruction is discarded at
  parse time; `duplicates` cannot see `D0 D0` today. Catching it needs the
  repetition preserved (parse-level check), not a new predicate.
- dropped_observable_referencers: once every mechanism referencing L0 is
  removed, no DEM text declares L0, so presence-based predicates have nothing
  to compare against. Same blind spot the demo corpus recorded for its
  skipped `missing observable` mutant (build_demo_corpus.py docstring).

Run (repo root, emlint importable):
    python campaigns/build_upstream_issue_corpus.py
Outputs:
    workloads/upstream_issues/*.dem
    manifests/upstream_issue_manifest.jsonl
    results/raw/upstream_issue_corpus_verification_<date>.json
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
BASELINE = ROOT / "workloads" / "demo" / "stim_rotated_surface_z_d3_r3.dem"
WORKLOADS = ROOT / "workloads" / "upstream_issues"
MANIFEST = ROOT / "manifests" / "upstream_issue_manifest.jsonl"
RESULTS = ROOT / "results" / "raw"

BASE_NAME = "stim_rotated_surface_z_d3_r3"

SURVEY = "notes/ecosystem/UPSTREAM_ISSUE_SURVEY.md (emlint-dev)"

MUTATIONS: list[dict[str, object]] = [
    {
        "mutation": "duplicate_target_in_mechanism",
        "issues": [
            ("PECOS-packages/PECOS", 800),
            ("PECOS-packages/PECOS", 813),
        ],
        "expected_check": "duplicates",
        "expected_behavior": "gap",
        "construct": "append\nerror(0.001) D0 D0",
    },
    {
        "mutation": "same_syndrome_disagreeing_observables",
        "issues": [("PECOS-packages/PECOS", 780)],
        "expected_check": "correctability",
        "expected_behavior": "caught",
        "construct": "append\nerror(0.001) D3 D4\nerror(0.001) D3 D4 L0",
    },
    {
        "mutation": "zero_probability",
        "issues": [("Deltakit/deltakit", 329)],
        "expected_check": "probability_bounds",
        "expected_behavior": "caught",
        "construct": "append\nerror(0) D0",
    },
    {
        "mutation": "negative_probability",
        "issues": [("Deltakit/deltakit", 329)],
        "expected_check": None,
        "expected_behavior": "unlintable",
        "construct": "append\nerror(-0.001) D0",
    },
    {
        "mutation": "dropped_detector_referencer",
        "issues": [("quantumlib/Stim", 202)],
        "expected_check": "sensitivity",
        "expected_behavior": "caught",
        "construct": "drop error lines referencing D0, keep detector annotation",
    },
    {
        "mutation": "dropped_observable_referencers",
        "issues": [("quantumlib/Stim", 202)],
        "expected_check": "observable_coverage",
        "expected_behavior": "gap",
        "construct": "drop all error lines referencing L0",
    },
]


def _construct(base_text: str, construct: str) -> str:
    if construct.startswith("append\n"):
        pad = "" if base_text.endswith("\n") else "\n"
        return base_text + pad + construct[len("append\n") :] + "\n"
    if construct.startswith("drop error lines referencing D0"):
        kept = [
            line
            for line in base_text.splitlines()
            if not (line.startswith("error(") and " D0" in line)
        ]
        return "\n".join(kept) + "\n"
    if construct.startswith("drop all error lines referencing L0"):
        return (
            "\n".join(
                line for line in base_text.splitlines() if "L0" not in line
            )
            + "\n"
        )
    raise ValueError(f"unknown construct: {construct}")


def _findings(report: emlint.Report) -> list[dict[str, object]]:
    return [
        {"name": r.name, "passed": r.passed, "severity": r.severity}
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
    base_text = BASELINE.read_text(encoding="utf-8")
    base_report = emlint.check(base_text)
    base_failing = sorted(
        f.name for f in base_report.results if not f.passed
    )
    if base_failing:
        print(
            f"FATAL: baseline {BASELINE.name} not clean: {base_failing}",
            file=sys.stderr,
        )
        return 1

    WORKLOADS.mkdir(parents=True, exist_ok=True)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)

    manifest_rows: list[dict[str, object]] = []
    verification: list[dict[str, object]] = []
    failures: list[str] = []

    manifest_rows.append(
        {
            "file": f"workloads/demo/{BASELINE.name}",
            "artifact_kind": "baseline_reference",
            "note": "baseline lives in the demo corpus; not duplicated here",
            "dem_sha256": hashlib.sha256(base_text.encode()).hexdigest(),
            "date": date,
            "environment": environment,
        }
    )

    for spec in MUTATIONS:
        mutation = str(spec["mutation"])
        expected_check = spec["expected_check"]
        expected_behavior = str(spec["expected_behavior"])
        text = _construct(base_text, str(spec["construct"]))
        path = WORKLOADS / f"{BASE_NAME}__{mutation}.dem"
        path.write_text(text, encoding="utf-8")

        behavior: str
        failing: list[str] = []
        raised: str | None = None
        if expected_behavior == "unlintable":
            try:
                report = emlint.check(text)
            except Exception as exc:  # noqa: BLE001 - recorded verbatim
                behavior = "unlintable"
                raised = f"{type(exc).__name__}: {exc}"
                exit_code = 3
            else:
                failing = sorted(
                    f.name for f in report.results if not f.passed
                )
                behavior = (
                    "caught"
                    if any(
                        f.name == expected_check and not f.passed
                        for f in report.results
                    )
                    else "not_flagged"
                )
                exit_code = _exit_code(_findings(report))
        else:
            report = emlint.check(text)
            failing = sorted(
                f.name for f in report.results if not f.passed
            )
            fires = any(
                f.name == expected_check and not f.passed
                for f in report.results
            )
            behavior = "caught" if fires else "not_flagged"
            exit_code = _exit_code(_findings(report))

        if expected_behavior == "caught":
            ok = behavior == "caught"
        elif expected_behavior == "gap":
            ok = behavior == "not_flagged"
        else:
            ok = behavior == "unlintable"
        issue_urls = [
            f"https://github.com/{repo}/issues/{num}"
            for repo, num in spec["issues"]  # type: ignore[union-attr]
        ]
        row = {
            "file": f"workloads/upstream_issues/{path.name}",
            "artifact_kind": {
                "caught": "mutant_caught",
                "gap": "mutant_gap",
                "unlintable": "mutant_unlintable",
            }[expected_behavior],
            "base": BASE_NAME,
            "mutation": mutation,
            "issues": [
                f"{repo}#{num}" for repo, num in spec["issues"]  # type: ignore[union-attr]
            ],
            "issue_urls": issue_urls,
            "survey": SURVEY,
            "expected_check": expected_check,
            "expected_behavior": expected_behavior,
            "verified_behavior": behavior,
            "verified_failing_checks": failing,
            "verified_exit_code": exit_code,
            "dem_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "date": date,
            "environment": environment,
        }
        if raised is not None:
            row["frontend_error"] = raised
        manifest_rows.append(row)
        verification.append(
            {
                "file": row["file"],
                "expectation": f"{expected_behavior} ({expected_check})",
                "verified": ok,
                "behavior": behavior,
                "failing_checks": failing,
                "exit_code": exit_code,
            }
        )
        if not ok:
            failures.append(
                f"{path.name}: expected {expected_behavior} "
                f"({expected_check}) but observed {behavior} "
                f"(failing: {failing})"
            )

    with MANIFEST.open("w", encoding="utf-8") as handle:
        for row in manifest_rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    verification_path = (
        RESULTS / f"upstream_issue_corpus_verification_{date}.json"
    )
    verification_path.write_text(
        json.dumps(
            {
                "date": date,
                "environment": environment,
                "survey": SURVEY,
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
