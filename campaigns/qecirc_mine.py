"""Mine qecirc circuits for circuit-level instances of the taxonomy mechanisms.

Uniform noise rule applied identically to every circuit: DEPOLARIZE1 after
single-qubit Cliffords, DEPOLARIZE2 after two-qubit gates, X_ERROR before
measurement, measurement flip. Same rule across schedules => schedule is the
only varying factor.
"""

from __future__ import annotations

import pathlib
import sys

import stim

import emlint

P1 = 1e-3
P2 = 1e-2
PM = 1e-2

SINGLE_QUBIT_CLIFFORDS = {
    "H",
    "S",
    "S_DAG",
    "X",
    "Y",
    "Z",
    "C_XYZ",
    "C_ZYX",
    "SQRT_X",
    "SQRT_X_DAG",
    "SQRT_Y",
    "SQRT_Y_DAG",
}
TWO_QUBIT = {
    "CX",
    "CY",
    "CZ",
    "XCX",
    "XCZ",
    "ZCX",
    "ISWAP",
    "ISWAP_DAG",
    "SWAP",
    "CXSWAP",
    "SWAPCX",
    "ZCX",
}


def add_noise(
    circuit: stim.Circuit, p1: float = P1, p2: float = P2, pm: float = PM
) -> stim.Circuit:
    out = stim.Circuit()
    for inst in circuit:
        if isinstance(inst, stim.CircuitRepeatBlock):
            blk = add_noise(inst.body_copy(), p1, p2, pm)
            out.append(stim.CircuitRepeatBlock(inst.repeat_count, blk))
            continue
        name = inst.name
        targets = inst.targets_copy()
        if name == "M" or name == "MZ" or name == "MX" or name == "MY":
            qargs = [t.value for t in targets]
            out.append("X_ERROR", qargs, p1)
            out.append(name, targets, pm)
            continue
        if name == "MR" or name == "MRX" or name == "MRZ":
            qargs = [t.value for t in targets]
            out.append(name, targets, pm)
            out.append("X_ERROR", qargs, p1)
            continue
        out.append(name, targets, inst.gate_args_copy())
        if name in TWO_QUBIT:
            qargs = [t.value for t in targets if t.is_qubit_target]
            out.append("DEPOLARIZE2", qargs, p2)
        elif name in SINGLE_QUBIT_CLIFFORDS:
            qargs = [t.value for t in targets if t.is_qubit_target]
            out.append("DEPOLARIZE1", qargs, p1)
    return out


def run_one(stim_path: pathlib.Path) -> dict:
    circuit = stim.Circuit.from_file(str(stim_path))
    noisy = add_noise(circuit)
    try:
        dem = noisy.detector_error_model(decompose_errors=False)
    except Exception as e:  # noqa: BLE001
        return {"path": stim_path.name, "error": f"DEM build failed: {e}"}
    try:
        report = emlint.check(dem)
    except Exception as e:  # noqa: BLE001
        return {"path": stim_path.name, "error": f"emlint failed: {e}"}
    fails = {}
    for r in report.results:
        if not r.passed and r.severity == "error":
            fails[r.name] = (r.message, r.counter_example)
        elif not r.passed and r.severity == "warning":
            fails[r.name] = (r.message, r.counter_example)
    return {
        "path": stim_path.name,
        "num_mechanisms": len(list(dem.flattened())),
        "num_detectors": dem.num_detectors,
        "num_observables": dem.num_observables,
        "failures": {k: v[0] for k, v in fails.items()},
        "counter_examples": {k: v[1] for k, v in fails.items() if v[1]},
    }


def main() -> None:
    base = pathlib.Path("/tmp/qecirc-website/data_yaml/circuits")
    targets: list[str] = []
    # Paired schedules on the same patch (d=3,5,7)
    for d in (3, 5, 7):
        for sched in (
            "depth-optimal-schedule",
            "edge-coloring-schedule",
            "edge-coloring-schedule-x-z-split",
            "alphasyndrome-schedule-mwpm",
        ):
            targets.append(f"rotated-surface-code-d-{d}--{sched}.stim-annotated")
    # Concatenated codes: encoding + a schedule if present
    for slug in ("shor-code", "carbon-code"):
        for f in sorted(base.glob(f"{slug}--*.stim-annotated")):
            if "encoding" in f.name or "schedule" in f.name:
                targets.append(f.name)
    # Flag gadgets: first 12
    for f in sorted(base.glob("flag-gadgets--*.stim-annotated"))[:12]:
        targets.append(f.name)

    for name in targets:
        p = base / name
        if not p.exists():
            print(f"MISSING {name}")
            continue
        res = run_one(p)
        if "error" in res:
            print(f"ERROR {name}: {res['error']}")
            continue
        status = "CLEAN" if not res["failures"] else "FAIL"
        print(
            f"{status} {name} mechs={res['num_mechanisms']} dets={res['num_detectors']} obs={res['num_observables']}"
        )
        for k, msg in res["failures"].items():
            ce = res["counter_examples"].get(k, "")
            ce_short = (ce[:160] + "...") if ce and len(ce) > 160 else ce
            print(f"    {k}: {msg[:160]}")
            if ce_short:
                print(f"      CE: {ce_short}")


if __name__ == "__main__":
    sys.exit(main())
