from __future__ import annotations

import importlib.metadata
import json
import platform
import re
import time
from pathlib import Path

import pymatching
import stim

from run_smoke import (
    RAW,
    CIRCUIT_DIR,
    DEM_DIR,
    ROOT,
    SEED,
    SHOTS,
    result_names,
    run_check,
    sha256,
    simulate,
    write_jsonl,
)

CAMPAIGN = "campaign_20260819"


def main() -> None:
    stim_version = stim.__version__
    emlint_version = importlib.metadata.version("emlint")
    environment = {
        "python": platform.python_version(),
        "stim": stim_version,
        "emlint": emlint_version,
        "pymatching": pymatching.__version__,
        "platform": platform.platform(),
        "repository_revision": "86e4e492ab144d37de9421f47bce72980c9cdbee",
        "working_tree_dirty": True,
    }
    generators = [
        ("repetition", "repetition_code:memory"),
        ("rotated_surface", "surface_code:rotated_memory_z"),
        ("unrotated_surface", "surface_code:unrotated_memory_z"),
    ]
    corpus_rows: list[dict[str, object]] = []
    mutation_rows: list[dict[str, object]] = []
    run_rows: list[dict[str, object]] = []
    mutation_kinds = [
        ("zero_probability", "Deterministic catch — error", "error(0) D0"),
        ("logical_without_syndrome", "Deterministic catch — error", "error(0.1) L0"),
        ("high_probability", "Deterministic catch — warning", "error(0.75) D0"),
        ("duplicate_fault", "Context-dependent — warning", "duplicate"),
        ("dead_detector", "Deterministic catch — warning", "dead"),
        ("coordinate_change", "Cosmetic-only today", "coordinate"),
    ]

    for family, generator in generators:
        for distance in range(3, 8):
            for rounds in (3, 4):
                corpus_id = f"{CAMPAIGN}_{family}_d{distance}_r{rounds}"
                parameters = {
                    "distance": distance,
                    "rounds": rounds,
                    "after_clifford_depolarization": 0.001,
                }
                circuit = stim.Circuit.generated(generator, **parameters)
                dem = circuit.detector_error_model(decompose_errors=True)
                circuit_bytes = str(circuit).encode()
                dem_bytes = str(dem).encode()
                circuit_path = CIRCUIT_DIR / f"{corpus_id}.stim"
                dem_path = DEM_DIR / f"{corpus_id}.dem"
                circuit_path.write_bytes(circuit_bytes)
                dem_path.write_bytes(dem_bytes)
                report, duration, check_output = run_check(
                    str(dem_path), f"{corpus_id}.emlint.json"
                )
                simulation_started = time.perf_counter()
                simulation = simulate(circuit, dem)
                simulation_duration = time.perf_counter() - simulation_started
                simulation_path = RAW / f"{corpus_id}.simulation.json"
                simulation_path.write_text(
                    json.dumps(simulation, indent=2) + "\n", encoding="utf-8"
                )
                input_hash = sha256(dem_bytes)
                corpus_rows.append(
                    {
                        "id": corpus_id,
                        "status": "PENDING_HUMAN_REVIEW",
                        "evidence_class": "REAL_CORPUS",
                        "source_or_parent": {
                            "source": "Stim built-in generator",
                            "generator": generator,
                            "stim_source_url": "https://github.com/quantumlib/Stim",
                            "source_commit_or_archive_hash": None,
                        },
                        "input_sha256": input_hash,
                        "stim_version": stim_version,
                        "emlint_version": emlint_version,
                        "parameters": parameters,
                        "artifacts": {
                            "circuit": str(circuit_path.relative_to(ROOT)),
                            "dem": str(dem_path.relative_to(ROOT)),
                            "check_json": check_output,
                            "simulation_json": str(simulation_path.relative_to(ROOT)),
                        },
                        "source_provenance": "Stim package and generator parameters are pinned; known-good status requires human review and citable p_L evidence.",
                        "nonempty_mechanism_count": len(list(dem.flattened())),
                        "simulation_command": f"PYTHONPATH=. .venv312/bin/python campaigns/run_campaign.py --id {corpus_id} --shots {SHOTS} --seed {SEED}",
                        "shot_budget": SHOTS,
                        "seed": SEED,
                        "observed_checks": result_names(report),
                        "check_duration_seconds": duration,
                        "simulation_duration_seconds": simulation_duration,
                        "block_reason": None,
                    }
                )
                run_rows.extend(
                    [
                        {
                            "id": f"{corpus_id}-check",
                            "timestamp": "2026-08-19",
                            "command": f"emlint.check({dem_path})",
                            "environment": environment,
                            "input_hashes": {"dem": input_hash},
                            "exit_code": (
                                1
                                if report.has_errors()
                                else 2 if report.has_warnings() else 0
                            ),
                            "stdout_path": check_output,
                            "stderr_path": None,
                            "duration_seconds": duration,
                            "random_seed": None,
                            "complete": True,
                            "blocked": False,
                            "block_reason": None,
                        },
                        {
                            "id": f"{corpus_id}-simulation",
                            "timestamp": "2026-08-19",
                            "command": f"pymatching decode_batch; shots={SHOTS}; seed={SEED}",
                            "environment": environment,
                            "input_hashes": {
                                "circuit": sha256(circuit_bytes),
                                "dem": input_hash,
                            },
                            "exit_code": 0,
                            "stdout_path": str(simulation_path.relative_to(ROOT)),
                            "stderr_path": None,
                            "duration_seconds": simulation_duration,
                            "random_seed": SEED,
                            "complete": True,
                            "blocked": False,
                            "block_reason": None,
                        },
                    ]
                )
                first_error = next(
                    line for line in str(dem).splitlines() if line.startswith("error(")
                )
                for kind, expected, payload in mutation_kinds:
                    mutated = str(dem)
                    if payload.startswith("error"):
                        mutated += f"\n{payload}\n"
                    elif payload == "duplicate":
                        mutated += f"\n{first_error}\n"
                    elif payload == "dead":
                        mutated += f"\ndetector(99, 99) D{dem.num_detectors}\n"
                    else:
                        mutated = re.sub(
                            r"detector\(([^,]+), ([^)]+)\)",
                            r"detector(99, \2)",
                            mutated,
                            count=1,
                        )
                    mutation_id = f"{corpus_id}__{kind}"
                    mutation_bytes = mutated.encode()
                    mutation_path = DEM_DIR / f"{mutation_id}.dem"
                    mutation_path.write_bytes(mutation_bytes)
                    mutation_report, mutation_duration, mutation_output = run_check(
                        str(mutation_path), f"{mutation_id}.emlint.json"
                    )
                    observed = result_names(mutation_report)
                    mutation_rows.append(
                        {
                            "id": mutation_id,
                            "status": "PENDING_HUMAN_REVIEW",
                            "evidence_class": "REALISTIC_MUTATION",
                            "source_or_parent": corpus_id,
                            "input_sha256": sha256(mutation_bytes),
                            "stim_version": stim_version,
                            "emlint_version": emlint_version,
                            "parameters": {
                                "operation": kind,
                                "stage": "DEM post-processing",
                            },
                            "artifacts": {
                                "dem": str(mutation_path.relative_to(ROOT)),
                                "check_json": mutation_output,
                            },
                            "expected_outcome": expected,
                            "observed_outcome": (
                                "detected" if observed else "not_detected"
                            ),
                            "expected_checks": (
                                ["probability_bounds"]
                                if kind == "zero_probability"
                                else (
                                    ["detectability"]
                                    if kind == "logical_without_syndrome"
                                    else []
                                )
                            ),
                            "observed_checks": observed,
                            "bug_rationale": f"Pre-labelled {kind} mutation applied to a pinned Stim DEM.",
                            "pre_run_expected_checks": "Fixed before executing emlint",
                            "check_duration_seconds": mutation_duration,
                            "block_reason": None,
                        }
                    )
                    run_rows.append(
                        {
                            "id": f"{mutation_id}-check",
                            "timestamp": "2026-08-19",
                            "command": f"emlint.check({mutation_path})",
                            "environment": environment,
                            "input_hashes": {"dem": sha256(mutation_bytes)},
                            "exit_code": (
                                1
                                if mutation_report.has_errors()
                                else 2 if mutation_report.has_warnings() else 0
                            ),
                            "stdout_path": mutation_output,
                            "stderr_path": None,
                            "duration_seconds": mutation_duration,
                            "random_seed": None,
                            "complete": True,
                            "blocked": False,
                            "block_reason": None,
                        }
                    )
    write_jsonl(ROOT / "CORPUS_MANIFEST.jsonl", corpus_rows)
    write_jsonl(ROOT / "MUTATION_MANIFEST.jsonl", mutation_rows)
    write_jsonl(ROOT / "RUN_LOG.jsonl", run_rows)
    print(
        json.dumps(
            {
                "corpus": len(corpus_rows),
                "mutations": len(mutation_rows),
                "runs": len(run_rows),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
