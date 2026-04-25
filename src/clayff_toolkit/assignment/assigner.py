from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .cif import AtomSite, CifStructure
from .params import ClayFFParameters


TETRA_O_CUTOFF = 1.85
OCTA_O_CUTOFF = 2.35
H_O_CUTOFF = 1.30
INTERLAYER_TYPES = {
    "Na": "Na",
    "K": "K",
    "Cs": "Cs",
    "Ca": "Ca",
    "Ba": "Ba",
    "Sr": "Sr",
    "Pb": "Pb",
    "Cl": "Cl",
}
SUBSTITUTED_OCTA_TYPES = {"mgo", "feo", "lio"}


@dataclass(frozen=True)
class AssignedAtom:
    index: int
    label: str
    element: str
    frac: tuple[float, float, float]
    output_frac: tuple[float, float, float]
    ff_type: str
    charge: float


@dataclass(frozen=True)
class BondRecord:
    index: int
    bond_type: str
    atom1_id: int
    atom2_id: int


@dataclass(frozen=True)
class AngleRecord:
    index: int
    angle_type: str
    atom1_id: int
    atom2_id: int
    atom3_id: int


@dataclass(frozen=True)
class AssignedStructure:
    title: str
    source_path: Path
    cell: CifStructure
    atoms: tuple[AssignedAtom, ...]
    bonds: tuple[BondRecord, ...]
    angles: tuple[AngleRecord, ...]


def _sorted_oxygen_distances(structure: CifStructure, atom: AtomSite) -> list[float]:
    distances = [
        structure.cell.distance(atom.frac, other.frac)
        for other in structure.atoms
        if other.element == "O"
    ]
    return sorted(distances)


def _classify_cation(structure: CifStructure, atom: AtomSite) -> str:
    distances = _sorted_oxygen_distances(structure, atom)
    if atom.element == "Si":
        return "st"
    if atom.element in INTERLAYER_TYPES:
        return INTERLAYER_TYPES[atom.element]
    if atom.element == "Mg":
        if len(distances) >= 6 and distances[5] <= OCTA_O_CUTOFF:
            return "mgo"
        return "Mg"
    if atom.element == "Fe":
        if len(distances) >= 6 and distances[5] <= OCTA_O_CUTOFF:
            return "feo"
        raise ValueError(
            f"Unable to classify Fe site {atom.label}: nearest O distances={distances[:7]}"
        )
    if atom.element == "Li":
        if len(distances) >= 6 and distances[5] <= OCTA_O_CUTOFF:
            return "lio"
        raise ValueError(
            f"Unable to classify Li site {atom.label}: nearest O distances={distances[:7]}"
        )
    if atom.element == "Al":
        if len(distances) >= 5 and distances[3] <= TETRA_O_CUTOFF and distances[4] > 2.50:
            return "at"
        if len(distances) >= 6 and distances[5] <= OCTA_O_CUTOFF:
            return "ao"
        raise ValueError(
            f"Unable to classify Al site {atom.label}: nearest O distances={distances[:7]}"
        )
    raise ValueError(f"Unsupported cation element: {atom.element} ({atom.label})")


def _build_hydrogen_owners(structure: CifStructure) -> tuple[dict[int, int], dict[int, list[int]]]:
    oxygens = [atom for atom in structure.atoms if atom.element == "O"]
    hydrogen_to_oxygen: dict[int, int] = {}
    oxygen_to_hydrogen: dict[int, list[int]] = {atom.index: [] for atom in oxygens}

    for atom in structure.atoms:
        if atom.element != "H":
            continue
        distances = sorted(
            (
                structure.cell.distance(atom.frac, oxygen.frac),
                oxygen.index,
            )
            for oxygen in oxygens
        )
        if not distances or distances[0][0] > H_O_CUTOFF:
            raise ValueError(
                f"Unable to find bonded oxygen for H site {atom.label}: nearest O distance={distances[0][0] if distances else 'N/A'}"
            )
        oxygen_index = distances[0][1]
        hydrogen_to_oxygen[atom.index] = oxygen_index
        oxygen_to_hydrogen[oxygen_index].append(atom.index)

    for oxygen_index, hydrogens in oxygen_to_hydrogen.items():
        if len(hydrogens) > 2:
            raise ValueError(
                f"Oxygen atom {oxygen_index} has {len(hydrogens)} bonded hydrogens; this is outside the supported ClayFF patterns."
            )
        hydrogens.sort()

    return hydrogen_to_oxygen, oxygen_to_hydrogen


def assign_structure(
    structure: CifStructure,
    forcefield: ClayFFParameters,
) -> AssignedStructure:
    supported = {
        "Si",
        "Al",
        "Mg",
        "Fe",
        "Li",
        "Na",
        "K",
        "Cs",
        "Ca",
        "Ba",
        "Sr",
        "Pb",
        "Cl",
        "O",
        "H",
    }
    unsupported = sorted({atom.element for atom in structure.atoms if atom.element not in supported})
    if unsupported:
        raise ValueError(
            f"Unsupported elements in {structure.path.name}: {', '.join(unsupported)}"
        )

    atom_lookup = {atom.index: atom for atom in structure.atoms}
    hydrogen_to_oxygen, oxygen_to_hydrogen = _build_hydrogen_owners(structure)

    cation_types: dict[int, str] = {}
    for atom in structure.atoms:
        if atom.element not in {"O", "H"}:
            cation_types[atom.index] = _classify_cation(structure, atom)

    oxygen_types: dict[int, str] = {}
    for atom in structure.atoms:
        if atom.element != "O":
            continue

        hydrogen_count = len(oxygen_to_hydrogen[atom.index])
        tetra_neighbors: list[str] = []
        octa_neighbors: list[str] = []

        for cation_index, cation_type in cation_types.items():
            cation = atom_lookup[cation_index]
            distance = structure.cell.distance(atom.frac, cation.frac)
            if cation_type in {"st", "at"} and distance <= TETRA_O_CUTOFF:
                tetra_neighbors.append(cation_type)
            elif cation_type in {"ao", "mgo"} and distance <= OCTA_O_CUTOFF:
                octa_neighbors.append(cation_type)

        has_at = "at" in tetra_neighbors
        has_substituted_octa = any(cation_type in SUBSTITUTED_OCTA_TYPES for cation_type in octa_neighbors)

        if hydrogen_count == 2:
            oxygen_type = "o*"
        elif hydrogen_count == 1:
            oxygen_type = "ohs" if has_substituted_octa else "oh"
        elif hydrogen_count == 0:
            if has_at and has_substituted_octa and "obss" in forcefield.atom_types:
                oxygen_type = "obss"
            elif has_at:
                oxygen_type = "obts"
            elif has_substituted_octa:
                oxygen_type = "obos"
            else:
                oxygen_type = "ob"
        else:
            raise ValueError(
                f"Oxygen {atom.label} has unsupported hydrogen count: {hydrogen_count}"
            )
        oxygen_types[atom.index] = oxygen_type

    assigned_atoms: list[AssignedAtom] = []
    bonds: list[BondRecord] = []
    angles: list[AngleRecord] = []

    output_frac: dict[int, tuple[float, float, float]] = {}
    for atom in structure.atoms:
        if atom.element != "H":
            output_frac[atom.index] = structure.cell.wrap_frac(atom.frac)

    for atom in structure.atoms:
        if atom.element != "H":
            continue
        oxygen_index = hydrogen_to_oxygen[atom.index]
        oxygen = atom_lookup[oxygen_index]
        oxygen_output_frac = output_frac[oxygen_index]
        delta = structure.cell.minimum_image_delta(oxygen.frac, atom.frac)
        output_frac[atom.index] = tuple(
            oxygen_output_frac[axis] + delta[axis] for axis in range(3)
        )

    for atom in structure.atoms:
        if atom.element not in {"O", "H"}:
            ff_type = cation_types[atom.index]
        elif atom.element == "O":
            ff_type = oxygen_types[atom.index]
        elif atom.element == "H":
            oxygen_index = hydrogen_to_oxygen[atom.index]
            oxygen_type = oxygen_types[oxygen_index]
            if oxygen_type == "o*":
                ff_type = "h*"
            elif oxygen_type in {"oh", "ohs"}:
                ff_type = "ho"
            else:
                raise ValueError(
                    f"Hydrogen {atom.label} attached to unsupported oxygen type {oxygen_type}"
                )
        else:
            raise ValueError(f"Unsupported element during assignment: {atom.element}")

        parameter = forcefield.require_atom_type(ff_type)
        if parameter.charge is None:
            raise ValueError(f"ClayFF atom type {ff_type} has no defined charge.")

        assigned_atoms.append(
            AssignedAtom(
                index=atom.index,
                label=atom.label,
                element=atom.element,
                frac=atom.frac,
                output_frac=output_frac[atom.index],
                ff_type=ff_type,
                charge=parameter.charge,
            )
        )

    assigned_lookup = {atom.index: atom for atom in assigned_atoms}
    for oxygen_index, hydrogen_ids in sorted(oxygen_to_hydrogen.items()):
        oxygen = assigned_lookup[oxygen_index]
        if oxygen.ff_type == "o*":
            if len(hydrogen_ids) != 2:
                raise ValueError(
                    f"Water oxygen {oxygen.label} must have 2 bonded hydrogens, found {len(hydrogen_ids)}"
                )
            for hydrogen_id in hydrogen_ids:
                bonds.append(
                    BondRecord(
                        index=len(bonds) + 1,
                        bond_type="o*-h*",
                        atom1_id=oxygen_index,
                        atom2_id=hydrogen_id,
                    )
                )
            angles.append(
                AngleRecord(
                    index=len(angles) + 1,
                    angle_type="h*-o*-h*",
                    atom1_id=hydrogen_ids[0],
                    atom2_id=oxygen_index,
                    atom3_id=hydrogen_ids[1],
                )
            )
        elif oxygen.ff_type == "oh":
            if len(hydrogen_ids) != 1:
                raise ValueError(
                    f"Hydroxyl oxygen {oxygen.label} must have 1 bonded hydrogen, found {len(hydrogen_ids)}"
                )
            bonds.append(
                BondRecord(
                    index=len(bonds) + 1,
                    bond_type="oh-ho",
                    atom1_id=oxygen_index,
                    atom2_id=hydrogen_ids[0],
                )
            )
        elif oxygen.ff_type == "ohs":
            if len(hydrogen_ids) != 1:
                raise ValueError(
                    f"Substituted hydroxyl oxygen {oxygen.label} must have 1 bonded hydrogen, found {len(hydrogen_ids)}"
                )
            bonds.append(
                BondRecord(
                    index=len(bonds) + 1,
                    bond_type="ohs-ho",
                    atom1_id=oxygen_index,
                    atom2_id=hydrogen_ids[0],
                )
            )

    return AssignedStructure(
        title=structure.title,
        source_path=structure.path,
        cell=structure,
        atoms=tuple(assigned_atoms),
        bonds=tuple(bonds),
        angles=tuple(angles),
    )
