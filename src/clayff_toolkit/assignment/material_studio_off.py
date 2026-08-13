"""Materials Studio OFF parsing and ClayFF consistency auditing."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import re
from typing import Literal

from .params import ClayFFParameters, load_clayff


AuditSeverity = Literal["error", "warning"]


@dataclass(frozen=True)
class MaterialStudioOffAtomType:
    name: str
    element: str
    mass: float
    charge: float
    connections: int


@dataclass(frozen=True)
class MaterialStudioOffVdw:
    atom_type: str
    model: str
    radius: float | None
    epsilon: float | None


@dataclass(frozen=True)
class MaterialStudioOffBond:
    atom_type_a: str
    atom_type_b: str
    model: str
    force_constant: float
    equilibrium_distance: float


@dataclass(frozen=True)
class MaterialStudioOffAngle:
    atom_type_a: str
    atom_type_b: str
    atom_type_c: str
    model: str
    force_constant: float
    equilibrium_angle: float


@dataclass(frozen=True)
class MaterialStudioOffDocument:
    path: Path
    preferences: dict[str, str]
    atom_types: dict[str, MaterialStudioOffAtomType]
    diagonal_vdw: dict[str, MaterialStudioOffVdw]
    bonds: dict[tuple[str, str], MaterialStudioOffBond]
    angles: dict[tuple[str, str, str], MaterialStudioOffAngle]
    equivalence_types: dict[str, frozenset[str]]
    sections: frozenset[str]
    coulombic_model: str | None


@dataclass(frozen=True)
class MaterialStudioOffAuditIssue:
    severity: AuditSeverity
    code: str
    message: str


@dataclass(frozen=True)
class MaterialStudioOffAuditReport:
    off_path: Path
    clayff_path: Path
    atom_type_count: int
    expected_atom_type_count: int
    bond_count: int
    angle_count: int
    issues: tuple[MaterialStudioOffAuditIssue, ...]

    @property
    def error_count(self) -> int:
        return sum(issue.severity == "error" for issue in self.issues)

    @property
    def warning_count(self) -> int:
        return sum(issue.severity == "warning" for issue in self.issues)

    @property
    def is_valid(self) -> bool:
        return self.error_count == 0


_SECTION_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
_REQUIRED_SECTIONS = {
    "VERSION",
    "HEADER",
    "PREFERENCES",
    "ATOMTYPES",
    "EQUIVALENCE_BOND",
    "EQUIVALENCE_ANGLE",
    "EQUIVALENCE_COULOMBIC",
    "EQUIVALENCE_OFF_DIAGONAL_VDW",
    "DIAGONAL_VDW",
    "BOND_STRETCH",
    "ANGLE_BEND",
    "COULOMBIC",
}


def _strip_comment(line: str) -> str:
    return line.split("!", 1)[0].strip()


def _read_sections(path: Path) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    active: str | None = None
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped == "#":
            continue
        if active is None:
            if _SECTION_NAME.fullmatch(stripped):
                active = stripped
                if active in sections:
                    raise ValueError(f"Duplicate Materials Studio OFF section {active} at line {line_number}.")
                sections[active] = []
            continue
        if stripped == "END":
            active = None
            continue
        sections[active].append(raw_line.rstrip())
    if active is not None:
        raise ValueError(f"Materials Studio OFF section {active} is missing END.")
    return sections


def _parse_preferences(lines: list[str]) -> dict[str, str]:
    preferences: dict[str, str] = {}
    for raw_line in lines:
        line = _strip_comment(raw_line)
        if not line:
            continue
        key, separator, value = line.partition(" ")
        if separator:
            preferences[key] = value.strip()
    return preferences


def _parse_atom_types(lines: list[str]) -> dict[str, MaterialStudioOffAtomType]:
    atom_types: dict[str, MaterialStudioOffAtomType] = {}
    for raw_line in lines:
        parts = _strip_comment(raw_line).split()
        if not parts:
            continue
        if len(parts) < 6:
            raise ValueError(f"Invalid Materials Studio OFF ATOMTYPES row: {raw_line.strip()}")
        name = parts[0]
        if name in atom_types:
            raise ValueError(f"Duplicate Materials Studio OFF atom type: {name}")
        try:
            atom_types[name] = MaterialStudioOffAtomType(
                name=name,
                element=parts[1],
                mass=float(parts[2]),
                charge=float(parts[3]),
                connections=int(parts[5]),
            )
        except ValueError as exc:
            raise ValueError(f"Invalid Materials Studio OFF ATOMTYPES row: {raw_line.strip()}") from exc
    return atom_types


def _parse_vdw(lines: list[str]) -> dict[str, MaterialStudioOffVdw]:
    entries: dict[str, MaterialStudioOffVdw] = {}
    for raw_line in lines:
        parts = _strip_comment(raw_line).split()
        if not parts:
            continue
        if len(parts) < 3:
            raise ValueError(f"Invalid Materials Studio OFF DIAGONAL_VDW row: {raw_line.strip()}")
        atom_type, model = parts[:2]
        if atom_type in entries:
            raise ValueError(f"Duplicate Materials Studio OFF DIAGONAL_VDW type: {atom_type}")
        try:
            if model == "IGNORE":
                radius = float(parts[2])
                epsilon = None
            elif model == "LJ_6_12" and len(parts) >= 4:
                radius = float(parts[2])
                epsilon = float(parts[3])
            else:
                radius = float(parts[2]) if len(parts) >= 3 else None
                epsilon = float(parts[3]) if len(parts) >= 4 else None
        except ValueError as exc:
            raise ValueError(f"Invalid Materials Studio OFF DIAGONAL_VDW row: {raw_line.strip()}") from exc
        entries[atom_type] = MaterialStudioOffVdw(atom_type, model, radius, epsilon)
    return entries


def _parse_bonds(lines: list[str]) -> dict[tuple[str, str], MaterialStudioOffBond]:
    bonds: dict[tuple[str, str], MaterialStudioOffBond] = {}
    for raw_line in lines:
        parts = _strip_comment(raw_line).split()
        if not parts:
            continue
        if len(parts) < 5:
            raise ValueError(f"Invalid Materials Studio OFF BOND_STRETCH row: {raw_line.strip()}")
        try:
            bond = MaterialStudioOffBond(
                atom_type_a=parts[0],
                atom_type_b=parts[1],
                model=parts[2],
                force_constant=float(parts[3]),
                equilibrium_distance=float(parts[4]),
            )
        except ValueError as exc:
            raise ValueError(f"Invalid Materials Studio OFF BOND_STRETCH row: {raw_line.strip()}") from exc
        key = tuple(sorted((bond.atom_type_a, bond.atom_type_b)))
        if key in bonds:
            raise ValueError(f"Duplicate Materials Studio OFF bond parameter: {'-'.join(key)}")
        bonds[key] = bond
    return bonds


def _parse_angles(lines: list[str]) -> dict[tuple[str, str, str], MaterialStudioOffAngle]:
    angles: dict[tuple[str, str, str], MaterialStudioOffAngle] = {}
    for raw_line in lines:
        parts = _strip_comment(raw_line).split()
        if not parts:
            continue
        if len(parts) < 6:
            raise ValueError(f"Invalid Materials Studio OFF ANGLE_BEND row: {raw_line.strip()}")
        try:
            angle = MaterialStudioOffAngle(
                atom_type_a=parts[0],
                atom_type_b=parts[1],
                atom_type_c=parts[2],
                model=parts[3],
                force_constant=float(parts[4]),
                equilibrium_angle=float(parts[5]),
            )
        except ValueError as exc:
            raise ValueError(f"Invalid Materials Studio OFF ANGLE_BEND row: {raw_line.strip()}") from exc
        ends = sorted((angle.atom_type_a, angle.atom_type_c))
        key = (ends[0], angle.atom_type_b, ends[1])
        if key in angles:
            raise ValueError(f"Duplicate Materials Studio OFF angle parameter: {'-'.join(key)}")
        angles[key] = angle
    return angles


def _parse_equivalence_types(sections: dict[str, list[str]]) -> dict[str, frozenset[str]]:
    result: dict[str, frozenset[str]] = {}
    for section in (
        "EQUIVALENCE_BOND",
        "EQUIVALENCE_ANGLE",
        "EQUIVALENCE_COULOMBIC",
        "EQUIVALENCE_OFF_DIAGONAL_VDW",
    ):
        names: set[str] = set()
        for raw_line in sections.get(section, []):
            parts = _strip_comment(raw_line).split()
            if parts and parts[0] not in {"END", "CENTER"}:
                names.add(parts[0])
        result[section] = frozenset(names)
    return result


def load_material_studio_off(path: str | Path) -> MaterialStudioOffDocument:
    """Parse the ClayFF-relevant parts of a Materials Studio OFF file."""

    off_path = Path(path)
    try:
        sections = _read_sections(off_path)
    except OSError as exc:
        raise ValueError(f"Unable to read Materials Studio OFF: {off_path}") from exc
    coulombic_model = None
    for raw_line in sections.get("COULOMBIC", []):
        parts = _strip_comment(raw_line).split()
        if len(parts) >= 3:
            coulombic_model = parts[2]
            break
    return MaterialStudioOffDocument(
        path=off_path,
        preferences=_parse_preferences(sections.get("PREFERENCES", [])),
        atom_types=_parse_atom_types(sections.get("ATOMTYPES", [])),
        diagonal_vdw=_parse_vdw(sections.get("DIAGONAL_VDW", [])),
        bonds=_parse_bonds(sections.get("BOND_STRETCH", [])),
        angles=_parse_angles(sections.get("ANGLE_BEND", [])),
        equivalence_types=_parse_equivalence_types(sections),
        sections=frozenset(sections),
        coulombic_model=coulombic_model,
    )


def _close(actual: float, expected: float, *, absolute: float = 1.0e-6, relative: float = 1.0e-6) -> bool:
    return math.isclose(actual, expected, abs_tol=absolute, rel_tol=relative)


def audit_material_studio_off(
    off_path: str | Path,
    clayff_path: str | Path,
) -> MaterialStudioOffAuditReport:
    """Audit a Materials Studio OFF against the toolkit ClayFF parameter source."""

    off = load_material_studio_off(off_path)
    source_path = Path(clayff_path)
    forcefield: ClayFFParameters = load_clayff(source_path)
    issues: list[MaterialStudioOffAuditIssue] = []

    def add(severity: AuditSeverity, code: str, message: str) -> None:
        issues.append(MaterialStudioOffAuditIssue(severity, code, message))

    for section in sorted(_REQUIRED_SECTIONS - off.sections):
        add("error", "missing-section", f"Missing required OFF section: {section}")

    expected_preferences = {
        "BONDS": "T",
        "ANGLES": "T",
        "COULOMB": "T",
        "VDW_COMBINATION_RULE": "GEOMETRIC",
        "ATOM_TYPING_ENGINE": "OFF",
    }
    for key, expected in expected_preferences.items():
        actual = off.preferences.get(key)
        if actual != expected:
            add("error", "preference-mismatch", f"{key}: expected {expected}, found {actual or 'missing'}")
    if off.coulombic_model != "CONST-EPS":
        add("error", "coulombic-model", f"COULOMBIC model must be CONST-EPS, found {off.coulombic_model or 'missing'}")

    expected_types = {
        name: parameter
        for name, parameter in forcefield.atom_types.items()
        if parameter.charge is not None
    }
    missing_types = sorted(set(expected_types) - set(off.atom_types))
    for atom_type in missing_types:
        add("error", "missing-atom-type", f"Missing ClayFF atom type: {atom_type}")
    extra_types = sorted(set(off.atom_types) - set(expected_types) - {"X"})
    for atom_type in extra_types:
        add("warning", "extra-atom-type", f"OFF contains an atom type not present in the ClayFF source: {atom_type}")

    for name, expected in expected_types.items():
        actual = off.atom_types.get(name)
        if actual is None:
            continue
        if actual.element != expected.element:
            add("error", "element-mismatch", f"{name}: expected element {expected.element}, found {actual.element}")
        if not _close(actual.mass, expected.mass, absolute=5.0e-4):
            add("error", "mass-mismatch", f"{name}: expected mass {expected.mass:.8g}, found {actual.mass:.8g}")
        if actual.connections != expected.connections:
            add("error", "connections-mismatch", f"{name}: expected {expected.connections} connections, found {actual.connections}")
        if not _close(actual.charge, float(expected.charge), absolute=1.0e-7):
            add("error", "charge-mismatch", f"{name}: expected charge {expected.charge:.8g}, found {actual.charge:.8g}")

        vdw = off.diagonal_vdw.get(name)
        if vdw is None:
            add("error", "missing-vdw", f"Missing DIAGONAL_VDW entry for {name}")
        elif expected.epsilon == 0.0 or expected.sigma == 0.0:
            if vdw.model != "IGNORE":
                add("error", "vdw-model", f"{name}: expected IGNORE VDW, found {vdw.model}")
        else:
            expected_radius = (2.0 ** (1.0 / 6.0)) * expected.sigma
            if vdw.model != "LJ_6_12":
                add("error", "vdw-model", f"{name}: expected LJ_6_12, found {vdw.model}")
            else:
                if vdw.radius is None or not _close(vdw.radius, expected_radius, absolute=2.0e-8):
                    add("error", "vdw-radius", f"{name}: expected LJ radius {expected_radius:.12g}, found {vdw.radius}")
                if vdw.epsilon is None or not _close(vdw.epsilon, expected.epsilon, absolute=2.0e-9):
                    add("error", "vdw-epsilon", f"{name}: expected epsilon {expected.epsilon:.12g}, found {vdw.epsilon}")

    for section, names in off.equivalence_types.items():
        for atom_type in sorted(set(expected_types) - names):
            add("error", "missing-equivalence", f"{section} has no entry for {atom_type}")

    for expected in forcefield.bonds.values():
        key = tuple(sorted((expected.atom_type_a, expected.atom_type_b)))
        actual = off.bonds.get(key)
        if actual is None:
            add("error", "missing-bond", f"Missing bond parameter: {expected.canonical_name}")
            continue
        if actual.model != "HARMONIC":
            add("error", "bond-model", f"{expected.canonical_name}: expected HARMONIC, found {actual.model}")
        if not _close(actual.force_constant, 2.0 * expected.k2, absolute=1.0e-6):
            add("error", "bond-force-constant", f"{expected.canonical_name}: expected {2.0 * expected.k2:.8g}, found {actual.force_constant:.8g}")
        if not _close(actual.equilibrium_distance, expected.r0, absolute=1.0e-7):
            add("error", "bond-distance", f"{expected.canonical_name}: expected {expected.r0:.8g}, found {actual.equilibrium_distance:.8g}")

    for expected in forcefield.angles.values():
        ends = sorted((expected.atom_type_a, expected.atom_type_c))
        key = (ends[0], expected.atom_type_b, ends[1])
        actual = off.angles.get(key)
        if actual is None:
            add("error", "missing-angle", f"Missing angle parameter: {expected.canonical_name}")
            continue
        if actual.model != "THETA_HARM":
            add("error", "angle-model", f"{expected.canonical_name}: expected THETA_HARM, found {actual.model}")
        if not _close(actual.force_constant, 2.0 * expected.k2, absolute=1.0e-6):
            add("error", "angle-force-constant", f"{expected.canonical_name}: expected {2.0 * expected.k2:.8g}, found {actual.force_constant:.8g}")
        if not _close(actual.equilibrium_angle, expected.theta0, absolute=1.0e-7):
            add("error", "angle-equilibrium", f"{expected.canonical_name}: expected {expected.theta0:.8g}, found {actual.equilibrium_angle:.8g}")

    return MaterialStudioOffAuditReport(
        off_path=off.path,
        clayff_path=source_path,
        atom_type_count=len(set(off.atom_types) - {"X"}),
        expected_atom_type_count=len(expected_types),
        bond_count=len(off.bonds),
        angle_count=len(off.angles),
        issues=tuple(issues),
    )
