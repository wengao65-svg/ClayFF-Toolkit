from __future__ import annotations

from pathlib import Path

from clayff_toolkit.assignment import audit_material_studio_off, default_clayff_path, load_clayff
from clayff_toolkit.cli import main


def _write_matching_off(path: Path) -> None:
    forcefield = load_clayff(default_clayff_path())
    types = [
        forcefield.atom_types[name]
        for name in forcefield.atom_type_order
        if forcefield.atom_types[name].charge is not None
    ]

    lines = [
        "VERSION",
        " Materials Studio    1",
        "END",
        "#",
        "HEADER",
        " Test ClayFF OFF",
        "END",
        "#",
        "PREFERENCES",
        " BONDS T",
        " ANGLES T",
        " COULOMB T",
        " VDW_COMBINATION_RULE GEOMETRIC",
        " ATOM_TYPING_ENGINE OFF",
        "END",
        "#",
        "ATOMTYPES",
        " X X 0.0 0.0 non 0 non",
    ]
    lines.extend(
        f" {item.name} {item.element} {item.mass:.12g} {item.charge:.12g} non {item.connections} non"
        for item in types
    )
    lines.extend(["END", "#"])

    for section in (
        "EQUIVALENCE_BOND",
        "EQUIVALENCE_ANGLE",
        "EQUIVALENCE_COULOMBIC",
        "EQUIVALENCE_OFF_DIAGONAL_VDW",
    ):
        lines.append(section)
        lines.extend(f" {item.name} ALL {item.name} X" for item in types)
        lines.extend(["END", "#"])

    lines.extend(["DIAGONAL_VDW", " X IGNORE 0.1"])
    for item in types:
        if item.epsilon == 0.0 or item.sigma == 0.0:
            lines.append(f" {item.name} IGNORE 0.1")
        else:
            radius = (2.0 ** (1.0 / 6.0)) * item.sigma
            lines.append(f" {item.name} LJ_6_12 {radius:.15g} {item.epsilon:.15g}")
    lines.extend(["END", "#", "BOND_STRETCH"])
    lines.extend(
        f" {item.atom_type_a} {item.atom_type_b} HARMONIC {2.0 * item.k2:.12g} {item.r0:.12g}"
        for item in forcefield.bonds.values()
    )
    lines.extend(["END", "#", "ANGLE_BEND"])
    lines.extend(
        f" {item.atom_type_a} {item.atom_type_b} {item.atom_type_c} THETA_HARM {2.0 * item.k2:.12g} {item.theta0:.12g}"
        for item in forcefield.angles.values()
    )
    lines.extend(["END", "#", "COULOMBIC", " X X CONST-EPS", "END", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def test_material_studio_off_audit_accepts_matching_forcefield(tmp_path: Path) -> None:
    off_path = tmp_path / "clayff.off"
    _write_matching_off(off_path)

    report = audit_material_studio_off(off_path, default_clayff_path())

    assert report.is_valid
    assert report.error_count == 0
    assert report.warning_count == 0
    assert report.atom_type_count == 27
    assert report.expected_atom_type_count == 27
    assert report.bond_count == 3
    assert report.angle_count == 1


def test_material_studio_off_audit_reports_parameter_difference(tmp_path: Path) -> None:
    off_path = tmp_path / "clayff.off"
    _write_matching_off(off_path)
    text = off_path.read_text(encoding="utf-8")
    off_path.write_text(text.replace(" st Si 28.0855 2.1", " st Si 28.0855 9.9", 1), encoding="utf-8")

    report = audit_material_studio_off(off_path, default_clayff_path())

    assert not report.is_valid
    assert any(issue.code == "charge-mismatch" and "st" in issue.message for issue in report.issues)


def test_audit_ms_off_cli_returns_nonzero_for_invalid_file(tmp_path: Path, capsys) -> None:
    off_path = tmp_path / "clayff.off"
    _write_matching_off(off_path)
    text = off_path.read_text(encoding="utf-8")
    off_path.write_text(text.replace(" ATOM_TYPING_ENGINE OFF", " ATOM_TYPING_ENGINE GATE1"), encoding="utf-8")

    exit_code = main(["audit-ms-off", str(off_path)])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "errors=1" in captured.out
    assert "preference-mismatch" in captured.out
