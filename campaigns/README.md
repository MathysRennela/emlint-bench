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
