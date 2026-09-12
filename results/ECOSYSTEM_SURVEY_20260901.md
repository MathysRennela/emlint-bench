# Ecosystem corpus survey — 2026-09-01

> **Provenance** — Date: 2026-09-01 · Campaign: crawler-axis survey of research `.stim`/`.dem` sources · Producer: manual survey (no script) · Environment: n/a · Evidence: frontier ingest rows in `results/RUN_LOG.jsonl` (2026-09-03), `results/raw/frontier_*.json`

Companion to the emlint ecosystem engagement plan. Candidate repositories for research-circuit/DEM
corpus mining (the ecosystem engagement plan is compiler-relationship-driven; this survey is the
crawler-driven axis from the 2026-09-01 corpus-expansion plan). Method: GitHub
repository search on `topic:quantum-error-correction stim`, `topic:qldpc`,
`topic:sinter stim`, plus GitHub code search for `extension:stim` /
`extension:dem` (code search is sparse — REST code search indexes only default
branches, so repository search was the productive channel).

None of these are ingested yet. Any ingest goes through the existing pipeline:
`CORPUS_MANIFEST.jsonl` provenance, eligibility corridor, and adjudication
bug classes from the emlint validation strategy; external DEMs are committed with
`*_corpus_meta.json`. Licenses must be verified per-repo at ingest time; entries
without a license are excluded from redistribution.

## Tier 1 — likely contains ready `.stim`/`.dem` artifacts

| Repo | What it offers | License (verify) | Ingest difficulty |
|---|---|---|---|
| [aleverrier/frontier](https://github.com/aleverrier/frontier) | Frontier decoder for QLDPC; consumes/constructs DEMs for bivariate-bicycle and gross codes; detector-error-model matrices | Apache-2.0 (verified) | **DONE 2026-09-01** — 6 DEMs ingested, see the frontier entries in `results/raw/` and the ecosystem engagement plan |
| [qec-codes/qec](https://github.com/qec-codes/qec) | Python LDPC/QLDPC code tools (28★, active) | TBD | Medium — check matrices, need circuit construction |
| [MarcSerraPeralta/qec-util](https://github.com/MarcSerraPeralta/qec-util) | Stim-centric QEC simulation utilities (circuits, noise, data handling) | TBD | Low — Python, stim-native |
| [adelshb/graphqec](https://github.com/adelshb/graphqec) | Tanner-graph code analysis incl. stim circuit export (18★) | TBD | Low-medium |
| [inmzhang/stim-rs](https://github.com/inmzhang/stim-rs) | Rust stim bindings; test fixtures may include circuits | TBD | Low value directly; fixture mining only |

## Tier 2 — generators/decoders; circuits derivable but not stored as artifacts

| Repo | What it offers | Note |
|---|---|---|
| [bledden/tridec](https://github.com/bledden/tridec) | GPU decoders consuming arbitrary stim DEMs; benchmarks include BB-code DEMs | DEM generation machinery, not stored artifacts |
| [bledden/pathfinder](https://github.com/bledden/pathfinder) | Neural surface-code + BB-code qLDPC benchmark | Circuit-generation scripts |
| [686f6c61/Quantum-DEMSpecBench](https://github.com/686f6c61/Quantum-DEMSpecBench) | DEM/Sinter conformance benchmark spec | Possibly ready-made DEM suite; small/young repo, verify substance before ingest |
| [afogelis/google-surface-code-reproduction](https://github.com/afogelis/google-surface-code-reproduction) | Reproduction of Google 2023 surface-code scaling experiment | Overlaps Stim builtins; low marginal diversity |
| [nzy1997/rust-qec](https://github.com/nzy1997/rust-qec) | Rust QEC simulation workspace with reproducible benchmarks | Cross-language check of DEM conventions |

## Tier 3 — known majors already inside the ecosystem engagement plan scope (listed for completeness, no new action)

Stim docs/examples, PyMatching examples/tests, sinter glue, qiskit-qec,
qecsim/qecsimext, errorcorrectionzoo (no circuits). These are either already
ingested (PyMatching-adjacent via stim builtins) or covered by the ecosystem engagement plan
engagement rows (QUITS covers QLDPC HGP/BB/BPC; LightStim covers BB memory).

## Survey conclusions

1. The crawler axis adds most value for **QLDPC DEM diversity beyond QUITS** —
   `frontier` (BB/gross DEMs) and `qec-codes/qec` are the two best candidates.
2. GitHub code search (`extension:stim`, `extension:dem`) is **not** a viable
   automated channel via the REST API (near-zero recall). A full survey of
   paper-supplementary repos needs either the web search UI (manual) or
   BigQuery/GH Archive (out of scope for now).
3. Most search hits are small reproduction repos whose circuits collapse to
   Stim builtins — consistent with the ecosystem engagement plan's warning that breadth must
   come from non-stim-convention compilers, not from crawling.
4. ~~Recommended first ingest: `frontier` pinned-release DEMs → quarantine class
   until adjudicated~~ — **executed 2026-09-01** (6 DEMs; Q102 `duplicates`
   findings pending adjudication).

## Qiskit QEC / qecsim overlap evaluation (Step 3 decision record)

Question: does a generic stabilizer→stim circuit converter fed by qiskit-qec or
qecsim add code-family or construction diversity not already reachable via QUITS
and LightStim?

Current QLDPC/multi-family coverage in the corpus:

- QUITS (ingested): hypergraph-product d9/d25, bivariate-bicycle BB72/BB144.
- LightStim (ingested): BB-code memory, surface memory, lattice surgery.
- Stim builtins (swept 2026-09-01): repetition, rotated/unrotated surface z/x,
  color (memory_xyz, d3 decomposed; d5/d7 undecomposed).

Assessment:

- **qiskit-qec**: provides stabilizer-code *representations* and code
  construction from parity-check matrices, but no detector-annotated syndrome
  circuit generator. Any ingest requires writing a schedule (CNOT ordering,
  ancilla reset policy, measurement wiring) by hand — i.e., the construction
  diversity gained is *our* schedule, not the library's. That is exactly the
  "annotation is manual and error-prone" risk already recorded in the ecosystem engagement plan
  (transversal-gate row, risk table). A hand-built schedule bugs would be
  corpus-level bugs contaminating known-good labels.
- **qecsim**: adds genuine code families not otherwise covered — toric, planar,
  Bacon-Shor, compass, subsystem — but is code-level (error models over
  stabilizers), also without detector-annotated circuits. Same manual-schedule
  caveat, plus Bacon-Shor/subsystem codes have gauge sectors whose detector
  semantics need a protocol-specific contract (the validation strategy
  applicability clause) before any check result is admissible.

Decision (revised 2026-09-01 after user correction): **proceed, reframed**. The
value of qiskit-qec/qecsim ingest is not construction diversity — it is running
the check battery against DEMs produced by *existing, independent pipelines* to
find real bugs (the same false-positive-hunt rationale as every other
the ecosystem engagement plan compiler row). The manual-schedule caveat still applies to how the
converter is built: corpus entries derived from hand-written schedules must be
labelled as such in provenance, since a schedule bug would be a corpus-level
bug, not a source-library defect. Priority sits behind the frontier ingest
(below), which needs no converter at all.
