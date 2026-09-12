"""Ingest frontier (aleverrier/frontier) DEMs into the emlint corpus.

Source: https://github.com/aleverrier/frontier, pinned commit
0e91d728e07999b5d0c2e4ccfb59fb674d8039f9 (2026-07-28), Apache-2.0.

Two artifact classes are ingested:

1. **Public Gross [[144,12,12]] stim circuits** shipped in the repo under
   `grosscode/assets/gross144/stim_circuits/` (memory_X / memory_Z at several
   error rates, 12 syndrome rounds). Copied verbatim; DEM derived locally.
2. **Q102 GB [[102,22,9]] sector circuits** generated locally by the frontier
   pipeline itself (`grosscode.codes.generalized_bicycle.
   build_generalized_bicycle_circuit_text`, arXiv:2604.19481v1 Table X
   three-ring schedule, sector-only Pauli circuits).

DEMs are derived with `decompose_errors=False` following frontier's own note:
their scheduled two-qubit Pauli faults can produce large detector hyperedges,
so stim mechanisms are kept undecomposed. Each DEM is checked with emlint;
results land in `raw/dems/frontier_*_meta.json` records mirroring the QUITS
ingest pattern.

Usage: PYTHONPATH=. .venv312/bin/python run_frontier_ingest_20260901.py /tmp/frontier
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import stim

import emlint
from emlint.report import format_json

FRONTIER_ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/frontier")
OUT_DIR = Path(__file__).parent.parent / "workloads" / "dems"
CHECK_DIR = Path(__file__).parent.parent / "results" / "raw"
COMMIT = "0e91d728e07999b5d0c2e4ccfb59fb674d8039f9"
REPO_URL = "https://github.com/aleverrier/frontier"
ERROR_RATES = (0.001, 0.004)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def emit(name: str, stim_text: str, provenance: dict[str, object]) -> None:
    """Parse circuit -> derive undecomposed DEM -> run emlint -> write artifacts."""
    circuit = stim.Circuit(stim_text)
    dem = circuit.detector_error_model(decompose_errors=False)
    dem_bytes = str(dem).encode()
    dem_path = OUT_DIR / f"{name}.dem"
    dem_path.write_bytes(dem_bytes)

    started = time.perf_counter()
    report = emlint.check(str(dem_path))
    duration = time.perf_counter() - started
    check_path = CHECK_DIR / f"{name}.emlint.json"
    check_path.write_text(format_json(report) + "\n", encoding="utf-8")

    failed = [r.name for r in report.results if not r.passed]
    meta = {
        name: {
            "source": "frontier",
            "repo": REPO_URL,
            "commit": COMMIT,
            "license": "Apache-2.0",
            "generated": "2026-09-01",
            "decompose_errors": False,
            "decompose_note": (
                "Undecomposed per frontier's own pipeline note: scheduled "
                "two-qubit Pauli faults produce large detector hyperedges."
            ),
            "num_qubits": circuit.num_qubits,
            "num_detectors": dem.num_detectors,
            "num_observables": dem.num_observables,
            "nonempty_mechanism_count": sum(
                1 for i in dem.flattened() if i.type == "error"
            ),
            "circuit_sha256": sha256(stim_text.encode()),
            "dem_sha256": sha256(dem_bytes),
            "stim_version": stim.__version__,
            "emlint_version": (
                emlint.__version__ if hasattr(emlint, "__version__") else None
            ),
            "observed_checks": failed,
            "check_duration_seconds": duration,
            "exit_code": (
                1 if report.has_errors() else 2 if report.has_warnings() else 0
            ),
            "adjudication": "PENDING_HUMAN_REVIEW",
            **provenance,
        }
    }
    meta_path = OUT_DIR / "frontier_corpus_meta.json"
    existing: dict[str, object] = {}
    if meta_path.exists():
        existing = json.loads(meta_path.read_text(encoding="utf-8"))
    existing.update(meta)
    meta_path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    print(
        f"{name}: dets={dem.num_detectors} obs={dem.num_observables} exit={meta[name]['exit_code']} checks={failed}"
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(FRONTIER_ROOT))

    # --- Class 1: public Gross [[144,12,12]] circuits shipped in the repo ---
    asset_dir = FRONTIER_ROOT / "grosscode" / "assets" / "gross144" / "stim_circuits"
    for sector in ("X", "Z"):
        for rate in ERROR_RATES:
            matches = sorted(asset_dir.glob(f"*memory_{sector}*error_rate={rate:}*"))
            if not matches:
                print(f"SKIP gross {sector} @{rate}: no asset")
                continue
            name = f"frontier_gross144_{sector.lower()}_p{rate}"
            emit(
                name,
                matches[0].read_text(encoding="utf-8"),
                {
                    "artifact_class": "repo-shipped public stim circuit",
                    "upstream_circuit": matches[0].name,
                    "circuit_description": (
                        "Gross [[144,12,12]] bivariate-bicycle memory, "
                        f"sector {sector}, 12 syndrome rounds, circuit-level noise"
                    ),
                },
            )

    # --- Class 2: Q102 GB circuits generated by the frontier pipeline ---
    from grosscode.codes.generalized_bicycle import (
        build_generalized_bicycle_circuit_text,
    )

    for sector in ("X", "Z"):
        text = build_generalized_bicycle_circuit_text(
            backend="q102_gb_102_22_9", sector=sector, error_rate=0.001
        )
        emit(
            f"frontier_q102_{sector.lower()}_p0.001",
            text,
            {
                "artifact_class": "generated locally by frontier pipeline",
                "circuit_description": (
                    "Q102 GB [[102,22,9]] generalized-bicycle memory, sector "
                    f"{sector}, arXiv:2604.19481v1 Table X three-ring schedule, "
                    "sector-only Pauli circuit (complementary sector and "
                    "loss/leakage not modelled)"
                ),
            },
        )


if __name__ == "__main__":
    main()
