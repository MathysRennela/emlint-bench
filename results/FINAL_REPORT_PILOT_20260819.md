# Validation pilot final report

> **Provenance** — Date: 2026-08-19 (campaign date; seed 20260819) · Campaign: local pilot corpus + mutation campaign (33 stim-generated DEMs, 192 mutations) · Producer: `campaigns/run_campaign.py`, `campaigns/run_smoke.py` · Environment: emlint 0.2.0, stim 1.16.0, pymatching 2.4.0, python 3.12.13 · Evidence: `results/raw/campaign_20260819_*.json`, `results/RUN_LOG.jsonl` (2026-08-19 rows) · Superseded by `FINAL_REPORT_2026-08-19.md`

Status: `BLOCKED`; local corpus and mutation campaign completed, external and
human-adjudication gates remain open.

## Question and scope

The campaign asks which current emlint checks detect actionable defects on
pinned real DEMs and realistic mutations. The completed local campaign covers
30 new Stim-generated DEMs plus the initial 3 smoke DEMs, 180 new mutations plus
12 smoke mutations, emlint 0.2.0, Stim 1.16.0, PyMatching 2.4.0, Python 3.12.13,
2,000-shot simulations, and seed 20260819. The repository was dirty at revision
`86e4e492ab144d37de9421f47bce72980c9cdbee`.

The campaign reaches the local corpus/mutation scale target, but not the full
milestone: a second external toolchain, independently adjudicated known-good
status, external CI integration, human diagnostic review, and a second source
provenance family remain unavailable.

## Execution status

| Phase | Status | Evidence |
|---|---|---|
| 0. Baseline | `PASS` | `RUN_LOG.jsonl`; 70 targeted tests passed |
| 1. Smoke | `PASS` | manifests and `raw/` |
| 2. Corpus | `BLOCKED` | 33 rows; provenance and known-good approval incomplete |
| 3. Adjudication | `BLOCKED` | `ADJUDICATION.md`; separator-sensitive warnings quarantined |
| 4. Mutations | `BLOCKED` | 192 rows; trusted deterministic subset complete, remaining attribution pending |
| 5. Comparison | `BLOCKED` | corpus simulations preserved; mutation workflow comparison incomplete |
| 6. Integration | `BLOCKED` | no external repository authorization |
| 7. Synthesis | `BLOCKED` | this report |

## Corpus and provenance

The campaign contains 33 non-empty DEMs, with 30 new entries across repetition,
rotated-surface, and unrotated-surface Stim generators. Mechanism counts range
from 35 to 6,593. Every entry has a DEM/circuit hash, parameters, tool versions,
check output, simulation output, and replay command.

These entries are not yet accepted as known-good. Stim package provenance is
pinned, but source commit/archive identity, citable p_L evidence, and human
approval are absent. They remain quarantined from false-positive denominators.

## Mutation design

Labels were fixed before checks ran. The new campaign includes 30 instances of
each of six operations: zero probability, logical error without syndrome, high
probability, duplicate fault, dead detector, and coordinate change.

The trusted deterministic observations are:

- zero probability: `probability_bounds` error, 30/30;
- logical error without syndrome: `detectability` error, 30/30;
- high probability: warning-level `probability_bounds`, 30/30;
- dead detector: warning-level `sensitivity`, 30/30.

Duplicate, coordinate, and detector-index conclusions are not promoted to
blind-spot or actionability claims because separator-induced duplicate warnings
contaminate their observed result sets.

## Detection results

For the 30 new corpus DEMs, zero failures were observed from the four priority
checks: `detectability`, `observable_coverage`, `probability_bounds`, and
`sensitivity`. This is finite evidence for the generated cases only. It is not
a validated false-positive rate because known-good status is pending.

The 30/30 deterministic mutation counts are empirical evidence for these exact
mutations. They do not establish prevalence, real-world external validity, or
that all source-pipeline defects are detectable.

## Diagnostic and workflow results

DEM-only check and simulation timing/output artifacts are preserved under
`raw/`. The campaign did not conduct a human time-to-first-hypothesis study,
so actionability and diagnosis-time claims remain pending. Circuit-backed
source-location metrics are unavailable from the current DEM-only output and
remain gated on `emlint explain`.

## Blind spots and negative results

See the internal blind-spot ledger. No empirical index-shift or coordinate-only
mutation is admitted as a confirmed blind spot. The campaign instead confirms
that these constructors are currently confounded by parser-created warning
findings and need repair after technical-debt item 3.

## Adjudication and pending decisions

See `ADJUDICATION.md`. Human decisions remain required for known-good status,
source-library versus valid-unusual-structure classification, diagnostic
actionability, and external-validity claims. The `duplicates` and
`correctability` outputs on separator-bearing DEMs are quarantined as
`PENDING_HUMAN_REVIEW` and are not used in the error gate.

## Reproduction

```text
PYTHONPATH=. PYTHONHASHSEED=0 .venv312/bin/python campaigns/run_campaign.py
.venv312/bin/python -m pytest -q tests/test_checks.py tests/test_synthetic_bug_corpus.py tests/test_stim_integration.py
```

The runner appends corpus, mutation, and run records. Replaying it produces a
new campaign and should use a new campaign identifier before publication.

## Claims discipline

- `REAL_CORPUS`: 33 pinned Stim-generated artifacts, pending known-good review.
- `REALISTIC_MUTATION`: trusted deterministic mutation observations, finite and
  campaign-specific.
- `TOY_MODEL`: existing unit-test corpus only.
- `THEORETICAL_LIMITATION`: DEM-only blind spots listed in the blind-spot file.

## Recommendation

The local validation campaign is sufficient to continue toward adjudication,
not to claim a completed external-validity pilot. Next obtain independent
provenance/p_L references and human review, repair the separator-target parser,
then rerun the warning-sensitive checks and mutation comparisons. Separately,
obtain a second external toolchain and one non-blocking CI integration before
marking the milestone complete.
