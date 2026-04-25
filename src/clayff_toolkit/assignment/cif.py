from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import shlex
from typing import Iterable, Sequence

import numpy as np
from ase import Atoms
from ase.io import read as ase_read


@dataclass(frozen=True)
class Cell:
    a: float
    b: float
    c: float
    alpha: float
    beta: float
    gamma: float

    def lattice_vectors(self) -> tuple[tuple[float, float, float], ...]:
        alpha = math.radians(self.alpha)
        beta = math.radians(self.beta)
        gamma = math.radians(self.gamma)

        ax = self.a
        ay = 0.0
        az = 0.0

        bx = self.b * math.cos(gamma)
        by = self.b * math.sin(gamma)
        bz = 0.0

        cx = self.c * math.cos(beta)
        cy = self.c * (math.cos(alpha) - math.cos(beta) * math.cos(gamma)) / math.sin(
            gamma
        )
        cz_sq = self.c * self.c - cx * cx - cy * cy
        cz = math.sqrt(max(cz_sq, 0.0))
        return ((ax, ay, az), (bx, by, bz), (cx, cy, cz))

    def frac_to_cart(self, frac: Sequence[float]) -> tuple[float, float, float]:
        a_vec, b_vec, c_vec = self.lattice_vectors()
        x = frac[0] * a_vec[0] + frac[1] * b_vec[0] + frac[2] * c_vec[0]
        y = frac[0] * a_vec[1] + frac[1] * b_vec[1] + frac[2] * c_vec[1]
        z = frac[0] * a_vec[2] + frac[1] * b_vec[2] + frac[2] * c_vec[2]
        return (x, y, z)

    def wrap_frac(self, frac: Sequence[float]) -> tuple[float, float, float]:
        return tuple(component - math.floor(component) for component in frac)

    def minimum_image_delta(
        self, origin: Sequence[float], target: Sequence[float]
    ) -> tuple[float, float, float]:
        return tuple(
            (target[index] - origin[index]) - round(target[index] - origin[index])
            for index in range(3)
        )

    def distance(self, frac_a: Sequence[float], frac_b: Sequence[float]) -> float:
        delta = self.minimum_image_delta(frac_a, frac_b)
        return math.dist((0.0, 0.0, 0.0), self.frac_to_cart(delta))

    def triclinic_box(
        self,
    ) -> tuple[float, float, float, float, float, float, float, float, float]:
        a_vec, b_vec, c_vec = self.lattice_vectors()
        xy = b_vec[0]
        xz = c_vec[0]
        ly = b_vec[1]
        yz = c_vec[1]
        lz = c_vec[2]
        return (0.0, self.a, 0.0, ly, 0.0, lz, xy, xz, yz)


@dataclass(frozen=True)
class AtomSite:
    index: int
    label: str
    element: str
    frac: tuple[float, float, float]


@dataclass(frozen=True)
class CifStructure:
    title: str
    path: Path
    cell: Cell
    atoms: tuple[AtomSite, ...]


def _tokenize(line: str) -> list[str]:
    return shlex.split(line, comments=False, posix=True)


def _read_scalar(lines: Iterable[str], key: str) -> str:
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(key):
            parts = _tokenize(stripped)
            if len(parts) < 2:
                break
            return parts[1]
    raise ValueError(f"Missing CIF scalar: {key}")


def parse_cif(path: str | Path) -> CifStructure:
    cif_path = Path(path)
    lines = cif_path.read_text(encoding="utf-8").splitlines()

    title = cif_path.stem
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("data_"):
            title = stripped[5:] or cif_path.stem
            break

    cell = Cell(
        a=float(_read_scalar(lines, "_cell_length_a")),
        b=float(_read_scalar(lines, "_cell_length_b")),
        c=float(_read_scalar(lines, "_cell_length_c")),
        alpha=float(_read_scalar(lines, "_cell_angle_alpha")),
        beta=float(_read_scalar(lines, "_cell_angle_beta")),
        gamma=float(_read_scalar(lines, "_cell_angle_gamma")),
    )

    atoms: list[AtomSite] = []
    line_count = len(lines)
    index = 0
    while index < line_count:
        stripped = lines[index].strip()
        if stripped != "loop_":
            index += 1
            continue

        header_index = index + 1
        headers: list[str] = []
        while header_index < line_count and lines[header_index].strip().startswith("_"):
            headers.append(lines[header_index].strip())
            header_index += 1

        required = {
            "_atom_site_type_symbol",
            "_atom_site_fract_x",
            "_atom_site_fract_y",
            "_atom_site_fract_z",
        }
        if not required.issubset(headers):
            index = header_index
            continue

        row_index = header_index
        atom_counter = 0
        while row_index < line_count:
            row = lines[row_index].strip()
            if not row or row == "loop_" or row.startswith("_"):
                break

            values = _tokenize(row)
            if len(values) < len(headers):
                break

            record = dict(zip(headers, values))
            atom_counter += 1
            label = record.get("_atom_site_label", f"{record['_atom_site_type_symbol']}{atom_counter}")
            atoms.append(
                AtomSite(
                    index=len(atoms) + 1,
                    label=label,
                    element=record["_atom_site_type_symbol"],
                    frac=(
                        float(record["_atom_site_fract_x"]),
                        float(record["_atom_site_fract_y"]),
                        float(record["_atom_site_fract_z"]),
                    ),
                )
            )
            row_index += 1
        break

    if not atoms:
        raise ValueError(f"No atom loop found in CIF: {cif_path}")

    return CifStructure(title=title, path=cif_path, cell=cell, atoms=tuple(atoms))


def structure_from_ase_atoms(
    atoms: Atoms,
    source_path: str | Path = "<memory>",
    title: str | None = None,
) -> CifStructure:
    if atoms.cell.rank < 3:
        raise ValueError("Periodic ClayFF assignment requires a 3D cell.")

    lengths = atoms.cell.lengths()
    angles = atoms.cell.angles()
    cell = Cell(
        a=float(lengths[0]),
        b=float(lengths[1]),
        c=float(lengths[2]),
        alpha=float(angles[0]),
        beta=float(angles[1]),
        gamma=float(angles[2]),
    )
    labels = atoms.arrays.get("labels")
    wrapped = atoms.get_scaled_positions(wrap=True)
    sites = []
    for index, atom in enumerate(atoms, start=1):
        label = str(labels[index - 1]) if labels is not None else f"{atom.symbol}{index}"
        sites.append(
            AtomSite(
                index=index,
                label=label,
                element=str(atom.symbol),
                frac=tuple(float(component) for component in wrapped[index - 1]),
            )
        )

    path = Path(source_path)
    return CifStructure(
        title=title or path.stem or "structure",
        path=path,
        cell=cell,
        atoms=tuple(sites),
    )


def ase_atoms_from_structure(structure: CifStructure) -> Atoms:
    cell_vectors = np.array(structure.cell.lattice_vectors(), dtype=float)
    symbols = [atom.element for atom in structure.atoms]
    scaled_positions = [atom.frac for atom in structure.atoms]
    labels = [atom.label for atom in structure.atoms]
    atoms = Atoms(
        symbols=symbols,
        scaled_positions=scaled_positions,
        cell=cell_vectors,
        pbc=True,
    )
    max_length = max((len(label) for label in labels), default=8)
    atoms.arrays["labels"] = np.array(labels, dtype=f"<U{max_length}")
    return atoms


def load_ase_atoms(path: str | Path) -> Atoms:
    structure_path = Path(path)
    if structure_path.suffix.lower() == ".cif":
        return ase_atoms_from_structure(parse_cif(structure_path))
    return ase_read(structure_path)


def load_structure(path: str | Path) -> CifStructure:
    structure_path = Path(path)
    if structure_path.suffix.lower() == ".cif":
        return parse_cif(structure_path)
    atoms = load_ase_atoms(structure_path)
    return structure_from_ase_atoms(atoms, structure_path)
