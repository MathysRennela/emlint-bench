# Demo benchmark numbers (20260912)

> **Provenance** — Date: 20260912 · Campaign: IEEE-demo performance refresh
> (SPRINT Day 5) · Producer: `campaigns/measure_demo_performance.py` ·
> Environment: emlint 0.2.2, stim 1.16.0,
> python 3.14.6, macOS-26.6.2-arm64-arm-64bit-Mach-O ·
> Evidence: `results/raw/demo_perf_20260912.json` (per-artifact medians of
> 5 runs)

| Claim | Measured | Artifact |
|---|---|---|
| d=7 full suite | **33 ms** (0.033 s) | `workloads/demo/stim_rotated_surface_z_d7_r7.dem` |
| per-DEM median (48 demo artifacts) | **2.73 ms** | whole demo corpus |

Timings are empirical evidence on the tested instances only, recorded with
the environment above; they are not comparable across versions and do not
constitute a proof of any performance bound.
