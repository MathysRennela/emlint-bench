"""Differential DEM experiment: stim vs PECOS (rotated surface code, d=3, r=3).

Companion experiment for the emlint ecosystem engagement plan, PECOS
section (step 1). Builds the same memory experiment twice through independent
circuit→DEM implementations and compares canonical signature multisets:

  - stim:  Circuit.generated("surface_code:rotated_memory_z") → detector_error_model()
  - PECOS: make_surface_code(...) → DetectorErrorModel.from_guppy(...)

Normalization: flatten REPEAT blocks, fuse duplicate signatures by summing
probabilities, sort. Comparison is signature-multiset based, never positional
(detector indexing and scheduling differ legitimately between the two
independently constructed circuits).

Noise mapping (v1, documented in the engagement plan's PECOS section, step 3):
  stim after_clifford_depolarization   → PECOS p1 (1q Cliffords) and p2 (2q)
  stim before_measure_flip_probability → PECOS p_meas
  stim after_reset_flip_probability    → PECOS p_prep
  before_round_data_depolarization     → omitted on both sides (PECOS idle
                                          noise needs explicit Idle gates)

Run: python campaigns/pecos_stim_differential.py
"""

from __future__ import annotations

from collections import defaultdict

import stim

P = 0.001
DISTANCE = 3
ROUNDS = 3

Signature = tuple[frozenset[int], frozenset[int]]


def stim_dem_signatures(dem: stim.DetectorErrorModel) -> dict[Signature, float]:
    sigs: dict[Signature, float] = defaultdict(float)
    for instr in dem.flattened():
        if instr.type != "error":
            continue
        p = instr.args_copy()[0]
        dets: set[int] = set()
        obs: set[int] = set()
        for t in instr.targets_copy():
            if t.is_relative_detector_id():
                dets.add(t.val)
            elif t.is_logical_observable_id():
                obs.add(t.val)
        sigs[(frozenset(dets), frozenset(obs))] += p
    return dict(sigs)


def pecos_dem_signatures(dem_text: str) -> dict[Signature, float]:
    # PECOS emits standard Stim DEM text; parse with stim and reuse the same
    # canonicalization so both sides go through identical code.
    return stim_dem_signatures(stim.DetectorErrorModel(dem_text))


def main() -> None:
    # --- stim side ---
    circuit = stim.Circuit.generated(
        "surface_code:rotated_memory_z",
        distance=DISTANCE,
        rounds=ROUNDS,
        after_clifford_depolarization=P,
        before_measure_flip_probability=P,
        after_reset_flip_probability=P,
    )
    dem_stim = circuit.detector_error_model(decompose_errors=False)
    stim_text_path = "results/raw/pecos_stim_differential_stim.dem"
    with open(stim_text_path, "w") as f:
        f.write(str(dem_stim))

    # --- PECOS side ---
    # NOTE: DetectorErrorModel.from_guppy is unusable in pecos 0.11.0.dev0 on
    # macOS arm64 — the wheel ships without libhelios_selene_interface.a
    # (Selene QIS engine fails to load). from_circuit bypasses Selene: it
    # builds the DEM from the annotated TickCircuit with native PECOS fault
    # propagation, which is also the cleaner differential (abstract circuit →
    # DEM on both sides).
    from pecos.guppy_gen import get_num_qubits
    from pecos.qec import DetectorErrorModel
    from pecos.qec.surface import SurfacePatch
    from pecos.qec.surface.circuit_builder import generate_tick_circuit_from_patch

    patch = SurfacePatch.create(distance=DISTANCE)
    meta_tc = generate_tick_circuit_from_patch(patch, num_rounds=ROUNDS, basis="Z")
    dem_pecos = DetectorErrorModel.from_circuit(
        meta_tc,
        p1=P,
        p2=P,
        p_meas=P,
        p_prep=P,
    )
    pecos_text = dem_pecos.to_string()
    pecos_text_path = "results/raw/pecos_stim_differential_pecos.dem"
    with open(pecos_text_path, "w") as f:
        f.write(pecos_text + "\n")

    # --- canonical comparison ---
    sig_stim = stim_dem_signatures(dem_stim)
    sig_pecos = pecos_dem_signatures(pecos_text)

    print(f"p={P} d={DISTANCE} r={ROUNDS} basis=Z")
    print(
        f"stim : num_detectors={dem_stim.num_detectors} num_observables={dem_stim.num_observables} "
        f"mechanisms={len(sig_stim)}"
    )
    print(
        f"pecos: num_detectors={dem_pecos.num_detectors} num_observables={dem_pecos.num_observables} "
        f"mechanisms={len(sig_pecos)}"
    )

    only_stim = set(sig_stim) - set(sig_pecos)
    only_pecos = set(sig_pecos) - set(sig_stim)
    common = set(sig_stim) & set(sig_pecos)

    prob_mismatch = []
    for s in sorted(common):
        a, b = sig_stim[s], sig_pecos[s]
        if abs(a - b) > 1e-9:
            prob_mismatch.append((s, a, b))

    print(
        f"\nsignature sets: common={len(common)} only_stim={len(only_stim)} only_pecos={len(only_pecos)}"
    )
    print(
        f"probability mismatches among common signatures (tol 1e-9): {len(prob_mismatch)}"
    )

    def fmt(sig: Signature) -> str:
        dets = ",".join(f"D{d}" for d in sorted(sig[0]))
        obs = ",".join(f"L{o}" for o in sorted(sig[1]))
        return f"{{{dets}}} {{{obs}}}"

    for s in sorted(only_stim, key=fmt)[:10]:
        print(f"  only stim : {fmt(s)}  p_total={sig_stim[s]:.6g}")
    for s in sorted(only_pecos, key=fmt)[:10]:
        print(f"  only pecos: {fmt(s)}  p_total={sig_pecos[s]:.6f}")
    for s, a, b in prob_mismatch[:10]:
        print(f"  p mismatch: {fmt(s)}  stim={a:.9f} pecos={b:.9f}")

    if not only_stim and not only_pecos and not prob_mismatch:
        print("\nRESULT: DEMs agree exactly on canonical signature multisets.")
    else:
        print(
            "\nRESULT: DISCREPANCY — adjudicate (stim bug / PECOS bug / semantic difference)."
        )


if __name__ == "__main__":
    main()
