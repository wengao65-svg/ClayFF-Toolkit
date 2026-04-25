"""Data-file validation for exported LAMMPS ClayFF data."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .charges import calculate_net_charge


@dataclass(frozen=True)
class DataValidationWarning:
    severity: str
    code: str
    message: str


@dataclass(frozen=True)
class DataValidationReport:
    atom_count: int
    bond_count: int
    angle_count: int
    atom_type_count: int
    bond_type_count: int
    angle_type_count: int
    net_charge: float
    warnings: tuple[DataValidationWarning, ...]


def _parse_header_counts(lines: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for line in lines[:30]:
        parts = line.split()
        if len(parts) >= 2 and parts[0].isdigit():
            label = " ".join(parts[1:])
            if label in {
                "atoms",
                "bonds",
                "angles",
                "atom types",
                "bond types",
                "angle types",
            }:
                counts[label] = int(parts[0])
    return counts


def _section_lines(lines: list[str], header: str) -> list[str]:
    if header not in lines:
        return []
    index = lines.index(header) + 2
    collected: list[str] = []
    while index < len(lines) and lines[index].strip():
        collected.append(lines[index])
        index += 1
    return collected


def validate_data_file(path: str | Path) -> DataValidationReport:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    counts = _parse_header_counts(lines)

    masses = _section_lines(lines, "Masses")
    pair_coeffs = _section_lines(lines, "Pair Coeffs # lj/cut/coul/long")
    atoms = _section_lines(lines, "Atoms # full")
    bonds = _section_lines(lines, "Bonds")
    angles = _section_lines(lines, "Angles")
    bond_coeffs = _section_lines(lines, "Bond Coeffs # harmonic")
    angle_coeffs = _section_lines(lines, "Angle Coeffs # harmonic")

    warnings: list[DataValidationWarning] = []

    required_sections = {
        "Masses": masses,
        "Pair Coeffs # lj/cut/coul/long": pair_coeffs,
        "Atoms # full": atoms,
    }
    for name, section in required_sections.items():
        if not section:
            warnings.append(
                DataValidationWarning(
                    severity="error",
                    code="missing-section",
                    message=f"Required section '{name}' is missing or empty.",
                )
            )

    if counts.get("atoms", 0) and counts["atoms"] != len(atoms):
        warnings.append(
            DataValidationWarning(
                severity="error",
                code="atom-count-mismatch",
                message=f"Header declares {counts['atoms']} atoms, but Atoms section contains {len(atoms)} lines.",
            )
        )
    if counts.get("bonds", 0) != len(bonds):
        warnings.append(
            DataValidationWarning(
                severity="warning" if counts.get("bonds", 0) == 0 and len(bonds) == 0 else "error",
                code="bond-count-mismatch",
                message=f"Header declares {counts.get('bonds', 0)} bonds, but Bonds section contains {len(bonds)} lines.",
            )
        )
    if counts.get("angles", 0) != len(angles):
        warnings.append(
            DataValidationWarning(
                severity="warning" if counts.get("angles", 0) == 0 and len(angles) == 0 else "error",
                code="angle-count-mismatch",
                message=f"Header declares {counts.get('angles', 0)} angles, but Angles section contains {len(angles)} lines.",
            )
        )

    mass_ids = {int(line.split()[0]) for line in masses if line.split()}
    pair_ids = {int(line.split()[0]) for line in pair_coeffs if line.split()}

    if mass_ids and pair_ids and mass_ids != pair_ids:
        warnings.append(
            DataValidationWarning(
                severity="error",
                code="type-id-mismatch",
                message="Masses and Pair Coeffs do not define the same atom type ids.",
            )
        )

    referenced_atom_types = {
        int(parts[2])
        for line in atoms
        if (parts := line.split()) and len(parts) >= 4 and parts[2].isdigit()
    }
    undefined_types = sorted(referenced_atom_types - mass_ids)
    if undefined_types:
        warnings.append(
            DataValidationWarning(
                severity="error",
                code="undefined-atom-types",
                message=f"Atoms section references undefined atom type ids: {undefined_types}.",
            )
        )

    if counts.get("bond types", 0) and not bond_coeffs:
        warnings.append(
            DataValidationWarning(
                severity="error",
                code="missing-bond-coeffs",
                message="Header declares bond types, but Bond Coeffs section is missing or empty.",
            )
        )
    if counts.get("angle types", 0) and not angle_coeffs:
        warnings.append(
            DataValidationWarning(
                severity="error",
                code="missing-angle-coeffs",
                message="Header declares angle types, but Angle Coeffs section is missing or empty.",
            )
        )

    net_charge = calculate_net_charge(path)
    if abs(net_charge) > 1e-3:
        warnings.append(
            DataValidationWarning(
                severity="warning",
                code="net-charge",
                message=f"Net charge is {net_charge:.6f} e, which should be reviewed before simulation.",
            )
        )

    return DataValidationReport(
        atom_count=len(atoms),
        bond_count=len(bonds),
        angle_count=len(angles),
        atom_type_count=len(mass_ids),
        bond_type_count=len(bond_coeffs),
        angle_type_count=len(angle_coeffs),
        net_charge=net_charge,
        warnings=tuple(warnings),
    )
