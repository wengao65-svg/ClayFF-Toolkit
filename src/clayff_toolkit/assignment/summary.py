"""Reusable summary helpers for loaded and assigned structures."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .assigner import AssignedStructure
from .cif import CifStructure


@dataclass(frozen=True)
class StructureSummary:
    atom_count: int
    element_counts: dict[str, int]
    cell_lengths: tuple[float, float, float]
    cell_angles: tuple[float, float, float]


@dataclass(frozen=True)
class AssignmentSummary:
    atom_count: int
    bond_count: int
    angle_count: int
    net_charge: float
    ff_type_counts: dict[str, int]
    element_counts: dict[str, int]


def summarize_structure(structure: CifStructure) -> StructureSummary:
    counts = Counter(atom.element for atom in structure.atoms)
    return StructureSummary(
        atom_count=len(structure.atoms),
        element_counts=dict(sorted(counts.items())),
        cell_lengths=(structure.cell.a, structure.cell.b, structure.cell.c),
        cell_angles=(structure.cell.alpha, structure.cell.beta, structure.cell.gamma),
    )


def summarize_assignment(assigned: AssignedStructure) -> AssignmentSummary:
    element_counts = Counter(atom.element for atom in assigned.atoms)
    ff_type_counts = Counter(atom.ff_type for atom in assigned.atoms)
    return AssignmentSummary(
        atom_count=len(assigned.atoms),
        bond_count=len(assigned.bonds),
        angle_count=len(assigned.angles),
        net_charge=sum(atom.charge for atom in assigned.atoms),
        ff_type_counts=dict(sorted(ff_type_counts.items())),
        element_counts=dict(sorted(element_counts.items())),
    )
