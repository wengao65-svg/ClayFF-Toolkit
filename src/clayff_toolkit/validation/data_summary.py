"""LAMMPS data-file summary helpers."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .charges import calculate_net_charge


@dataclass(frozen=True)
class DataFileSummary:
    atom_count: int
    bond_count: int
    angle_count: int
    atom_type_counts: dict[str, int]
    net_charge: float


def summarize_data_file(path: str | Path) -> DataFileSummary:
    lines = Path(path).read_text(encoding="utf-8").splitlines()

    counts: dict[str, int] = {}
    for line in lines[:20]:
        parts = line.split()
        if len(parts) >= 2 and parts[0].isdigit() and parts[1] in {"atoms", "bonds", "angles"}:
            counts[parts[1]] = int(parts[0])

    mass_map: dict[int, str] = {}
    if "Masses" in lines:
        index = lines.index("Masses") + 2
        while index < len(lines) and lines[index].strip():
            left, _, comment = lines[index].partition("#")
            mass_map[int(left.split()[0])] = comment.strip()
            index += 1

    atom_types: list[str] = []
    if "Atoms # full" in lines:
        index = lines.index("Atoms # full") + 2
        while index < len(lines) and lines[index].strip():
            left, _, _ = lines[index].partition("#")
            parts = left.split()
            atom_types.append(mass_map[int(parts[2])])
            index += 1

    return DataFileSummary(
        atom_count=int(counts.get("atoms", 0)),
        bond_count=int(counts.get("bonds", 0)),
        angle_count=int(counts.get("angles", 0)),
        atom_type_counts=dict(sorted(Counter(atom_types).items())),
        net_charge=calculate_net_charge(path),
    )
