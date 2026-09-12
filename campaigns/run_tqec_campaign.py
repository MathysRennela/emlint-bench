"""TQEC corpus campaign: pinned-provenance rerun of checks + simulations.

Two units:

- ``v020`` (default): reruns the current emlint frontend over the six on-disk
  TQEC 0.2.0 DEMs (memory_z/x k1-2, cnot k1-2; the CZ gallery is blocked
  upstream — see the internal library-structural-bugs ledger) and runs the same pymatching
  smoke simulation as run_smoke.py. This unit is frozen: it documents the
  tqec#1034 bug (tqec 0.2.0 silently emitted invalid CZ circuits).

- ``main``: generates DEMs from TQEC installed at the pinned main commit
  (pip install git+https://github.com/tqec/tqec@<sha>), same galleries and
  parameters. On main the unsupported spatial-Hadamard configuration raises
  NotImplementedError instead of emitting invalid circuits (tqec#1034), so
  the CZ gallery is excluded by construction, not by blocker.

Both units append manifest rows to CORPUS_MANIFEST.jsonl and run rows to
RUN_LOG.jsonl, and write a per-signature raw-instruction verification table
for the `duplicates` adjudication.

Provenance: TQEC v0.2.0 tag = commit 5909ddec049c1649dc5bdd8fa4fd15c261e51b48
(verified against the tqec/tqec GitHub API 2026-09-03); the on-disk artifacts
were installed from the PyPI 0.2.0 wheel (no direct_url.json). DEMs were
extracted with detector_error_model(decompose_errors=True) under
NoiseModel.uniform_depolarizing(0.001), do_not_use_database=True
(internal tqec probe script, library study). The main commit is recorded in
TQEC_MAIN_COMMIT (verified against the tqec/tqec GitHub API 2026-09-03).
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import time
from collections import defaultdict
from pathlib import Path

import pymatching
import stim

import emlint
from emlint.report import format_json

ROOT = Path(__file__).parent
SEED = 20260819
SHOTS = 2_000
TQEC_COMMIT_V020 = "5909ddec049c1649dc5bdd8fa4fd15c261e51b48"
TQEC_MAIN_COMMIT = "bc1f808116a19857b5512588fb61273ec2c90a15"

FILES = [
    ("tqec_memory_z_k1", "memory_z", 1),
    ("tqec_memory_z_k2", "memory_z", 2),
    ("tqec_memory_x_k1", "memory_x", 1),
    ("tqec_memory_x_k2", "memory_x", 2),
    ("tqec_cnot_k1", "cnot", 1),
    ("tqec_cnot_k2", "cnot", 2),
]

MAIN_GALLERIES = {
    "memory_z": "memory_z",
    "memory_x": "memory_x",
    "cnot": "cnot",
}


def generate_dem(gallery: str, k: int) -> tuple[str, str]:
    """Generate (stim circuit text, DEM text) from the installed tqec.

    Requires tqec installed at TQEC_MAIN_COMMIT (pip install
    git+https://github.com/tqec/tqec@TQEC_MAIN_COMMIT). Same extraction
    contract as the internal tqec probe script: gallery constructor, fill_ports_for_
    minimal_simulation() when the graph has ports, compile_block_graph(),
    do_not_use_database=True, NoiseModel.uniform_depolarizing(0.001),
    decompose_errors=True. The CZ gallery is excluded by construction
    (raises NotImplementedError on main — tqec#1034).
    """
    import tqec
    from tqec import NoiseModel
    from tqec.compile import compile_block_graph
    from tqec.gallery.cnot import cnot
    from tqec.gallery.memory import memory
    from tqec.utils.enums import Basis

    del tqec  # import-guard: fail loudly if tqec is absent
    makers = {
        "memory_z": lambda: memory(Basis.Z),
        "memory_x": lambda: memory(Basis.X),
        "cnot": cnot,
    }
    graph = makers[MAIN_GALLERIES[gallery]]()
    if graph.num_ports:
        graph = graph.fill_ports_for_minimal_simulation()[0].graph
    compiled = compile_block_graph(graph)
    noise = NoiseModel.uniform_depolarizing(0.001)
    try:  # tqec <= 0.2.0
        circuit = compiled.generate_stim_circuit(
            k, noise_model=noise, do_not_use_database=True
        )
    except TypeError:  # tqec main: database opt-out via None arguments
        circuit = compiled.generate_stim_circuit(
            k, noise_model=noise, detector_database=None, database_path=None
        )
    dem = circuit.detector_error_model(decompose_errors=True)
    return str(circuit), str(dem)


def direct_url_commit() -> str | None:
    """Return the tqec source commit from direct_url.json, if installed from git."""
    try:
        dist = importlib.metadata.distribution("tqec")
    except importlib.metadata.PackageNotFoundError:
        return None
    direct_url_file = getattr(dist, "_path", None)
    if direct_url_file is None:
        return None
    url_file = direct_url_file / "direct_url.json"
    if not url_file.is_file():
        return None
    data = json.loads(url_file.read_text())
    if "vcs_info" in data:
        return data["vcs_info"].get("commit_id")
    url = data.get("url", "")
    return url.rsplit("@", 1)[-1] if "@" in url else None


FILES = [
    ("tqec_memory_z_k1", "memory_z", 1),
    ("tqec_memory_z_k2", "memory_z", 2),
    ("tqec_memory_x_k1", "memory_x", 1),
    ("tqec_memory_x_k2", "memory_x", 2),
    ("tqec_cnot_k1", "cnot", 1),
    ("tqec_cnot_k2", "cnot", 2),
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def simulate(circuit: stim.Circuit, dem: stim.DetectorErrorModel) -> dict[str, object]:
    sampler = circuit.compile_detector_sampler(seed=SEED)
    detectors, observables = sampler.sample(shots=SHOTS, separate_observables=True)
    decoder = pymatching.Matching.from_detector_error_model(dem)
    predictions = decoder.decode_batch(detectors)
    failures = int((predictions != observables).any(axis=1).sum())
    return {
        "decoder": "pymatching.Matching.from_detector_error_model",
        "shots": SHOTS,
        "seed": SEED,
        "logical_failures": failures,
        "logical_error_rate": failures / SHOTS,
    }


def duplicates_raw_instruction_verification(
    dem: stim.DetectorErrorModel,
) -> dict[str, int]:
    """Classify each duplicate merged-signature group by raw-instruction identity.

    For every (decoder-facing detector set, observable set) signature with
    more than one mechanism, record whether the underlying raw instructions
    are distinct (different probability/targets/hints — valid Stim output at
    merged-signature granularity) or identical (a genuine duplicate).

    Uses emlint's frontend, which preserves one ErrorMechanism per raw Stim
    error instruction together with decomposition hints (known technical-debt item: decomposition-boundary preservation).
    """
    from emlint.frontends import from_stim_dem

    model = from_stim_dem(dem)
    groups: dict[tuple, list[tuple]] = defaultdict(list)
    for mech in model.iter_flattened():
        dets: set[int] = set(mech.detectors)
        for cdets, _cobs in mech.decomposition_hints:
            dets |= set(cdets)
        fingerprint = (
            mech.probability,
            tuple(sorted(mech.detectors)),
            tuple(sorted(mech.observables)),
            tuple(
                sorted(
                    (tuple(sorted(cd)), tuple(sorted(co)))
                    for cd, co in mech.decomposition_hints
                )
            ),
        )
        groups[(frozenset(dets), frozenset(mech.observables))].append(fingerprint)
    distinct_raw = 0
    identical_raw = 0
    for fingerprints in groups.values():
        if len(fingerprints) < 2:
            continue
        if len(set(fingerprints)) == len(fingerprints):
            distinct_raw += 1
        else:
            identical_raw += 1
    return {
        "duplicate_signature_groups": distinct_raw + identical_raw,
        "groups_with_distinct_raw_instructions": distinct_raw,
        "groups_with_identical_raw_instructions": identical_raw,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--unit",
        choices=("v020", "main"),
        default="v020",
        help=(
            "v020: frozen 0.2.0-wheel artifacts (tqec#1034 evidence). "
            "main: generate DEMs from tqec installed at TQEC_MAIN_COMMIT."
        ),
    )
    args = parser.parse_args()
    unit_main = args.unit == "main"

    src = ROOT.parent / "external" / ("tqec_main" if unit_main else "tqec")  # source DEMs are internal library-study artifacts, not redistributed; outputs preserved under results/raw/
    raw = ROOT / "raw" / ("tqec_main" if unit_main else "tqec")
    raw.mkdir(parents=True, exist_ok=True)

    if unit_main:
        installed_commit = direct_url_commit()
        if installed_commit != TQEC_MAIN_COMMIT:
            raise SystemExit(
                f"tqec is not installed at the pinned main commit: expected "
                f"git+https://github.com/tqec/tqec@{TQEC_MAIN_COMMIT}, "
                f"direct_url.json reports {installed_commit!r}. Install with: "
                f"pip install git+https://github.com/tqec/tqec@{TQEC_MAIN_COMMIT}"
            )
        tqec_commit = TQEC_MAIN_COMMIT
        tqec_version = (
            f"{importlib.metadata.version('tqec')}+git.{TQEC_MAIN_COMMIT[:12]}"
        )
        provenance_note = (
            "tqec installed from git at the pinned main commit "
            f"(direct_url.json verified). Circuit generated with "
            "fill_ports_for_minimal_simulation() when the graph has ports, "
            "compile_block_graph(), do_not_use_database=True, "
            "NoiseModel.uniform_depolarizing(0.001); DEM extracted with "
            "decompose_errors=True (same contract as the internal tqec probe script)."
        )
        source_provenance = (
            f"TQEC main at {TQEC_MAIN_COMMIT}; CZ variant excluded by "
            "construction (unsupported spatial-Hadamard configuration raises "
            "NotImplementedError on main — tqec#1034)."
        )
    else:
        tqec_commit = TQEC_COMMIT_V020
        tqec_version = "0.2.0"
        provenance_note = (
            "TQEC v0.2.0 tag (annotated) resolves to this commit; "
            "artifacts installed from the PyPI 0.2.0 wheel. Circuit "
            "generated with fill_ports_for_minimal_simulation(), "
            "compile_block_graph(), do_not_use_database=True, "
            "NoiseModel.uniform_depolarizing(0.001); DEM extracted "
            "with decompose_errors=True."
        )
        source_provenance = (
            "TQEC 0.2.0 gallery; CZ variant blocked upstream (stim "
            "deterministic-observable failure, "
            "the internal library-structural-bugs ledger)."
        )

    emlint_version = importlib.metadata.version("emlint")
    environment = {
        "python": __import__("platform").python_version(),
        "stim": stim.__version__,
        "emlint": emlint_version,
        "pymatching": pymatching.__version__,
        "tqec": tqec_version if unit_main else "0.2.0",
    }
    prefix = "tqec_main_" if unit_main else "tqec_"
    corpus_rows: list[dict[str, object]] = []
    run_rows: list[dict[str, object]] = []
    adjudication_rows: dict[str, dict[str, int]] = {}

    for _v020_id, gallery, k in FILES:
        corpus_id = prefix + _v020_id[len("tqec_") :]
        if unit_main:
            circuit_path = src / f"{gallery}_k{k}.stim"
            dem_path = src / f"{gallery}_k{k}.dem"
            if not circuit_path.is_file():
                circuit_text, dem_text = generate_dem(gallery, k)
                circuit_path.parent.mkdir(parents=True, exist_ok=True)
                circuit_path.write_text(circuit_text, encoding="utf-8")
                dem_path.write_text(dem_text, encoding="utf-8")
        else:
            circuit_path = src / f"{gallery}_k{k}.stim"
            dem_path = src / f"{gallery}_k{k}.dem"
        dem_bytes = dem_path.read_bytes()
        circuit_bytes = circuit_path.read_bytes()
        dem = stim.DetectorErrorModel(dem_bytes.decode())
        circuit = stim.Circuit(circuit_bytes.decode())

        started = time.perf_counter()
        report = emlint.check(dem_path)
        duration = time.perf_counter() - started
        check_path = raw / f"{corpus_id}.emlint.json"
        check_path.write_text(format_json(report) + "\n", encoding="utf-8")

        simulation = simulate(circuit, dem)
        simulation_path = raw / f"{corpus_id}.simulation.json"
        simulation_path.write_text(
            json.dumps(simulation, indent=2) + "\n", encoding="utf-8"
        )

        observed = [r.name for r in report.results if not r.passed]
        corpus_rows.append(
            {
                "id": corpus_id,
                "status": "PENDING_HUMAN_REVIEW",
                "evidence_class": "REAL_CORPUS",
                "source_or_parent": {
                    "source": "TQEC gallery",
                    "generator": f"tqec.gallery.{gallery}",
                    "library_version": tqec_version,
                    "source_commit_or_archive_hash": tqec_commit,
                    "provenance_note": provenance_note,
                },
                "input_sha256": sha256(dem_bytes),
                "stim_version": stim.__version__,
                "emlint_version": emlint_version,
                "parameters": {"gallery": gallery, "k": k, "noise": 0.001},
                "artifacts": {
                    "circuit": str(circuit_path.relative_to(ROOT.parent.parent.parent)),
                    "dem": str(dem_path.relative_to(ROOT.parent.parent.parent)),
                    "check_json": str(check_path.relative_to(ROOT)),
                    "simulation_json": str(simulation_path.relative_to(ROOT)),
                },
                "source_provenance": source_provenance,
                "nonempty_mechanism_count": len(list(dem.flattened())),
                "simulation_command": (
                    f"python campaigns/run_tqec_campaign.py "
                    f"(shots={SHOTS}, seed={SEED})"
                ),
                "shot_budget": SHOTS,
                "seed": SEED,
                "observed_checks": observed,
                "exit_code": (
                    1 if report.has_errors() else 2 if report.has_warnings() else 0
                ),
                "check_duration_seconds": duration,
                "block_reason": None,
            }
        )
        run_rows.append(
            {
                "id": f"check-{corpus_id}",
                "timestamp": "2026-09-03",
                "command": f"emlint.check({dem_path})",
                "environment": environment,
                "input_hashes": {"dem": sha256(dem_bytes)},
                "exit_code": (
                    1 if report.has_errors() else 2 if report.has_warnings() else 0
                ),
                "stdout_path": str(check_path.relative_to(ROOT)),
                "stderr_path": None,
                "duration_seconds": duration,
                "random_seed": None,
                "complete": True,
                "blocked": False,
                "block_reason": None,
            }
        )
        run_rows.append(
            {
                "id": f"simulation-{corpus_id}",
                "timestamp": "2026-09-03",
                "command": f"pymatching decode_batch; shots={SHOTS}; seed={SEED}",
                "environment": environment,
                "input_hashes": {
                    "circuit": sha256(circuit_bytes),
                    "dem": sha256(dem_bytes),
                },
                "exit_code": 0,
                "stdout_path": str(simulation_path.relative_to(ROOT)),
                "stderr_path": None,
                "duration_seconds": None,
                "random_seed": SEED,
                "complete": True,
                "blocked": False,
                "block_reason": None,
            }
        )
        if "duplicates" in observed:
            adjudication_rows[corpus_id] = duplicates_raw_instruction_verification(dem)

    with (ROOT / "CORPUS_MANIFEST.jsonl").open("a", encoding="utf-8") as handle:
        for row in corpus_rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    with (ROOT / "RUN_LOG.jsonl").open("a", encoding="utf-8") as handle:
        for row in run_rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    adjudication_filename = "TQEC_DUPLICATES_ADJUDICATION_%s.json" % time.strftime("%Y%m%d")
    (ROOT / adjudication_filename).write_text(
        json.dumps(adjudication_rows, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    for row in corpus_rows:
        sim = json.loads((raw / f"{row['id']}.simulation.json").read_text())
        print(
            f"{row['id']}: exit={row['exit_code']} "
            f"observed={row['observed_checks']} "
            f"p_L={sim['logical_error_rate']:.4f}"
        )
    print(json.dumps(adjudication_rows, indent=1))


if __name__ == "__main__":
    main()
