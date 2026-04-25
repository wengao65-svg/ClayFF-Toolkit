from __future__ import annotations

from pathlib import Path

from clayff_toolkit.assignment import load_ase_atoms
from clayff_toolkit.substitution.engine import classify_structure


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "substitution_input"


def test_substitution_classifier_finds_framework_sites() -> None:
    atoms = load_ase_atoms(FIXTURES / "cammt_c2m_32.cif")
    classification = classify_structure(atoms)

    assert classification.tetra_sites
    assert classification.octa_sites
    assert classification.interlayer_sites
