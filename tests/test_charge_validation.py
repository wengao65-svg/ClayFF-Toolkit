from __future__ import annotations

from pathlib import Path

from clayff_toolkit.validation import calculate_net_charge, parse_atoms_section_charges


REFERENCE_DIR = Path(__file__).resolve().parent / "fixtures" / "assignment_reference"


def test_charge_parser_reads_full_atoms_section() -> None:
    data_path = REFERENCE_DIR / "MMT_0W_rank3_d9.545.data"
    charges = parse_atoms_section_charges(data_path)
    assert len(charges) == 323
    assert abs(sum(charges)) <= 1e-3


def test_calculate_net_charge_matches_reference_file() -> None:
    data_path = REFERENCE_DIR / "test.data"
    assert abs(calculate_net_charge(data_path)) <= 1e-3
