# emlint Validation Campaign — 2026-08-19 Final Report

> **Provenance** — Date: 2026-08-19 (milestone report; library-study artifacts it references were re-run 2026-09-03) · Campaign: milestone rollup — pilot, QECirc, TQEC, clifft studies · Producer: `campaigns/run_smoke.py`, `campaigns/run_campaign.py`, internal library-study runners · Environment: recorded per run in `results/RUN_LOG.jsonl` · Evidence: `results/raw/`, `results/RUN_LOG.jsonl`, `results/ADJUDICATION.md`

Status: `BLOCKED` for the full external-validity milestone; `PASS` for the
bounded local campaign and the complete available QECirc annotated-STIM study.

## 1. Question and scope

This campaign investigated:

1. which current emlint checks produce useful evidence on pinned real or
   externally sourced DEMs;
2. whether structural candidates can be found in QECirc, TQEC, and Clifft;
3. which planned checks should be prioritized;
4. which conclusions are limited by DEM-only context, parser technical debt, or
   missing human/source adjudication.

Workflow comparison was intentionally skipped. No upstream issue was filed.
TD:3, Stim decomposed-error separator handling, was quarantined rather than
fixed in this campaign.

Evidence classes used:

- `REAL_CORPUS`: pinned external library artifacts or pinned local generated
  artifacts;
- `REALISTIC_MUTATION`: seeded mutations of generated DEMs;
- `TOY_MODEL`: small hand-built/unit-test constructions;
- `THEORETICAL_LIMITATION`: limitation derived from the representation or
  check contract.

## 2. Execution status

| Workstream | Status | Evidence |
|---|---|---|
| Existing emlint baseline and targeted tests | `PASS` | `results/FINAL_REPORT_PILOT_20260819.md`; 70 targeted tests |
| Local Stim corpus and mutation pilot | `PASS` for bounded evidence; milestone `BLOCKED` | `results/RESULTS.md`, `results/FINAL_REPORT_PILOT_20260819.md` |
| QECirc annotated-format verification | `PASS` for available annotated corpus | the internal QECirc extraction note |
| QECirc full available annotated corpus | `PASS` | the internal qecirc campaign structural and noisy outputs |
| QECirc error adjudication | `PASS`; no confirmed source bug | internal QECirc error-classification and candidate-adjudication notes |
| TQEC study | `BLOCKED` for upstream classification; candidate reproduced | the internal library-structural-bugs ledger and tqec probe record |
| Clifft study | `BLOCKED` for upstream classification; release discrepancy reproduced | the internal library-structural-bugs ledger and clifft probe record |
| Workflow comparison | `BLOCKED` by revised scope | this report; strategy revision |
| Human/source maintainer adjudication | `BLOCKED` | pending TQEC and Clifft confirmations |
| Full external-validity milestone | `BLOCKED` | missing independent known-good approval, second external toolchain gate, CI integration, and human diagnostic study |

## 3. Corpus and provenance

### Local validation pilot

The local pilot contains:

- 33 non-empty DEMs: 30 new Stim-generated DEMs plus 3 smoke DEMs;
- 192 mutation rows;
- emlint `0.2.0`;
- Stim `1.16.0`;
- Python `3.12.13`;
- PyMatching `2.4.0` where used;
- 2,000-shot simulations with seed `20260819`.

Known-good status and independent source approval remain pending. These rows
are not used to claim a validated false-positive rate.

### QECirc corpus

The QECirc source was pinned to:

```text
https://github.com/qecirc/qecirc-website
2a939badcb06ff711fb957f3d1358edfbacba338
```

The checkout contains:

- 968 YAML circuit records;
- 670 `stim-annotated` bodies;
- 298 records without an annotated STIM body.

All 670 annotated bodies parsed and produced DEMs. The 298 records without an
annotated body were recorded as unavailable, not counted as passing or failing.
The bare QECirc `stim` body is not interchangeable with `stim-annotated`:
the latter contains the detector and observable annotations required for DEM
extraction.

QECirc artifacts:

- the qecirc campaign provenance record;
- `structural.jsonl`;
- `noisy.jsonl`;
- `structural/dem/`;
- `noisy/dem/`.

### TQEC and Clifft

TQEC was tested at `0.2.0` with Stim `1.16.0`, Python `3.12.13`, and uniform
depolarizing noise `p=0.001`. Memory and CNOT examples produced non-empty DEMs
without priority-check errors. Both filled CZ minimal-simulation variants
failed Stim deterministic-observable validation before DEM extraction.

Clifft was tested at PyPI `0.8.0` with Stim `1.16.0`, Python `3.12.13`, on macOS
arm64. Two repository fixtures failed Clifft parsing because `T_DAG` and `U3`
were rejected; a third fixture compiled and sampled successfully. This remains
a release/source discrepancy candidate, not an emlint or numerical-simulation
finding.

## 4. Mutation design

The local mutation campaign fixed expected outcomes before running checks. It
included 30 instances of each of six operations:

- zero probability;
- logical error without syndrome;
- high probability;
- duplicate fault;
- dead detector;
- coordinate change.

Trusted deterministic observations:

- zero probability: `probability_bounds`, 30/30 errors;
- logical error without syndrome: `detectability`, 30/30 errors;
- high probability: warning-level probability check, 30/30;
- dead detector: `sensitivity`, 30/30 warnings.

Duplicate, coordinate, and detector-index conclusions remain quarantined where
separator-sensitive parsing contaminates interpretation.

The QECirc campaign was not a mutation campaign. It was a pinned external
corpus study with two passes:

1. annotated extraction without noise (`STRUCTURAL_ONLY`);
2. synthetic gate-level depolarizing noise with `p=0.001`.

The corrected noise convention is:

- `DEPOLARIZE2(0.001)` after supported two-qubit gates;
- `DEPOLARIZE1(0.001)` after other gates with qubit targets;
- reset and measurement instructions excluded;
- recursive transformation through `REPEAT` blocks.

An earlier pass incorrectly added noise after reset/measurement instructions.
Its 78-error aggregate is superseded and must not be reused.

## 5. Detection results

### Local mutation evidence

The deterministic mutation ratios above are empirical evidence for those exact
seeded constructions. They do not establish prevalence or real-world coverage.

### QECirc structural-only pass

All 670 annotated bodies extracted successfully. No-noise check results were:

- `observable_coverage` errors: 529;
- `sensitivity` warnings: 607.

These are expected because the circuits contain annotations but no physical
error mechanisms. They are not QECirc bug evidence and are not mechanism-level
false positives.

### QECirc corrected noisy pass

All 670 noisy circuits produced DEMs without Stim extraction failures:

| Result | Circuits |
|---|---:|
| Exit 0 | 322 |
| Warning-only exit 2 | 310 |
| Error exit 1 | 38 |

Check findings:

| Check | Severity | Circuits |
|---|---|---:|
| `detectability` | error | 38 |
| `correctability` | warning | 231 |
| `duplicates` | warning | 125 |

These counts are not a false-positive rate. They require circuit-role and
protocol applicability adjudication.

The 38 detectability results classify as:

- 30 explicitly non-fault-tolerant state-preparation circuits;
- 7 syndrome-extraction circuits declaring `circuit-distance:1`;
- 1 post-selected FT state-preparation circuit whose protocol contract makes the
generic DEM-only detectability invariant too strong.

The final adjudication found no confirmed QECirc structural bug.

### TQEC and Clifft findings

TQEC’s CZ failures occurred before DEM extraction, so emlint could not have
caught them. They remain candidate source-library findings pending pinned source
commit, project tests, and maintainer confirmation.

Clifft’s `T_DAG`/`U3` failures occurred in the released parser before simulation.
They remain a package/source compatibility candidate pending source-versus-wheel
reproduction.

## 6. Diagnostic and workflow results

No human time-to-first-hypothesis study was run. No workflow comparison was run,
per the revised scope. No claim is made about developer actionability or time
saved.

DEM-only diagnostics can identify mechanisms, detectors, observables, and
syndromes, but not the source circuit operation that generated them. This was
especially important for QECirc ID 470: the DEM alone suggested a violation,
but source protocol semantics showed that the generic check was inapplicable.

Circuit-backed diagnosis remains gated on `emlint explain` and a circuit-aware
validation contract.

## 7. Blind spots and negative results

Confirmed or reinforced limitations:

1. **Circuit-role blindness.** A generic DEM check cannot infer whether a DEM is
   a memory circuit, an encoder, a state-preparation protocol, or a post-selected
   verification circuit.
2. **Protocol-contract blindness.** `detectability` is not universally valid for
   post-selected state preparation. Accepted residual errors may be correctable
   after ideal syndrome correction.
3. **Noiseless vacuity.** Detector/observable annotations without mechanisms do
   not provide evidence for mechanism-level checks.
4. **Bare-circuit ambiguity.** QECirc bare `stim` bodies can produce empty DEMs;
   the annotated representation must be selected explicitly.
5. **Separator-sensitive parsing.** TD:3 contaminates `duplicates` and
   `correctability` interpretation on decomposed Stim DEMs.
6. **Pre-DEM failures.** TQEC deterministic-observable failures and Clifft parser
   failures are outside the DEM-only pipeline.
7. **Simulation-blind structural mutations.** Detector index shifts and some
   annotation/coordinate changes cannot be trusted as simulation evidence and
   require structural or circuit-backed checks.
8. **No source localization.** DEM-only counterexamples do not identify the
   originating circuit operation.

Negative results:

- no confirmed QECirc structural bug;
- no confirmed TQEC upstream bug;
- no confirmed Clifft upstream bug;
- no workflow-value conclusion;
- no validated external false-positive rate;
- no evidence supporting promotion of `duplicates` or `correctability` to errors.

## 8. Adjudication and pending decisions

Completed classifications:

- QECirc empty DEMs: wrong body format selected; use `stim-annotated`;
- QECirc non-fault-tolerant preparation findings: expected under metadata;
- QECirc distance-one syndrome findings: consistent with declared distance;
- QECirc ID 470: protocol/check-contract mismatch, not a source bug;
- QECirc duplicate warnings: quarantined under TD:3;
- TQEC CZ: candidate, pending source/maintainer adjudication;
- Clifft gate support: release/interface discrepancy candidate, pending source
  commit and maintainer adjudication.

Human decisions still required before external conclusions are published:

- whether TQEC’s CZ gallery variants are expected to compile deterministically;
- whether Clifft `0.8.0` is intended to support `T_DAG` and `U3`;
- whether the QECirc 298 records without annotated STIM should be included via
  another representation;
- whether any protocol-specific QECirc findings justify an upstream report.

## 9. Reproduction

### Local validation pilot

```text
PYTHONPATH=. PYTHONHASHSEED=0 .venv312/bin/python campaigns/run_campaign.py
.venv312/bin/python -m pytest -q tests/test_checks.py tests/test_synthetic_bug_corpus.py tests/test_stim_integration.py
```

### QECirc corpus

Clone the pinned checkout to `/tmp/qecirc-website`, then run:

```text
PYTHONPATH=. .venv312/bin/python the qecirc campaign runner (library study) --phase structural
PYTHONPATH=. .venv312/bin/python the qecirc campaign runner (library study) --phase noisy
```

Classification and adjudication:

```text
PYTHONPATH=. .venv312/bin/python the qecirc error classifier (library study)
the qecirc candidate adjudicator (library study)
```

The corrected runner excludes reset and measurement instructions from noise
insertion. The previous all-quantum-instruction run is superseded.

## 10. Claims discipline

### `REAL_CORPUS`

- 670 QECirc annotated bodies at a pinned repository commit extracted into
  DEMs successfully.
- QECirc produced 322 exit-0, 310 warning-only, and 38 error outcomes under the
  explicitly documented synthetic gate-noise transformation.
- TQEC CZ generation failed Stim deterministic-observable validation in the
  tested environment.
- Clifft `0.8.0` rejected `T_DAG` and `U3` in tested repository fixtures.

These are observations, not proofs of general library behavior.

### `REALISTIC_MUTATION`

- The local deterministic mutation catches are evidence for the exact seeded
  mutations and their tested emlint versions.

### `TOY_MODEL`

- Unit tests and hand-built DEMs support check-specific behavior but do not
  establish external prevalence.

### `THEORETICAL_LIMITATION`

- DEM-only checking cannot infer circuit role, post-selection semantics, source
  locations, or pre-DEM compiler/parser failures without additional context.

## 11. Recommendation

Stop this campaign here; do not add more corpus or checks today.

Prioritized next steps:

1. **Repair TD:3 decomposition preservation.** This is the highest-priority
   technical prerequisite because it contaminates separator-sensitive warnings.
2. **Add applicability metadata/contracts.** Corpus manifests and reports should
   record circuit role, protocol, decoder assumptions, noise convention, and the
   applicable check set.
3. **Separate structural and noisy validation in tooling.** Empty/noiseless DEMs
   should be labelled `STRUCTURAL_ONLY`, not treated as mechanism-level passes.
4. **Design a protocol-specific post-selected state-preparation check.** It must
   validate verification acceptance and residual correctability, not reuse the
   generic `detectability` invariant.
5. **Investigate TQEC CZ with a pinned source commit and project tests.** Prepare
   an upstream issue only if maintainers confirm the variants are expected to be
   deterministic.
6. **Reproduce Clifft against the exact source commit and published wheel.**
   File the release/interface issue only after source/wheel identity is settled.
7. **Add a circuit-backed validation path.** Preserve operation provenance so
   DEM counterexamples can be traced to circuit locations.
8. **Resume external validity later.** Add a second independently adjudicated
   toolchain, one authorized non-blocking CI integration, and a human diagnostic
   study before making workflow or prevalence claims.

The central lesson is that validation quality depends first on matching a check
to the source protocol's contract. A larger corpus or more checks cannot repair
an applicability mismatch.
