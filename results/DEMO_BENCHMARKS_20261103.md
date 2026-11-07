# Demo benchmark numbers (20261103)

> **Provenance** — Date: 20261103 · Campaign: IEEE-demo performance refresh
> (SPRINT Day 5) · Producer: `campaigns/measure_demo_performance.py` ·
> Environment: emlint 0.2.4, stim 1.16.0,
> python 3.14.4, Linux-7.0.0-38-generic-x86_64-with-glibc2.43 ·
> Evidence: `results/raw/demo_perf_20261103.json` (per-artifact medians of
> 5 runs)

| Claim | Measured | Artifact |
|---|---|---|
| d=7 full suite | **199 ms** (0.199 s) | `workloads/demo/stim_rotated_surface_z_d7_r7.dem` |
| per-DEM median (48 demo artifacts) | **14.77 ms** | whole demo corpus |

Timings are empirical evidence on the tested instances only, recorded with
the environment above; they are not comparable across versions and do not
constitute a proof of any performance bound.
