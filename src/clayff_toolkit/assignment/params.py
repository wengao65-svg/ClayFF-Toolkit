from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AtomTypeParameter:
    name: str
    mass: float
    element: str
    connections: int
    charge: float | None
    epsilon: float
    sigma: float


@dataclass(frozen=True)
class BondParameter:
    atom_type_a: str
    atom_type_b: str
    r0: float
    k2: float

    @property
    def canonical_name(self) -> str:
        return f"{self.atom_type_a}-{self.atom_type_b}"


@dataclass(frozen=True)
class AngleParameter:
    atom_type_a: str
    atom_type_b: str
    atom_type_c: str
    theta0: float
    k2: float

    @property
    def canonical_name(self) -> str:
        return f"{self.atom_type_a}-{self.atom_type_b}-{self.atom_type_c}"


@dataclass(frozen=True)
class ClayFFParameters:
    atom_types: dict[str, AtomTypeParameter]
    bonds: dict[tuple[str, str], BondParameter]
    angles: dict[tuple[str, str, str], AngleParameter]
    atom_type_order: tuple[str, ...]

    def require_atom_type(self, atom_type: str) -> AtomTypeParameter:
        try:
            return self.atom_types[atom_type]
        except KeyError as exc:
            raise KeyError(f"ClayFF atom type not found: {atom_type}") from exc

    def get_bond(self, atom_type_a: str, atom_type_b: str) -> BondParameter:
        for key in ((atom_type_a, atom_type_b), (atom_type_b, atom_type_a)):
            if key in self.bonds:
                return self.bonds[key]
        raise KeyError(f"ClayFF bond parameter not found: {atom_type_a}-{atom_type_b}")

    def get_angle(
        self, atom_type_a: str, atom_type_b: str, atom_type_c: str
    ) -> AngleParameter:
        for key in (
            (atom_type_a, atom_type_b, atom_type_c),
            (atom_type_c, atom_type_b, atom_type_a),
        ):
            if key in self.angles:
                return self.angles[key]
        raise KeyError(
            f"ClayFF angle parameter not found: {atom_type_a}-{atom_type_b}-{atom_type_c}"
        )


def _parse_float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def _ab_to_epsilon_sigma(a_coeff: float, b_coeff: float) -> tuple[float, float]:
    if a_coeff <= 0.0 or b_coeff <= 0.0:
        return (0.0, 0.0)
    sigma = (a_coeff / b_coeff) ** (1.0 / 6.0)
    epsilon = (b_coeff * b_coeff) / (4.0 * a_coeff)
    return (epsilon, sigma)


def load_clayff(path: str | Path) -> ClayFFParameters:
    ff_path = Path(path)
    lines = ff_path.read_text(encoding="utf-8").splitlines()

    atom_types_raw: dict[str, dict[str, float | str | None]] = {}
    nonbond: dict[str, tuple[float, float]] = {}
    bonds: dict[tuple[str, str], BondParameter] = {}
    angles: dict[tuple[str, str, str], AngleParameter] = {}
    atom_type_order: list[str] = []

    section = ""
    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("!") or stripped.startswith(">"):
            continue
        if stripped.startswith("#"):
            section = stripped.lower()
            continue
        if stripped.startswith("@"):
            continue

        parts = stripped.split()
        if section.startswith("#atom_types"):
            if len(parts) < 6:
                continue
            atom_type = parts[2]
            charge = _parse_float(parts[-1])
            atom_types_raw[atom_type] = {
                "mass": float(parts[3]),
                "element": parts[4],
                "connections": int(parts[5]),
                "charge": charge,
            }
            atom_type_order.append(atom_type)
        elif section.startswith("#quadratic_bond"):
            if len(parts) < 5:
                continue
            bond = BondParameter(
                atom_type_a=parts[2],
                atom_type_b=parts[3],
                r0=float(parts[4]),
                k2=float(parts[5]),
            )
            bonds[(bond.atom_type_a, bond.atom_type_b)] = bond
        elif section.startswith("#quadratic_angle"):
            if len(parts) < 6:
                continue
            angle = AngleParameter(
                atom_type_a=parts[2],
                atom_type_b=parts[3],
                atom_type_c=parts[4],
                theta0=float(parts[5]),
                k2=float(parts[6]),
            )
            angles[(angle.atom_type_a, angle.atom_type_b, angle.atom_type_c)] = angle
        elif section.startswith("#nonbond"):
            if len(parts) < 5:
                continue
            nonbond[parts[2]] = (float(parts[3]), float(parts[4]))

    atom_types: dict[str, AtomTypeParameter] = {}
    for atom_type, raw in atom_types_raw.items():
        a_coeff, b_coeff = nonbond.get(atom_type, (0.0, 0.0))
        epsilon, sigma = _ab_to_epsilon_sigma(a_coeff, b_coeff)
        atom_types[atom_type] = AtomTypeParameter(
            name=atom_type,
            mass=float(raw["mass"]),
            element=str(raw["element"]),
            connections=int(raw["connections"]),
            charge=raw["charge"] if isinstance(raw["charge"], float) else None,
            epsilon=epsilon,
            sigma=sigma,
        )

    return ClayFFParameters(
        atom_types=atom_types,
        bonds=bonds,
        angles=angles,
        atom_type_order=tuple(atom_type_order),
    )
