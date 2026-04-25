from __future__ import annotations

from collections import Counter
from pathlib import Path

from clayff_toolkit.assignment import (
    assign_file,
    assign_structure,
    default_clayff_path,
    load_clayff,
    load_ase_atoms,
    structure_from_ase_atoms,
)
from clayff_toolkit.substitution.engine import classify_structure
from clayff_toolkit.validation import calculate_net_charge


FIXTURES = Path(__file__).resolve().parent / "fixtures"
INPUT_DIR = FIXTURES / "assignment_input"
REFERENCE_DIR = FIXTURES / "assignment_reference"


def parse_data_summary(path: Path) -> dict[str, object]:
    lines = path.read_text(encoding="utf-8").splitlines()
    summary: dict[str, object] = {
        "counts": {},
        "atom_types": [],
        "charges": [],
        "net_charge": 0.0,
        "bond_count": 0,
        "angle_count": 0,
    }

    for line in lines[:20]:
        parts = line.split()
        if len(parts) >= 2 and parts[0].isdigit() and parts[1] in {"atoms", "bonds", "angles"}:
            summary["counts"][parts[1]] = int(parts[0])

    mass_map: dict[int, str] = {}
    if "Masses" in lines:
        index = lines.index("Masses") + 2
        while index < len(lines) and lines[index].strip():
            left, _, comment = lines[index].partition("#")
            mass_map[int(left.split()[0])] = comment.strip()
            index += 1

    if "Atoms # full" in lines:
        index = lines.index("Atoms # full") + 2
        while index < len(lines) and lines[index].strip():
            left, _, _ = lines[index].partition("#")
            parts = left.split()
            atom_type = mass_map[int(parts[2])]
            charge = float(parts[3])
            summary["atom_types"].append(atom_type)
            summary["charges"].append(charge)
            summary["net_charge"] += charge
            index += 1

    summary["atom_type_counts"] = Counter(summary["atom_types"])
    summary["bond_count"] = int(summary["counts"].get("bonds", 0))
    summary["angle_count"] = int(summary["counts"].get("angles", 0))
    return summary


def test_reference_assignments_match_legacy_summaries(tmp_path: Path) -> None:
    cases = [
        "MMT_0W_rank3_d9.545",
        "MMT_64W_rank1_d15.183",
        "MMT_96W_rank1_d18.516",
        "cammt_c2m_32",
        "test",
    ]

    for case in cases:
        input_path = INPUT_DIR / f"{case}.cif"
        output_path = tmp_path / f"{case}.data"
        reference_path = REFERENCE_DIR / f"{case}.data"

        assign_file(input_path, output_path, default_clayff_path())

        generated = parse_data_summary(output_path)
        reference = parse_data_summary(reference_path)

        assert generated["atom_types"] == reference["atom_types"], case
        assert generated["charges"] == reference["charges"], case
        assert generated["atom_type_counts"] == reference["atom_type_counts"], case
        if case != "cammt_c2m_32":
            assert generated["bond_count"] == reference["bond_count"], case
            assert generated["angle_count"] == reference["angle_count"], case
        else:
            assert generated["bond_count"] < reference["bond_count"], case
        assert abs(calculate_net_charge(output_path) - reference["net_charge"]) <= 1e-8, case


def test_assign_file_accepts_periodic_xyz_input(tmp_path: Path) -> None:
    input_path = FIXTURES / "substitution_input" / "MMT_96W_rank1_d18.516.xyz"
    output_path = tmp_path / "mmt96_from_xyz.data"

    assign_file(input_path, output_path, default_clayff_path())

    assert output_path.exists()
    assert abs(calculate_net_charge(output_path)) <= 1e-3


def test_assignment_supports_extended_species_profiles() -> None:
    atoms = load_ase_atoms(FIXTURES / "substitution_input" / "cammt_c2m_32.cif")
    classification = classify_structure(atoms)
    modified = atoms.copy()
    symbols = modified.get_chemical_symbols()
    symbols[classification.octa_sites[0]] = "Fe"
    symbols[classification.interlayer_sites[0]] = "K"
    modified.set_chemical_symbols(symbols)

    structure = structure_from_ase_atoms(modified, "extended_species.cif")
    forcefield = load_clayff(default_clayff_path())
    assigned = assign_structure(structure, forcefield)
    assigned_types = {atom.ff_type for atom in assigned.atoms}

    assert "feo" in assigned_types
    assert "K" in assigned_types
