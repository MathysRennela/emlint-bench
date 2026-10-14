"""Probe: can a Stim DEM be converted to parity-check matrices that a
code-level distance solver (Qubitserf) can use as a distance backend?

One-off audit campaign, 2026-10-14. Toy models first (hand-built DEMs, no stim
dependency in construction), then real stim circuits. Every stage prints the
same four quantities so they can be compared line by line:

  brute force        exhaustive minimum-weight undetectable set (toy only)
  stim                stim.DetectorErrorModel.shortest_graphlike_error
  emlint              experimental/checks.py:check_distance
  qubitserf           minimum weight of the kernel of the recovered block

The conversion under test: one column per mechanism that flips one or two
detectors, holding that mechanism's detector incidence vector; one block per
connected component of the resulting detector graph. Mechanisms flipping three
or more detectors have no column representation and are counted, not modelled.

Usage:  python probe_qubitserf_distance_adapter.py [--json OUT]
Requires: stim, numpy, qldpc, qubitserf, emlint (importable).
"""

from __future__ import annotations

import argparse
import collections
import itertools
import json
import os
import sys
from typing import NamedTuple

import numpy as np
import stim


# --------------------------------------------------------------- conversion


class Block(NamedTuple):
    """One recovered parity-check matrix and its per-column observable parity."""

    matrix: np.ndarray
    observable_parity: np.ndarray


def mechanism_columns(
    dem: stim.DetectorErrorModel,
) -> tuple[list[tuple[tuple[int, ...], int]], dict]:
    """Return ([(detector set, observable parity)], weight statistics)."""
    stats = {
        "mechanisms_total": 0,
        "mechanisms_with_separator": 0,
        "mechanisms_weight_0": 0,
        "mechanisms_weight_1": 0,
        "mechanisms_weight_2": 0,
        "mechanisms_weight_3_or_more": 0,
        "probability_mass_total": 0.0,
        "probability_mass_with_separator": 0.0,
        "probability_mass_on_weight_3_or_more": 0.0,
    }
    columns: list[tuple[tuple[int, ...], int]] = []
    for instruction in dem.flattened():
        if instruction.type != "error":
            continue
        targets = instruction.targets_copy()
        probability = instruction.args_copy()[0]
        stats["mechanisms_total"] += 1
        stats["probability_mass_total"] += probability
        if any(target.is_separator() for target in targets):
            # A separator-bearing mechanism is a product of independent
            # mechanisms, not one hyperedge. It is not a single column, and it
            # is counted here so that dropping it is never silent.
            stats["mechanisms_with_separator"] += 1
            stats["probability_mass_with_separator"] += probability
            continue
        detectors = tuple(
            sorted(t.val for t in targets if t.is_relative_detector_id())
        )
        parity = sum(1 for t in targets if t.is_logical_observable_id()) % 2
        weight = len(detectors)
        if weight == 0:
            stats["mechanisms_weight_0"] += 1
        elif weight == 1:
            stats["mechanisms_weight_1"] += 1
            columns.append((detectors, parity))
        elif weight == 2:
            stats["mechanisms_weight_2"] += 1
            columns.append((detectors, parity))
        else:
            stats["mechanisms_weight_3_or_more"] += 1
            stats["probability_mass_on_weight_3_or_more"] += probability
    total = stats["probability_mass_total"]
    for key in (
        "probability_mass_with_separator",
        "probability_mass_on_weight_3_or_more",
    ):
        stats[key] = stats[key] / total if total else 0.0
    return columns, stats


def dem_to_blocks(dem: stim.DetectorErrorModel) -> tuple[list[Block], dict]:
    """Convert a graphlike DEM to one parity-check matrix per connected component."""
    columns, stats = mechanism_columns(dem)
    adjacency: dict[int, set[int]] = collections.defaultdict(set)
    for detectors, _ in columns:
        for detector in detectors:
            adjacency[detector]  # materialise isolated nodes
        for left, right in zip(detectors, detectors[1:]):
            adjacency[left].add(right)
            adjacency[right].add(left)

    seen: set[int] = set()
    blocks: list[Block] = []
    for start in sorted(adjacency):
        if start in seen:
            continue
        nodes, stack = [start], [start]
        seen.add(start)
        while stack:
            node = stack.pop()
            for neighbour in adjacency[node]:
                if neighbour not in seen:
                    seen.add(neighbour)
                    nodes.append(neighbour)
                    stack.append(neighbour)
        inside = set(nodes)
        selected = [c for c in columns if set(c[0]) <= inside]
        row_of = {detector: i for i, detector in enumerate(sorted(nodes))}
        matrix = np.zeros((len(row_of), len(selected)), dtype=np.uint8)
        for column, (detectors, _) in enumerate(selected):
            for detector in detectors:
                matrix[row_of[detector], column] = 1
        blocks.append(
            Block(
                matrix=matrix,
                observable_parity=np.array(
                    [parity for _, parity in selected], dtype=np.uint8
                ),
            )
        )
    return blocks, stats


# ------------------------------------------------------------- measurements


def brute_force_logical_distance(dem: stim.DetectorErrorModel) -> int | None:
    """Minimum weight subset with zero syndrome and odd observable parity."""
    mechanisms = []
    for instruction in dem.flattened():
        if instruction.type != "error":
            continue
        detectors = frozenset(
            t.val for t in instruction.targets_copy() if t.is_relative_detector_id()
        )
        parity = (
            sum(1 for t in instruction.targets_copy() if t.is_logical_observable_id())
            % 2
        )
        mechanisms.append((detectors, parity))
    for size in range(1, len(mechanisms) + 1):
        for combination in itertools.combinations(range(len(mechanisms)), size):
            syndrome: set[int] = set()
            parity = 0
            for index in combination:
                detectors, mechanism_parity = mechanisms[index]
                syndrome ^= detectors
                parity ^= mechanism_parity
            if not syndrome and parity == 1:
                return size
    return None


def minimum_witness(block: Block) -> tuple[int, int] | None:
    """Explicit minimum-weight kernel element of weight 3, and its observable parity.

    For distinct columns x, y the vector x XOR y lies in the kernel exactly when
    it is itself a column, which gives a three-mechanism witness without any
    search. Returns (weight, observable parity) or None if no weight-3 element
    exists.
    """
    index = {tuple(block.matrix[:, j].tolist()): j for j in range(block.matrix.shape[1])}
    columns = list(index)
    for i, left in enumerate(columns):
        for right in columns[i + 1 :]:
            combined = tuple((a ^ b) & 1 for a, b in zip(left, right))
            third = index.get(combined)
            if third is not None:
                parity = int(
                    block.observable_parity[
                        [index[left], index[right], third]
                    ].sum()
                    % 2
                )
                return 3, parity
    return None


def load_emlint_check_distance():
    """Import the experimental distance check from the emlint development tree.

    Set EMLINT_DEV_ROOT to the checkout if it is not importable from here.
    """
    root = os.environ.get("EMLINT_DEV_ROOT")
    if root:
        sys.path.insert(0, root)
    try:
        from experimental.checks import check_distance
        from emlint.frontends import from_stim_dem
    except ImportError as error:  # pragma: no cover - environment guard
        raise SystemExit(
            "cannot import emlint / experimental.checks; set EMLINT_DEV_ROOT to "
            f"the emlint development checkout ({error})"
        )
    return check_distance, from_stim_dem


def measure(name: str, dem: stim.DetectorErrorModel, brute: int | None = None) -> dict:
    from qubitserf import distfind as code_distance

    check_distance, from_stim_dem = load_emlint_check_distance()

    blocks, stats = dem_to_blocks(dem)
    per_block = []
    for block in blocks:
        try:
            solver = code_distance.classical_distance(block.matrix)
        except Exception as error:  # noqa: BLE001
            solver = f"error: {error}"
        witness = minimum_witness(block)
        per_block.append(
            {
                "rows": int(block.matrix.shape[0]),
                "columns": int(block.matrix.shape[1]),
                "qubitserf_classical_distance": solver,
                "minimum_weight_3_witness": None if witness is None else witness[0],
                "witness_observable_parity": None if witness is None else witness[1],
            }
        )
    solvers = [
        b["qubitserf_classical_distance"]
        for b in per_block
        if isinstance(b["qubitserf_classical_distance"], int)
    ]
    try:
        chain = dem.shortest_graphlike_error()
        stim_distance = None if chain is None else len(chain)
    except Exception as error:  # noqa: BLE001
        stim_distance = f"error: {error}"
    emlint_result = check_distance(from_stim_dem(dem))
    return {
        "name": name,
        "detectors": dem.num_detectors,
        "observables": dem.num_observables,
        "weight_statistics": stats,
        "blocks": per_block,
        "qubitserf_minimum_over_blocks": min(solvers) if solvers else None,
        "stim_shortest_graphlike_error": stim_distance,
        "emlint_check_distance_message": emlint_result.message,
        "brute_force": brute,
    }


# ----------------------------------------------------------------- toy DEMs


def repetition_capacity_dem(distance: int, probability: float = 0.1) -> str:
    """Repetition-code capacity experiment text.

    Detector D_i compares the neighbouring stabilizers Z_i Z_{i+1}; every data
    qubit also flips L0, so the undetectable set of all qubits is the logical
    operator of weight `distance`.
    """
    lines = [f"detector({i}) D{i}" for i in range(distance - 1)]
    lines.append(f"error({probability}) D0 L0")
    for i in range(1, distance - 1):
        lines.append(f"error({probability}) D{i - 1} D{i} L0")
    lines.append(f"error({probability}) D{distance - 2} L0")
    return "\n".join(lines)


def graphlike_submodel(dem: stim.DetectorErrorModel) -> stim.DetectorErrorModel:
    """Keep only mechanisms that flip at most two detectors."""
    out = stim.DetectorErrorModel()
    for instruction in dem.flattened():
        if instruction.type in ("detector", "logical_observable"):
            out.append(instruction)
        elif instruction.type == "error":
            targets = instruction.targets_copy()
            if any(t.is_separator() for t in targets):
                continue
            if sum(1 for t in targets if t.is_relative_detector_id()) <= 2:
                out.append(instruction)
    return out


def surface_code_memory(distance: int, rounds: int, basis: str = "z"):
    probability = 0.001
    return stim.Circuit.generated(
        f"surface_code:rotated_memory_{basis}",
        distance=distance,
        rounds=rounds,
        after_clifford_depolarization=probability,
        before_round_data_depolarization=probability,
        before_measure_flip_probability=probability,
        after_reset_flip_probability=probability,
    )


# --------------------------------------------------------------------- main


def run() -> dict:
    stages: dict[str, list[dict]] = {"toy": [], "graphlike": [], "hyperedge": []}

    for distance in (3, 5):
        dem = stim.DetectorErrorModel(repetition_capacity_dem(distance))
        stages["toy"].append(
            measure(
                f"repetition-code capacity, distance {distance}",
                dem,
                brute=brute_force_logical_distance(dem),
            )
        )
    broken_text = repetition_capacity_dem(5) + "\nerror(0.1) D0 D1 D2\n"
    broken = stim.DetectorErrorModel(broken_text)
    stages["toy"].append(
        measure(
            "repetition-code capacity, distance 5, one weight-3 mechanism added",
            broken,
            brute=brute_force_logical_distance(broken),
        )
    )

    for distance in (3, 5):
        circuit = surface_code_memory(distance, rounds=distance)
        full = circuit.detector_error_model(
            decompose_errors=True,
            flatten_loops=True,
            approximate_disjoint_errors=True,
        )
        stages["graphlike"].append(
            measure(
                f"rotated_memory_z distance {distance} rounds {distance}, "
                "graphlike submodel",
                graphlike_submodel(full),
            )
        )
        stages["hyperedge"].append(
            measure(
                f"rotated_memory_z distance {distance} rounds {distance}, "
                "full circuit-level model",
                full,
            )
        )

    return {"stages": stages}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", help="write the measurements to this path")
    arguments = parser.parse_args()

    report = run()
    for stage, rows in report["stages"].items():
        print(f"\n=== {stage}")
        for row in rows:
            print(f"\n  {row['name']}")
            print(
                f"    detectors={row['detectors']} observables={row['observables']}"
            )
            stats = row["weight_statistics"]
            print(
                f"    mechanisms: total={stats['mechanisms_total']} "
                f"with-separator={stats['mechanisms_with_separator']} "
                f"(probability mass "
                f"{stats['probability_mass_with_separator']:.3f}); "
                f"separator-free weight 0={stats['mechanisms_weight_0']} "
                f"1={stats['mechanisms_weight_1']} "
                f"2={stats['mechanisms_weight_2']} "
                f">=3={stats['mechanisms_weight_3_or_more']} "
                f"(probability mass "
                f"{stats['probability_mass_on_weight_3_or_more']:.3f})"
            )
            for block in row["blocks"]:
                print(
                    f"    block rows={block['rows']} cols={block['columns']}: "
                    f"qubitserf={block['qubitserf_classical_distance']} "
                    f"weight-3 witness parity="
                    f"{block['witness_observable_parity']}"
                )
            print(
                f"    qubitserf minimum over blocks : "
                f"{row['qubitserf_minimum_over_blocks']}"
            )
            print(f"    stim graphlike error chain    : {row['stim_shortest_graphlike_error']}")
            print(f"    emlint check_distance         : {row['emlint_check_distance_message']}")
            if row["brute_force"] is not None:
                print(f"    brute force ground truth      : {row['brute_force']}")

    if arguments.json:
        with open(arguments.json, "w") as handle:
            json.dump(report, handle, indent=2, default=str)
        print(f"\nwrote {arguments.json}")


if __name__ == "__main__":
    main()