"""QECirc noisy-corpus campaign: 714 DEMs rerun with applicability context.

Reruns the current emlint frontend over the QECirc noisy corpus (p=0.001,
commit 2a939badcb06ff711fb957f3d1358edfbacba338) with applicability context
declared per circuit role, per the v0.2.2 contract:

- ``circuit_role=state_preparation`` for preparation-method families. The
  QECirc public library is a state-preparation corpus: its non-encoding
  method families are state-preparation synthesis heuristics (ft/det-ft/
  non-ft heuristics, flag-at-origin, RL-discovered circuits, tableau
  preparation) and the measurement schedules used by those circuits
  (cardinal, zx-coloration, edge-coloring, depth-optimal, alphasyndrome,
  bivariate-bicycle). detectability is outside its applicability domain for
  these roles (no complete syndrome is claimed) and must surface as an
  explicit ``skipped`` result.
- ``circuit_role=encoding`` for encoding families (``*encoding*``). No
  ``complete_syndrome`` claim is made, so detectability surfaces as
  ``inconclusive`` (exit 2) rather than a verdict.
- ``decoder=matching (pymatching)`` declared so the 275 preview
  ``correctability`` warnings are interpreted under a stated decoder
  assumption.

Verification gate: after role declaration, zero ``detectability`` error
verdicts may remain. Any residual detectability failure is a genuine finding
that the role map failed to cover and is reported (never silently dropped).

Appends manifest rows to CORPUS_MANIFEST.jsonl and run rows to RUN_LOG.jsonl.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import time
from collections import Counter
from pathlib import Path

import stim

import emlint
from emlint.report import format_json

ROOT = Path(__file__).parent
SRC = ROOT.parent / "external" / "qecirc_noisy" / "dem"  # source DEMs are internal library-study artifacts, not redistributed; outputs preserved under results/raw/
RAW = ROOT / "raw" / "qecirc_noisy"
QECIRC_COMMIT = "2a939badcb06ff711fb957f3d1358edfbacba338"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def role_for(name: str) -> str:
    """Filename-based circuit role; the rule is documented in the module docstring."""
    return "encoding" if "encoding" in name else "state_preparation"


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    emlint_version = importlib.metadata.version("emlint")
    environment = {
        "python": __import__("platform").python_version(),
        "stim": stim.__version__,
        "emlint": emlint_version,
    }
    status_counts: Counter[str] = Counter()
    exit_counts: Counter[int] = Counter()
    finding_counts: Counter[str] = Counter()
    residual_detectability_failures: list[str] = []
    corpus_rows: list[dict[str, object]] = []
    run_rows: list[dict[str, object]] = []

    for path in sorted(SRC.glob("*.dem")):
        role = role_for(path.stem)
        context = {"circuit_role": role, "decoder": "matching (pymatching)"}
        dem_bytes = path.read_bytes()
        try:
            stim.DetectorErrorModel(dem_bytes.decode())
        except Exception as exc:  # pragma: no cover - corpus is pre-validated
            run_rows.append(
                {
                    "id": f"check-qecirc_noisy_{path.stem}",
                    "timestamp": "2026-09-03",
                    "command": f"emlint.check({path})",
                    "environment": environment,
                    "input_hashes": {"dem": sha256(dem_bytes)},
                    "exit_code": 3,
                    "stdout_path": None,
                    "stderr_path": str(exc)[:200],
                    "duration_seconds": None,
                    "random_seed": None,
                    "complete": False,
                    "blocked": True,
                    "block_reason": "parse failure",
                }
            )
            continue

        started = time.perf_counter()
        report = emlint.check(path, context=context)
        duration = time.perf_counter() - started
        check_path = RAW / f"qecirc_noisy_{path.stem}.emlint.json"
        check_path.write_text(format_json(report) + "\n", encoding="utf-8")

        failed = [r for r in report.results if not r.passed]
        observed = sorted(r.name for r in failed)
        for r in report.results:
            status_counts[r.status] += 1
        for name in observed:
            finding_counts[name] += 1
        exit_code = 1 if report.has_errors() else 2 if report.has_warnings() else 0
        exit_counts[exit_code] += 1
        detectability = next(
            (r for r in report.results if r.name == "detectability"), None
        )
        if (
            detectability is not None
            and detectability.status == "verdict"
            and not detectability.passed
        ):
            residual_detectability_failures.append(path.name)

        corpus_rows.append(
            {
                "id": f"qecirc_noisy_{path.stem}",
                "status": "PENDING_HUMAN_REVIEW",
                "evidence_class": "REAL_CORPUS",
                "source_or_parent": {
                    "source": "QECirc noisy corpus",
                    "library": "qecirc-website",
                    "source_commit_or_archive_hash": QECIRC_COMMIT,
                    "noise": (
                        "DEPOLARIZE2(p) after each supported two-qubit gate; "
                        "DEPOLARIZE1(p) after each other gate (reset and "
                        "measurement excluded), p=0.001"
                    ),
                    "declared_context": context,
                    "role_rule": (
                        "encoding if 'encoding' in filename else "
                        "state_preparation; QECirc's library is a "
                        "state-preparation corpus, its schedule families are "
                        "measurement schedules for preparation circuits"
                    ),
                },
                "input_sha256": sha256(dem_bytes),
                "stim_version": stim.__version__,
                "emlint_version": emlint_version,
                "parameters": {"p": 0.001, "circuit_role": role},
                "artifacts": {
                    "dem": str(path.relative_to(ROOT.parent.parent)),
                    "check_json": str(check_path.relative_to(ROOT)),
                },
                "source_provenance": (
                    "qecirc noisy pass 2 (synthetic depolarizing "
                    "noise); provenance in "
                    "the qecirc campaign provenance record (internal library study)"
                ),
                "nonempty_mechanism_count": None,
                "simulation_command": None,
                "shot_budget": None,
                "seed": None,
                "observed_checks": observed,
                "exit_code": exit_code,
                "check_duration_seconds": duration,
                "block_reason": None,
            }
        )
        run_rows.append(
            {
                "id": f"check-qecirc_noisy_{path.stem}",
                "timestamp": "2026-09-03",
                "command": f"emlint.check({path}, context={context})",
                "environment": environment,
                "input_hashes": {"dem": sha256(dem_bytes)},
                "exit_code": exit_code,
                "stdout_path": str(check_path.relative_to(ROOT)),
                "stderr_path": None,
                "duration_seconds": duration,
                "random_seed": None,
                "complete": True,
                "blocked": False,
                "block_reason": None,
            }
        )

    with (ROOT / "CORPUS_MANIFEST.jsonl").open("a", encoding="utf-8") as handle:
        for row in corpus_rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    with (ROOT / "RUN_LOG.jsonl").open("a", encoding="utf-8") as handle:
        for row in run_rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    print(f"files: {len(corpus_rows) + sum(1 for r in run_rows if r['blocked'])}")
    print(f"result-status counts: {dict(status_counts)}")
    print(f"exit-code counts: {dict(exit_counts)}")
    print(f"finding counts by check: {dict(finding_counts)}")
    print(
        "VERIFICATION detectability residual error verdicts: "
        f"{len(residual_detectability_failures)}"
    )
    for name in residual_detectability_failures:
        print(f"  RESIDUAL: {name}")


if __name__ == "__main__":
    main()
