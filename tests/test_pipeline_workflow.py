from __future__ import annotations

from pathlib import Path

from clayff_toolkit.pipeline import ToolkitPipeline


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_substitute_assign_validate_runs_end_to_end(tmp_path: Path) -> None:
    input_path = FIXTURES / "substitution_input" / "cammt_c2m_32.cif"
    substituted_path = tmp_path / "cammt_substituted.cif"
    data_path = tmp_path / "cammt_substituted.data"

    result = ToolkitPipeline().substitute_assign_validate(
        input_path=input_path,
        substituted_structure_path=substituted_path,
        output_path=data_path,
        preset="octa-only",
        interlayer_species="Ca",
    )

    assert substituted_path.exists()
    assert data_path.exists()
    assert result.substituted_path == substituted_path
    assert result.substitution_log is not None
    assert result.substitution_log["rule"] == "octa-only"
    assert result.substitution_log["charge_balance"]["interlayer_species"] == "Ca"
    assert abs(result.net_charge) <= 1e-3
