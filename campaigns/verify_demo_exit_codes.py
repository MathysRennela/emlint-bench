"""Verify emlint CLI exit codes (0/1/2) across the demo corpus.

Sprint task (Day 5): verify exit codes 0/1/2 across the demo corpus. Runs the
installed `emlint` CLI on every artifact recorded in
manifests/demo_manifest.jsonl and checks:

- the exit code matches the build-time verified exit code,
- the exit code is one of 0/1/2 (never 3: every demo artifact must be
  lintable by construction),
- baseline artifacts exit 0 or 2 (warnings allowed), mutants exit 1 or 2.

Results are recorded under results/raw/ (dated). This script never
adjudicates findings; it only verifies the exit-code contract.

Run (repo root, emlint installed):
    python campaigns/verify_demo_exit_codes.py
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "manifests" / "demo_manifest.jsonl"
RESULTS = ROOT / "results" / "raw"


def main() -> int:
    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    # Locate the emlint package from this interpreter and invoke the CLI via
    # `python -c` with the package root on PYTHONPATH. The console script is
    # not used directly because editable/cwd installs do not put the package
    # on sys.path for entry-point scripts.
    spec = importlib.util.find_spec("emlint")
    if spec is None or spec.origin is None:
        print("FATAL: emlint not importable (pip install emlint)")
        return 3
    pkg_root = str(Path(spec.origin).resolve().parent.parent)
    cli_code = (
        "import sys; sys.argv = ['emlint'] + sys.argv[1:]; "
        "from emlint.cli import main; main()"
    )
    env = {**os.environ, "PYTHONPATH": pkg_root}

    rows = [
        json.loads(line)
        for line in MANIFEST.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    artifacts = [r for r in rows if r.get("artifact_kind") in ("baseline", "baseline_pinned", "mutant")]

    records: list[dict[str, object]] = []
    failures: list[str] = []
    for row in artifacts:
        path = ROOT / str(row["file"])
        if not path.is_file():
            failures.append(f"{row['file']}: artifact missing")
            continue
        proc = subprocess.run(
            [sys.executable, "-c", cli_code, "check", str(path)],
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )
        code = proc.returncode
        expected = row.get("verified_exit_code")
        ok_contract = code in (0, 1, 2)
        ok_match = expected is None or code == expected
        record = {
            "file": row["file"],
            "kind": row["artifact_kind"],
            "exit_code": code,
            "expected_exit_code": expected,
            "matches_build_time": code == expected,
            "stderr_tail": proc.stderr.strip().splitlines()[-1:] if proc.stderr else [],
        }
        records.append(record)
        if code == 3:
            failures.append(f"{row['file']}: exit 3 (unlintable) — demo corpus must be lintable")
        elif not ok_contract:
            failures.append(f"{row['file']}: exit {code} outside the 0/1/2 contract")
        elif expected is not None and code != expected:
            failures.append(
                f"{row['file']}: CLI exit {code} != build-time verified exit {expected}"
            )

    summary = {
        "date": date,
        "emlint_version": importlib.metadata.version("emlint"),
        "platform": platform.platform(),
        "emlint_package_root": pkg_root,
        "artifacts_checked": len(records),
        "exit_code_histogram": {
            str(c): sum(1 for r in records if r["exit_code"] == c) for c in (0, 1, 2, 3)
        },
        "failures": failures,
        "records": records,
    }
    out = RESULTS / f"demo_exitcodes_{date}.json"
    RESULTS.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "artifacts_checked": len(records),
                "exit_code_histogram": summary["exit_code_histogram"],
                "failures": len(failures),
                "results_file": str(out),
            }
        )
    )
    for failure in failures:
        print(f"  FAIL {failure}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())