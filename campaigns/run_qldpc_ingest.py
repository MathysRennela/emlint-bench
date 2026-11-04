"""Ingest the qldpc-challenge corpus (.dem + .stim) into emlint-bench.

Source: https://github.com/unitaryfoundation/qldpc-challenge, commit pinned at
ingest time (see PROVENANCE below). Each code directory ships a memory
experiment for two bases (memory_x, memory_z): a Stim circuit and the DEM
derived from it (stim's detector_error_model). Both artifacts are copied
verbatim; the DEM is then checked with emlint and the result recorded.

This is a *real-corpus* ingest (no synthesis). The DEMs are the ones the
challenge uses for its refutation gate, so they are treated as known-good
input for the gate-ready false-positive audit; adjudication happens in
emlint-dev's FINDINGS_LEDGER, not here.

Usage:
    PYTHONPATH=. /home/mathys/github/emlint-dev/.venv/bin/python campaigns/run_qldpc_ingest.py
    PYTHONPATH=. /home/mathys/github/emlint-dev/.venv/bin/python campaigns/run_qldpc_ingest.py --limit 50
    PYTHONPATH=. ... campaigns/run_qldpc_ingest.py --skip-emlint   # copy only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

import stim

import emlint
from emlint.report import format_json

SOURCE_ROOT = Path("/home/mathys/github/qldpc-challenge")
BENCH_ROOT = Path(__file__).resolve().parent.parent
OUT_DEMS = BENCH_ROOT / "workloads" / "dems"
OUT_CIRCUITS = BENCH_ROOT / "workloads" / "circuits"
CHECK_DIR = BENCH_ROOT / "results" / "raw"
META_PATH = OUT_DEMS / "qldpc_corpus_meta.json"
MANIFEST_PATH = BENCH_ROOT / "manifests" / "QLDPC_MANIFEST.jsonl"

COMMIT = "8b289cb8ecf4dbb9f837836f6e219f3a0b553973"
REPO_URL = "https://github.com/unitaryfoundation/qldpc-challenge"
LICENSE = "Apache-2.0"
GENERATED = "2026-11-04"
PROVENANCE = (
    "qldpc-challenge verified code submission: memory experiment circuit "
    "(stim) and its detector_error_model, used by the challenge's refutation "
    "gate. Copied verbatim; no regeneration."
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def emlint_version() -> str:
    try:
        from importlib.metadata import version as _v

        return _v("emlint")
    except Exception:
        return "unknown"


def load_meta() -> dict:
    if META_PATH.is_file():
        try:
            return json.loads(META_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_meta(meta: dict) -> None:
    META_PATH.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


def load_manifest_ids() -> set[str]:
    ids: set[str] = set()
    if MANIFEST_PATH.is_file():
        for line in MANIFEST_PATH.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                ids.add(json.loads(line)["id"])
            except Exception:
                pass
    return ids


def append_manifest(entry: dict) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def discover() -> list[tuple[str, str, Path, Path]]:
    """Return list of (code_dir, basis, dem_src, stim_src)."""
    out = []
    for dem_src in sorted((SOURCE_ROOT / "circuits").glob("*/memory_*.dem")):
        code_dir = dem_src.parent.name
        basis = dem_src.stem  # memory_x / memory_z
        stim_src = dem_src.with_suffix(".stim")
        out.append((code_dir, basis, dem_src, stim_src))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="process only first N DEMs")
    parser.add_argument("--skip-emlint", action="store_true", help="copy artifacts only")
    parser.add_argument("--source", type=Path, default=SOURCE_ROOT)
    args = parser.parse_args()

    source_root = args.source
    # rebuild discover with source_root
    items = []
    for dem_src in sorted((source_root / "circuits").glob("*/memory_*.dem")):
        code_dir = dem_src.parent.name
        basis = dem_src.stem
        stim_src = dem_src.with_suffix(".stim")
        items.append((code_dir, basis, dem_src, stim_src))
    if args.limit is not None:
        items = items[: args.limit]

    OUT_DEMS.mkdir(parents=True, exist_ok=True)
    OUT_CIRCUITS.mkdir(parents=True, exist_ok=True)
    CHECK_DIR.mkdir(parents=True, exist_ok=True)

    meta = load_meta()
    manifest_ids = load_manifest_ids()

    ev = emlint_version()
    stim_ver = stim.__version__
    t0 = time.monotonic()
    n_done = 0
    n_skipped = 0

    for idx, (code_dir, basis, dem_src, stim_src) in enumerate(items, 1):
        ident = f"qldpc_{code_dir}_{basis}"
        dem_dest = OUT_DEMS / f"{ident}.dem"
        stim_dest = OUT_CIRCUITS / f"{ident}.stim"
        check_path = CHECK_DIR / f"{ident}.emlint.json"

        # copy artifacts (idempotent)
        if not dem_dest.is_file():
            shutil.copy2(dem_src, dem_dest)
        if stim_src.is_file() and not stim_dest.is_file():
            shutil.copy2(stim_src, stim_dest)

        dem_bytes = dem_dest.read_bytes()
        dem_sha = sha256_bytes(dem_bytes)
        stim_sha = sha256_file(stim_dest) if stim_dest.is_file() else None

        # run emlint if needed
        if (not args.skip_emlint) and not check_path.is_file():
            started = time.perf_counter()
            report = emlint.check(str(dem_dest))
            duration = time.perf_counter() - started
            check_path.write_text(format_json(report) + "\n", encoding="utf-8")
            failed = [r.name for r in report.results if not r.passed]
            exit_code = 1 if report.has_errors() else (2 if report.has_warnings() else 0)
            num_det = report.num_detectors
            num_obs = report.num_observables
            num_mech = report.num_error_mechanisms
            observed = failed
            check_duration = duration
        elif check_path.is_file():
            # load from existing check json for meta
            try:
                cj = json.loads(check_path.read_text(encoding="utf-8"))
                failed = [r["name"] for r in cj.get("results", []) if not r.get("passed", True)]
                exit_code = 1 if cj.get("has_errors") else (2 if cj.get("has_warnings") else 0)
                num_det = cj.get("num_detectors")
                num_obs = cj.get("num_observables")
                num_mech = cj.get("num_error_mechanisms")
                observed = failed
                check_duration = cj.get("check_duration_seconds")
            except Exception:
                observed = []
                exit_code = None
                num_det = num_obs = num_mech = None
                check_duration = None
        else:
            observed = []
            exit_code = None
            num_det = num_obs = num_mech = None
            check_duration = None

        meta[ident] = {
            "source": "qldpc-challenge",
            "repo": REPO_URL,
            "commit": COMMIT,
            "license": LICENSE,
            "generated": GENERATED,
            "code_dir": code_dir,
            "basis": basis,
            "circuit_description": (
                f"qLDPC code {code_dir} memory experiment ({basis}), "
                f"verified submission from qldpc-challenge"
            ),
            "known_correct": True,
            "expected_result": "pending_adjudication",
            "adjudication": None,
            "bug_class_exercised": None,
            "num_detectors": num_det,
            "num_observables": num_obs,
            "nonempty_mechanism_count": num_mech,
            "dem_sha256": dem_sha,
            "stim_sha256": stim_sha,
            "stim_version": stim_ver,
            "emlint_version": ev,
            "observed_checks": observed,
            "check_duration_seconds": check_duration,
            "exit_code": exit_code,
            "artifact_paths": {
                "dem": f"workloads/dems/{ident}.dem",
                "stim": f"workloads/circuits/{ident}.stim",
                "check_json": f"results/raw/{ident}.emlint.json",
            },
            "provenance": PROVENANCE,
        }

        # manifest entry (idempotent)
        if ident not in manifest_ids:
            entry = {
                "id": ident,
                "file": f"workloads/dems/{ident}.dem",
                "circuit_file": f"workloads/circuits/{ident}.stim",
                "dem_sha256": dem_sha,
                "stim_sha256": stim_sha,
                "source": "qldpc-challenge",
                "repo": REPO_URL,
                "commit": COMMIT,
                "license": LICENSE,
                "generated": GENERATED,
                "code_dir": code_dir,
                "basis": basis,
                "known_correct": True,
                "expected_result": "pending_adjudication",
                "adjudication": None,
                "environment": {
                    "emlint": ev,
                    "stim": stim_ver,
                    "python": sys.version.split()[0],
                },
            }
            append_manifest(entry)
            manifest_ids.add(ident)

        save_meta(meta)
        n_done += 1
        print(
            f"{idx:4d}/{len(items)} {ident}: dets={num_det} obs={num_obs} "
            f"mech={num_mech} exit={exit_code} checks={observed}",
            flush=True,
        )

    elapsed = time.monotonic() - t0
    print(f"\nDONE: processed {n_done} DEMs in {elapsed:.1f}s")
    print(f"meta: {META_PATH}")
    print(f"manifest: {MANIFEST_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
