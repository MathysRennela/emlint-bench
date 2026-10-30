# Patchwork (arXiv:2610.22112): candidate corpus source — deferred until the tool ships

Date: 2026-10-16

**Provenance**

- Campaign: none — paper triage / candidate-source tracking only; no artifacts
  were generated or ingested in this repository.
- Source: arXiv:2610.22112v1, "Patchwork: automated lattice surgery and
  space-time partitioning for real-time decoding" (C. Chamberland, M. Li,
  S. Thornton, J. G. Lietz, M. Ren, A. deMarti iOlius — NVIDIA; submitted
  2026-10-15). HTML: <https://arxiv.org/html/2610.22112v1>.
- Evidence: the paper's text only; no DEM/circuit artifact paths in this repo.
- Relationship: slot in the same decision pattern as
  `QECIRC_CORPUS_NOTE_20260901.md` (a source either enters the corpus as a
  campaign or is deferred with a recorded reason) and
  `ECOSYSTEM_SURVEY_20260901.md` (frontier ingested; rest deferred). Future
  ingest would follow the `run_tqec_campaign.py` / mqt-qecc ingest pattern:
  pinned tool version → ExpD benchmark artifacts → full emlint battery →
  `RUN_LOG.jsonl` + dated results files.

## Decision

**Deferred (BLOCKED), recorded as a candidate.** In principle a
high-relevance DEM source; in practice its DEMs cannot be attributed or
regenerated today, which violates this repository's provenance contract
(see `README.md` § Provenance).

## What the source is

Patchwork is an automated lattice-surgery compiler for arbitrary multi-qubit
Pauli measurements on a fixed narrow-corridor surface-code layout. Per its
Appendix B: *"Patchwork (to be released) takes a declarative description of a
lattice-surgery program and produces everything a decoding experiment needs:
the noisy syndrome-extraction circuit, its DEM, the space-time partition of
that DEM into commit, buffer, and cleanup regions"* — local DEMs are
constructed from the syndrome-extraction circuit and noise model using Stim.
The paper does not ship a public artifact release; "to be released" is quoted
verbatim from the HTML as of 2026-10-16.

## Why it is a candidate (relevance case, not a proof)

Everything below is a reading of one paper, not measured evidence on artifacts.

1. **Uncovered detector-geometry class.** The corpus to date (Stim builtins
   sweep, TQEC, qecirc, mqt-qecc ingest) is dominated by standard surface-code
   uniform schedules plus concat/flag structures. Patchwork DEMs arise from
   merged patches with elongated stabilizers, domain-wall stabilizers
   (mixed XX+ZZ), weight-5 twist stabilizers with Y factors, and per-geometry
   gate schedules — detector/observable supports of a kind no corpus entry
   exercises.
2. **Arbitrary-weight multi-qubit Pauli measurements.** The paper's ExpD
   benchmark (three sequential measurements, ten logical qubits, distances
   d ≤ 11) yields detectors/observables that do not correspond to the
   memory/CNOT workflows every current corpus source produces.
3. **A scale axis the corpus lacks.** Section XI.2 ("DEM scaling with
   multi-qubit Pauli measurement sizes") parameterizes DEM size by
   measurement weight — a natural controlled sweep for emlint performance
   profiling, replaying a structurally fixed DEM family across a scaling
   factor.
4. **Relevant prior art for `emlint equiv`.** The commit/buffer/cleanup
   space-time DEM partition, with correction effects composed across local
   DEMs into a global observable update, is a concrete instance of DEM
   equivalence/composition — directly relevant to the prototype-only
   `emlint equiv` layer tracked in emlint-dev `notes/SCOPE.md`
   (`papers/eqthdem/`). Recorded here so the connection is findable; analysis
   belongs to the emlint-dev side, not a bench campaign.

## Why deferred

- The tool is unreleased ("to be released"); the paper contains no GitHub
  link, no artifact DOI, and no supplementary DEM/circuit files.
- Without a released build we can neither pin a toolchain version nor
  regenerate the ExpD DEMs from recorded generator parameters. Committing
  hypothetical, unreproducible DEMs would break the cross-version
  comparability the corpus exists for.

## Re-ingest criteria (what unblocks it)

1. A public, versioned Patchwork release (repo or artifact DOI) that can emit
   noisy syndrome-extraction circuits and DEMs for a declarative
   lattice-surgery program.
2. Then, as a normal campaign: pin the tool version in `manifests/`, build
   the ExpD benchmark (three measurements, ten logical qubits; sweep the
   reported distances d ≤ 11 and, if accessible, the weight sweep of §XI.2),
   run the full emlint battery (`emlint.check(dem)`), and record per the
   conventions in `results/README.md`.
3. Interim alternative if the lattice-surgery-schedule gap must be filled
   before then: no open-source equivalent of Patchwork's end-to-end
   DEM generation exists today; TQEC (already in corpus) and
   `latticesurgery-com/lattice-surgery-compiler` (abstract surgery
   instructions; no end-to-end DEM generation) do not close it. The gap
   stays open until Patchwork or a successor ships.
