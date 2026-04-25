from __future__ import annotations

import warnings
from pathlib import Path

from clayff_toolkit.assignment import load_ase_atoms, load_structure


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "substitution_input"


def test_custom_cif_loading_avoids_ase_triclinic_warning() -> None:
    cif_path = FIXTURES / "cammt_c2m_32.cif"
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        atoms = load_ase_atoms(cif_path)
    assert atoms.pbc.all()
    assert not caught


def test_load_structure_preserves_triclinic_cell() -> None:
    structure = load_structure(FIXTURES / "cammt_c2m_32.cif")
    assert structure.cell.beta == 99.0
    assert len(structure.atoms) > 0
