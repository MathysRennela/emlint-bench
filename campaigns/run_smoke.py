from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform

import time
from pathlib import Path

import pymatching
import stim

import emlint
from emlint.report import Report, format_json

ROOT = Path(__file__).parent
RAW = ROOT / "raw"
DEM_DIR = RAW / "dems"
CIRCUIT_DIR = RAW / "circuits"
SEED = 20260819
SHOTS = 2_000


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def result_names(report: Report) -> list[str]:
    return [result.name for result in report.results if not result.passed]


def run_check(source: str, output_name: str) -> tuple[Report, float, str]:
    started = time.perf_counter()
    report = emlint.check(source)
    duration = time.perf_counter() - started
    output_path = RAW / output_name
    output_path.write_text(format_json(report) + "\n", encoding="utf-8")
    return report, duration, str(output_path.relative_to(ROOT))


def simulate(circuit: stim.Circuit, dem: stim.DetectorErrorModel) -> dict[str, object]:
    sampler = circuit.compile_detector_sampler(seed=SEED)
    detectors, observables = sampler.sample(shots=SHOTS, separate_observables=True)
    decoder = pymatching.Matching.from_detector_error_model(dem)
    predictions = decoder.decode_batch(detectors)
    failures = int((predictions != observables).any(axis=1).sum())
    return {
        "decoder": "pymatching.Matching.from_detector_error_model",
        "shots": SHOTS,
        "seed": SEED,
        "logical_failures": failures,
        "logical_error_rate": failures / SHOTS,
    }


def main() -> None:
    for directory in (RAW, DEM_DIR, CIRCUIT_DIR):
        directory.mkdir(parents=True, exist_ok=True)

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

    sources = [
        (
            "stim_repetition_d3_r3",
            "repetition_code:memory",
            {"distance": 3, "rounds": 3, "after_clifford_depolarization": 0.001},
        ),
        (
            "stim_surface_rotated_z_d3_r3",
            "surface_code:rotated_memory_z",
            {"distance": 3, "rounds": 3, "after_clifford_depolarization": 0.001},
        ),
        (
            "stim_surface_rotated_x_d3_r3",
            "surface_code:rotated_memory_x",
            {"distance": 3, "rounds": 3, "after_clifford_depolarization": 0.001},
        ),
    ]
    corpus_rows: list[dict[str, object]] = []
    run_rows: list[dict[str, object]] = []
    mutation_rows: list[dict[str, object]] = []

    for corpus_id, generator, parameters in sources:
        circuit = stim.Circuit.generated(generator, **parameters)
        dem = circuit.detector_error_model(decompose_errors=True)
        circuit_bytes = str(circuit).encode()
        dem_bytes = str(dem).encode()
        circuit_path = CIRCUIT_DIR / f"{corpus_id}.stim"
        dem_path = DEM_DIR / f"{corpus_id}.dem"
        circuit_path.write_bytes(circuit_bytes)
        dem_path.write_bytes(dem_bytes)
        report, duration, output_path = run_check(
            str(dem_path), f"{corpus_id}.emlint.json"
        )
        simulation = simulate(circuit, dem)
        simulation_path = RAW / f"{corpus_id}.simulation.json"
        simulation_path.write_text(
            json.dumps(simulation, indent=2) + "\n", encoding="utf-8"
        )
        status = "PENDING_HUMAN_REVIEW"
        corpus_rows.append(
            {
                "id": corpus_id,
                "status": status,
                "evidence_class": "REAL_CORPUS",
                "source_or_parent": {
                    "source": "Stim built-in generator",
                    "generator": generator,
                    "stim_source_url": "https://github.com/quantumlib/Stim",
                    "source_commit_or_archive_hash": None,
                },
                "input_sha256": sha256(dem_bytes),
                "stim_version": stim_version,
                "emlint_version": emlint_version,
                "parameters": parameters,
                "artifacts": {
                    "circuit": str(circuit_path.relative_to(ROOT)),
                    "dem": str(dem_path.relative_to(ROOT)),
                    "check_json": output_path,
                    "simulation_json": str(simulation_path.relative_to(ROOT)),
                },
                "source_provenance": "Built-in Stim generator is pinned by package version; known-good status and published p_L reference require human review.",
                "nonempty_mechanism_count": len(list(dem.flattened())),
                "simulation_command": f".venv312/bin/python campaigns/run_smoke.py --simulation {corpus_id} --shots {SHOTS} --seed {SEED}",
                "shot_budget": SHOTS,
                "seed": SEED,
                "observed_checks": result_names(report),
                "check_duration_seconds": duration,
                "block_reason": None,
            }
        )
        run_rows.append(
            {
                "id": f"check-{corpus_id}",
                "timestamp": "2026-08-19",
                "command": f"emlint.check({dem_path})",
                "environment": environment,
                "input_hashes": {"dem": sha256(dem_bytes)},
                "exit_code": (
                    1 if report.has_errors() else 2 if report.has_warnings() else 0
                ),
                "stdout_path": output_path,
                "stderr_path": None,
                "duration_seconds": duration,
                "random_seed": None,
                "complete": True,
                "blocked": False,
                "block_reason": None,
            }
        )
        run_rows.append(
            {
                "id": f"simulation-{corpus_id}",
                "timestamp": "2026-08-19",
                "command": f"pymatching decode_batch; shots={SHOTS}; seed={SEED}",
                "environment": environment,
                "input_hashes": {
                    "circuit": sha256(circuit_bytes),
                    "dem": sha256(dem_bytes),
                },
                "exit_code": 0,
                "stdout_path": str(simulation_path.relative_to(ROOT)),
                "stderr_path": None,
                "duration_seconds": None,
                "random_seed": SEED,
                "complete": True,
                "blocked": False,
                "block_reason": None,
            }
        )

        mutation_specs = [
            (
                "zero_probability",
                "DEM post-processing",
                "Deterministic catch — error",
                "Inject a zero-probability mechanism that should be rejected.",
                "error(0) D0",
            ),
            (
                "high_probability",
                "DEM post-processing",
                "Deterministic catch — warning",
                "Inject a probability above 0.5.",
                "error(0.75) D0",
            ),
            (
                "detector_index_shift",
                "DEM post-processing",
                "Simulation-blind",
                "Shift one detector label without changing structural self-consistency assumptions.",
                None,
            ),
            (
                "coordinate_only",
                "DEM post-processing",
                "Cosmetic-only today",
                "Change detector coordinate metadata; coordinates are not used by current sensitivity.",
                None,
            ),
        ]
        for mutation_id, stage, expected, rationale, injected in mutation_specs:
            mutated = str(dem)
            if injected is not None:
                mutated += f"\n{injected}\n"
            elif mutation_id == "detector_index_shift":
                mutated = mutated.replace(" D0", " D1", 1)
            else:
                mutated = mutated.replace("detector(0)", "detector(1)", 1)
            mutation_bytes = mutated.encode()
            mutation_path = DEM_DIR / f"{corpus_id}__{mutation_id}.dem"
            mutation_path.write_bytes(mutation_bytes)
            mutation_report, mutation_duration, mutation_output = run_check(
                str(mutation_path), f"{corpus_id}__{mutation_id}.emlint.json"
            )
            observed = result_names(mutation_report)
            run_rows.append(
                {
                    "id": f"check-{corpus_id}__{mutation_id}",
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
            mutation_rows.append(
                {
                    "id": f"{corpus_id}__{mutation_id}",
                    "status": "PENDING_HUMAN_REVIEW",
                    "evidence_class": "REALISTIC_MUTATION",
                    "source_or_parent": corpus_id,
                    "input_sha256": sha256(mutation_bytes),
                    "stim_version": stim_version,
                    "emlint_version": emlint_version,
                    "parameters": {"operation": mutation_id, "stage": stage},
                    "artifacts": {
                        "dem": str(mutation_path.relative_to(ROOT)),
                        "check_json": mutation_output,
                    },
                    "expected_outcome": expected,
                    "observed_outcome": "detected" if observed else "not_detected",
                    "expected_checks": (
                        ["probability_bounds"]
                        if mutation_id == "zero_probability"
                        else (
                            ["high_probability_mechanisms"]
                            if mutation_id == "high_probability"
                            else []
                        )
                    ),
                    "observed_checks": observed,
                    "bug_rationale": rationale,
                    "pre_run_expected_checks": "Fixed before executing emlint",
                    "check_duration_seconds": mutation_duration,
                    "block_reason": None,
                }
            )

    write_jsonl(ROOT / "CORPUS_MANIFEST.jsonl", corpus_rows)
    write_jsonl(ROOT / "MUTATION_MANIFEST.jsonl", mutation_rows)
    write_jsonl(ROOT / "RUN_LOG.jsonl", run_rows)
    (ROOT / "ENVIRONMENT.json").write_text(
        json.dumps(environment, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "corpus": len(corpus_rows),
                "mutations": len(mutation_rows),
                "runs": len(run_rows),
                "environment": environment,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
