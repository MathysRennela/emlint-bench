"""Extended Stim built-in corpus sweep (campaign_20260901_sweep).

Two-axis sweep that broadens the pinned campaign_20260819 corpus:

- Structure axis: 6 generator families x distances 2..7 x rounds
  {1, 2, d-1, d, 3d} at fixed after_clifford_depolarization=0.001.
- Noise axis: 3 representative generators x each noise knob
  {after_clifford_depolarization, after_reset_flip_probability,
  before_measure_flip_probability, before_round_data_depolarization}
  x strengths {0, 1e-4, 1e-3, 1e-2, 0.1, 0.5}, plus one combined config.

Writes SWEEP_MANIFEST.jsonl (fresh file). The pinned campaign_20260819
manifests are left untouched. Empty DEMs (p=0) are labelled
STRUCTURAL_ONLY per the validation-strategy eligibility corridor and are
not simulated (pymatching cannot load an empty DEM). Color-code d>=5
DEMs are generated with decompose_errors=False because stim cannot
decompose their three-symptom errors; the flag is recorded per entry.

Usage: PYTHONPATH=. .venv312/bin/python run_sweep_20260901.py
"""

from __future__ import annotations

import importlib.metadata
import json
import platform
import time
from pathlib import Path
from typing import Any

import pymatching
import stim

from run_smoke import (
    CIRCUIT_DIR,
    DEM_DIR,
    RAW,
    ROOT,
    SEED,
    SHOTS,
    result_names,
    run_check,
    sha256,
    simulate,
)

CAMPAIGN = "campaign_20260901_sweep"
MANIFEST = ROOT / "SWEEP_MANIFEST.jsonl"

STRENGTHS = (0.0, 1e-4, 1e-3, 1e-2, 0.1, 0.5)
NOISE_KNOBS = (
    "after_clifford_depolarization",
    "after_reset_flip_probability",
    "before_measure_flip_probability",
    "before_round_data_depolarization",
)

# (family, generator, distances, decompose_ok_for_all_distances)
STRUCTURE_GENERATORS = [
    ("repetition", "repetition_code:memory", range(2, 8), True),
    ("rotated_surface_z", "surface_code:rotated_memory_z", range(2, 8), True),
    ("rotated_surface_x", "surface_code:rotated_memory_x", range(2, 8), True),
    ("unrotated_surface_z", "surface_code:unrotated_memory_z", range(2, 8), True),
    ("unrotated_surface_x", "surface_code:unrotated_memory_x", range(2, 8), True),
    ("color", "color_code:memory_xyz", (3, 5, 7), False),
]

# (family, generator, distance) representatives for the noise axis
NOISE_REPRESENTATIVES = [
    ("repetition", "repetition_code:memory", 3),
    ("rotated_surface_z", "surface_code:rotated_memory_z", 3),
    ("color", "color_code:memory_xyz", 3),
]


def rounds_for(distance: int) -> list[int]:
    values = {1, 2, distance - 1, distance, 3 * distance}
    return sorted(v for v in values if v >= 1)


def build_id(family: str, distance: int, rounds: int, noise_key: str) -> str:
    noise_tag = noise_key.replace("_", "") or "baseline"
    return f"{CAMPAIGN}_{family}_d{distance}_r{rounds}_{noise_tag}"


def error_mechanism_count(dem: stim.DetectorErrorModel) -> int:
    """Count error instructions only; dem.flattened() also yields detector
    and shift_detectors instructions, which are not mechanisms."""
    return sum(
        1
        for instr in dem.flattened()
        if isinstance(instr, stim.DemInstruction) and instr.type == "error"
    )


def ingest(
    corpus_id: str,
    generator: str,
    parameters: dict[str, Any],
    decompose: bool,
    stim_version: str,
    emlint_version: str,
    environment_note: str,
    rows: list[dict[str, object]],
) -> None:
    """Generate, check, and (when non-empty) simulate one sweep entry."""
    try:
        circuit = stim.Circuit.generated(generator, **parameters)
        dem = circuit.detector_error_model(decompose_errors=decompose)
    except Exception as exc:  # noqa: BLE001 - blocked entries are recorded, not raised
        rows.append(
            {
                "id": corpus_id,
                "status": "BLOCKED",
                "block_reason": f"stim generation/DEM failed: {exc}",
                "evidence_class": "REAL_CORPUS",
                "source_or_parent": {
                    "source": "Stim built-in generator",
                    "generator": generator,
                },
                "parameters": parameters,
            }
        )
        return

    circuit_bytes = str(circuit).encode()
    dem_bytes = str(dem).encode()
    circuit_path = CIRCUIT_DIR / f"{corpus_id}.stim"
    dem_path = DEM_DIR / f"{corpus_id}.dem"
    circuit_path.write_bytes(circuit_bytes)
    dem_path.write_bytes(dem_bytes)

    report, duration, check_output = run_check(
        str(dem_path), f"{corpus_id}.emlint.json"
    )

    mechanism_count = error_mechanism_count(dem)
    empty = mechanism_count == 0
    simulation_json = None
    simulation_duration = None
    if not empty:
        started = time.perf_counter()
        simulation = simulate(circuit, dem)
        simulation_duration = time.perf_counter() - started
        simulation_path = RAW / f"{corpus_id}.simulation.json"
        simulation_path.write_text(
            json.dumps(simulation, indent=2) + "\n", encoding="utf-8"
        )
        simulation_json = str(simulation_path.relative_to(ROOT))

    rows.append(
        {
            "id": corpus_id,
            "status": "PENDING_HUMAN_REVIEW",
            "block_reason": None,
            "evidence_class": "STRUCTURAL_ONLY" if empty else "REAL_CORPUS",
            "source_or_parent": {
                "source": "Stim built-in generator",
                "generator": generator,
                "stim_source_url": "https://github.com/quantumlib/Stim",
                "source_commit_or_archive_hash": None,
            },
            "input_sha256": sha256(dem_bytes),
            "stim_version": stim_version,
            "emlint_version": emlint_version,
            "parameters": {**parameters, "decompose_errors": decompose},
            "artifacts": {
                "circuit": str(circuit_path.relative_to(ROOT)),
                "dem": str(dem_path.relative_to(ROOT)),
                "check_json": check_output,
                "simulation_json": simulation_json,
            },
            "source_provenance": environment_note,
            "nonempty_mechanism_count": mechanism_count,
            "num_detectors": dem.num_detectors,
            "num_observables": dem.num_observables,
            "simulation_command": (
                None
                if empty
                else f"PYTHONPATH=. .venv312/bin/python campaigns/run_sweep_20260901.py --id {corpus_id} --shots {SHOTS} --seed {SEED}"
            ),
            "shot_budget": None if empty else SHOTS,
            "seed": None if empty else SEED,
            "observed_checks": result_names(report),
            "check_duration_seconds": duration,
            "simulation_duration_seconds": simulation_duration,
        }
    )


def main() -> None:
    stim_version = stim.__version__
    emlint_version = importlib.metadata.version("emlint")
    environment_note = (
        "Stim package and generator parameters are pinned; known-good status "
        "requires human review and citable p_L evidence."
    )
    rows: list[dict[str, object]] = []

    # --- Structure axis ---
    for family, generator, distances, decompose_ok in STRUCTURE_GENERATORS:
        for distance in distances:
            for rounds in rounds_for(distance):
                corpus_id = build_id(family, distance, rounds, "")
                parameters = {
                    "distance": distance,
                    "rounds": rounds,
                    "after_clifford_depolarization": 0.001,
                }
                ingest(
                    corpus_id,
                    generator,
                    parameters,
                    decompose_ok,
                    stim_version,
                    emlint_version,
                    environment_note,
                    rows,
                )

    # --- Noise axis ---
    for family, generator, distance in NOISE_REPRESENTATIVES:
        decompose = family != "color" or distance == 3
        for knob in NOISE_KNOBS:
            for strength in STRENGTHS:
                corpus_id = build_id(family, distance, distance, f"{knob}{strength}")
                parameters = {"distance": distance, "rounds": distance, knob: strength}
                ingest(
                    corpus_id,
                    generator,
                    parameters,
                    decompose,
                    stim_version,
                    emlint_version,
                    environment_note,
                    rows,
                )
        combined = {knob: 1e-3 for knob in NOISE_KNOBS}
        corpus_id = build_id(family, distance, distance, "combined1e-3")
        ingest(
            corpus_id,
            generator,
            {"distance": distance, "rounds": distance, **combined},
            decompose,
            stim_version,
            emlint_version,
            environment_note,
            rows,
        )

    with MANIFEST.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    blocked = sum(1 for row in rows if row["status"] == "BLOCKED")
    structural = sum(1 for row in rows if row["evidence_class"] == "STRUCTURAL_ONLY")
    detected = sum(1 for row in rows if row.get("observed_checks"))
    print(
        json.dumps(
            {
                "campaign": CAMPAIGN,
                "entries": len(rows),
                "blocked": blocked,
                "structural_only": structural,
                "with_check_findings": detected,
                "stim": stim_version,
                "emlint": emlint_version,
                "platform": platform.platform(),
                "pymatching": pymatching.__version__,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
