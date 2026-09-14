from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from clayff_toolkit.assignment import material_studio
from clayff_toolkit.assignment import (
    MATERIAL_STUDIO_XSD_PROFILES,
    assign_structure_file,
    default_clayff_path,
    load_material_studio_structure,
    write_material_studio_xsd,
)
from clayff_toolkit.cli import main
from clayff_toolkit.pipeline import ToolkitPipeline


FIXTURES = Path(__file__).resolve().parent / "fixtures"
SOURCE_CIF = FIXTURES / "assignment_input" / "MMT_0W_rank3_d9.545.cif"


def _base_nodes(path: Path) -> tuple[ET.Element, list[ET.Element], list[ET.Element]]:
    root = ET.parse(path).getroot()
    identity = root.find(
        "./AtomisticTreeRoot/SymmetrySystem/MappingSet/MappingFamily/IdentityMapping"
    )
    assert identity is not None
    atoms = [node for node in identity if node.tag == "Atom3d" and node.get("Name")]
    bonds = [node for node in identity if node.tag == "Bond" and node.get("Connects")]
    return identity, atoms, bonds


def _assigned_source():
    return assign_structure_file(SOURCE_CIF, default_clayff_path())


def test_cif_to_material_studio_xsd_round_trip(tmp_path: Path) -> None:
    structure, assigned, _ = _assigned_source()
    output = tmp_path / "assigned.xsd"

    result = write_material_studio_xsd(structure, assigned, output)
    loaded = load_material_studio_structure(output)
    identity, atoms, bonds = _base_nodes(output)

    assert result.mode == "rebuilt"
    assert len(loaded.atoms) == len(assigned.atoms)
    assert len(atoms) == len(assigned.atoms)
    assert len(bonds) == len(assigned.bonds)
    assert [atom.get("ForcefieldType") for atom in atoms] == [
        atom.ff_type for atom in assigned.atoms
    ]
    assert [float(atom.get("Charge", "nan")) for atom in atoms] == pytest.approx(
        [atom.charge for atom in assigned.atoms]
    )
    mapped = set(identity.get("MappedObjects", "").split(","))
    assert mapped == {node.get("ID") for node in [*atoms, *bonds]}


@pytest.mark.parametrize(
    ("ms_version", "xsd_version", "property_count"),
    [
        ("2020", "20.1", 63),
        ("2021", "21.1", 63),
        ("2022", "22.1", 63),
        ("2023", "23.1", 63),
        ("2024", "24.1", 85),
    ],
)
def test_rebuilt_xsd_uses_selected_materials_studio_profile(
    tmp_path: Path,
    ms_version: str,
    xsd_version: str,
    property_count: int,
) -> None:
    structure, assigned, _ = _assigned_source()
    output = tmp_path / f"assigned-{ms_version}.xsd"

    result = write_material_studio_xsd(
        structure,
        assigned,
        output,
        ms_version=ms_version,
    )

    root = ET.parse(output).getroot()
    atomistic_root = root.find("AtomisticTreeRoot")
    assert atomistic_root is not None
    properties = atomistic_root.findall("Property")
    assert result.target_version == ms_version
    assert result.xsd_version == xsd_version
    assert root.get("Version") == xsd_version
    assert root.get("WrittenBy") == "ClayFF-Toolkit"
    assert atomistic_root.get("NumProperties") == str(property_count)
    assert len(properties) == property_count
    assert [
        (node.get("Name"), node.get("DefinedOn"), node.get("Type"))
        for node in properties
    ] == list(MATERIAL_STUDIO_XSD_PROFILES[ms_version].properties)


def test_explicit_legacy_profile_removes_ms_2024_properties(tmp_path: Path) -> None:
    structure, assigned, _ = _assigned_source()
    source = tmp_path / "source-2024.xsd"
    output = tmp_path / "output-2020.xsd"
    write_material_studio_xsd(
        structure,
        assigned,
        source,
        ms_version="2024",
    )

    result = write_material_studio_xsd(
        structure,
        assigned,
        output,
        source_xsd=source,
        ms_version="2020",
    )

    root = ET.parse(output).getroot()
    atomistic_root = root.find("AtomisticTreeRoot")
    assert atomistic_root is not None
    property_names = [node.get("Name", "") for node in atomistic_root.findall("Property")]
    assert result.mode == "patched"
    assert root.get("Version") == "20.1"
    assert len(property_names) == 63
    assert not any("PUBCHEM" in name for name in property_names)


def test_unknown_materials_studio_version_is_rejected(tmp_path: Path) -> None:
    structure, assigned, _ = _assigned_source()

    with pytest.raises(ValueError, match="Unsupported Materials Studio version"):
        write_material_studio_xsd(
            structure,
            assigned,
            tmp_path / "unsupported.xsd",
            ms_version="2019",
        )


def test_existing_xsd_is_patched_without_reformatting(tmp_path: Path) -> None:
    structure, assigned, _ = _assigned_source()
    source = tmp_path / "source.xsd"
    write_material_studio_xsd(structure, assigned, source)
    original = source.read_text(encoding="latin1")
    first_type = assigned.atoms[0].ff_type
    source.write_text(
        original.replace(f'ForcefieldType="{first_type}"', 'ForcefieldType="wrong"', 1)
        .replace(f'Charge="{assigned.atoms[0].charge:.12g}"', 'Charge="999"', 1),
        encoding="latin1",
    )
    output = tmp_path / "patched.xsd"

    result = write_material_studio_xsd(
        structure,
        assigned,
        output,
        source_xsd=source,
    )

    assert result.mode == "patched"
    patched = output.read_text(encoding="latin1")
    assert 'ForcefieldType="wrong"' not in patched
    assert 'Charge="999"' not in patched
    assert len(patched) == len(original)


def test_topology_conflict_can_error_or_rebuild(tmp_path: Path) -> None:
    structure, assigned, _ = _assigned_source()
    source = tmp_path / "source.xsd"
    write_material_studio_xsd(structure, assigned, source)
    tree = ET.parse(source)
    identity = tree.getroot().find(
        "./AtomisticTreeRoot/SymmetrySystem/MappingSet/MappingFamily/IdentityMapping"
    )
    assert identity is not None
    bond = next(node for node in identity if node.tag == "Bond")
    identity.remove(bond)
    tree.write(source, encoding="latin1", xml_declaration=True)

    with pytest.raises(ValueError, match="topology"):
        write_material_studio_xsd(
            structure,
            assigned,
            tmp_path / "strict.xsd",
            source_xsd=source,
            topology_conflict="error",
        )

    result = write_material_studio_xsd(
        structure,
        assigned,
        tmp_path / "rebuilt.xsd",
        source_xsd=source,
        topology_conflict="rebuild",
    )
    assert result.mode == "rebuilt"


def test_auto_rebuild_preserves_input_xsd_schema(tmp_path: Path) -> None:
    structure, assigned, _ = _assigned_source()
    source = tmp_path / "source-2023.xsd"
    write_material_studio_xsd(
        structure,
        assigned,
        source,
        ms_version="2023",
    )
    tree = ET.parse(source)
    identity = tree.getroot().find(
        "./AtomisticTreeRoot/SymmetrySystem/MappingSet/MappingFamily/IdentityMapping"
    )
    assert identity is not None
    identity.remove(next(node for node in identity if node.tag == "Bond"))
    tree.write(source, encoding="latin1", xml_declaration=True)
    output = tmp_path / "rebuilt-auto.xsd"

    result = write_material_studio_xsd(
        structure,
        assigned,
        output,
        source_xsd=source,
    )

    root = ET.parse(output).getroot()
    atomistic_root = root.find("AtomisticTreeRoot")
    assert atomistic_root is not None
    assert result.mode == "rebuilt"
    assert result.target_version == "auto"
    assert result.xsd_version == "23.1"
    assert root.get("Version") == "23.1"
    assert len(atomistic_root.findall("Property")) == 63


def test_assign_ms_cli_and_pipeline(tmp_path: Path, capsys) -> None:
    cli_output = tmp_path / "cli.xsd"
    exit_code = main(
        ["assign-ms", str(SOURCE_CIF), str(cli_output), "--ms-version", "2021"]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert cli_output.exists()
    assert "mode=rebuilt" in captured.out
    assert "xsd_version=21.1" in captured.out

    pipeline_output = tmp_path / "pipeline.xsd"
    result = ToolkitPipeline().assign_material_studio(
        SOURCE_CIF,
        pipeline_output,
        ms_version="2022",
    )
    assert result.path == pipeline_output
    assert result.mode == "rebuilt"
    assert result.xsd_version == "22.1"


def test_material_studio_output_requires_explicit_overwrite(tmp_path: Path) -> None:
    structure, assigned, _ = _assigned_source()
    output = tmp_path / "assigned.xsd"
    write_material_studio_xsd(structure, assigned, output)

    with pytest.raises(FileExistsError):
        write_material_studio_xsd(structure, assigned, output)

    result = write_material_studio_xsd(
        structure,
        assigned,
        output,
        overwrite=True,
    )
    assert result.path == output


def test_failed_overwrite_preserves_existing_output(
    monkeypatch, tmp_path: Path
) -> None:
    structure, assigned, _ = _assigned_source()
    output = tmp_path / "assigned.xsd"
    original = b"existing private XSD content"
    output.write_bytes(original)

    def fail_validation(*args, **kwargs):
        raise ValueError("simulated validation failure")

    monkeypatch.setattr(material_studio, "_validate_written_xsd", fail_validation)

    with pytest.raises(ValueError, match="simulated validation failure"):
        write_material_studio_xsd(
            structure,
            assigned,
            output,
            overwrite=True,
        )

    assert output.read_bytes() == original
