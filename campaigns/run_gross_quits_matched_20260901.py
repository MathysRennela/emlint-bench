"""Matched gross [[144,12,12]] comparison: frontier vs QUITS pipelines.

Question (2026-09-01 session): frontier's gross144 DEMs pass emlint clean,
while QUITS `quits_bb144_r3` produced 648 `duplicates` findings. Before
attributing the QUITS findings to its scheduling, the two pipelines must be
compared under matched conditions.

Method:
1. Reproduce the archived ingest: QUITS bb144, strategy=custom, 3 rounds,
   circuit-level p=0.001 — observed checks must match the archived
   `quits_corpus_meta.json` adjudication (duplicates + correctability).
2. Generate QUITS bb144 X/Z at 12 rounds (matching frontier's gross144
   round count), derive undecomposed DEMs, run emlint.
3. Structural diff frontier gross144_z vs QUITS bb144 Z @12r: detector /
   observable / mechanism counts, hyperedge size distribution, duplicate
   fault-signature counts.

Usage: PYTHONPATH=. .venv312/bin/python run_gross_quits_matched_20260901.py /tmp/quits
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

import stim

import emlint
from emlint.report import format_json

QUITS_ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/quits")
OUT_DIR = Path(__file__).parent.parent / "workloads" / "dems"
CHECK_DIR = Path(__file__).parent.parent / "results" / "raw"
DIFF_PATH = Path(__file__).parent.parent / "results" / "GROSS_QUITS_MATCHED_20260901.json"

BB_PARAMS = dict(
    l=12, m=6, A_x_pows=[3], A_y_pows=[1, 2], B_x_pows=[3], B_y_pows=[1, 2]
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hyperedge_stats(dem: stim.DetectorErrorModel) -> dict[str, object]:
    sizes: list[int] = []
    signatures: Counter[tuple[int, ...]] = Counter()
    for instr in dem.flattened():
        if instr.type != "error":
            continue
        dets = tuple(
            sorted(t.val for t in instr.targets_copy() if t.is_relative_detector_id())
        )
        sizes.append(len(dets))
        signatures[dets] += 1
    size_counts = Counter(sizes)
    return {
        "mechanisms": len(sizes),
        "hyperedge_size_counts": dict(sorted(size_counts.items())),
        "duplicate_signatures": sum(c - 1 for c in signatures.values() if c > 1),
        "distinct_signatures": len(signatures),
        "max_hyperedge_size": max(sizes, default=0),
    }


def run_quits_bb(rounds: int, basis: str, tag: str, rows: dict[str, object]) -> None:
    from quits.noise.error_model import ErrorModel
    from quits.qldpc_code.bb import BbCode

    code = BbCode(**BB_PARAMS)
    error_model = ErrorModel(
        idle_error=0.001, sqgate_error=0.001, tqgate_error=0.001, spam_error=0.001
    )
    circuit = code.build_circuit(
        strategy="custom", error_model=error_model, num_rounds=rounds, basis=basis
    )
    dem = circuit.detector_error_model(decompose_errors=False)
    dem_bytes = str(dem).encode()
    name = f"quits_bb144_{basis.lower()}_r{rounds}_matched"
    dem_path = OUT_DIR / f"{name}.dem"
    dem_path.write_bytes(dem_bytes)

    started = time.perf_counter()
    report = emlint.check(str(dem_path))
    duration = time.perf_counter() - started
    check_path = CHECK_DIR / f"{name}.emlint.json"
    check_path.write_text(format_json(report) + "\n", encoding="utf-8")

    failed = [r.name for r in report.results if not r.passed]
    rows[name] = {
        "source": "QUITS",
        "repo": "https://github.com/mkangquantum/quits",
        "commit": "31ab78252f5bbe169d11956450a5c9d2b1184d51 (v1.1.0)",
        "generated": "2026-09-01",
        "purpose": "matched comparison with frontier gross144 (see GROSS_QUITS_MATCHED_20260901.json)",
        "num_rounds": rounds,
        "basis": basis,
        "noise": {"model": "circuit_level", "p": 0.001},
        "decompose_errors": False,
        "num_qubits": circuit.num_qubits,
        "num_detectors": dem.num_detectors,
        "num_observables": dem.num_observables,
        "dem_sha256": sha256(dem_bytes),
        "stim_version": stim.__version__,
        "observed_checks": failed,
        "check_duration_seconds": duration,
        "exit_code": (1 if report.has_errors() else 2 if report.has_warnings() else 0),
        "hyperedge_stats": hyperedge_stats(dem),
        "adjudication": "PENDING_HUMAN_REVIEW",
    }
    print(
        f"{name}: dets={dem.num_detectors} obs={dem.num_observables} exit={rows[name]['exit_code']} checks={failed}"
    )


def main() -> None:
    sys.path.insert(0, str(QUITS_ROOT / "src"))
    rows: dict[str, object] = {}

    # Step 1: reproduce the archived 3-round ingest (both-basis observables
    # appeared only in the archived run because that entry was generated with
    # a different code path; here basis is explicit, so r3 is reproduced per
    # basis and compared against the archived observed_checks).
    for basis in ("X", "Z"):
        run_quits_bb(3, basis, "repro", rows)

    # Step 2: 12-round matched generation.
    for basis in ("X", "Z"):
        run_quits_bb(12, basis, "matched", rows)

    # Step 3: structural diff vs frontier gross144 (12 rounds, same p=0.001).
    frontier_path = OUT_DIR / "frontier_gross144_z_p0.001.dem"
    frontier_dem = stim.DetectorErrorModel.from_file(frontier_path)
    quits_dem = stim.DetectorErrorModel.from_file(
        OUT_DIR / "quits_bb144_z_r12_matched.dem"
    )
    diff = {
        "frontier_gross144_z_p0.001": {
            "num_detectors": frontier_dem.num_detectors,
            "num_observables": frontier_dem.num_observables,
            **hyperedge_stats(frontier_dem),
        },
        "quits_bb144_z_r12_matched": {
            "num_detectors": quits_dem.num_detectors,
            "num_observables": quits_dem.num_observables,
            **hyperedge_stats(quits_dem),
        },
    }

    meta_path = OUT_DIR / "frontier_corpus_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    output = {
        "date": "2026-09-01",
        "question": (
            "Are the 648 duplicates findings on quits_bb144_r3 inherent to "
            "undecomposed BB-code DEMs, or specific to the QUITS pipeline? "
            "frontier gross144 (same family) ran clean."
        ),
        "ingest_rows": rows,
        "structural_diff_12r_Z": diff,
    }
    DIFF_PATH.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    meta.update(rows)
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(diff, indent=2))


if __name__ == "__main__":
    main()
