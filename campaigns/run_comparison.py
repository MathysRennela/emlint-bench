"""Phase 5: fixed-budget workflow comparison.

Compares three workflows per mutation (phase 5 of the internal bug-audit plan):
  1. simulation only — sample shots, decode, count logical failures;
  2. emlint only — run the check battery;
  3. emlint followed by simulation — simulate only if emlint passes.

Power analysis (recorded up front): at N=20,000 shots and baseline logical
error rate p in [0.001, 0.01], the two-sided ~2-sigma minimum detectable
effect is 3*sqrt(p(1-p)/N) ≈ 0.0007–0.0021. Mutations whose true effect is
below this MDE cannot be adjudicated by simulation at this budget; that is a
budget limitation, not a detection success or failure.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pymatching
import stim

from run_smoke import ROOT, SEED, SHOTS, sha256

DEMS = ROOT / "raw" / "dems"
OUT = ROOT / "raw"
COMPARISON_SHOTS = 20_000


def simulate(dem_path: Path) -> dict[str, object]:
    """Decode COMPARISON_SHOTS shots against *dem_path*; return failure stats."""
    dem = stim.DetectorErrorModel(dem_path.read_text())
    # The mutation DEMs are standalone artifacts: decode them against
    # themselves so any structural damage the decoder cannot exploit shows up
    # as prediction failures.
    sampler = dem.compile_sampler(seed=SEED)
    detectors, observables, _flipped_errors = sampler.sample(shots=COMPARISON_SHOTS)
    decoder = pymatching.Matching.from_detector_error_model(dem)
    started = time.perf_counter()
    predictions = decoder.decode_batch(detectors)
    elapsed = time.perf_counter() - started
    failures = int((predictions != observables).any(axis=1).sum())
    return {
        "shots": COMPARISON_SHOTS,
        "seed": SEED,
        "logical_failures": failures,
        "logical_error_rate": failures / COMPARISON_SHOTS,
        "decode_seconds": round(elapsed, 3),
    }


def main() -> None:
    manifest = [
        json.loads(line)
        for line in (ROOT / "MUTATION_MANIFEST.jsonl").read_text().splitlines()
    ]
    campaign = [r for r in manifest if r["id"].startswith("campaign_20260819")]
    seen = set()
    unique = []
    for r in campaign:
        if r["id"] not in seen:
            seen.add(r["id"])
            unique.append(r)

    comparison_rows: list[dict[str, object]] = []
    for row in unique:
        mut_dem = DEMS / f"{row['id']}.dem"
        parent_id = row["source_or_parent"]
        parent_dem = DEMS / f"{parent_id}.dem"

        t0 = time.perf_counter()
        sim_mut = simulate(mut_dem)
        sim_time = time.perf_counter() - t0

        t0 = time.perf_counter()
        lint_report = json.loads((ROOT / row["artifacts"]["check_json"]).read_text())
        lint_failures = [r for r in lint_report["results"] if not r["passed"]]
        lint_time = row.get("check_duration_seconds") or 0.0

        parent_sim_path = OUT / f"{parent_id}.simulation.json"
        parent_sim = json.loads(parent_sim_path.read_text())
        base_rate = float(parent_sim["logical_error_rate"])
        mut_rate = float(sim_mut["logical_error_rate"])
        mde = 3 * (base_rate * (1 - base_rate) / COMPARISON_SHOTS) ** 0.5
        effect = mut_rate - base_rate
        sim_detects = abs(effect) > mde

        comparison_rows.append(
            {
                "id": row["id"],
                "mutation_kind": row["parameters"]["operation"],
                "budget_shots": COMPARISON_SHOTS,
                "seed": SEED,
                "baseline_rate": base_rate,
                "mutant_rate": mut_rate,
                "effect": round(effect, 6),
                "mde_2sigma": round(mde, 6),
                "workflow1_simulation_only_detected": sim_detects,
                "workflow2_emlint_only_detected": bool(lint_failures),
                "emlint_checks_firing": [r["name"] for r in lint_failures],
                "emlint_seconds": round(float(lint_time), 4),
                "simulation_seconds": round(sim_time, 4),
                "within_budget_resolution": not sim_detects and abs(effect) <= mde,
            }
        )

    out_path = OUT / "phase5_workflow_comparison.jsonl"
    with out_path.open("w", encoding="utf-8") as handle:
        for r in comparison_rows:
            handle.write(json.dumps(r, sort_keys=True) + "\n")

    # Aggregate
    kinds: dict[str, dict[str, int]] = {}
    for r in comparison_rows:
        k = kinds.setdefault(
            r["mutation_kind"],
            {"n": 0, "sim_only": 0, "lint_only": 0, "both": 0, "neither": 0},
        )
        k["n"] += 1
        s, l = (
            r["workflow1_simulation_only_detected"],
            r["workflow2_emlint_only_detected"],
        )
        if s and l:
            k["both"] += 1
        elif s:
            k["sim_only"] += 1
        elif l:
            k["lint_only"] += 1
        else:
            k["neither"] += 1

    print(json.dumps(kinds, indent=2))
    print(f"wrote {len(comparison_rows)} rows to {out_path.relative_to(ROOT.parent)}")


if __name__ == "__main__":
    main()
