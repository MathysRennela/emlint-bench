# Campaigns

One script per historical audit campaign; these are run-once records kept for
reproducibility. They require `emlint` (pip install emlint) and the pinned
validation corpus.

Several scripts read or append to `CORPUS_MANIFEST.jsonl` and
`MUTATION_MANIFEST.jsonl`. Those manifests are part of the pinned validation
corpus in the emlint development repository (not public); they are
hash-pinned, so all evidence produced here remains verifiable from the
recorded hashes. When re-running a campaign, provide the manifests at the
paths the script expects.

Note: these scripts were moved from their original workspace; output-path
constants were remapped to this repository layout (workloads/, results/).

The taxonomy corpus-mining script `qecirc_mine.py` is retained here as a historical QECirc campaign script. Its interpretation is recorded in `results/QECIRC_CORPUS_NOTE_20260901.md`.

Scripts whose input DEM trees were produced by internal library-study tooling
(`run_qecirc_noisy_campaign.py`, `run_tqec_campaign.py`) expect those inputs
under `external/`; the inputs are not redistributed here, but the outputs of
the original runs are preserved under `results/raw/`.

The upstream-issue fixture corpus (`build_upstream_issue_corpus.py`) turns the
strong-tier findings of the emlint-dev ecosystem survey
(`notes/ecosystem/UPSTREAM_ISSUE_SURVEY.md`) into labeled fixtures under
`workloads/upstream_issues/`, with `manifests/upstream_issue_manifest.jsonl`.
Labels are `caught` (expected check fires), `gap` (predicate class applies but
the current build does not flag it), and `unlintable` (frontend rejects the
text; exit-3 contract). The build fails loudly if any observed behavior drifts
from its label, so gap fixtures flip to `caught` when coverage lands.

The issue-146 circuit-check audit (`run_circuit_check_audit.py`) is a separate,
on-demand campaign. It reads `manifests/circuit_check_audit_issue146.jsonl`,
verifies fixture hashes, and records every circuit check result, including
`skipped` and `inconclusive` as not exercised. It runs no Monte Carlo shots and
is not part of the default `pytest` suite or CI. Run from the benchmark root:

```bash
uv run --no-project --with stim==1.16.0 python campaigns/run_circuit_check_audit.py \
  --emlint-source /path/to/emlint-dev
```

The flag-gadget family is covered by two fixtures: the bare source-derived
gadget (its five annotation/record checks are not exercised because the gadget
declares no annotations) and a derived annotated memory variant
(`flag_gadget_chao_reichardt_w4_memory_annotated.stim`, same flagged-check
schedule unrolled into a memory experiment with authored annotations) which
exercises all six registered checks. The repetition and Bacon–Shor hook-check
gaps are schedule-inherent (no bare weight-4-or-higher cycles) and stay
recorded as not exercised, not passes.
