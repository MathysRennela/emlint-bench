# Results

Historical campaign outputs: run logs, per-artifact check reports,
simulation records, adjudications, and final reports.

## Index

| File | Date | Campaign / producer | Status |
|---|---|---|---|
| `RUN_LOG.jsonl` | 2026-08-19 → 2026-09-03 (per-row timestamps) | Append-only log; one record per command across all campaigns | frozen record; append-only |
| `FINAL_REPORT_PILOT_20260819.md` | 2026-08-19 | Local pilot corpus + mutation campaign (`run_campaign.py`, `run_smoke.py`); emlint 0.2.0 | superseded by `FINAL_REPORT_2026-08-19.md` |
| `FINAL_REPORT_2026-08-19.md` | 2026-08-19 | Milestone rollup: pilot, QECirc, TQEC, clifft studies | shipped with emlint v0.2.x evidence |
| `RESULTS.md` | 2026-08-19 → 2026-09-03 | Validation workflow phases 0–7 | `EXECUTED`; external-validity claims bounded |
| `ADJUDICATION.md` | 2026-08-23 → 2026-09-03 | Living adjudication ledger for all campaigns | adjudicated; some rows `PENDING_HUMAN_REVIEW` |
| `TQEC_DUPLICATES_ADJUDICATION_20260903.json` | 2026-09-03 | TQEC 0.2.0 pinned campaign (`run_tqec_campaign.py`) | evidence for the `duplicates` class |
| `GROSS_QUITS_MATCHED_20260901.json` | 2026-09-01 | Gross/BB QUITS-vs-frontier matched comparison (`run_gross_quits_matched_20260901.py`) | Q102 `duplicates` pending review |
| `PREVIEW_TQEC_QECIRC_RERUN_20260819.json` | ≤ 2026-08-19 (dated by first citation in `FINAL_REPORT_2026-08-19.md`) | TQEC/QECirc rerun preview (`run_preview_integration.py`, not migrated — reads private inputs) | preview appendix |
| `ECOSYSTEM_SURVEY_20260901.md` | 2026-09-01 | Crawler-axis survey of research `.stim`/`.dem` sources (manual) | frontier ingested; rest deferred |
| `raw/pecos_stim_differential_{stim,pecos,pecos_d5}.dem` | 2026-09-12 | stim-vs-PECOS differential experiments (`campaigns/pecos_stim_differential.py`, `campaigns/pecos_stim_same_circuit_differential.py`) | phase-1 discrepancy adjudicated; phase-2 same-circuit sweep |
| `raw/` | per campaign | Per-artifact check (`*.emlint.json`) and simulation (`*.simulation.json`) outputs; see `RUN_LOG.jsonl` for the row-to-file map | frozen record |

## Conventions for new results files

1. **Name files with a `_YYYYMMDD` suffix** matching the date of the run that
   produced them. Never reuse an existing dated filename; never overwrite a
   historical file.
2. **Every narrative file starts with a provenance header** (blockquote,
   `**Provenance**`) recording: Date, Campaign, Producer (script + invocation),
   Environment (emlint/stim/decoder/python versions), Evidence (artifact paths
   inside this repository), and relationship to other reports (supersedes /
   superseded by).
3. `RUN_LOG.jsonl` is append-only: one row per command, timestamped, with
   input hashes. Machine artifacts (`*.emlint.json`, `*.simulation.json`) are
   never edited after the run.
4. Findings from other projects are adjudicated in `ADJUDICATION.md`; the
   authoritative findings ledger lives in the emlint development repository
   (private).

References to `CORPUS_MANIFEST.jsonl` / `MUTATION_MANIFEST.jsonl` point to the
pinned validation corpus in the emlint development repository (private,
hash-pinned); all evidence here remains verifiable from the recorded hashes.
