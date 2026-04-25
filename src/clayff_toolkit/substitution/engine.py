#!/usr/bin/env python3
"""Batch random substitutions for layered clay structures.

The script walks an input directory recursively, reads supported structure
files, identifies tetrahedral/octahedral framework sites, applies random
substitution rules with anti-clustering constraints, adjusts interlayer
cations for charge balance, and writes the modified structures to an output
directory while preserving the original subdirectory layout.

Supported formats are delegated to ASE. Tested on CIF and periodic XYZ
(extended XYZ) structures.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from itertools import combinations
from typing import Dict, List, Sequence, Set, Tuple

import numpy as np
from ase import Atoms
from ase.io import write

from ..assignment.cif import load_ase_atoms


SUPPORTED_SUFFIXES = {
    ".cif",
    ".xyz",
    ".vasp",
    ".poscar",
    ".contcar",
    ".res",
}
SUPPORTED_FILENAMES = {"POSCAR", "CONTCAR"}
INTERLAYER_CATIONS = {"Li", "Na", "K", "Rb", "Cs", "Ca", "Sr", "Ba"}
TETRA_NEIGHBOR_MAX = 2.05
TETRA_FIFTH_MIN = 2.20
OCTA_NEIGHBOR_MAX = 2.45
FRAMEWORK_CLEARANCE = 1.25
DEFAULT_MIN_INTERLAYER_DISTANCE = 3.20
DEFAULT_MIN_WATER_O_DISTANCE = 2.10
DEFAULT_MIN_WATER_H_DISTANCE = 2.00
MAX_SPLIT_MULTIPLIER = 2


class SubstitutionError(RuntimeError):
    """Raised when a structure cannot satisfy the requested substitutions."""


class InterlayerPlacementError(SubstitutionError):
    """Raised when interlayer cations cannot be placed under current constraints."""


@dataclass(frozen=True)
class RuleDefinition:
    name: str
    tetra_ratio: Fraction
    octa_ratio: Fraction


@dataclass
class StructureClassification:
    tetra_sites: List[int]
    octa_sites: List[int]
    tetra_oxygen_map: Dict[int, Set[int]]
    octa_oxygen_map: Dict[int, Set[int]]
    tetra_graph: Dict[int, Set[int]]
    octa_graph: Dict[int, Set[int]]
    tetra_to_octa_conflicts: Dict[int, Set[int]]
    interlayer_sites: List[int]
    water_oxygen_sites: List[int]
    water_hydrogen_sites: List[int]


@dataclass(frozen=True)
class PlacementConstraints:
    label: str
    min_interlayer_distance: float
    min_water_o_distance: float
    min_water_h_distance: float


PRESET_RULES = {
    "tetra-octa": RuleDefinition(
        name="tetra-octa",
        tetra_ratio=Fraction(1, 32),
        octa_ratio=Fraction(1, 8),
    ),
    "octa-only": RuleDefinition(
        name="octa-only",
        tetra_ratio=Fraction(0, 1),
        octa_ratio=Fraction(1, 8),
    ),
}

RULE_OUTPUT_SUFFIX = {
    "octa-only": "octa",
    "tetra-octa": "tetra-octa",
}


def default_constraint_tiers(
    min_interlayer_distance: float = DEFAULT_MIN_INTERLAYER_DISTANCE,
    min_water_o_distance: float = DEFAULT_MIN_WATER_O_DISTANCE,
    min_water_h_distance: float = DEFAULT_MIN_WATER_H_DISTANCE,
) -> List[PlacementConstraints]:
    return dedupe_constraint_tiers(
        [
            PlacementConstraints(
                label="strict",
                min_interlayer_distance=min_interlayer_distance,
                min_water_o_distance=min_water_o_distance,
                min_water_h_distance=min_water_h_distance,
            ),
            PlacementConstraints(
                label="medium",
                min_interlayer_distance=max(min_interlayer_distance - 0.20, 0.0),
                min_water_o_distance=max(min_water_o_distance - 0.10, 0.0),
                min_water_h_distance=max(min_water_h_distance - 0.10, 0.0),
            ),
            PlacementConstraints(
                label="relaxed",
                min_interlayer_distance=max(min_interlayer_distance - 0.40, 0.0),
                min_water_o_distance=max(min_water_o_distance - 0.20, 0.0),
                min_water_h_distance=max(min_water_h_distance - 0.20, 0.0),
            ),
        ]
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Recursively apply random clay-layer substitutions to structure "
            "files in a directory."
        )
    )
    parser.add_argument(
        "input_dir",
        type=Path,
        help="Input directory containing structures. Subdirectories are included.",
    )
    parser.add_argument(
        "output_dir",
        type=Path,
        help="Output directory. Relative folder structure will be preserved.",
    )
    parser.add_argument(
        "--presets",
        nargs="+",
        choices=sorted(PRESET_RULES),
        default=["tetra-octa", "octa-only"],
        help="Predefined substitution rules to apply.",
    )
    parser.add_argument(
        "--interlayer",
        nargs="+",
        choices=["Ca", "Na"],
        default=["Ca"],
        help="Target interlayer cation species to generate.",
    )
    parser.add_argument(
        "--tetra-ratio",
        type=str,
        help=(
            "Custom tetrahedral substitution ratio, for example 1/32. "
            "When provided together with --octa-ratio, presets are ignored."
        ),
    )
    parser.add_argument(
        "--octa-ratio",
        type=str,
        help=(
            "Custom octahedral substitution ratio, for example 1/8. "
            "When provided together with --tetra-ratio, presets are ignored."
        ),
    )
    parser.add_argument(
        "--rule-name",
        type=str,
        default="custom",
        help="Name used in the output folder when a custom rule is supplied.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=20260402,
        help="Global random seed. File-level seeds are derived from it.",
    )
    parser.add_argument(
        "--strict-ratio",
        action="store_true",
        help=(
            "Require the number of framework sites multiplied by each ratio to "
            "be an exact integer. Otherwise the script rounds to the nearest integer."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze all structures and print planned substitutions without writing files.",
    )
    parser.add_argument(
        "--num-variants",
        type=int,
        default=1,
        help="Number of random structure variants to generate for each input/rule/interlayer combination.",
    )
    parser.add_argument(
        "--min-interlayer-distance",
        type=float,
        default=DEFAULT_MIN_INTERLAYER_DISTANCE,
        help="Minimum allowed distance between same-species interlayer cations in Angstrom.",
    )
    parser.add_argument(
        "--min-water-o-distance",
        type=float,
        default=DEFAULT_MIN_WATER_O_DISTANCE,
        help="Minimum allowed distance from an interlayer cation to a water oxygen in Angstrom.",
    )
    parser.add_argument(
        "--min-water-h-distance",
        type=float,
        default=DEFAULT_MIN_WATER_H_DISTANCE,
        help="Minimum allowed distance from an interlayer cation to a water hydrogen in Angstrom.",
    )
    parser.add_argument(
        "--fallback-tiers",
        type=str,
        default="",
        help=(
            "Semicolon-separated fallback tiers in the form "
            "'label:ii,ow,hw;label:ii,ow,hw' or 'ii,ow,hw;ii,ow,hw'. "
            "The primary tier from --min-* is always tried first."
        ),
    )
    return parser.parse_args(argv)


def parse_fraction(text: str) -> Fraction:
    try:
        value = Fraction(text)
    except Exception as exc:  # pragma: no cover - argparse-facing
        raise argparse.ArgumentTypeError(f"Invalid fraction: {text}") from exc
    if value < 0:
        raise argparse.ArgumentTypeError(f"Fraction must be non-negative: {text}")
    return value


def resolve_rules(args: argparse.Namespace) -> List[RuleDefinition]:
    has_custom = args.tetra_ratio is not None or args.octa_ratio is not None
    if has_custom:
        if args.tetra_ratio is None or args.octa_ratio is None:
            raise SystemExit("--tetra-ratio and --octa-ratio must be supplied together.")
        return [
            RuleDefinition(
                name=args.rule_name,
                tetra_ratio=parse_fraction(args.tetra_ratio),
                octa_ratio=parse_fraction(args.octa_ratio),
            )
        ]
    return [PRESET_RULES[name] for name in args.presets]


def resolve_constraint_tiers(args: argparse.Namespace) -> List[PlacementConstraints]:
    primary = PlacementConstraints(
        label="strict",
        min_interlayer_distance=args.min_interlayer_distance,
        min_water_o_distance=args.min_water_o_distance,
        min_water_h_distance=args.min_water_h_distance,
    )
    tiers = [primary]

    if args.fallback_tiers.strip():
        raw_tiers = [item.strip() for item in args.fallback_tiers.split(";") if item.strip()]
        for index, raw_tier in enumerate(raw_tiers, start=1):
            label = f"fallback_{index}"
            value_text = raw_tier
            if ":" in raw_tier:
                maybe_label, maybe_values = raw_tier.split(":", 1)
                if maybe_label.strip():
                    label = maybe_label.strip()
                    value_text = maybe_values
            parts = [part.strip() for part in value_text.split(",")]
            if len(parts) != 3:
                raise SystemExit(
                    "--fallback-tiers must use 'label:ii,ow,hw;label:ii,ow,hw' format."
                )
            tier = PlacementConstraints(
                label=label,
                min_interlayer_distance=float(parts[0]),
                min_water_o_distance=float(parts[1]),
                min_water_h_distance=float(parts[2]),
            )
            tiers.append(tier)
        return dedupe_constraint_tiers(tiers)

    defaults = default_constraint_tiers(
        min_interlayer_distance=args.min_interlayer_distance,
        min_water_o_distance=args.min_water_o_distance,
        min_water_h_distance=args.min_water_h_distance,
    )[1:]
    tiers.extend(defaults)
    return dedupe_constraint_tiers(tiers)


def resolve_rule(
    preset: str | None = None,
    *,
    tetra_ratio: str | Fraction | None = None,
    octa_ratio: str | Fraction | None = None,
    rule_name: str = "custom",
) -> RuleDefinition:
    if preset is not None:
        try:
            return PRESET_RULES[preset]
        except KeyError as exc:
            available = ", ".join(sorted(PRESET_RULES))
            raise ValueError(f"Unknown preset '{preset}'. Available: {available}") from exc
    if tetra_ratio is None or octa_ratio is None:
        raise ValueError("Either preset or both tetra_ratio and octa_ratio must be supplied.")
    tetra = tetra_ratio if isinstance(tetra_ratio, Fraction) else parse_fraction(str(tetra_ratio))
    octa = octa_ratio if isinstance(octa_ratio, Fraction) else parse_fraction(str(octa_ratio))
    return RuleDefinition(name=rule_name, tetra_ratio=tetra, octa_ratio=octa)


def dedupe_constraint_tiers(
    tiers: Sequence[PlacementConstraints],
) -> List[PlacementConstraints]:
    deduped: List[PlacementConstraints] = []
    seen = set()
    for tier in tiers:
        key = (
            round(tier.min_interlayer_distance, 8),
            round(tier.min_water_o_distance, 8),
            round(tier.min_water_h_distance, 8),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(tier)
    return deduped


def collect_structure_files(root: Path) -> List[Path]:
    files: List[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.name in SUPPORTED_FILENAMES or path.suffix.lower() in SUPPORTED_SUFFIXES:
            files.append(path)
    return sorted(files)


def rule_output_suffix(rule: RuleDefinition) -> str:
    return RULE_OUTPUT_SUFFIX.get(rule.name, rule.name)


def variant_output_path(
    output_dir: Path,
    rel_path: Path,
    rule: RuleDefinition,
    interlayer_species: str,
    variant_index: int,
    num_variants: int,
    multiple_interlayer_species: bool,
) -> Path:
    suffix = rel_path.suffix
    stem = rel_path.stem if suffix else rel_path.name
    name_parts = [stem, rule_output_suffix(rule)]
    if multiple_interlayer_species:
        name_parts.append(interlayer_species)
    if num_variants > 1:
        name_parts.append(str(variant_index))
    filename = "_".join(name_parts) + suffix
    return output_dir / rel_path.parent / filename


def site_count_from_ratio(
    total_sites: int,
    ratio: Fraction,
    strict: bool,
    warnings_list: List[str],
    label: str,
) -> int:
    if ratio == 0:
        return 0
    expected = total_sites * ratio
    if expected.denominator == 1:
        return expected.numerator
    if strict:
        raise SubstitutionError(
            f"{label} count is not an integer: {total_sites} * {ratio} = {float(expected):.6f}"
        )
    rounded = int(round(float(expected)))
    warnings_list.append(
        f"{label} count rounded from {float(expected):.6f} to {rounded}."
    )
    return rounded


def classify_structure(atoms: Atoms) -> StructureClassification:
    oxygen_indices = [idx for idx, atom in enumerate(atoms) if atom.symbol == "O"]
    if not oxygen_indices:
        raise SubstitutionError("No oxygen atoms found; cannot classify framework sites.")

    tetra_sites: List[int] = []
    octa_sites: List[int] = []
    tetra_oxygen_map: Dict[int, Set[int]] = {}
    octa_oxygen_map: Dict[int, Set[int]] = {}

    for idx, atom in enumerate(atoms):
        if atom.symbol not in {"Si", "Al", "Mg"}:
            continue
        distances = atoms.get_distances(idx, oxygen_indices, mic=True)
        pairs = sorted(zip(oxygen_indices, distances), key=lambda item: item[1])
        ordered_distances = [distance for _, distance in pairs]
        d4 = ordered_distances[3] if len(ordered_distances) >= 4 else math.inf
        d5 = ordered_distances[4] if len(ordered_distances) >= 5 else math.inf
        d6 = ordered_distances[5] if len(ordered_distances) >= 6 else math.inf

        if d4 <= TETRA_NEIGHBOR_MAX and d5 > TETRA_FIFTH_MIN:
            tetra_sites.append(idx)
            tetra_oxygen_map[idx] = {
                oxygen_idx for oxygen_idx, distance in pairs if distance <= TETRA_NEIGHBOR_MAX
            }
            continue

        if d6 <= OCTA_NEIGHBOR_MAX:
            octa_sites.append(idx)
            octa_oxygen_map[idx] = {
                oxygen_idx for oxygen_idx, distance in pairs if distance <= OCTA_NEIGHBOR_MAX
            }
            continue

        nearest = ", ".join(f"{distance:.3f}" for distance in ordered_distances[:6])
        raise SubstitutionError(
            f"Could not classify atom #{idx + 1} ({atom.symbol}); nearest O distances: {nearest}"
        )

    tetra_graph = build_shared_oxygen_graph(tetra_sites, tetra_oxygen_map)
    octa_graph = build_shared_oxygen_graph(octa_sites, octa_oxygen_map)

    tetra_to_octa_conflicts: Dict[int, Set[int]] = {}
    for tetra_idx in tetra_sites:
        conflicts = {
            octa_idx
            for octa_idx in octa_sites
            if tetra_oxygen_map[tetra_idx] & octa_oxygen_map[octa_idx]
        }
        tetra_to_octa_conflicts[tetra_idx] = conflicts

    framework_indices = set(tetra_sites) | set(octa_sites)
    interlayer_sites = [
        idx
        for idx, atom in enumerate(atoms)
        if atom.symbol in INTERLAYER_CATIONS and idx not in framework_indices
    ]
    water_oxygen_sites, water_hydrogen_sites = identify_water_sites(atoms)

    return StructureClassification(
        tetra_sites=tetra_sites,
        octa_sites=octa_sites,
        tetra_oxygen_map=tetra_oxygen_map,
        octa_oxygen_map=octa_oxygen_map,
        tetra_graph=tetra_graph,
        octa_graph=octa_graph,
        tetra_to_octa_conflicts=tetra_to_octa_conflicts,
        interlayer_sites=interlayer_sites,
        water_oxygen_sites=water_oxygen_sites,
        water_hydrogen_sites=water_hydrogen_sites,
    )


def identify_water_sites(atoms: Atoms) -> Tuple[List[int], List[int]]:
    hydrogen_indices = [idx for idx, atom in enumerate(atoms) if atom.symbol == "H"]
    if not hydrogen_indices:
        return [], []

    water_oxygen_sites: List[int] = []
    water_hydrogen_sites: Set[int] = set()
    for idx, atom in enumerate(atoms):
        if atom.symbol != "O":
            continue
        distances = atoms.get_distances(idx, hydrogen_indices, mic=True)
        bonded_h = [
            hydrogen_idx
            for hydrogen_idx, distance in zip(hydrogen_indices, distances)
            if distance < 1.25
        ]
        if len(bonded_h) >= 2:
            water_oxygen_sites.append(idx)
            water_hydrogen_sites.update(bonded_h[:2])
    return water_oxygen_sites, sorted(water_hydrogen_sites)


def build_shared_oxygen_graph(
    nodes: Sequence[int],
    oxygen_map: Dict[int, Set[int]],
) -> Dict[int, Set[int]]:
    graph = {node: set() for node in nodes}
    oxygen_to_nodes: Dict[int, List[int]] = defaultdict(list)
    for node in nodes:
        for oxygen_idx in oxygen_map[node]:
            oxygen_to_nodes[oxygen_idx].append(node)
    for node_list in oxygen_to_nodes.values():
        for i, node_i in enumerate(node_list):
            for node_j in node_list[i + 1 :]:
                graph[node_i].add(node_j)
                graph[node_j].add(node_i)
    return graph


def stable_seed(*parts: object) -> int:
    text = "||".join(str(part) for part in parts)
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def choose_independent_set(
    nodes: Sequence[int],
    graph: Dict[int, Set[int]],
    target_size: int,
    rng: np.random.Generator,
    forbidden: Set[int] | None = None,
) -> List[int] | None:
    forbidden = forbidden or set()
    available = set(nodes) - forbidden
    if target_size == 0:
        return []
    if len(available) < target_size:
        return None

    randomness = {node: rng.random() for node in available}

    def branch(current_available: Set[int], chosen: List[int]) -> List[int] | None:
        if len(chosen) == target_size:
            return list(chosen)
        if len(current_available) < target_size - len(chosen):
            return None

        node = max(
            current_available,
            key=lambda item: (len(graph[item] & current_available), randomness[item]),
        )
        actions = ["include", "exclude"]
        if rng.random() < 0.5:
            actions.reverse()

        for action in actions:
            if action == "include":
                reduced = current_available - {node} - (graph[node] & current_available)
                result = branch(reduced, chosen + [node])
            else:
                reduced = current_available - {node}
                result = branch(reduced, chosen)
            if result is not None:
                return result
        return None

    return branch(available, [])


def choose_substitutions(
    classification: StructureClassification,
    tetra_count: int,
    octa_count: int,
    rng: np.random.Generator,
) -> Tuple[List[int], List[int]]:
    tetra_nodes = classification.tetra_sites
    octa_nodes = classification.octa_sites

    if tetra_count > len(tetra_nodes):
        raise SubstitutionError(
            f"Requested {tetra_count} tetrahedral substitutions, but only {len(tetra_nodes)} tetra sites exist."
        )
    if octa_count > len(octa_nodes):
        raise SubstitutionError(
            f"Requested {octa_count} octahedral substitutions, but only {len(octa_nodes)} octa sites exist."
        )

    tetra_randomness = {node: rng.random() for node in tetra_nodes}

    def tetra_branch(
        current_available: Set[int],
        chosen_tetra: List[int],
    ) -> Tuple[List[int], List[int]] | None:
        if len(chosen_tetra) == tetra_count:
            forbidden_octa: Set[int] = set()
            for tetra_idx in chosen_tetra:
                forbidden_octa.update(classification.tetra_to_octa_conflicts[tetra_idx])
            octa_selection = choose_independent_set(
                octa_nodes,
                classification.octa_graph,
                octa_count,
                rng,
                forbidden=forbidden_octa,
            )
            if octa_selection is not None:
                return list(chosen_tetra), octa_selection
            return None

        if len(current_available) < tetra_count - len(chosen_tetra):
            return None

        node = max(
            current_available,
            key=lambda item: (
                len(classification.tetra_graph[item] & current_available),
                tetra_randomness[item],
            ),
        )
        actions = ["include", "exclude"]
        if rng.random() < 0.5:
            actions.reverse()

        for action in actions:
            if action == "include":
                reduced = (
                    current_available
                    - {node}
                    - (classification.tetra_graph[node] & current_available)
                )
                result = tetra_branch(reduced, chosen_tetra + [node])
            else:
                reduced = current_available - {node}
                result = tetra_branch(reduced, chosen_tetra)
            if result is not None:
                return result
        return None

    result = tetra_branch(set(tetra_nodes), [])
    if result is None:
        raise SubstitutionError(
            "Could not find a substitution pattern that satisfies the nearest-neighbor "
            "and tetra/octa conflict constraints."
        )
    tetra_selection, octa_selection = result
    tetra_selection.sort()
    octa_selection.sort()
    return tetra_selection, octa_selection


def select_subset_by_separation(
    atoms: Atoms,
    candidate_indices: Sequence[int],
    target_count: int,
    min_distance: float,
    rng: np.random.Generator,
) -> List[int]:
    if target_count == 0:
        return []
    if target_count > len(candidate_indices):
        raise SubstitutionError(
            f"Cannot choose {target_count} interlayer sites from {len(candidate_indices)} candidates."
        )

    graph = {idx: set() for idx in candidate_indices}
    for i, idx_i in enumerate(candidate_indices):
        for idx_j in candidate_indices[i + 1 :]:
            if atoms.get_distance(idx_i, idx_j, mic=True) < min_distance:
                graph[idx_i].add(idx_j)
                graph[idx_j].add(idx_i)

    candidate_order = list(candidate_indices)
    rng.shuffle(candidate_order)
    chosen = choose_independent_set(candidate_order, graph, target_count, rng)
    if chosen is None:
        raise InterlayerPlacementError(
            f"Cannot choose {target_count} interlayer sites satisfying the minimum distance {min_distance:.2f} A."
        )
    chosen.sort()
    return chosen


def generate_interlayer_positions(
    atoms: Atoms,
    classification: StructureClassification,
    existing_indices: Sequence[int],
    target_count: int,
    min_interlayer_distance: float,
    min_water_o_distance: float,
    min_water_h_distance: float,
    rng: np.random.Generator,
) -> np.ndarray:
    if target_count == 0:
        return np.zeros((0, 3), dtype=float)
    if not existing_indices:
        raise InterlayerPlacementError(
            "No existing interlayer cation positions found, so new interlayer sites cannot be generated."
        )

    scaled_positions = atoms.get_scaled_positions(wrap=True)
    if target_count <= len(existing_indices):
        selected = select_subset_by_separation(
            atoms,
            existing_indices,
            target_count,
            min_interlayer_distance,
            rng,
        )
        return scaled_positions[selected].copy()
    max_supported = len(existing_indices) * MAX_SPLIT_MULTIPLIER
    if target_count > max_supported:
        raise InterlayerPlacementError(
            f"Requested {target_count} interlayer cations from {len(existing_indices)} seed sites. "
            f"The current generator supports up to {max_supported} using at most {MAX_SPLIT_MULTIPLIER} ions per seed site."
        )

    split_count = target_count - len(existing_indices)
    source_indices = list(existing_indices)
    rng.shuffle(source_indices)
    existing_set = set(existing_indices)
    framework_indices = [idx for idx in range(len(atoms)) if idx not in existing_set]
    framework_positions = atoms.get_positions()

    radius_candidates = build_radius_candidates(min_interlayer_distance)
    phase_candidates = np.linspace(0.0, np.pi, 16, endpoint=False).tolist()

    generated = None
    for split_sites in ranked_split_site_sets(
        atoms=atoms,
        site_indices=source_indices,
        split_count=split_count,
        water_oxygen_sites=classification.water_oxygen_sites,
    ):
        generated = backtrack_interlayer_positions(
            atoms=atoms,
            source_indices=source_indices,
            split_sites=split_sites,
            scaled_positions=scaled_positions,
            framework_indices=framework_indices,
            framework_positions=framework_positions,
            water_oxygen_sites=classification.water_oxygen_sites,
            water_hydrogen_sites=classification.water_hydrogen_sites,
            generated_scaled=[],
            radius_candidates=radius_candidates,
            phase_candidates=phase_candidates,
            min_interlayer_distance=min_interlayer_distance,
            min_water_o_distance=min_water_o_distance,
            min_water_h_distance=min_water_h_distance,
        )
        if generated is not None:
            break

    if generated is None:
        raise InterlayerPlacementError(
            "Unable to generate interlayer positions that satisfy ion-ion and ion-water distance constraints."
        )
    return np.array(generated)


def ranked_split_site_sets(
    atoms: Atoms,
    site_indices: Sequence[int],
    split_count: int,
    water_oxygen_sites: Sequence[int],
) -> List[Set[int]]:
    if split_count <= 0:
        return [set()]
    site_scores = {}
    for idx in site_indices:
        if water_oxygen_sites:
            min_water = min(
                atoms.get_distance(idx, water_idx, mic=True) for water_idx in water_oxygen_sites
            )
        else:
            min_water = math.inf
        site_scores[idx] = min_water

    combos = []
    for combo in combinations(site_indices, split_count):
        score = sum(site_scores[idx] for idx in combo)
        combos.append((score, set(combo)))
    combos.sort(key=lambda item: item[0], reverse=True)
    return [combo for _, combo in combos]


def build_radius_candidates(min_interlayer_distance: float) -> List[float]:
    base = max(min_interlayer_distance / 2.0, 1.20)
    max_radius = base + 1.40
    return np.linspace(base, max_radius, 9).tolist()


def backtrack_interlayer_positions(
    atoms: Atoms,
    source_indices: Sequence[int],
    split_sites: Set[int],
    scaled_positions: np.ndarray,
    framework_indices: Sequence[int],
    framework_positions: np.ndarray,
    water_oxygen_sites: Sequence[int],
    water_hydrogen_sites: Sequence[int],
    generated_scaled: List[np.ndarray],
    radius_candidates: Sequence[float],
    phase_candidates: Sequence[float],
    min_interlayer_distance: float,
    min_water_o_distance: float,
    min_water_h_distance: float,
) -> List[np.ndarray] | None:
    if not source_indices:
        return list(generated_scaled)

    current_idx = source_indices[0]
    remaining = source_indices[1:]
    copies = 2 if current_idx in split_sites else 1
    center_scaled = scaled_positions[current_idx].copy()

    for site_points in generate_site_position_candidates(
        atoms=atoms,
        center_scaled=center_scaled,
        copies=copies,
        radius_candidates=radius_candidates,
        phase_candidates=phase_candidates,
    ):
        if not positions_are_valid(
            atoms=atoms,
            candidate_scaled=site_points,
            framework_positions=framework_positions,
            framework_indices=framework_indices,
            water_oxygen_sites=water_oxygen_sites,
            water_hydrogen_sites=water_hydrogen_sites,
            other_scaled=generated_scaled,
            min_interlayer_distance=min_interlayer_distance,
            min_water_o_distance=min_water_o_distance,
            min_water_h_distance=min_water_h_distance,
        ):
            continue
        result = backtrack_interlayer_positions(
            atoms=atoms,
            source_indices=remaining,
            split_sites=split_sites,
            scaled_positions=scaled_positions,
            framework_indices=framework_indices,
            framework_positions=framework_positions,
            water_oxygen_sites=water_oxygen_sites,
            water_hydrogen_sites=water_hydrogen_sites,
            generated_scaled=generated_scaled + site_points,
            radius_candidates=radius_candidates,
            phase_candidates=phase_candidates,
            min_interlayer_distance=min_interlayer_distance,
            min_water_o_distance=min_water_o_distance,
            min_water_h_distance=min_water_h_distance,
        )
        if result is not None:
            return result
    return None


def generate_site_position_candidates(
    atoms: Atoms,
    center_scaled: np.ndarray,
    copies: int,
    radius_candidates: Sequence[float],
    phase_candidates: Sequence[float],
) -> List[List[np.ndarray]]:
    if copies == 1:
        return [[center_scaled % 1.0]]

    basis_1, basis_2 = layer_plane_basis(atoms.cell.array)
    candidates: List[List[np.ndarray]] = []
    for radius in radius_candidates:
        for phase in phase_candidates:
            offsets_cart = []
            for index in range(copies):
                angle = phase + (2.0 * np.pi * index / copies)
                offsets_cart.append(
                    radius * (math.cos(angle) * basis_1 + math.sin(angle) * basis_2)
                )
            site_points = []
            for offset_cart in offsets_cart:
                offset_scaled = np.linalg.solve(atoms.cell.array.T, offset_cart)
                site_points.append((center_scaled + offset_scaled) % 1.0)
            candidates.append(site_points)
    return candidates


def layer_plane_basis(cell: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    vector_a = np.array(cell[0], dtype=float)
    vector_b = np.array(cell[1], dtype=float)
    basis_1 = vector_a / np.linalg.norm(vector_a)
    basis_2 = vector_b - np.dot(vector_b, basis_1) * basis_1
    basis_2 /= np.linalg.norm(basis_2)
    return basis_1, basis_2


def positions_are_valid(
    atoms: Atoms,
    candidate_scaled: Sequence[np.ndarray],
    framework_positions: np.ndarray,
    framework_indices: Sequence[int],
    water_oxygen_sites: Sequence[int],
    water_hydrogen_sites: Sequence[int],
    other_scaled: Sequence[np.ndarray],
    min_interlayer_distance: float,
    min_water_o_distance: float,
    min_water_h_distance: float,
) -> bool:
    candidate_cart = [np.dot(point, atoms.cell.array) for point in candidate_scaled]

    for i, pos_i in enumerate(candidate_cart):
        for pos_j in candidate_cart[i + 1 :]:
            if mic_distance(pos_i, pos_j, atoms.cell.array) < min_interlayer_distance:
                return False

    for pos in candidate_cart:
        for idx in framework_indices:
            if mic_distance(pos, framework_positions[idx], atoms.cell.array) < FRAMEWORK_CLEARANCE:
                return False
        for idx in water_oxygen_sites:
            if mic_distance(pos, atoms.positions[idx], atoms.cell.array) < min_water_o_distance:
                return False
        for idx in water_hydrogen_sites:
            if mic_distance(pos, atoms.positions[idx], atoms.cell.array) < min_water_h_distance:
                return False
        for other in other_scaled:
            other_cart = np.dot(other, atoms.cell.array)
            if mic_distance(pos, other_cart, atoms.cell.array) < min_interlayer_distance:
                return False
    return True


def mic_distance(pos_a: np.ndarray, pos_b: np.ndarray, cell: np.ndarray) -> float:
    inv_cell = np.linalg.inv(cell.T)
    delta_frac = inv_cell @ (pos_a - pos_b)
    delta_frac -= np.round(delta_frac)
    delta_cart = cell.T @ delta_frac
    return float(np.linalg.norm(delta_cart))


def apply_substitutions(
    atoms: Atoms,
    classification: StructureClassification,
    tetra_selection: Sequence[int],
    octa_selection: Sequence[int],
    interlayer_species: str,
    interlayer_count: int,
    constraints: PlacementConstraints,
    rng: np.random.Generator,
) -> Tuple[Atoms, np.ndarray]:
    modified = atoms.copy()
    symbols = modified.get_chemical_symbols()

    for idx in classification.tetra_sites:
        symbols[idx] = "Si"
    for idx in classification.octa_sites:
        symbols[idx] = "Al"
    for idx in tetra_selection:
        symbols[idx] = "Al"
    for idx in octa_selection:
        symbols[idx] = "Mg"
    modified.set_chemical_symbols(symbols)

    generated_positions = generate_interlayer_positions(
        atoms=modified,
        classification=classification,
        existing_indices=classification.interlayer_sites,
        target_count=interlayer_count,
        min_interlayer_distance=constraints.min_interlayer_distance,
        min_water_o_distance=constraints.min_water_o_distance,
        min_water_h_distance=constraints.min_water_h_distance,
        rng=rng,
    )

    keep_mask = np.ones(len(modified), dtype=bool)
    keep_mask[classification.interlayer_sites] = False
    modified = modified[keep_mask]
    cleanup_cif_metadata(modified)

    if interlayer_count:
        interlayer_atoms = Atoms(
            symbols=[interlayer_species] * interlayer_count,
            scaled_positions=generated_positions,
            cell=modified.cell,
            pbc=modified.pbc,
        )
        modified += interlayer_atoms

    return modified, generated_positions


def output_format_for_path(path: Path) -> str | None:
    if path.name in {"POSCAR", "CONTCAR"}:
        return "vasp"
    suffix = path.suffix.lower()
    if suffix == ".xyz":
        return "extxyz"
    if suffix == ".cif":
        return "cif"
    if suffix == ".vasp":
        return "vasp"
    if suffix in {".poscar", ".contcar"}:
        return "vasp"
    return None


def cleanup_cif_metadata(atoms: Atoms) -> None:
    atoms.info.pop("occupancy", None)
    if "spacegroup_kinds" in atoms.arrays:
        del atoms.arrays["spacegroup_kinds"]


def constraints_to_dict(constraints: PlacementConstraints) -> Dict[str, object]:
    return {
        "label": constraints.label,
        "min_interlayer_distance": constraints.min_interlayer_distance,
        "min_water_o_distance": constraints.min_water_o_distance,
        "min_water_h_distance": constraints.min_water_h_distance,
    }


def process_structure(
    input_path: Path,
    output_path: Path,
    rule: RuleDefinition,
    interlayer_species: str,
    variant_index: int,
    global_seed: int,
    strict_ratio: bool,
    constraint_tiers: Sequence[PlacementConstraints],
    dry_run: bool,
) -> Dict[str, object]:
    atoms = load_ase_atoms(input_path)
    classification = classify_structure(atoms)
    warnings_list: List[str] = []

    tetra_count = site_count_from_ratio(
        len(classification.tetra_sites),
        rule.tetra_ratio,
        strict_ratio,
        warnings_list,
        "Tetrahedral substitution",
    )
    octa_count = site_count_from_ratio(
        len(classification.octa_sites),
        rule.octa_ratio,
        strict_ratio,
        warnings_list,
        "Octahedral substitution",
    )
    layer_charge = tetra_count + octa_count
    interlayer_charge = 2 if interlayer_species == "Ca" else 1
    if layer_charge % interlayer_charge != 0:
        raise SubstitutionError(
            f"Layer charge {layer_charge} cannot be neutralized by only {interlayer_species}."
        )
    interlayer_count = layer_charge // interlayer_charge

    local_seed = stable_seed(
        global_seed,
        input_path.resolve(),
        rule.name,
        interlayer_species,
        variant_index,
    )
    rng = np.random.default_rng(local_seed)
    tetra_selection, octa_selection = choose_substitutions(
        classification,
        tetra_count,
        octa_count,
        rng,
    )

    generated_positions = np.zeros((0, 3), dtype=float)
    selected_constraints = constraint_tiers[0]
    selected_tier_index = 1
    placement_attempts: List[Dict[str, object]] = []
    if not dry_run:
        modified = None
        last_error = None
        for tier_index, constraints in enumerate(constraint_tiers, start=1):
            try:
                tier_rng = np.random.default_rng(stable_seed(local_seed, "placement", tier_index))
                modified, generated_positions = apply_substitutions(
                    atoms=atoms,
                    classification=classification,
                    tetra_selection=tetra_selection,
                    octa_selection=octa_selection,
                    interlayer_species=interlayer_species,
                    interlayer_count=interlayer_count,
                    constraints=constraints,
                    rng=tier_rng,
                )
                selected_constraints = constraints
                selected_tier_index = tier_index
                placement_attempts.append(
                    {
                        "tier_index": tier_index,
                        "status": "used",
                        "constraints": constraints_to_dict(constraints),
                    }
                )
                break
            except InterlayerPlacementError as exc:
                last_error = exc
                placement_attempts.append(
                    {
                        "tier_index": tier_index,
                        "status": "failed",
                        "constraints": constraints_to_dict(constraints),
                        "error": str(exc),
                    }
                )
        if modified is None:
            if last_error is None:
                raise InterlayerPlacementError("Interlayer placement failed without an error.")
            raise last_error
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fmt = output_format_for_path(output_path)
        write(str(output_path), modified, format=fmt)
        write_log(output_path, build_log_payload(
            input_path=input_path,
            output_path=output_path,
            rule=rule,
            interlayer_species=interlayer_species,
            local_seed=local_seed,
            classification=classification,
            tetra_selection=tetra_selection,
            octa_selection=octa_selection,
            variant_index=variant_index,
            interlayer_count=interlayer_count,
            layer_charge=layer_charge,
            generated_positions=generated_positions,
            warnings_list=warnings_list,
            selected_constraints=selected_constraints,
            selected_tier_index=selected_tier_index,
            placement_attempts=placement_attempts,
        ))

    return build_log_payload(
        input_path=input_path,
        output_path=output_path,
        rule=rule,
        interlayer_species=interlayer_species,
        local_seed=local_seed,
        classification=classification,
        tetra_selection=tetra_selection,
        octa_selection=octa_selection,
        variant_index=variant_index,
        interlayer_count=interlayer_count,
        layer_charge=layer_charge,
        generated_positions=generated_positions,
        warnings_list=warnings_list,
        selected_constraints=selected_constraints,
        selected_tier_index=selected_tier_index,
        placement_attempts=placement_attempts,
    )


def run_substitution_case(
    input_path: str | Path,
    output_path: str | Path,
    *,
    preset: str | None = "tetra-octa",
    interlayer_species: str = "Ca",
    tetra_ratio: str | Fraction | None = None,
    octa_ratio: str | Fraction | None = None,
    rule_name: str = "custom",
    variant_index: int = 1,
    seed: int = 20260402,
    strict_ratio: bool = False,
    constraint_tiers: Sequence[PlacementConstraints] | None = None,
    dry_run: bool = False,
) -> Dict[str, object]:
    rule = resolve_rule(
        preset,
        tetra_ratio=tetra_ratio,
        octa_ratio=octa_ratio,
        rule_name=rule_name,
    )
    active_constraint_tiers = list(constraint_tiers or default_constraint_tiers())
    return process_structure(
        input_path=Path(input_path).resolve(),
        output_path=Path(output_path).resolve(),
        rule=rule,
        interlayer_species=interlayer_species,
        variant_index=variant_index,
        global_seed=seed,
        strict_ratio=strict_ratio,
        constraint_tiers=active_constraint_tiers,
        dry_run=dry_run,
    )


def build_log_payload(
    input_path: Path,
    output_path: Path,
    rule: RuleDefinition,
    interlayer_species: str,
    local_seed: int,
    classification: StructureClassification,
    tetra_selection: Sequence[int],
    octa_selection: Sequence[int],
    variant_index: int,
    interlayer_count: int,
    layer_charge: int,
    generated_positions: np.ndarray,
    warnings_list: Sequence[str],
    selected_constraints: PlacementConstraints,
    selected_tier_index: int,
    placement_attempts: Sequence[Dict[str, object]],
) -> Dict[str, object]:
    return {
        "input_file": str(input_path),
        "output_file": str(output_path),
        "rule": rule.name,
        "rule_output_suffix": rule_output_suffix(rule),
        "tetra_ratio": str(rule.tetra_ratio),
        "octa_ratio": str(rule.octa_ratio),
        "seed": int(local_seed),
        "variant_index": variant_index,
        "site_counts": {
            "tetra_total": len(classification.tetra_sites),
            "octa_total": len(classification.octa_sites),
            "existing_interlayer_total": len(classification.interlayer_sites),
        },
        "substitutions": {
            "tetra_count": len(tetra_selection),
            "octa_count": len(octa_selection),
            "tetra_indices_1based": [idx + 1 for idx in tetra_selection],
            "octa_indices_1based": [idx + 1 for idx in octa_selection],
        },
        "charge_balance": {
            "layer_charge": layer_charge,
            "interlayer_species": interlayer_species,
            "interlayer_count": interlayer_count,
        },
        "placement_constraints": constraints_to_dict(selected_constraints),
        "placement_label": selected_constraints.label,
        "placement_tier_index": selected_tier_index,
        "placement_attempts": list(placement_attempts),
        "generated_interlayer_scaled_positions": np.round(generated_positions, 8).tolist(),
        "warnings": list(warnings_list),
    }


def write_log(output_path: Path, payload: Dict[str, object]) -> None:
    log_path = output_path.with_suffix(output_path.suffix + ".substitution.json")
    with log_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def build_summary_row(
    *,
    input_dir: Path,
    payload: Dict[str, object] | None = None,
    failure: Dict[str, object] | None = None,
) -> Dict[str, object]:
    if payload is not None:
        input_file = Path(str(payload["input_file"]))
        output_file = Path(str(payload["output_file"]))
        input_relpath = str(input_file.relative_to(input_dir))
        return {
            "status": "success",
            "input_file": str(input_file),
            "input_relpath": input_relpath,
            "input_name": input_file.name,
            "output_file": str(output_file),
            "output_name": output_file.name,
            "rule": payload["rule"],
            "rule_output_suffix": payload["rule_output_suffix"],
            "interlayer_species": payload["charge_balance"]["interlayer_species"],
            "variant_index": payload["variant_index"],
            "placement_label": payload["placement_label"],
            "placement_tier_index": payload["placement_tier_index"],
            "min_interlayer_distance": payload["placement_constraints"]["min_interlayer_distance"],
            "min_water_o_distance": payload["placement_constraints"]["min_water_o_distance"],
            "min_water_h_distance": payload["placement_constraints"]["min_water_h_distance"],
            "tetra_count": payload["substitutions"]["tetra_count"],
            "octa_count": payload["substitutions"]["octa_count"],
            "interlayer_count": payload["charge_balance"]["interlayer_count"],
            "layer_charge": payload["charge_balance"]["layer_charge"],
            "seed": payload["seed"],
            "error": "",
        }

    if failure is None:
        raise ValueError("Either payload or failure must be provided.")

    input_file = Path(str(failure["input_file"]))
    output_file = Path(str(failure["output_file"]))
    input_relpath = str(input_file.relative_to(input_dir))
    return {
        "status": "failure",
        "input_file": str(input_file),
        "input_relpath": input_relpath,
        "input_name": input_file.name,
        "output_file": str(output_file),
        "output_name": output_file.name,
        "rule": failure["rule"],
        "rule_output_suffix": RULE_OUTPUT_SUFFIX.get(str(failure["rule"]), str(failure["rule"])),
        "interlayer_species": failure["interlayer_species"],
        "variant_index": failure["variant_index"],
        "placement_label": "",
        "placement_tier_index": "",
        "min_interlayer_distance": "",
        "min_water_o_distance": "",
        "min_water_h_distance": "",
        "tetra_count": "",
        "octa_count": "",
        "interlayer_count": "",
        "layer_charge": "",
        "seed": "",
        "error": failure["error"],
    }


def write_summary_csv(path: Path, rows: Sequence[Dict[str, object]]) -> None:
    fieldnames = [
        "status",
        "input_file",
        "input_relpath",
        "input_name",
        "output_file",
        "output_name",
        "rule",
        "rule_output_suffix",
        "interlayer_species",
        "variant_index",
        "placement_label",
        "placement_tier_index",
        "min_interlayer_distance",
        "min_water_o_distance",
        "min_water_h_distance",
        "tetra_count",
        "octa_count",
        "interlayer_count",
        "layer_charge",
        "seed",
        "error",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    rules = resolve_rules(args)
    constraint_tiers = resolve_constraint_tiers(args)
    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()

    if args.num_variants < 1:
        print("--num-variants must be at least 1.", file=sys.stderr)
        return 2

    if not input_dir.is_dir():
        print(f"Input directory does not exist: {input_dir}", file=sys.stderr)
        return 2

    structure_files = collect_structure_files(input_dir)
    if not structure_files:
        print(f"No supported structure files found under {input_dir}", file=sys.stderr)
        return 2

    manifests: List[Dict[str, object]] = []
    failures: List[Dict[str, str]] = []

    for input_path in structure_files:
        rel_path = input_path.relative_to(input_dir)
        for rule in rules:
            for interlayer_species in args.interlayer:
                for variant_index in range(1, args.num_variants + 1):
                    output_path = variant_output_path(
                        output_dir=output_dir,
                        rel_path=rel_path,
                        rule=rule,
                        interlayer_species=interlayer_species,
                        variant_index=variant_index,
                        num_variants=args.num_variants,
                        multiple_interlayer_species=len(args.interlayer) > 1,
                    )
                    try:
                        payload = process_structure(
                            input_path=input_path,
                            output_path=output_path,
                            rule=rule,
                            interlayer_species=interlayer_species,
                            variant_index=variant_index,
                            global_seed=args.seed,
                            strict_ratio=args.strict_ratio,
                            constraint_tiers=constraint_tiers,
                            dry_run=args.dry_run,
                        )
                        manifests.append(payload)
                        status = "PLAN" if args.dry_run else "OK"
                        print(
                            f"[{status}] {rel_path} -> {output_path.name} "
                            f"(tetra={payload['substitutions']['tetra_count']}, "
                            f"octa={payload['substitutions']['octa_count']}, "
                            f"interlayer={payload['charge_balance']['interlayer_count']}, "
                            f"placement={payload['placement_label']}"
                            f"#{payload['placement_tier_index']})"
                        )
                    except Exception as exc:
                        failures.append(
                            {
                                "input_file": str(input_path),
                                "rule": rule.name,
                                "interlayer_species": interlayer_species,
                                "variant_index": variant_index,
                                "output_file": str(output_path),
                                "error": str(exc),
                            }
                        )
                        print(
                            f"[FAIL] {rel_path} -> {output_path.name}: {exc}",
                            file=sys.stderr,
                        )

    summary_rows = [build_summary_row(input_dir=input_dir, payload=item) for item in manifests]
    summary_rows.extend(
        build_summary_row(input_dir=input_dir, failure=item) for item in failures
    )

    summary = {
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "rules": [rule.name for rule in rules],
        "interlayer_species": args.interlayer,
        "num_variants": args.num_variants,
        "constraint_tiers": [constraints_to_dict(tier) for tier in constraint_tiers],
        "dry_run": args.dry_run,
        "success_count": len(manifests),
        "failure_count": len(failures),
        "summary_rows": summary_rows,
        "results": manifests,
        "failures": failures,
    }

    if not args.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        summary_path = output_dir / "substitution_summary.json"
        with summary_path.open("w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2, ensure_ascii=False)
        write_summary_csv(output_dir / "substitution_summary.csv", summary_rows)
        successful_rows = [row for row in summary_rows if row["status"] == "success"]
        write_summary_csv(output_dir / "successful_structures.csv", successful_rows)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
