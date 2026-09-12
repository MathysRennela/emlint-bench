# qecirc corpus note: what a circuit library can and cannot say about the taxonomy

Date: 2026-09-01
Status: EMPIRICAL (everything here is corpus evidence on specific instances; nothing is proven)

**Provenance**

- Campaign: `campaigns/qecirc_mine.py`
- Source: QECirc `stim-annotated` circuits
- Evidence: selected-circuit findings described in this report
- Relationship: moved from `emlint-dev/papers/taxonomy/` on 2026-09-12
Artifact: `campaigns/qecirc_mine.py`; corpus snapshot cloned to `/tmp/qecirc-website` (shallow, `github.com/qecirc/qecirc-website`, data license in `LICENSE-DATA` in that repo).

## Motivation

The Unitary Foundation QLDPC challenge informed the taxonomy by supplying real
code *specs* whose failure modes became checks and manuscript caveats. qecirc
(https://qecirc.com/) supplies real *circuits* (968 STIM files, 82 codes), which
is the artifact type the manuscript's open problem 6 (circuit-level grounding)
lives at. This note records a first mining pass and what it does and does not
establish. qecdb (https://qecdb.org/) was also evaluated and excluded: it is
currently empty (0 codes) and its schema (`n,k,d`, rate, stabilizer weight) is
single-code metadata that cannot express composition or seam data.

## Method

- Source: qecirc's `.stim-annotated` variants (the raw `.stim` files declare no
  `DETECTOR`/`OBSERVABLE_INCLUDE`; the annotated variants add them).
- Uniform noise rule injected identically into every circuit: `DEPOLARIZE1(1e-3)`
  after single-qubit Cliffords, `DEPOLARIZE2(1e-2)` after two-qubit gates,
  `X_ERROR(1e-3)` before measurement, measurement flip `1e-2`. Same rule across
  schedules, so the schedule is the only varying factor within a code.
- DEM built with `stim` (both `decompose_errors=False` and `=True` spot-checked;
  findings below hold under both), then the full emlint battery via
  `emlint.check(dem)`.
- Targets: rotated surface code d=3/5/7 under four schedules (depth-optimal,
  edge-coloring, edge-coloring X/Z-split, Alphasyndrome-MWPM); Shor and Carbon
  encoding circuits (concatenated class); 12 flag gadgets.

## Findings

### F1. Paired schedules: the battery is schedule-insensitive at fixed interface data

Same patch, same noise rule, four schedules: every error-severity check passes
on all twelve schedule/code pairs. The only non-passing check is `duplicates`
(warning), and it fires for *all four* schedules at d=5 and d=7 (counts
309/272/268/268 at d=5; 814/816/816/810 at d=7) and for none at d=3.
Consequence for open problem 6: the emlint battery, as it stands, cannot
distinguish schedules that differ in fault-path routing — consistent with the
manuscript's §3.3 position that code-level tools do not transfer to circuit
level for free, and with the OP6 framing that a *negative* result delimits the
calculus to code-level screening. The paired-schedule corpus entries are the
right controlled experiment for any future circuit-level seam certificate:
identical interface data, different circuit.

### F2. Detector-support signatures are non-injective on standard, correct DEMs

`duplicates` (warning severity; property: the signature map
`m ↦ (det(m), obs(m))` is injective) fires on every standard multi-round
surface-code DEM tested — including stim's own canonical
`stim.Circuit.generated("surface_code:rotated_memory_x", ...)` at d=3, 5, 7
under standard noise. Distinct physical fault locations legitimately share a
detector signature (boundary-adjacent paths; the effect grows with rounds and
distance; the qecirc d=3 schedules are clean only because they run 3 rounds
without per-round data depolarization).

Two consequences:

- For emlint (side observation, not a manuscript claim): the `duplicates`
  docstring frames the phenomenon as "typically happens when a DEM is assembled
  from sub-circuits", but the observed base rate on canonical single-code DEMs
  is 100% at ≥3 rounds. Warning severity keeps this contract-compliant, but the
  check conflates benign signature collision with the double-counting bug it
  was designed for; a location-aware refinement (or an explicit
  "expected-on-canonical-DEM" note) would restore signal.
- For the manuscript (§9, OP2, OP6): at circuit level, interface data — the
  detector sets the boundary-signature certificate consumes — does **not**
  identify fault paths. Any certificate that reasons from detector supports
  must not assume signature uniqueness; this is a concrete, empirical form of
  the "graphlike results are definitional representations, not
  circuit-transfer theorems" caveat in §10.

### F3. Gadget-level and seam-adjacent corpus entries carry no interface data

All 298 flag-gadget circuits declare no detectors and have no annotated
variant; they are single-shot building blocks (e.g. weight-10 X-type
stabilizer measurement with one flag ancilla, verified to distance 3 by the
source construction, arXiv:2508.14200). The same holds for the entries closest
to a seam in the whole corpus: the Lift-Connected Surface Code [[65,5,5]]
schedules (cardinal, cardinal-n-s-merged, ZX-coloration) and the
hypergraph-product/SHYPS circuits declare no `DETECTOR` instructions, and the
[[65,5,5]] circuits are single-shot (one extraction round, each ancilla
measured once), so even mechanical round-over-round annotation — the standard
construction — is not available. emlint cannot consume any of these without an
externally supplied wrapping context. This is
itself the manuscript-relevant point: the corpus stores gadgets *noiseless and
detector-less*, i.e. without the interface schedule data that §9.1's
certificate consumes. A certificate format for composed layouts would need to
specify how gadget-level entries attach detectors — currently undefined
anywhere, in the corpus and in the manuscript.

### F4. Encoding circuits declare no observables

Shor/Carbon `circuit-synth-encoding` circuits have detectors but
`num_observables = 0`, so `observable_coverage` trivially passes. Encoding
circuits are the corpus's "composition entry points" (product state → code),
and the manuscript's calculus has no operation of this type (§2's three
mechanisms and §3.2's four compositions all act code → code). Candidate scope
remark rather than a new formalism: state preparation is a fifth,
boundary-condition-like composition the taxonomy currently does not name.

## What this pass does not establish

- No circuit-level instance of shortcut, re-exposure, or rerouting was found in
  the sampled subset (12 flag gadgets, 8 encoding circuits, 12 schedule
  circuits). Absence in a 32-circuit sample is weak evidence; the composed and
  lift-connected entries (`Lift-Connected Surface Code`, SHYPS, hypergraph
  products) are unsampled and are the likelier hunting ground.
- Nothing here bears on open problems 1, 4, or 7 (multi-seam rank counts,
  2-complex bound, certificate engineering), which are mathematical, not
  corpus, problems.
- Open problem 3 (disguises beyond balanced sectors) was not exercised: the
  encoding circuits declare no observables, so sector-resolved distance data
  cannot be extracted from the DEMs as stored.

1. The corpus cannot currently support DEM-level analysis of its own
   seam-adjacent entries (F3): the Lift-Connected Surface Code schedules —
   structurally the closest thing to a seam in qecirc — are stored without
   detectors. Any OP6 attack needs detector-annotated composed-layout
   circuits, which must come from the generating tools directly, not from
   qecirc as ingested.
2. Decide whether F2's non-injectivity belongs in §9 as a limitation of
   detector-support certificates, and whether `duplicates` gets a
   location-aware refinement in emlint. **(Done on the manuscript side:
   see the §9.1 remark added to MANUSCRIPT_QEC.md.)**
3. If OP6 is attacked seriously, use the paired-schedule entries (F1) as the
   controlled test set for any circuit-level seam certificate.
