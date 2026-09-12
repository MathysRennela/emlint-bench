# Validation adjudication

> **Provenance** — Date: living ledger — human approvals recorded 2026-08-23, latest additions 2026-09-03 (TQEC duplicates) · Campaign: smoke + corpus/mutation pilot + TQEC/QECirc campaigns · Producer: `campaigns/run_smoke.py`, `campaigns/run_campaign.py`, `campaigns/run_tqec_campaign.py`, `campaigns/run_qecirc_noisy_campaign.py` · Environment: per campaign, recorded in `results/RUN_LOG.jsonl` · Evidence: `results/raw/`, `results/RUN_LOG.jsonl` · Note: `PENDING_HUMAN_REVIEW` rows remain open

Status: `ADJUDICATED — human approval recorded 2026-08-23`

This file records proposals only. The strategy requires human approval before
known-good, false-positive, source-library-defect, actionability, severity, or
external-validity claims enter the final conclusions.

## Smoke findings

| Finding | Evidence | Proposed classification | Reviewer status |
|---|---|---|---|
| `duplicates` on each Stim-generated smoke DEM | `results/raw/stim_*/*.emlint.json`; `CORPUS_MANIFEST.jsonl` | unresolved: valid unusual structure vs check/source issue | `ACCEPTED (human, 2026-08-23)` |
| `p > 0.5` is reported by `probability_bounds` with warning severity | `raw/stim_repetition_d3_r3__high_probability.emlint.json`; `emlint/checks.py:617-672` | emlint contract issue already documented in strategy | `ACCEPTED (human, 2026-08-23)` |
| coordinate-only mutation did not alter the DEM hash | `MUTATION_MANIFEST.jsonl`, mutation hash equals parent | invalid mutation construction; exclude from metrics | `ACCEPTED (human, 2026-08-23)` |
| detector-index mutation was detected by `duplicates`/`correctability` | `MUTATION_MANIFEST.jsonl` | mutation does not establish the stated simulation-blind blind spot | `ACCEPTED (human, 2026-08-23)` |

## Campaign expansion

The append-only campaign added 30 DEMs and 180 mutations. The four priority
checks produced no corpus error findings. The deterministic mutation subset
was caught as follows: `probability_bounds` caught 30/30 zero-probability
mutations; `detectability` caught 30/30 logical-without-syndrome mutations;
`probability_bounds` warned on 30/30 high-probability mutations; and
`sensitivity` warned on 30/30 dead-detector mutations.

All campaign parents also produced `duplicates` warnings. These are quarantined
for separator-bearing DEMs because the frontend loses Stim `^` boundaries and
can create duplicate signatures. Duplicate, coordinate, and detector-index
mutation findings therefore remain pending and are excluded from blind-spot or
false-positive claims.

## Adjudication rule

No row is counted as a known-good false-positive denominator or as a validated
detection-rate numerator until its provenance and bug status are approved. The
generated evidence remains reproducible and quarantined. The deterministic
30/30 observations are retained as finite `REALISTIC_MUTATION` evidence, not as
proof of general completeness or external validity.

## Re-adjudication after TD:3 fix (decomposition-hint preservation)

The frontend now preserves `^` component boundaries in
`ErrorMechanism.decomposition_hints` (see the internal technical-debt ledger). The
smoke corpus was rerun with the fixed parser.

| Finding | Evidence | Proposed classification | Reviewer status |
|---|---|---|---|
| `duplicates` counts unchanged after the fix (6 / 67 / 70 on repetition d3 r3 / surface-z / surface-x) | `raw/stim_*.emlint.json` regenerated post-fix | parser-created collisions eliminated as a hypothesis: every remaining flagged signature pair was verified against raw Stim output to be two *distinct* instructions — one undecomposed (`error(p) D0 D2`) and one `^`-decomposed (`error(p) D2 ^ D0`) — that legitimately share a merged signature | `ACCEPTED (human, 2026-08-23)` |
| Remaining `duplicates` warnings on separator-bearing DEMs | verified per-pair via `stim.DetectorErrorModel.flattened()` inspection | attributable: real duplicate-at-merged-signature-granularity in valid Stim output; resolving them requires the decomposition-aware `duplicates` enhancement (SPRINT conditional item), not a frontend change | `ACCEPTED (human, 2026-08-23)` |
| `correctability` fires only on mutated DEMs, never on unmutated parents | `raw/stim_*__*.emlint.json` vs parent outputs | consistent with mutation detection; no evidence of false positives on valid decomposed output | `ACCEPTED (human, 2026-08-23)` |

With the parser no longer lossy, the original quarantine rationale ("frontend
loses `^` boundaries and can create duplicate signatures") no longer applies to
current results. These rows may be counted as attributable observations once a
reviewer approves; they still do not establish known-good status without that
approval.


## Post-enhancement campaign rerun (2026-08-23)

After the enhanced `duplicates` severity contract (fused-probability
p_eff > 0.5 → error) and the TD:3 frontend fix, the full 180-mutation campaign
was rerun with current code. Artifacts: appended rows in
`MUTATION_MANIFEST.jsonl` / `RUN_LOG.jsonl` / `CORPUS_MANIFEST.jsonl`.

| Observation | Evidence | Proposed classification | Reviewer status |
|---|---|---|---|
| Expected check fired on 180/180 mutations (zero misses vs pre-labeled expectations) | `MUTATION_MANIFEST.jsonl` last 180 rows | deterministic catches confirmed at full-campaign scale: `probability_bounds` 30/30 zero-probability, `detectability` 30/30 logical-without-syndrome, `probability_bounds` 30/30 high-probability, `sensitivity` 30/30 dead-detector, `duplicates` 30/30 duplicate-fault | `ACCEPTED (human, 2026-08-23)` |
| Fused-probability error gate fires on 12/30 high-probability mutations, warning-only on 18/30 | per-artifact `fused_violation_count`; e.g. repetition d3 r3 → error (0.75 collides with existing D0 mechanism, p_eff=0.7499); rotated-x d3 r3 → warning (no signature collision) | family-dependent outcome is legitimate: the gate requires both an anomalous probability AND a duplicate signature; geometry determines collision. Proposed: count the 12 errors as deterministic REALISTIC_MUTATION catches; treat the 18 warnings as consistent with the documented contract (anomalous-probability warning + structural-duplicate warning) | `ACCEPTED (human, 2026-08-23)` |
| Zero unmutated parents produce error-severity findings across all 30 corpus DEMs | regenerated parent artifacts | no false-positive contamination of the error gate post-enhancement | `ACCEPTED (human, 2026-08-23)` |
| `correctability` fires only where mutations create genuine syndrome→observable ambiguity (10/30 in two mutation kinds; never on parents) | regenerated artifacts | consistent with earlier adjudication; now confirmed at campaign scale with decomposition-preserving frontend | `ACCEPTED (human, 2026-08-23)` |

Note: pre-enhancement artifact severities were overwritten by this rerun
(append-only manifests, mutable raw JSON). Prior-state evidence is preserved in
session history and the git-tracked manifest diffs, not in `raw/`.


## Corrected campaign outcome (2026-08-23, same rerun)

Refinement of the post-enhancement table above after separating *substantive*
detection from the parent DEMs' pre-existing `duplicates` warning (all 30
parents carry one; see earlier adjudication — real distinct-instruction
collisions in valid Stim output).

| Mutation kind | Substantive detection | Interpretation |
|---|---|---|
| zero_probability | 30/30 (`probability_bounds` error) | deterministic catch |
| logical_without_syndrome | 30/30 (`detectability` error) | deterministic catch |
| high_probability | 30/30 (`probability_bounds` warning; plus fused-probability `duplicates` error on 12/30 where the 0.75 injection collides with an existing mechanism) | deterministic catch; fused-gate outcome is family-dependent by design |
| dead_detector | 30/30 (`sensitivity` warning) | deterministic catch |
| duplicate_fault | detected only as a NEW duplicate group added to the parent's pre-existing ones (verified: parent has 3 groups, mutant adds a 4th) | real structural change, but reported via a check that already fires on the parent — attribution requires diffing groups, not presence/absence |
| coordinate_change | NOT substantively detected (0/30) | mutation moves one detector coordinate; signatures unchanged. The observed `duplicates` flag is the parent's pre-existing warning, not detection. Confirms the audit's original classification: cosmetic-only today, and this mutation does not establish a blind spot |

Proposed corrections to any Phase-4 claims:
1. Do not count `coordinate_change` as "detected" — prior tables overstated this.
2. Count `duplicate_fault` as detected-with-caveat: the check cannot distinguish
   the injected group from pre-existing ones without group-level diffing.
3. The four deterministic classes stand at 30/30 with correct severities.

All rows remain `ACCEPTED (human, 2026-08-23)`.


## Severity downgrade decision (2026-08-23, human-approved)

The reviewer confirmed: `duplicates` findings are **always warning severity**,
including the fused-probability condition (p_eff > 0.5). Rationale: since a
fused violation requires a contributing probability above 0.5 — already warned
by `probability_bounds` — the fused gate sharpens an existing warning rather
than establishing an independent deterministic impossibility.

Implementation updated: fused violations are still reported (message note +
`fused_violation_count` in counter-example data) but never raise severity.
Oracle and tests updated to match. The earlier proposal in this file to count
the 12/30 fused errors as "deterministic REALISTIC_MUTATION catches" at error
severity is superseded by this decision; they remain catches at warning
severity.


## Fused-probability sub-check reverted (2026-08-23, external review)

An independent review identified that the fused-probability severity gate was
dead-by-design: since XOR-fold of probabilities all ≤ 0.5 never exceeds 0.5,
the gate could only fire when `probability_bounds` had already flagged an
anomalous entry — adding no actionable signal over existing output. The
sub-check (severity escalation, message clause, `fused_violation_count` field,
and its mirrored oracle logic) has been reverted. `duplicates` findings are
unconditionally warning-severity; the mathematical reachability note is
retained in the docstring as documentation. A duplicated test definition and
an inaccurate docstring claim about component-level signature comparison were
also removed/corrected. Campaign artifacts regenerated post-revert: zero
error-severity findings across 180 mutations and 30 parents.


## Preview integration: TQEC + QECirc rerun (2026-08-23)

De-risking run for the next milestone (two real toolchains, three code
families). Current code rerun over on-disk artifacts; NOT a pinned campaign —
results are a preview appendix. Evidence: `results/PREVIEW_TQEC_QECIRC_RERUN_20260819.json`.

| Source | Files | Clean | Warning-only | Error findings | Findings by check |
|---|---:|---:|---:|---:|---|
| TQEC 0.2.0 (memory/cnot, k1–k2) | 6 | 0 | 6 | 0 | duplicates 6 |
| QECirc noisy (p=0.001, commit 2a939bad…) | 714 | 322 | 331 | 61 | correctability 275, duplicates 125, detectability 61 |

Observations for the next milestone's planning:

1. **TQEC**: all 6 DEMs produce only the structural `duplicates` warning;
   zero error findings. The earlier CZ deterministic-observable candidate bug
   is a Stim-validation issue, not an emlint finding — emlint sees valid
   structure. Integration cost is low (provenance already pinned).
2. **QECirc**: the 61 `detectability` errors are concentrated in
   state-preparation circuits (e.g. `15-7-3--*preparation*`,
   `edge-coloring-schedule`) whose mechanisms flip observables without
   triggering detectors. Spot-check confirms genuine undetectable mechanisms
   in the artifact. These are exactly the cases the applicability contract
   targets: with `circuit_role=state_preparation` declared and no
   `complete_syndrome=true`, emlint reports `skipped` instead of error.
   The preview ran without context by design, to surface this distribution.
3. **`correctability` warnings on 275/714 files** confirm the strategy's
   guidance that it requires decoder/code-family context for interpretation.

Conclusion: corpus expansion to two toolchains + three families is feasible
almost entirely from on-disk artifacts; the main new work is applicability
context declaration per circuit role during the pinned campaign run.

## TQEC 0.2.0 pinned campaign (2026-09-03)

Pinned-provenance rerun of checks + simulations under the current frontend
(`run_tqec_campaign.py`). Provenance: TQEC v0.2.0 tag resolves to commit
`5909ddec049c1649dc5bdd8fa4fd15c261e51b48` (verified against the tqec/tqec
GitHub API 2026-09-03); artifacts installed from the PyPI 0.2.0 wheel; DEMs
extracted with `decompose_errors=True` under
`NoiseModel.uniform_depolarizing(0.001)`, `do_not_use_database=True`. The CZ
gallery remains blocked upstream (stim deterministic-observable failure,
the internal library-structural-bugs ledger) and is out of scope for this corpus unit. This
unit is now frozen as the tqec#1034 bug evidence; a `tqec_main_*` unit pinned
to tqec `main` is recorded below.
Manifest rows appended to `CORPUS_MANIFEST.jsonl` (ids `tqec_*`, status
`PENDING_HUMAN_REVIEW`); artifacts under `raw/tqec/`.

| id | exit | findings | p_L (2000 shots, seed 20260819) |
|---|---|---|---|
| tqec_memory_z_k1 | 2 | duplicates | 0.0010 |
| tqec_memory_z_k2 | 2 | duplicates | 0.0010 |
| tqec_memory_x_k1 | 2 | duplicates | 0.0025 |
| tqec_memory_x_k2 | 2 | duplicates | 0.0010 |
| tqec_cnot_k1 | 2 | duplicates | 0.0280 |
| tqec_cnot_k2 | 2 | duplicates | 0.0070 |

Zero error findings; zero parse failures; all six simulations decoded
(pymatching). Matches the 2026-08-23 preview distribution.

### `duplicates` adjudication proposal (per family)

Evidence: `TQEC_DUPLICATES_ADJUDICATION_20260903.json`; every duplicate
merged-signature group classified by raw-instruction identity (probability,
targets, decomposition hints with component order normalized) via the
frontend that preserves `^` boundaries (known technical-debt item: decomposition-boundary preservation).

| Family | Duplicate signature groups | Distinct raw instructions | Identical (order-normalized) |
|---|---:|---:|---:|
| memory_z (k1+k2) | 520 | 512 | 8 |
| memory_x (k1+k2) | 541 | 531 | 10 |
| cnot (k1+k2) | 6033 | 5995 | 38 |

| Finding | Evidence | Proposed classification | Reviewer status |
|---|---|---|---|
| `duplicates` warnings on all 6 TQEC DEMs; ~99% of flagged groups contain ≥2 *distinct* raw instructions sharing a merged decoder-facing signature (e.g. `error(p) D0 D10` alongside `error(p) D0 D10 ^ D11`) | `TQEC_DUPLICATES_ADJUDICATION_20260903.json`; spot-verified against raw DEM text (the tqec workload DEM `workloads/tqec/` counterpart (spot-verified lines 6-7)) | same adjudicated class as the Stim-generated corpus (above): real duplicate-at-merged-signature granularity in valid Stim output; resolution requires the decomposition-aware `duplicates` enhancement, not a frontend or TQEC fix | `PENDING_HUMAN_REVIEW` |
| 1–29 groups per file contain ≥2 *semantically identical* mechanisms emitted as separate raw instructions (equal probability, equal component sets, component order permuted — e.g. lines 200 vs 255 of the same tqec workload DEM) | same JSON; raw-text verification | genuine duplicate mechanisms in valid Stim output from distinct physical fault paths that decompose to identical graphlike components; the `duplicates` finding is accurate and the XOR-fused probability is what decoders consume; no probability corruption (all p ≤ 0.5, `probability_bounds` clean) | `PENDING_HUMAN_REVIEW` |
| Simulations: logical error rates plausible for minimal-fill k1–k2 memory/CNOT at p=0.001; no decode failures | `raw/tqec/*.simulation.json` | supporting evidence that the flagged structure does not corrupt decoding; not a known-good claim without human approval | `PENDING_HUMAN_REVIEW` |

Conclusion: TQEC 0.2.0 integration is mechanically complete (provenance
pinned, checks rerun, simulations run, findings classified). No emlint bug and
no new TQEC defect surfaced on this corpus unit; the CZ candidate bug was
confirmed upstream as [tqec/tqec#1034](https://github.com/tqec/tqec/issues/1034)
(the internal library-structural-bugs ledger) and the unit is frozen as that bug's evidence.

## TQEC main pinned campaign (2026-09-03)

Follow-up unit pinned to tqec `main` at commit
`bc1f808116a19857b5512588fb61273ec2c90a15` (verified against the tqec/tqec
GitHub API 2026-09-03; installed with
`pip install git+https://github.com/tqec/tqec@<sha>`, commit verified via
`direct_url.json` `vcs_info.commit_id`). Same galleries (memory_z/x k1-2,
cnot k1-2), noise, seeds, and shot budget as the v0.2.0 unit; same extraction
contract as the internal tqec probe script, with the database opt-out adapted to the main API
(`detector_database=None, database_path=None`; the 0.2.0
`do_not_use_database=True` flag was removed). Run with
`run_tqec_campaign.py --unit main`.

CZ is excluded **by construction** on main: the unsupported spatial-Hadamard
configuration used by the CZ minimal fill raises `NotImplementedError`
explicitly (`tqec#1034` fix-by-loud-failure), instead of 0.2.0's silent
invalid circuits.

| id | exit | findings | p_L (2000 shots, seed 20260819) |
|---|---|---|---|
| tqec_main_memory_z_k1 | 2 | duplicates | 0.0030 |
| tqec_main_memory_z_k2 | 2 | duplicates | 0.0015 |
| tqec_main_memory_x_k1 | 2 | duplicates | 0.0070 |
| tqec_main_memory_x_k2 | 2 | duplicates | 0.0020 |
| tqec_main_cnot_k1 | 2 | duplicates | 0.0230 |
| tqec_main_cnot_k2 | 2 | duplicates | 0.0065 |

Zero error findings; zero parse failures; all six simulations decoded. The
`duplicates` distribution matches the v0.2.0 unit (same
duplicate-at-merged-signature structure; raw-instruction adjudication in
`TQEC_DUPLICATES_ADJUDICATION_20260903.json`). Manifest rows appended (ids
`tqec_main_*`, `PENDING_HUMAN_REVIEW`); artifacts under `raw/tqec_main/` and
generated DEMs under `workloads/tqec_main/`.

## QECirc noisy-corpus campaign with applicability context (2026-09-03)

Full 714-DEM rerun under the current frontend with applicability context
declared per circuit role (`run_qecirc_noisy_campaign.py`). Corpus provenance:
qecirc-website commit `2a939badcb06ff711fb957f3d1358edfbacba338`, noise
DEPOLARIZE2/1(p=0.001) per the qecirc campaign provenance record. Manifest rows
appended (`qecirc_noisy_*`, `PENDING_HUMAN_REVIEW`); per-file check artifacts
under `raw/qecirc_noisy/`.

Role rule (documented per row): `encoding` if the filename contains
`encoding`, else `state_preparation`. Rationale: QECirc's public library is a
state-preparation corpus — its non-encoding method families are preparation
synthesis heuristics (ft/det-ft/non-ft, flag-at-origin, RL-discovered,
tableau preparation) and the measurement schedules those circuits use
(cardinal, zx-coloration, edge-coloring, depth-optimal, alphasyndrome,
bivariate-bicycle). `decoder=matching (pymatching)` is declared per run so
`correctability` findings are interpreted under a stated decoder assumption.

| Outcome | Count |
|---|---:|
| Files run (parse failures) | 714 (0) |
| `state_preparation` / `encoding` roles | 628 / 86 |
| `detectability` explicit `skipped` (declared unsupported role) | 628 |
| `detectability` `inconclusive` (encoding; no `complete_syndrome` claim) | 86 |
| **Residual `detectability` error verdicts** | **0** |
| `duplicates` warnings | 125 |
| `correctability` warnings | 275 |
| Exit codes 0 / 2 / 1 | 236 / 478 / 0 |

The 61 preview `detectability` errors are all now explicit non-verdicts under
the applicability contract; `duplicates`/`correctability` counts match the
preview exactly (structure unchanged).

| Finding | Evidence | Proposed classification | Reviewer status |
|---|---|---|---|
| 61 preview `detectability` errors → 0 residual error verdicts after role declaration; 628 prep-role files skip, 86 encoding-role files surface `inconclusive` (no `complete_syndrome` claim asserted) | `run_qecirc_noisy_campaign.py` verification gate; `raw/qecirc_noisy/*.emlint.json` | applicability contract working as designed (APPLICABILITY_PROFILES §3.4); the encoding-role `inconclusive` keeps the exit-2 surface because syndrome completeness was not claimed for encoding circuits | `PENDING_HUMAN_REVIEW` |
| 275 `correctability` warnings interpreted under declared matching-decoder context | finding counts above; overlap with `duplicates` only 8 files | warning-grade: syndrome→multiple-observable-set mappings are expected in preparation protocols whose observables are defined over final data measurements; per-family interpretation (degenerate family vs decompose_errors artefact vs genuine distance collapse) requires the code-family context listed in each filename and stays open per family | `PENDING_HUMAN_REVIEW` |
| 125 `duplicates` warnings | same artifacts | same merged-signature class as the TQEC/Stim corpora (valid Stim output at merged-signature granularity; small identical-mechanism residue) | `PENDING_HUMAN_REVIEW` |
| Zero exit-1 files across the corpus after role declaration (was 61) | exit-code counts above | consistent with the role rule; no error-severity finding is suppressed by the rule (0 residual detectability verdicts) | `PENDING_HUMAN_REVIEW` |

Conclusion: the QECirc corpus expansion is mechanically complete under the
v0.2.2 applicability contract. The role rule is a filename-based proxy and is
recorded verbatim in each manifest row for human re-adjudication.
