"""Reproducible matched clean/buggy DEM decoder experiment.

Run from the repository root with:

    .venv312/bin/python benchmarks/matched_surface_code_experiment.py

The circuit sampler is identical for both cases. Only the decoder DEM is
changed, so the two logical-error-rate estimates are paired measurements of
clean versus deliberately buggy decoder behavior, not two different physical
noise experiments.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np
import pymatching  # type: ignore[import-not-found]
import stim

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "benchmarks"
TASK = "surface_code:rotated_memory_z"
DISTANCE = 3
ROUNDS = 3
NOISE = 0.02
SEED = 20260807
SHOTS = 100_000
DECOMPOSE_ERRORS = True


def build_circuit() -> stim.Circuit:
    """Build the one fixed physical circuit used by both decoder cases."""
    return stim.Circuit.generated(
        TASK,
        rounds=ROUNDS,
        distance=DISTANCE,
        after_clifford_depolarization=NOISE,
    )


def build_buggy_dem(clean_dem: stim.DetectorErrorModel) -> stim.DetectorErrorModel:
    """Remove every logical-edge mechanism while preserving observable count.

    This is intentionally not a physically valid replacement model: it leaves
    the detector graph but removes all DEM mechanisms that carry L0. The final
    zero-probability marker makes the observable dimension remain one, allowing
    PyMatching to decode the same sample shape. The clean circuit, and hence
    the sampled physical noise, is not changed.
    """
    retained = [
        line
        for line in str(clean_dem).splitlines()
        if not (" L0" in line or " L0 " in line)
    ]
    retained.append("error(0) L0")
    return stim.DetectorErrorModel("\n".join(retained))


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def main() -> None:
    circuit = build_circuit()
    clean_dem = circuit.detector_error_model(decompose_errors=DECOMPOSE_ERRORS)
    buggy_dem = build_buggy_dem(clean_dem)

    assert clean_dem.num_detectors == buggy_dem.num_detectors
    assert clean_dem.num_observables == buggy_dem.num_observables == 1

    sampler = circuit.compile_detector_sampler(seed=SEED)
    detector_samples, observable_samples = sampler.sample(
        shots=SHOTS, separate_observables=True
    )

    timings: dict[str, float] = {}
    rates: dict[str, dict[str, float | int]] = {}
    for name, dem in (("clean", clean_dem), ("buggy", buggy_dem)):
        started = time.perf_counter()
        matcher = pymatching.Matching.from_detector_error_model(dem)
        predictions = np.asarray(matcher.decode_batch(detector_samples))
        elapsed = time.perf_counter() - started
        failures = int(np.count_nonzero(predictions != observable_samples))
        timings[name] = elapsed
        rates[name] = {
            "failures": failures,
            "shots": SHOTS,
            "logical_error_rate": failures / SHOTS,
            "decoder_seconds": elapsed,
            "decoder_shots_per_second": SHOTS / elapsed,
        }

    circuit_text = str(circuit)
    clean_dem_text = str(clean_dem)
    buggy_dem_text = str(buggy_dem)
    result = {
        "status": "empirical_evidence_only",
        "matched_pair": True,
        "match_definition": "One fixed clean circuit sampler and one fixed seed feed both decoders; only the decoder DEM changes.",
        "circuit_generator": {
            "task": TASK,
            "distance": DISTANCE,
            "rounds": ROUNDS,
            "after_clifford_depolarization": NOISE,
            "decompose_errors": DECOMPOSE_ERRORS,
        },
        "sampling": {
            "shots": SHOTS,
            "seed": SEED,
            "detector_sample_shape": list(detector_samples.shape),
            "observable_sample_shape": list(observable_samples.shape),
        },
        "bug_definition": "Delete every clean DEM error line containing L0, then append error(0) L0 to preserve one observable dimension.",
        "dimensions": {
            "clean_detectors": clean_dem.num_detectors,
            "buggy_detectors": buggy_dem.num_detectors,
            "clean_observables": clean_dem.num_observables,
            "buggy_observables": buggy_dem.num_observables,
        },
        "rates": rates,
        "paired_decoder_prediction_disagreements": int(
            np.count_nonzero(
                np.asarray(
                    pymatching.Matching.from_detector_error_model(
                        clean_dem
                    ).decode_batch(detector_samples)
                )
                != np.asarray(
                    pymatching.Matching.from_detector_error_model(
                        buggy_dem
                    ).decode_batch(detector_samples)
                )
            )
        ),
        "artifacts": {
            "circuit_sha256": sha256(circuit_text),
            "clean_dem_sha256": sha256(clean_dem_text),
            "buggy_dem_sha256": sha256(buggy_dem_text),
        },
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "stim": importlib.metadata.version("stim"),
            "pymatching": importlib.metadata.version("pymatching"),
            "numpy": importlib.metadata.version("numpy"),
        },
    }

    json_path = OUT_DIR / "matched_surface_code_experiment.json"
    json_path.write_text(json.dumps(result, indent=2) + "\n")
    (OUT_DIR / "matched_surface_code_circuit.txt").write_text(circuit_text)
    (OUT_DIR / "matched_surface_code_clean.dem").write_text(clean_dem_text)
    (OUT_DIR / "matched_surface_code_buggy.dem").write_text(buggy_dem_text)

    report = f"""# Matched clean/buggy surface-code experiment

**Status:** empirical evidence only; no mathematical proof is claimed.

## Reproduction

```text
.venv312/bin/python benchmarks/matched_surface_code_experiment.py
```

The runner writes the machine-readable result to
`benchmarks/matched_surface_code_experiment.json` and preserves the exact
circuit and both DEMs alongside this report.

## Exact setup

- Stim generator call: `stim.Circuit.generated({TASK!r}, rounds={ROUNDS}, distance={DISTANCE}, after_clifford_depolarization={NOISE!r})`
- Rendered circuit: `benchmarks/matched_surface_code_circuit.txt`
- DEM conversion: `circuit.detector_error_model(decompose_errors={DECOMPOSE_ERRORS!r})`
- Decoder: `pymatching.Matching.from_detector_error_model`
- Shots: `{SHOTS:,}`
- Fixed sampler seed: `{SEED}`
- Noise parameter: after-Clifford depolarization `p={NOISE}`

## Matched-pair definition

This is a genuinely matched comparison: one sampler generated all detector and
observable samples from the clean circuit, with the same seed, and both decoder
models consumed those identical detector samples. The clean and buggy DEMs have
identical dimensions (`{clean_dem.num_detectors}` detectors and one observable).
The buggy DEM is deliberately constructed by deleting every error mechanism
containing `L0`, then appending `error(0) L0` only to preserve the observable
count. It is therefore a decoder-model bug, not a second physical circuit.

## Measured result

| Decoder DEM | Logical failures | Shots | Logical-error-rate | Decoder rate |
|---|---:|---:|---:|---:|
| clean | {rates['clean']['failures']:,} | {SHOTS:,} | {rates['clean']['logical_error_rate']:.8f} | {rates['clean']['decoder_shots_per_second']:.0f} shots/s |
| buggy | {rates['buggy']['failures']:,} | {SHOTS:,} | {rates['buggy']['logical_error_rate']:.8f} | {rates['buggy']['decoder_shots_per_second']:.0f} shots/s |

The two decoder predictions differed on
`{result['paired_decoder_prediction_disagreements']:,}` of `{SHOTS:,}` identical
sampled shots. The rates are finite-sample estimates from this one seed and
shot budget; they are not exact rates and do not establish a theorem about
other distances, rounds, noise values, decoders, or seeds.

## Provenance

- Circuit SHA-256: `{result['artifacts']['circuit_sha256']}`
- Clean DEM SHA-256: `{result['artifacts']['clean_dem_sha256']}`
- Buggy DEM SHA-256: `{result['artifacts']['buggy_dem_sha256']}`
- Python: `{sys.version.split()[0]}`
- Stim: `{result['environment']['stim']}`
- PyMatching: `{result['environment']['pymatching']}`
- NumPy: `{result['environment']['numpy']}`
- Platform: `{platform.platform()}`

## Interpretation boundary

The experiment supports the empirical statement that this deliberately buggy
DEM produced a higher observed logical-failure fraction than the clean DEM on
this exact matched d=3, three-round circuit sample. It does **not** prove that
all DEM bugs inflate logical error rates, that the difference generalizes, or
that the buggy DEM represents a valid physical noise process.
"""
    (OUT_DIR / "MATCHED_SURFACE_CODE_EXPERIMENT.md").write_text(report)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
