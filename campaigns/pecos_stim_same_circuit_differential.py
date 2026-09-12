"""Differential DEM experiment, phase 2: same-circuit comparison.

Phase 1 (pecos_stim_differential.py) compared independently *constructed*
circuits and found a detector-set convention difference (PECOS 28 detectors vs
stim 24 at d=3 r=3; PECOS uses the conserved-eigenvalue convention for
first-round X-stabilizer detectors). Phase 2 removes construction from the
equation:

  PECOS TickCircuit (surface builder) --translated--> stim Circuit
  stim DEM (from that circuit)  vs  PECOS DEM (from the same TickCircuit)

Any remaining discrepancy is attributable to the DEM builders, not to circuit
construction or detector conventions. The translator is minimal and only
handles the gate vocabulary the surface builder emits
(QAlloc/H/CX/MZ/MeasureFree/Idle); noise is inserted at stim-equivalent
locations (DEPOLARIZE1 after 1q Cliffords and Idle locations, DEPOLARIZE2
after CX, X_ERROR before measurement / after reset).

This runner sweeps: d in {3, 5} x basis in {Z, X}, plus an idle-noise config
(fill_idle_gates: per-tick identity gates receiving p1, documented by PECOS as
matching stim's DEPOLARIZE1-on-idles convention).

Run: python campaigns/pecos_stim_same_circuit_differential.py
"""

from __future__ import annotations

from collections import defaultdict

import stim

P = 0.001

Signature = tuple[frozenset[int], frozenset[int]]


def dem_signatures(dem: stim.DetectorErrorModel) -> dict[Signature, float]:
    sigs: dict[Signature, float] = defaultdict(float)
    for instr in dem.flattened():
        if instr.type != "error":
            continue
        dets: set[int] = set()
        obs: set[int] = set()
        for t in instr.targets_copy():
            if t.is_relative_detector_id():
                dets.add(t.val)
            elif t.is_logical_observable_id():
                obs.add(t.val)
        sigs[(frozenset(dets), frozenset(obs))] += instr.args_copy()[0]
    return dict(sigs)


def tickcircuit_to_stim(tc, p: float, idle_mode: str = "none") -> stim.Circuit:
    """Translate a PECOS TickCircuit into an annotated stim Circuit.

    Detector/observable record offsets in PECOS metadata are negative offsets
    into the full measurement record, so all annotations are emitted after the
    full gate stream, where stim's rec[-k] has the same meaning.

    idle_mode: how to translate Idle gates (from fill_idle_gates):
      - "none": drop them (no idle noise on either side)
      - "depol1": DEPOLARIZE1(p) — matches PECOS from_circuit(p_idle=p)
      Verified 2026-09-12: from_circuit(p_idle=p) matches DEPOLARIZE1 exactly;
      from_circuit(p_idle_linear_rate=p) / (p_idle_z_linear_rate=p) match
      Z_ERROR(p) exactly (Z-only idle noise). The fill_idle_gates docstring's
      claim that idles "receive p1 noise" is inaccurate for from_circuit: an
      explicit p_idle* parameter is required.
    """
    import json

    out = stim.Circuit()
    for i in range(tc.num_ticks()):
        tick = tc.get_tick(i)
        for gate in tick.gate_batches():
            gt = str(gate.gate_type).split(".")[-1]
            qs = list(gate.qubits)
            if gt == "QAlloc":
                out.append("R", qs)
                out.append("X_ERROR", qs, p)
            elif gt == "H":
                out.append("H", qs)
                out.append("DEPOLARIZE1", qs, p)
            elif gt == "CX":
                out.append("CX", qs)
                out.append("DEPOLARIZE2", qs, p)
            elif gt in ("MZ", "MeasureFree"):
                out.append("X_ERROR", qs, p)
                out.append("M", qs)
            elif gt == "Idle":
                if idle_mode == "depol1":
                    out.append("DEPOLARIZE1", qs, p)
            else:
                raise ValueError(f"unhandled gate type {gt} on qubits {qs}")

    dets = json.loads(tc.get_meta("detectors"))
    for d in sorted(dets, key=lambda d: d["id"]):
        x, y, t = d["coords"]
        targets = [stim.target_rec(r) for r in d["records"]]
        out.append("DETECTOR", targets, (x, y, t))
    obs = json.loads(tc.get_meta("observables"))
    for o in obs:
        targets = [stim.target_rec(r) for r in o["records"]]
        out.append("OBSERVABLE_INCLUDE", targets, o.get("id", 0))
    return out


def run_config(distance: int, rounds: int, basis: str, fill_idles: bool) -> bool:
    from pecos.qec import DetectorErrorModel
    from pecos.qec.surface import SurfacePatch
    from pecos.qec.surface.circuit_builder import generate_tick_circuit_from_patch

    patch = SurfacePatch.create(distance=distance)
    tc = generate_tick_circuit_from_patch(patch, num_rounds=rounds, basis=basis)
    if fill_idles:
        tc.fill_idle_gates()

    idle_mode = "depol1" if fill_idles else "none"
    circuit = tickcircuit_to_stim(tc, P, idle_mode=idle_mode)
    dem_stim = circuit.detector_error_model(decompose_errors=False)
    pecos_kwargs = dict(p1=P, p2=P, p_meas=P, p_prep=P)
    if fill_idles:
        # Idle locations are only noised via an explicit p_idle* parameter;
        # p_idle is the uniform-depolarizing spelling (DEPOLARIZE1-equivalent).
        pecos_kwargs["p_idle"] = P
    dem_pecos = DetectorErrorModel.from_circuit(tc, **pecos_kwargs)
    sig_pecos = stim.DetectorErrorModel(dem_pecos.to_string())

    s_stim = dem_signatures(dem_stim)
    s_pecos = dem_signatures(sig_pecos)

    label = f"d={distance} r={rounds} basis={basis}" + (" +idles" if fill_idles else "")
    print(f"--- {label} ---")
    print(
        f"stim (translated PECOS circuit): num_detectors={dem_stim.num_detectors} "
        f"mechanisms={len(s_stim)}"
    )
    print(
        f"pecos (from_circuit):            num_detectors={sig_pecos.num_detectors} "
        f"mechanisms={len(s_pecos)}"
    )

    only_stim = set(s_stim) - set(s_pecos)
    only_pecos = set(s_pecos) - set(s_stim)
    common = set(s_stim) & set(s_pecos)
    mismatches = [
        (s, s_stim[s], s_pecos[s])
        for s in sorted(common)
        if abs(s_stim[s] - s_pecos[s]) > 1e-6
    ]
    print(
        f"signature sets: common={len(common)} only_stim={len(only_stim)} "
        f"only_pecos={len(only_pecos)}; p mismatches (tol 1e-6): {len(mismatches)}"
    )

    def fmt(sig: Signature) -> str:
        dets = ",".join(f"D{d}" for d in sorted(sig[0]))
        obs = ",".join(f"L{o}" for o in sorted(sig[1]))
        return f"{{{dets}}} {{{obs}}}"

    for s in sorted(only_stim, key=fmt)[:5]:
        print(f"  only stim : {fmt(s)}  p_total={s_stim[s]:.6g}")
    for s in sorted(only_pecos, key=fmt)[:5]:
        print(f"  only pecos: {fmt(s)}  p_total={s_pecos[s]:.6g}")
    for s, a, b in mismatches[:5]:
        print(f"  p mismatch: {fmt(s)}  stim={a:.9f} pecos={b:.9f}")

    ok = not only_stim and not only_pecos and not mismatches
    print(f"RESULT: {'AGREE' if ok else 'DISCREPANCY — adjudicate'}\n")
    return ok


def main() -> None:
    configs = [
        (3, 3, "Z", False),
        (5, 5, "Z", False),
        (3, 3, "X", False),
        (5, 5, "X", False),
        (3, 3, "Z", True),  # idle-noise mapping via fill_idle_gates
    ]
    results = {c: run_config(*c) for c in configs}
    n_ok = sum(1 for c in configs if results[c])
    print(f"summary: {n_ok}/{len(configs)} configs agree")


if __name__ == "__main__":
    main()
