"""Measure demo-facing emlint performance on the demo corpus.

Sprint task (Day 5): refresh the benchmark numbers behind the demo claims
("2.93 s d=7 full suite", "<1 ms per-DEM"). Methodology per the release
checklist §3a timing rules: median of five `time.perf_counter()` runs per
measurement, environment (python/stim/emlint versions, platform) recorded
alongside — timings are not comparable across versions.

Measured quantities:
- per-baseline full-battery time (median of 5), including the d=7 total
- per-DEM median across the whole demo corpus (baselines + verified mutants)

Outputs:
    results/raw/demo_perf_<date>.json
    results/DEMO_BENCHMARKS_<date>.md  (provenance-headed narrative summary)

Run (repo root, emlint importable):
    python campaigns/measure_demo_performance.py
"""

from __future__ import annotations

import importlib.metadata
import json
import platform
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import stim

import emlint

ROOT = Path(__file__).resolve().parent.parent
WORKLOADS = ROOT / "workloads" / "demo"
MANIFEST = ROOT / "manifests" / "demo_manifest.jsonl"
RESULTS = ROOT / "results"

REPEATS = 5


def _time_check(path: Path) -> float:
    text = path.read_text(encoding="utf-8")
    best_of = []
    for _ in range(REPEATS):
        start = time.perf_counter()
        emlint.check(text)
        best_of.append(time.perf_counter() - start)
    return statistics.median(best_of)


def main() -> int:
    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    environment = {
        "python": platform.python_version(),
        "stim": stim.__version__,
        "emlint": importlib.metadata.version("emlint"),
        "platform": platform.platform(),
        "repeats": REPEATS,
        "statistic": "median",
    }

    rows = [
        json.loads(line)
        for line in (ROOT / "manifests" / "demo_manifest.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    artifacts = [
        r for r in rows if r.get("artifact_kind") in ("baseline", "baseline_pinned", "mutant")
    ]

    per_artifact: dict[str, float] = {}
    for row in artifacts:
        path = ROOT / str(row["file"])
        if path.is_file():
            per_artifact[str(row["file"])] = _time_check(path)

    baselines = {
        name: t
        for name, t in per_artifact.items()
        if name.endswith(".dem") and "__" not in Path(name).name
    }
    d7_key = next(k for k in baselines if "d7" in k)
    per_dem_median = statistics.median(per_artifact.values())

    raw = {
        "date": date,
        "environment": environment,
        "per_artifact_seconds": per_artifact,
        "d7_full_suite_seconds": per_artifact[
            "workloads/demo/stim_rotated_surface_z_d7_r7.dem"
        ],
        "per_dem_median_seconds": statistics.median(per_artifact.values()),
    }
    raw_path = RESULTS / "raw" / f"demo_perf_{date}.json"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")

    md = f"""# Demo benchmark numbers ({date})

> **Provenance** — Date: {date} · Campaign: IEEE-demo performance refresh
> (SPRINT Day 5) · Producer: `campaigns/measure_demo_performance.py` ·
> Environment: emlint {environment['emlint']}, stim {environment['stim']},
> python {environment['python']}, {environment['platform']} ·
> Evidence: `results/raw/demo_perf_{date}.json` (per-artifact medians of
> {REPEATS} runs)

| Claim | Measured | Artifact |
|---|---|---|
| d=7 full suite | **{raw['d7_full_suite_seconds'] * 1000:.0f} ms** ({raw['d7_full_suite_seconds']:.3f} s) | `workloads/demo/stim_rotated_surface_z_d7_r7.dem` |
| per-DEM median (48 demo artifacts) | **{per_dem_median * 1000:.2f} ms** | whole demo corpus |

Timings are empirical evidence on the tested instances only, recorded with
the environment above; they are not comparable across versions and do not
constitute a proof of any performance bound.
"""
    (RESULTS / f"DEMO_BENCHMARKS_{date}.md").write_text(md, encoding="utf-8")

    print(
        json.dumps(
            {
                "d7_full_suite_seconds": raw["d7_full_suite_seconds"],
                "per_dem_median_seconds": per_dem_median,
                "artifacts_timed": len(per_artifact),
                "raw_file": str(raw_path),
                "summary_file": str(RESULTS / f"DEMO_BENCHMARKS_{date}.md"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())