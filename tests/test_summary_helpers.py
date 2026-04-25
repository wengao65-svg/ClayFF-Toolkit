from __future__ import annotations

from pathlib import Path

from clayff_toolkit.assignment import (
    assign_structure_file,
    default_clayff_path,
    summarize_assignment,
    summarize_structure,
)
from clayff_toolkit.validation import summarize_data_file


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_structure_and_assignment_summaries_are_consistent() -> None:
    structure_path = FIXTURES / "substitution_input" / "cammt_c2m_32.cif"
    structure, assigned, _ = assign_structure_file(structure_path, default_clayff_path())

    structure_summary = summarize_structure(structure)
    assignment_summary = summarize_assignment(assigned)

    assert structure_summary.atom_count == assignment_summary.atom_count
    assert structure_summary.element_counts["Si"] > 0
    assert assignment_summary.ff_type_counts["st"] > 0
    assert abs(assignment_summary.net_charge) <= 1e-3


def test_data_file_summary_reads_reference_counts() -> None:
    data_path = FIXTURES / "assignment_reference" / "MMT_64W_rank1_d15.183.data"
    summary = summarize_data_file(data_path)

    assert summary.atom_count == 515
    assert summary.bond_count == 160
    assert summary.angle_count == 64
    assert summary.atom_type_counts["o*"] == 64
