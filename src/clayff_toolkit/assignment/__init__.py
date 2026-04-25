"""ClayFF assignment services."""

from .assigner import AssignedStructure, assign_structure
from .cif import (
    CifStructure,
    ase_atoms_from_structure,
    load_ase_atoms,
    load_structure,
    parse_cif,
    structure_from_ase_atoms,
)
from .params import ClayFFParameters, load_clayff
from .profiles import (
    INTERLAYER_TYPES as PROFILE_INTERLAYER_TYPES,
    MineralProfile,
    MineralProfileMatch,
    PROFILE_CATALOG,
    assignment_markers,
    infer_mineral_profiles,
)
from .service import (
    assign_file,
    assign_loaded_structure,
    assign_structure_file,
    assign_structure_to_path,
    default_clayff_path,
)
from .summary import AssignmentSummary, StructureSummary, summarize_assignment, summarize_structure

__all__ = [
    "AssignedStructure",
    "AssignmentSummary",
    "ClayFFParameters",
    "CifStructure",
    "MineralProfile",
    "MineralProfileMatch",
    "PROFILE_CATALOG",
    "PROFILE_INTERLAYER_TYPES",
    "StructureSummary",
    "ase_atoms_from_structure",
    "assignment_markers",
    "assign_file",
    "assign_loaded_structure",
    "assign_structure",
    "assign_structure_file",
    "assign_structure_to_path",
    "default_clayff_path",
    "load_ase_atoms",
    "load_structure",
    "load_clayff",
    "parse_cif",
    "structure_from_ase_atoms",
    "infer_mineral_profiles",
    "summarize_assignment",
    "summarize_structure",
]
