"""Ingest mqt.qecc (Munich Quantum Toolkit QECC) color-code DEMs into the corpus.

Source: mqt.qecc 2.0.0 (https://github.com/munich-quantum-toolkit/qecc),
PyPI package `mqt.qecc`, MIT license. The synthesis API
(`mqt.qecc.circuit_synthesis.synthesize_encoding_circuit`,
`CNOTCircuit.to_stim_circuit`) was verified on 2026-08-24
(the ecosystem engagement plan, mqt.qecc section).

mqt.qecc exports bare Clifford-isometry circuits with no DETECTOR or
OBSERVABLE_INCLUDE annotations, so each corpus DEM is hand-assembled here
(emlint-side work, per the ecosystem engagement plan):

1. Encoding: `synthesize_encoding_circuit(HexagonalColorCode(d))` converted to
   a Stim circuit. The isometry's logical input is explicitly X-initialized
   (X_L = +1; the synthesis realizes a sqrt-X-like logical Clifford, so the
   default uninitialized input would leave the logical frame rotated). For
   memory Z a transversal H layer (logical Hadamard for self-dual 2D color
   codes) then yields a |0>_L state.
2. Noise (circuit-level, uniform p=0.001): X_ERROR after R, Z_ERROR after RX,
   DEPOLARIZE1 after single-qubit gates, DEPOLARIZE2 after each CX, and
   MZ(p) measurement flip. No idle noise on ancillas.
3. Syndrome extraction: one ancilla per check row, d rounds, round 1 compared
   to nothing (deterministic) and rounds >= 2 compared to the previous round.
4. Final transversal data measurement with check-parity detectors and a
   logical observable (Lz for memory Z, Lx for memory X).

Correctness gate per entry: with the noise stripped, 500 shots must produce
zero detection events and zero observable flips (all detectors deterministic).
Each DEM is then checked with emlint; results land in
`raw/dems/mqt_qecc_corpus_meta.json` mirroring the frontier ingest pattern.

Usage: .venv/bin/python run_mqt_qecc_ingest_20260902.py
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import stim

import emlint
from emlint.report import format_json
from mqt.qecc import codes
from mqt.qecc.circuit_synthesis import synthesize_encoding_circuit

OUT_DIR = Path(__file__).parent.parent / "workloads" / "dems"
CHECK_DIR = Path(__file__).parent.parent / "results" / "raw"
PACKAGE = "mqt.qecc"
PACKAGE_VERSION = "2.0.0"
REPO_URL = "https://github.com/munich-quantum-toolkit/qecc"
LICENSE = "MIT"
GENERATED = "2026-09-02"
P = 0.001
ROUNDS = 5
SHOTS = 500
DISTANCES: tuple[int, ...] = tuple(int(a) for a in sys.argv[1:]) or (3, 5, 7)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _rows(matrix: object) -> list[list[int]]:
    dense = matrix.toarray() if hasattr(matrix, "toarray") else np.asarray(matrix)
    return [[int(j) for j in np.flatnonzero(row)] for row in dense]


def _noise_after_encoding(enc: stim.Circuit, p: float) -> stim.Circuit:
    noisy = stim.Circuit()
    for inst in enc:
        name = inst.name
        targets = [t.qubit_value for t in inst.targets_copy()]
        if name in ("CX", "CNOT"):
            noisy.append("CX", targets)
            for i in range(0, len(targets), 2):
                noisy.append("DEPOLARIZE2", targets[i : i + 2], p)
        elif name in ("R", "RX"):
            # Noiseless initialization (standard memory-experiment convention):
            # a fault on the isometry's init instructions is an undetectable
            # logical fault by construction (it flips the encoded logical
            # before any syndrome exists).
            noisy.append(name, targets)
        elif name in ("H", "S", "S_DAG", "H_XZ"):
            noisy.append(name, targets)
            noisy.append("DEPOLARIZE1", targets, p)
        else:
            raise ValueError(f"unexpected encoding instruction: {name}")
    return noisy


def _extraction_round(
    checks_z: list[list[int]],
    checks_x: list[list[int]],
    n: int,
    p: float,
) -> tuple[stim.Circuit, int]:
    """One noisy syndrome-extraction round measuring both check banks.

    The Z bank (data->ancilla CXs) and the X bank (H-sandwiched ancilla->data
    CXs) are applied as sequential layers; CNOTs within a bank commute, and the
    banks use disjoint ancillas. Measuring both banks every round is what makes
    single-qubit X and Z faults on the data detectable (a single-basis memory
    leaves the conjugate-basis faults undetectable — caught by check
    detectability on the toy model).
    """
    circ = stim.Circuit()
    for i, support in enumerate(checks_z):
        anc = n + i
        for j in support:
            circ.append("CX", [j, anc])
            circ.append("DEPOLARIZE2", [j, anc], p)
    nz = len(checks_z)
    for i, support in enumerate(checks_x):
        anc = n + nz + i
        circ.append("H", [anc])
        circ.append("DEPOLARIZE1", [anc], p)
        for j in support:
            circ.append("CX", [anc, j])
            circ.append("DEPOLARIZE2", [anc, j], p)
        circ.append("H", [anc])
        circ.append("DEPOLARIZE1", [anc], p)
    ancillas = [n + i for i in range(nz + len(checks_x))]
    circ.append("MZ", ancillas, p)
    return circ, len(ancillas)


def _data_final(basis: str, n: int, p: float) -> tuple[stim.Circuit, int]:
    """Final H layer (X memory only) + transversal data measurement."""
    circ = stim.Circuit()
    if basis == "X":
        circ.append("H", list(range(n)))
        circ.append("DEPOLARIZE1", list(range(n)), p)
    circ.append("MZ", list(range(n)), p)
    return circ, n


def build_circuit(
    basis: str, code: codes.CSSCode, rounds: int, p: float
) -> tuple[stim.Circuit, dict[str, object]]:
    n = code.n
    checks_z = _rows(code.Hz)
    checks_x = _rows(code.Hx)
    logical = _rows(code.Lz if basis == "Z" else code.Lx)[0]
    num_anc = len(checks_z) + len(checks_x)

    iso = synthesize_encoding_circuit(code)
    # qubit `logical_to_input` is the free isometry input (left uninitialized by
    # the synthesis; the logical action is a sqrt-X-like Clifford, so input |+>
    # yields X_L = +1). Initialize it explicitly in the X basis.
    logical_inputs = [int(q) for q in iso.logical_to_input_mapping(code)]
    for q in logical_inputs:
        iso.initialize_qubit(q, "X")
    enc = _noise_after_encoding(iso.to_stim_circuit(), p)

    circ = stim.Circuit()
    circ += enc
    if basis == "Z":
        # X_L = +1 state; a transversal H on the data qubits is a logical
        # Hadamard for self-dual 2D color codes and yields a |0>_L state.
        circ.append("H", list(range(n)))
        circ.append("DEPOLARIZE1", list(range(n)), p)

    first, num_m = _extraction_round(checks_z, checks_x, n, p)
    circ += first
    for i in range(num_anc):
        circ.append("DETECTOR", [stim.target_rec(-num_m + i)])

    if rounds >= 3:
        body, num_m = _extraction_round(checks_z, checks_x, n, p)
        for i in range(num_anc):
            body.append(
                "DETECTOR",
                [stim.target_rec(-num_m + i), stim.target_rec(-2 * num_m + i)],
            )
        circ += body * (rounds - 2)

    last, num_m = _extraction_round(checks_z, checks_x, n, p)
    circ += last
    last_round_start = circ.num_measurements - num_m
    # The last round's ancilla measurements must also be compared to the
    # previous round: without this, a fault that flips both a last-round
    # ancilla and a data qubit in that ancilla's check support cancels the
    # final data-vs-ancilla detector (caught by check detectability).
    for i in range(num_anc):
        circ.append(
            "DETECTOR",
            [stim.target_rec(-num_m + i), stim.target_rec(-2 * num_m + i)],
        )

    fin, num_fin = _data_final(basis, n, p)
    circ += fin

    # Final detectors only for the memory basis: the transversal data
    # measurement reads that basis, so only its bank can be compared to data.
    final_checks = checks_z if basis == "Z" else checks_x
    bank_offset = 0 if basis == "Z" else len(checks_z)
    total = circ.num_measurements
    for i, support in enumerate(final_checks):
        recs = [stim.target_rec(last_round_start + bank_offset + i - total)]
        recs += [stim.target_rec(j - num_fin) for j in support]
        circ.append("DETECTOR", recs)
    circ.append(
        "OBSERVABLE_INCLUDE",
        [stim.target_rec(j - num_fin) for j in logical],
        0,
    )

    info = {
        "n": int(n),
        "k": int(code.k),
        "d": int(code.distance),
        "num_checks_z": len(checks_z),
        "num_checks_x": len(checks_x),
        "logical_support": [int(j) for j in logical],
        "logical_to_input": logical_inputs,
        "init": "logical input X-initialized (X_L = +1); Z memory adds a "
        "transversal H layer after encoding",
    }
    return circ, info


def noiseless_is_deterministic(
    basis: str, code: codes.CSSCode, rounds: int
) -> tuple[bool, float, float]:
    """The p=0 variant must have no error mechanisms in its DEM (stim rejects
    non-deterministic detectors, and any surviving error line means the assembly
    is wrong). Returns (ok, detection_rate, observable_flip_rate)."""
    circuit, _ = build_circuit(basis, code, rounds, 0.0)
    dem = circuit.detector_error_model(decompose_errors=False)
    ok = all(inst.type != "error" for inst in dem.flattened())
    sampler = circuit.compile_detector_sampler(seed=20260902)
    sample = sampler.sample(SHOTS, append_observables=True)
    dets, obs = sample[:, : dem.num_detectors], sample[:, dem.num_detectors :]
    return ok, float(dets.sum() / SHOTS), float(obs.sum() / SHOTS)


def emit(name: str, basis: str, distance: int, rounds: int) -> None:
    code = codes.HexagonalColorCode(distance)
    circuit, info = build_circuit(basis, code, rounds, P)

    ok, det_rate, obs_rate = noiseless_is_deterministic(basis, code, rounds)
    if not ok or det_rate > 0 or obs_rate > 0:
        raise SystemExit(
            f"{name}: noiseless circuit is non-deterministic "
            f"(dem_errors_ok={ok}, detection_rate={det_rate}, "
            f"observable_flip_rate={obs_rate}) — assembly is wrong, "
            "aborting before writing artifacts"
        )

    try:
        dem = circuit.detector_error_model(decompose_errors=True)
        decompose = True
    except Exception:
        dem = circuit.detector_error_model(decompose_errors=False)
        decompose = False
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
            "source": "mqt.qecc",
            "repo": REPO_URL,
            "package_version": PACKAGE_VERSION,
            "license": LICENSE,
            "generated": GENERATED,
            "code_family": "hexagonal 2D color code (mqt.qecc HexagonalColorCode)",
            "memory_basis": basis,
            "rounds": rounds,
            "noise_model": {
                "p": P,
                "init_noise": "none (noiseless state preparation; an init "
                "fault on the free logical input is an undetectable logical "
                "fault by construction)",
                "depolarize1_after_1q": P,
                "depolarize2_after_CX": P,
                "measurement_flip": P,
                "idle_ancilla_noise": "none",
            },
            "assembly": "encoding (mqt.qecc) + noise + syndrome extraction + "
            "detectors hand-assembled emlint-side (no upstream DEM export)",
            "decompose_errors": decompose,
            "num_qubits": circuit.num_qubits,
            "num_detectors": dem.num_detectors,
            "num_observables": dem.num_observables,
            "nonempty_mechanism_count": sum(
                1 for i in dem.flattened() if i.type == "error"
            ),
            "code": info,
            "noiseless_deterministic": True,
            "noiseless_shots": SHOTS,
            "noiseless_detection_rate": det_rate,
            "noiseless_observable_flip_rate": obs_rate,
            "circuit_sha256": sha256(str(circuit).encode()),
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
        }
    }
    meta_path = OUT_DIR / "mqt_qecc_corpus_meta.json"
    existing: dict[str, object] = {}
    if meta_path.exists():
        existing = json.loads(meta_path.read_text(encoding="utf-8"))
    existing.update(meta)
    meta_path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    print(
        f"{name}: dets={dem.num_detectors} obs={dem.num_observables} "
        f"exit={meta[name]['exit_code']} checks={failed}"
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for d in DISTANCES:
        for basis in ("X", "Z"):
            emit(f"mqt_qecc_hexd{d}_{basis.lower()}_r{ROUNDS}", basis, d, ROUNDS)


if __name__ == "__main__":
    main()
