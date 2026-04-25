"""Service layer for ClayFF assignment workflows."""

from __future__ import annotations

from pathlib import Path

from .assigner import AssignedStructure, assign_structure
from .cif import CifStructure, load_structure
from .lammps_writer import write_lammps_data
from .params import ClayFFParameters, load_clayff


def default_clayff_path() -> Path:
    return Path(__file__).resolve().parent.parent / "resources" / "clayff.txt"


def load_default_clayff() -> ClayFFParameters:
    return load_clayff(default_clayff_path())


def assign_loaded_structure(
    structure: CifStructure,
    forcefield: ClayFFParameters | None = None,
) -> tuple[AssignedStructure, ClayFFParameters]:
    active_forcefield = forcefield or load_default_clayff()
    return assign_structure(structure, active_forcefield), active_forcefield


def assign_structure_file(
    input_structure: str | Path,
    clayff_path: str | Path | None = None,
) -> tuple[CifStructure, AssignedStructure, ClayFFParameters]:
    structure = load_structure(input_structure)
    forcefield = load_clayff(clayff_path or default_clayff_path())
    assigned, active_forcefield = assign_loaded_structure(structure, forcefield)
    return structure, assigned, active_forcefield


def assign_structure_to_path(
    structure: CifStructure,
    output_path: str | Path,
    forcefield: ClayFFParameters | None = None,
) -> Path:
    assigned, active_forcefield = assign_loaded_structure(structure, forcefield)
    return write_lammps_data(assigned, active_forcefield, output_path)


def assign_file(
    input_structure: str | Path,
    output_data: str | Path,
    clayff_path: str | Path | None = None,
) -> Path:
    structure, _, forcefield = assign_structure_file(input_structure, clayff_path)
    return assign_structure_to_path(structure, output_data, forcefield)
