"""Run the pinned, offline circuit-check false-positive audit for issue 146.

This is an on-demand corpus campaign, not a default-CI test. It checks source
hashes before parsing and records skipped/inconclusive results separately from
passing verdicts.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable, Protocol

import stim

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "manifests" / "circuit_check_audit_issue146.jsonl"
DEFAULT_OUTPUT = ROOT / "results" / "raw" / "circuit_check_audit_issue146.json"


class StimSource(Protocol):
    def __call__(self, row: dict[str, Any]) -> tuple[str, dict[str, Any]]: ...


def _generated(row: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    source = row.get("source", {})
    parameters = row["parameters"]
    circuit = stim.Circuit.generated(row["task"], **parameters)
    text = str(circuit)
    return text, {
        "source": source,
        "task": row["task"],
        "parameters": parameters,
    }


def _fixture_bytes(row: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    path = (ROOT / row["path"]).resolve()
    if ROOT not in path.parents:
        raise ValueError(f"{row['id']}: fixture path escapes benchmark root")
    compressed = path.read_bytes()
    compressed_sha = hashlib.sha256(compressed).hexdigest()
    expected_compressed_sha = row.get("compressed_sha256")
    if expected_compressed_sha and compressed_sha != expected_compressed_sha:
        raise ValueError(f"{row['id']}: compressed hash mismatch: {compressed_sha}")
    raw = (
        gzip.decompress(compressed)
        if row["input_kind"] == "stim_gzip_fixture"
        else compressed
    )
    sha = hashlib.sha256(raw).hexdigest()
    if sha != row["sha256"]:
        raise ValueError(f"{row['id']}: fixture hash mismatch: {sha}")
    return raw, {
        "path": str(path.relative_to(ROOT)),
        "compressed_sha256": compressed_sha if compressed_sha != sha else None,
        "sha256": sha,
        "source": row.get("source", {}),
    }


def _plain_fixture(row: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    raw, metadata = _fixture_bytes(row)
    return raw.decode("utf-8"), metadata


def _gzip_fixture(row: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    raw, metadata = _fixture_bytes(row)
    return raw.decode("utf-8"), metadata


SOURCE_ADAPTERS: dict[str, StimSource] = {
    "stim_generated": _generated,
    "stim_fixture": _plain_fixture,
    "stim_gzip_fixture": _gzip_fixture,
}


def _read_manifest(path: Path) -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("manifest contains duplicate case IDs")
    for row in rows:
        if row.get("expected_clean") is not True:
            raise ValueError(f"{row['id']}: this audit accepts clean inputs only")
        if row.get("input_kind") not in SOURCE_ADAPTERS:
            raise ValueError(
                f"{row['id']}: unknown input kind {row.get('input_kind')!r}"
            )
    return rows


def _check_result(
    result: Any, elapsed_s: float, not_exercised_reason: str | None = None
) -> dict[str, Any]:
    status = result.status
    passed = result.passed
    if status == "verdict" and not passed:
        disposition = "potential_false_positive"
    elif not_exercised_reason is not None:
        disposition = "not_exercised"
    elif status == "verdict":
        disposition = "pass"
    else:
        disposition = "not_exercised"
    return {
        "name": result.name,
        "passed": passed,
        "status": status,
        "severity": result.severity,
        "disposition": disposition,
        "not_exercised_reason": not_exercised_reason,
        "message": result.message,
        "counter_example": result.counter_example,
        "counter_example_data": result.counter_example_data,
        "hint": result.hint,
        "elapsed_seconds": elapsed_s,
    }


def _run_case(row: dict[str, Any], checks: dict[str, Callable]) -> dict[str, Any]:
    source = row.get("source", {})
    expected_version = row.get("stim_version", source.get("stim_version"))
    if expected_version is not None and expected_version != stim.__version__:
        raise ValueError(
            f"{row['id']}: requires stim {expected_version}, "
            f"running {stim.__version__}"
        )
    text, source_metadata = SOURCE_ADAPTERS[row["input_kind"]](row)
    circuit = stim.Circuit(text)
    expected_not_exercised = row.get("not_exercised_checks", {})
    results: dict[str, Any] = {}
    for registered_name, check in checks.items():
        started = time.perf_counter()
        try:
            result = check(circuit)
        except Exception as ex:  # record failures without hiding other checks
            results[registered_name] = {
                "name": registered_name,
                "status": "exception",
                "disposition": "exception",
                "error": f"{type(ex).__name__}: {ex}",
                "elapsed_seconds": time.perf_counter() - started,
            }
            continue
        results[registered_name] = _check_result(
            result,
            time.perf_counter() - started,
            expected_not_exercised.get(registered_name),
        )

    return {
        "id": row["id"],
        "family": row["family"],
        "input_kind": row["input_kind"],
        "source_metadata": source_metadata,
        "input_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "num_qubits": circuit.num_qubits,
        "num_measurements": circuit.num_measurements,
        "num_detectors": circuit.num_detectors,
        "num_observables": circuit.num_observables,
        "checks": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emlint-source", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    emlint_source = args.emlint_source.resolve()
    if not emlint_source.is_dir():
        parser.error(f"not an emlint source directory: {emlint_source}")
    sys.path.insert(0, str(emlint_source))
    import emlint
    from emlint.circuits import EXPERIMENTAL_CIRCUIT_CHECKS

    rows = _read_manifest(args.manifest.resolve())
    started = time.perf_counter()
    cases = [_run_case(row, EXPERIMENTAL_CIRCUIT_CHECKS) for row in rows]
    elapsed = time.perf_counter() - started
    potential_false_positives = [
        f"{case['id']}:{name}"
        for case in cases
        for name, result in case["checks"].items()
        if result["disposition"] == "potential_false_positive"
    ]
    exceptions = [
        f"{case['id']}:{name}"
        for case in cases
        for name, result in case["checks"].items()
        if result["disposition"] == "exception"
    ]
    not_exercised = [
        f"{case['id']}:{name}={result['status']} "
        f"({result.get('not_exercised_reason') or result['message']})"
        for case in cases
        for name, result in case["checks"].items()
        if result["disposition"] == "not_exercised"
    ]
    report = {
        "campaign": "issue146-circuit-check-false-positive-audit",
        "emlint_source": str(
            Path(emlint.__file__).resolve().relative_to(emlint_source)
        ),
        "emlint_version": getattr(emlint, "__version__", None),
        "stim_version": stim.__version__,
        "manifest": str(args.manifest.resolve().relative_to(ROOT)),
        "case_count": len(cases),
        "registered_check_names": list(EXPERIMENTAL_CIRCUIT_CHECKS),
        "potential_false_positives": potential_false_positives,
        "exceptions": exceptions,
        "not_exercised": not_exercised,
        "elapsed_seconds": elapsed,
        "cases": cases,
        "interpretation": (
            "A skipped or inconclusive result is not counted as a pass or a "
            "false positive; it is recorded as not exercised. Potential false "
            "positives require human adjudication."
        ),
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8"
    )
    print(
        f"cases={len(cases)} checks={len(EXPERIMENTAL_CIRCUIT_CHECKS)} "
        f"potential_false_positives={len(potential_false_positives)} "
        f"exceptions={len(exceptions)} not_exercised={len(not_exercised)} "
        f"elapsed_s={elapsed:.3f} output={output}"
    )
    return 1 if potential_false_positives or exceptions else 0


if __name__ == "__main__":
    raise SystemExit(main())
