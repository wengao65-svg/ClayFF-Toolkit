"""Materials Studio XSD import and ClayFF export support."""

from __future__ import annotations

from dataclasses import dataclass
from io import StringIO
import math
import os
from pathlib import Path
import re
import tempfile
from typing import Literal
import xml.etree.ElementTree as ET
from xml.dom import minidom

import numpy as np
from ase.io import write as ase_write

from .assigner import AssignedStructure
from .cif import AtomSite, Cell, CifStructure, ase_atoms_from_structure, load_structure
from .params import ClayFFParameters, load_clayff


TopologyConflictPolicy = Literal["rebuild", "error"]


@dataclass(frozen=True)
class MaterialStudioWriteResult:
    path: Path
    mode: Literal["patched", "rebuilt"]
    atom_count: int
    bond_count: int


def _vector(value: str | None, name: str) -> np.ndarray:
    if value is None:
        raise ValueError(f"Materials Studio XSD is missing {name}.")
    parts = value.split(",")
    if len(parts) != 3:
        raise ValueError(f"Invalid Materials Studio {name}: {value}")
    return np.asarray([float(part) for part in parts], dtype=float)


def _angle(vector_a: np.ndarray, vector_b: np.ndarray) -> float:
    denominator = float(np.linalg.norm(vector_a) * np.linalg.norm(vector_b))
    if denominator == 0.0:
        raise ValueError("Materials Studio XSD contains a zero-length cell vector.")
    cosine = float(np.dot(vector_a, vector_b) / denominator)
    return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))


def _identity_mapping(root: ET.Element) -> ET.Element:
    atomistic_root = root.find("AtomisticTreeRoot")
    if atomistic_root is None:
        raise ValueError("Materials Studio XSD has no AtomisticTreeRoot.")
    symmetry_system = atomistic_root.find("SymmetrySystem")
    if symmetry_system is None:
        raise ValueError("Only periodic Materials Studio XSD structures are supported.")
    mapping_set = symmetry_system.find("MappingSet")
    mapping_family = mapping_set.find("MappingFamily") if mapping_set is not None else None
    identity = mapping_family.find("IdentityMapping") if mapping_family is not None else None
    if identity is None:
        raise ValueError("Materials Studio XSD has no periodic IdentityMapping.")
    return identity


def _space_group(identity: ET.Element) -> ET.Element:
    space_group = identity.find("SpaceGroup")
    if space_group is None:
        raise ValueError("Materials Studio XSD has no SpaceGroup definition.")
    group_name = space_group.get("GroupName") or space_group.get("Name") or ""
    it_number = space_group.get("ITNumber")
    if it_number not in {None, "1"} or group_name.replace(" ", "").upper() not in {
        "",
        "P1",
        "GROUPNAME",
    }:
        raise ValueError(
            "Only explicit P1 Materials Studio XSD structures are supported; "
            f"found GroupName={group_name!r}, ITNumber={it_number!r}."
        )
    return space_group


def _base_atom_elements(identity: ET.Element) -> list[ET.Element]:
    atoms = [child for child in identity if child.tag == "Atom3d" and child.get("Name")]
    if not atoms:
        raise ValueError("Materials Studio XSD IdentityMapping contains no base atoms.")
    return atoms


def _parse_xsd(path: str | Path) -> tuple[ET.ElementTree, ET.Element, list[ET.Element]]:
    xsd_path = Path(path)
    try:
        tree = ET.parse(xsd_path)
    except (ET.ParseError, OSError) as exc:
        raise ValueError(f"Unable to parse Materials Studio XSD: {xsd_path}") from exc
    root = tree.getroot()
    if root.tag != "XSD":
        raise ValueError(f"Expected Materials Studio XSD root element, found {root.tag!r}.")
    identity = _identity_mapping(root)
    _space_group(identity)
    return tree, identity, _base_atom_elements(identity)


def load_material_studio_structure(path: str | Path) -> CifStructure:
    """Load the explicit base atoms from a periodic P1 Materials Studio XSD."""

    xsd_path = Path(path)
    tree, identity, atom_elements = _parse_xsd(xsd_path)
    space_group = _space_group(identity)
    a_vector = _vector(space_group.get("AVector"), "AVector")
    b_vector = _vector(space_group.get("BVector"), "BVector")
    c_vector = _vector(space_group.get("CVector"), "CVector")
    cell = Cell(
        a=float(np.linalg.norm(a_vector)),
        b=float(np.linalg.norm(b_vector)),
        c=float(np.linalg.norm(c_vector)),
        alpha=_angle(b_vector, c_vector),
        beta=_angle(a_vector, c_vector),
        gamma=_angle(a_vector, b_vector),
    )

    atoms: list[AtomSite] = []
    for index, atom in enumerate(atom_elements, start=1):
        element = atom.get("Components")
        xyz = atom.get("XYZ")
        if not element or not xyz:
            raise ValueError(
                f"Materials Studio atom ID={atom.get('ID')} is missing Components or XYZ."
            )
        coordinates = xyz.split(",")
        if len(coordinates) != 3:
            raise ValueError(f"Invalid XYZ value for Materials Studio atom {atom.get('Name')}: {xyz}")
        atoms.append(
            AtomSite(
                index=index,
                label=atom.get("Name") or f"{element}{index}",
                element=element,
                frac=tuple(float(component) for component in coordinates),
            )
        )

    symmetry_system = tree.getroot().find("./AtomisticTreeRoot/SymmetrySystem")
    title = symmetry_system.get("Name") if symmetry_system is not None else None
    return CifStructure(
        title=title or xsd_path.stem,
        path=xsd_path,
        cell=cell,
        atoms=tuple(atoms),
    )


def _desired_bond_pairs(assigned: AssignedStructure) -> set[tuple[int, int]]:
    return {
        tuple(sorted((bond.atom1_id, bond.atom2_id)))
        for bond in assigned.bonds
    }


def _existing_topology(
    identity: ET.Element,
    atom_elements: list[ET.Element],
) -> tuple[set[tuple[int, int]], bool]:
    atom_ids = [atom.get("ID") for atom in atom_elements]
    index_by_id = {atom_id: index for index, atom_id in enumerate(atom_ids, start=1)}
    bond_ids: dict[str, tuple[int, int]] = {}
    valid = None not in index_by_id and len(index_by_id) == len(atom_elements)
    for bond in identity:
        if bond.tag != "Bond" or not bond.get("Connects"):
            continue
        endpoints = bond.get("Connects", "").split(",")
        if len(endpoints) != 2 or any(endpoint not in index_by_id for endpoint in endpoints):
            valid = False
            continue
        pair = tuple(sorted((index_by_id[endpoints[0]], index_by_id[endpoints[1]])))
        bond_id = bond.get("ID")
        if not bond_id or bond_id in bond_ids:
            valid = False
            continue
        bond_ids[bond_id] = pair

    for atom in atom_elements:
        expected = {
            bond_id
            for bond_id, pair in bond_ids.items()
            if index_by_id[atom.get("ID")] in pair
        }
        actual = {value for value in atom.get("Connections", "").split(",") if value}
        if actual != expected:
            valid = False
    return set(bond_ids.values()), valid


def _structure_matches_xsd(
    assigned: AssignedStructure,
    atom_elements: list[ET.Element],
    tolerance: float = 2.0e-4,
) -> bool:
    if len(assigned.atoms) != len(atom_elements):
        return False
    for assigned_atom, xsd_atom in zip(assigned.atoms, atom_elements):
        if assigned_atom.element != xsd_atom.get("Components"):
            return False
        xyz = xsd_atom.get("XYZ")
        if not xyz:
            return False
        coordinates = tuple(float(value) for value in xyz.split(","))
        delta = tuple(
            (assigned_atom.frac[axis] - coordinates[axis])
            - round(assigned_atom.frac[axis] - coordinates[axis])
            for axis in range(3)
        )
        if math.sqrt(sum(component * component for component in delta)) > tolerance:
            return False
    return True


def _format_charge(value: float) -> str:
    return f"{value:.12g}"


def _source_encoding(data: bytes) -> str:
    match = re.match(br"\s*<\?xml[^>]*encoding=[\"']([^\"']+)", data, re.IGNORECASE)
    return match.group(1).decode("ascii") if match else "utf-8"


def _set_attribute(tag: str, name: str, value: str) -> str:
    pattern = re.compile(rf"(\s{name}=)([\"'])[^\"']*\2")
    replacement = rf'\1"{value}"'
    if pattern.search(tag):
        return pattern.sub(replacement, tag, count=1)
    insertion = f' {name}="{value}"'
    marker = tag.rfind("/>")
    if marker < 0:
        marker = tag.rfind(">")
    return tag[:marker] + insertion + tag[marker:]


def _patch_xsd_text(
    source_path: Path,
    output_path: Path,
    atom_elements: list[ET.Element],
    assigned: AssignedStructure,
) -> None:
    data = source_path.read_bytes()
    encoding = _source_encoding(data)
    text = data.decode(encoding)
    assigned_by_id = {
        atom_element.get("ID"): assigned_atom
        for atom_element, assigned_atom in zip(atom_elements, assigned.atoms)
    }
    patched_ids: set[str] = set()
    tag_pattern = re.compile(r"<Atom3d\b[^>]*>")

    def replace(match: re.Match[str]) -> str:
        tag = match.group(0)
        id_match = re.search(r"\bID=(['\"])(.*?)\1", tag)
        name_match = re.search(r"\bName=(['\"])(.*?)\1", tag)
        if not id_match or not name_match:
            return tag
        atom_id = id_match.group(2)
        assigned_atom = assigned_by_id.get(atom_id)
        if assigned_atom is None:
            return tag
        patched_ids.add(atom_id)
        tag = _set_attribute(tag, "ForcefieldType", assigned_atom.ff_type)
        return _set_attribute(tag, "Charge", _format_charge(assigned_atom.charge))

    patched = tag_pattern.sub(replace, text)
    if patched_ids != set(assigned_by_id):
        missing = sorted(set(assigned_by_id) - patched_ids)
        raise ValueError(f"Unable to locate base atom tags while patching XSD: {missing[:5]}")
    output_path.write_bytes(patched.encode(encoding))


def _rebuild_xsd(
    structure: CifStructure,
    assigned: AssignedStructure,
    output_path: Path,
) -> None:
    atoms = ase_atoms_from_structure(structure)
    connectivity = np.zeros((len(assigned.atoms), len(assigned.atoms)), dtype=int)
    for atom1_id, atom2_id in _desired_bond_pairs(assigned):
        connectivity[atom1_id - 1, atom2_id - 1] = 1
        connectivity[atom2_id - 1, atom1_id - 1] = 1

    buffer = StringIO()
    ase_write(buffer, atoms, format="xsd", connectivity=connectivity)
    root = ET.fromstring(buffer.getvalue())
    root.set("Version", "6.0")
    root.set("WrittenBy", "ClayFF-Toolkit")
    identity = _identity_mapping(root)
    atom_elements = _base_atom_elements(identity)
    if len(atom_elements) != len(assigned.atoms):
        raise ValueError("ASE XSD writer returned an unexpected atom count.")

    for atom_element, source_atom, assigned_atom in zip(
        atom_elements, structure.atoms, assigned.atoms
    ):
        atom_element.set("Name", source_atom.label)
        atom_element.set("ForcefieldType", assigned_atom.ff_type)
        atom_element.set("Charge", _format_charge(assigned_atom.charge))
        atom_element.attrib.pop("Connections", None)

    bond_elements = [child for child in identity if child.tag == "Bond"]
    if len(bond_elements) != len(assigned.bonds):
        raise ValueError("ASE XSD writer returned an unexpected bond count.")
    connections_by_atom: dict[int, list[str]] = {
        atom.index: [] for atom in assigned.atoms
    }
    atom_id_by_index = {
        index: atom_element.get("ID")
        for index, atom_element in enumerate(atom_elements, start=1)
    }
    desired_pairs = sorted(_desired_bond_pairs(assigned))
    for bond_element, (atom1_id, atom2_id) in zip(bond_elements, desired_pairs):
        bond_element.set(
            "Connects",
            f"{atom_id_by_index[atom1_id]},{atom_id_by_index[atom2_id]}",
        )
        bond_id = bond_element.get("ID")
        if bond_id is None:
            raise ValueError("ASE XSD writer returned a bond without an ID.")
        connections_by_atom[atom1_id].append(bond_id)
        connections_by_atom[atom2_id].append(bond_id)

    for index, atom_element in enumerate(atom_elements, start=1):
        connection_ids = connections_by_atom[index]
        if connection_ids:
            atom_element.set("Connections", ",".join(connection_ids))

    symmetry_system = root.find("./AtomisticTreeRoot/SymmetrySystem")
    if symmetry_system is not None:
        symmetry_system.set("Name", structure.title)
        symmetry_system.set("PeriodicDisplayType", "In-Cell")

    space_group = _space_group(identity)
    reciprocal = identity.find("ReciprocalLattice3D")
    if reciprocal is None:
        raise ValueError("ASE XSD writer returned no ReciprocalLattice3D node.")
    atom_ids = [atom.get("ID") for atom in atom_elements]
    bond_ids = [bond.get("ID") for bond in bond_elements]
    if any(value is None for value in atom_ids + bond_ids):
        raise ValueError("ASE XSD writer returned an object without an ID.")
    mapped_ids = [str(value) for value in atom_ids + bond_ids]
    identity.set("MappedObjects", ",".join(mapped_ids))
    identity.set("NumImages", str(len(mapped_ids)))
    identity.set("DefectObjects", f"{space_group.get('ID')},{reciprocal.get('ID')}")
    identity.set("NumDefects", "2")
    identity_id = identity.get("ID")
    for element in [*atom_elements, *bond_elements]:
        element.set("Mapping", str(identity_id))
        element.set("Parent", "2")

    space_group.set("Name", "P1")
    space_group.set("GroupName", "P1")
    space_group.set("Children", str(reciprocal.get("ID")))
    reciprocal.set("Parent", str(space_group.get("ID")))
    mapping_set = root.find("./AtomisticTreeRoot/SymmetrySystem/MappingSet")
    if mapping_set is None:
        raise ValueError("ASE XSD writer returned no MappingSet.")
    mapping_set.set("SymmetryDefinition", str(space_group.get("ID")))
    mapping_family = mapping_set.find("MappingFamily")
    if mapping_family is None:
        raise ValueError("ASE XSD writer returned no MappingFamily.")
    mapping_family.set("NumImageMappings", "0")
    if symmetry_system is not None:
        symmetry_system.set("Children", ",".join([*mapped_ids, str(space_group.get("ID"))]))

    xml_bytes = ET.tostring(root, encoding="utf-8")
    document = minidom.parseString(xml_bytes).toprettyxml(indent="\t", encoding="latin1")
    declaration_end = document.find(b"?>")
    if declaration_end >= 0:
        document = document[: declaration_end + 2] + b"\n<!DOCTYPE XSD []>" + document[declaration_end + 2 :]
    output_path.write_bytes(document)


def _validate_written_xsd(
    path: Path,
    assigned: AssignedStructure,
    *,
    validate_generated_links: bool,
) -> None:
    tree, identity, atom_elements = _parse_xsd(path)
    if not _structure_matches_xsd(assigned, atom_elements):
        raise ValueError(f"Written Materials Studio XSD does not match assigned structure: {path}")
    for assigned_atom, atom_element in zip(assigned.atoms, atom_elements):
        if atom_element.get("ForcefieldType") != assigned_atom.ff_type:
            raise ValueError(f"Written XSD lost ClayFF type for atom {assigned_atom.index}.")
        charge = atom_element.get("Charge")
        if charge is None or abs(float(charge) - assigned_atom.charge) > 1.0e-10:
            raise ValueError(f"Written XSD lost ClayFF charge for atom {assigned_atom.index}.")
    topology, valid = _existing_topology(identity, atom_elements)
    if not valid or topology != _desired_bond_pairs(assigned):
        raise ValueError(f"Written Materials Studio XSD has inconsistent H-O topology: {path}")
    if not validate_generated_links:
        return

    root = tree.getroot()
    all_ids = [element.get("ID") for element in root.iter() if element.get("ID")]
    if len(all_ids) != len(set(all_ids)):
        raise ValueError(f"Written Materials Studio XSD contains duplicate object IDs: {path}")
    bond_elements = [child for child in identity if child.tag == "Bond"]
    mapped = {value for value in identity.get("MappedObjects", "").split(",") if value}
    expected_mapped = {
        element.get("ID") for element in [*atom_elements, *bond_elements]
    }
    if mapped != expected_mapped:
        raise ValueError(f"Written Materials Studio XSD has invalid MappedObjects: {path}")
    space_group = _space_group(identity)
    reciprocal = identity.find("ReciprocalLattice3D")
    if reciprocal is None or reciprocal.get("Parent") != space_group.get("ID"):
        raise ValueError(f"Written Materials Studio XSD has invalid reciprocal lattice links: {path}")
    defects = {value for value in identity.get("DefectObjects", "").split(",") if value}
    if defects != {space_group.get("ID"), reciprocal.get("ID")}:
        raise ValueError(f"Written Materials Studio XSD has invalid DefectObjects: {path}")


def write_material_studio_xsd(
    structure: CifStructure,
    assigned: AssignedStructure,
    output_path: str | Path,
    *,
    source_xsd: str | Path | None = None,
    topology_conflict: TopologyConflictPolicy = "rebuild",
    overwrite: bool = False,
) -> MaterialStudioWriteResult:
    """Write a ClayFF-assigned Materials Studio XSD document."""

    if topology_conflict not in {"rebuild", "error"}:
        raise ValueError(f"Unsupported topology conflict policy: {topology_conflict}")
    path = Path(output_path)
    if path.suffix.lower() != ".xsd":
        raise ValueError("Materials Studio output path must use the .xsd extension.")
    if path.exists() and not overwrite:
        raise FileExistsError(f"Output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)

    temp_file = tempfile.NamedTemporaryFile(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    )
    temp_file.close()
    temp_path = Path(temp_file.name)

    mode: Literal["patched", "rebuilt"] = "rebuilt"
    try:
        source_path = Path(source_xsd) if source_xsd is not None else None
        if source_path is not None:
            _, identity, atom_elements = _parse_xsd(source_path)
            topology, valid = _existing_topology(identity, atom_elements)
            can_patch = (
                valid
                and topology == _desired_bond_pairs(assigned)
                and _structure_matches_xsd(assigned, atom_elements)
            )
            if can_patch:
                _patch_xsd_text(source_path, temp_path, atom_elements, assigned)
                mode = "patched"
            elif topology_conflict == "error":
                raise ValueError(
                    "Input XSD structure or H-O topology does not match the ClayFF assignment."
                )

        if mode == "rebuilt":
            _rebuild_xsd(structure, assigned, temp_path)

        _validate_written_xsd(
            temp_path,
            assigned,
            validate_generated_links=mode == "rebuilt",
        )
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)

    return MaterialStudioWriteResult(
        path=path,
        mode=mode,
        atom_count=len(assigned.atoms),
        bond_count=len(assigned.bonds),
    )


def assign_material_studio_file(
    input_structure: str | Path,
    output_xsd: str | Path,
    clayff_path: str | Path | None = None,
    *,
    topology_conflict: TopologyConflictPolicy = "rebuild",
    overwrite: bool = False,
) -> MaterialStudioWriteResult:
    """Assign ClayFF and export a Materials Studio XSD document."""

    input_path = Path(input_structure)
    structure = load_structure(input_path)
    if clayff_path is None:
        from .service import default_clayff_path

        clayff_path = default_clayff_path()
    forcefield: ClayFFParameters = load_clayff(clayff_path)
    from .assigner import assign_structure

    assigned = assign_structure(structure, forcefield)
    source_xsd = input_path if input_path.suffix.lower() == ".xsd" else None
    return write_material_studio_xsd(
        structure,
        assigned,
        output_xsd,
        source_xsd=source_xsd,
        topology_conflict=topology_conflict,
        overwrite=overwrite,
    )
