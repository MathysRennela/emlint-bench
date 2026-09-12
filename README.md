# emlint-bench

Corpus audits and benchmarks for [emlint](https://github.com/MathysRennela/emlint), a static linter for Stim Detector Error Models (DEMs).

This repository tracks emlint's behavior across releases over a fixed set of DEM/circuit artifacts, following the clifft/clifft-bench companion-repo pattern.

## Layout

| Directory | Contents |
|---|---|
| `manifests/` | Pinned artifact manifests (sweep manifest, environment pins). Hashes make every artifact reproducible. |
| `schemas/` | JSON schemas for manifest and corpus metadata records. |
| `workloads/` | Bulk DEM/circuit artifacts (circuits, stress DEMs, per-compiler DEM dumps). Stim-generated DEMs are regenerable from manifest parameters. |
| `campaigns/` | Run-once campaign and ingest scripts, one per audit campaign. |
| `results/` | Campaign outputs: run logs, check reports, adjudication records. |
| `scripts/` | Benchmark utility scripts. |

## Running a benchmark

1. Create an environment and install the release under test:

       python -m venv .venv && source .venv/bin/activate
       pip install "emlint==<version>" -r requirements.txt

2. Run a campaign (all paths are relative to this repository root):

       python campaigns/run_smoke.py            # quick sanity tier
       python campaigns/run_campaign.py --id <corpus_id> --shots 20000 --seed 20260819

   Campaign scripts whose inputs are internal library-study artifacts
   (`run_qecirc_noisy_campaign.py`, `run_tqec_campaign.py`) additionally need
   those DEMs under `external/`; see campaigns/README.md.

3. Record everything needed for cross-version comparability: emlint/stim/
   python versions, platform, seed, shot budget, and the emlint release tag —
   append to `results/RUN_LOG.jsonl` and write the narrative summary to
   `results/` (see `results/README.md` for the record format).

4. Do not edit historical results; add a new dated section instead.

## Provenance

All artifacts are described by manifests pinned by sha256. Stim-generated DEMs regenerate deterministically from the generator parameters recorded in the manifest; external-library DEMs are committed with their toolchain versions. Historical campaign records reference the emlint pinned validation corpus by hash.

## Relationship to emlint

The curated regression fixtures consumed by emlint's own test suite live in the emlint repository. This repository holds the broader audit corpus, campaigns, and benchmark results.

## License

Apache 2.0
