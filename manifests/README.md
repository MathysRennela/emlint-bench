# Manifests

- `SWEEP_MANIFEST.jsonl` — Stim builtins sweep (224 entries). One JSON object per
  sweep entry; artifact paths are relative to this repository root:
  `workloads/circuits/`, `workloads/dems/` (regenerable from the recorded
  generator parameters), and `results/raw/` for check/simulation outputs.
- `ENVIRONMENT.json` — toolchain versions used to produce the artifacts.

Stim-generated DEMs are not committed: regenerate them from the manifest
parameters at the pinned stim version and verify against the recorded hashes
(byte hash first, then the platform-independent semantic fingerprint recorded
in each row).
