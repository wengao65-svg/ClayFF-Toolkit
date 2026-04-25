from __future__ import annotations

from pathlib import Path

from clayff_toolkit.assignment import assign_structure_file, default_clayff_path, infer_mineral_profiles
from clayff_toolkit.validation import validate_assigned_structure


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_montmorillonite_fixture_prefers_montmorillonite_profile() -> None:
    structure_path = FIXTURES / "assignment_input" / "MMT_64W_rank1_d15.183.cif"
    _, assigned, _ = assign_structure_file(structure_path, default_clayff_path())
    matches = infer_mineral_profiles(assigned)

    assert matches[0].profile.key == "montmorillonite"


def test_validation_report_exposes_profile_and_warnings() -> None:
    structure_path = FIXTURES / "substitution_input" / "cammt_c2m_32.cif"
    _, assigned, _ = assign_structure_file(structure_path, default_clayff_path())
    report = validate_assigned_structure(assigned)

    assert report.inferred_profile.profile.display_name
    assert 0.0 <= report.confidence <= 1.0
    assert report.alternatives
