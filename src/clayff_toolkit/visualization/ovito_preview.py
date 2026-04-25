"""OVITO-based structure rendering helpers for the GUI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

import numpy as np
from ase.data import atomic_numbers, covalent_radii

from ..assignment import AssignedStructure, CifStructure
from ..assignment.cif import Cell
from ..validation import ValidationReport


DEFAULT_ELEMENT_COLORS = {
    "H": "#87ceeb",
    "O": "#d73027",
    "Si": "#3f7fdb",
    "Al": "#86b8e7",
    "Mg": "#53b46a",
    "Fe": "#9b5f46",
    "Li": "#9dd7ff",
    "Na": "#6cc0ff",
    "K": "#6e77ff",
    "Ca": "#3aa76d",
    "Cs": "#8866cc",
    "Ba": "#5a8c5a",
    "Sr": "#3ca973",
    "Pb": "#5e6472",
    "Cl": "#53a653",
}
DEFAULT_RENDER_SIZE = (1200, 760)
DEFAULT_CAMERA_DIR = np.array((2.0, 1.3, -1.1), dtype=float)
PREVIEW_WRAP_TO_PRIMARY_CELL = True


@dataclass
class OvitoPreviewScene:
    widget: object
    viewport: object
    pipeline: object
    cell_vis: object | None
    interactive: bool
    backend: str
    zoom_all_size: tuple[int, int] | None = None
    in_scene: bool = False


def _hex_to_rgb(color: str) -> tuple[float, float, float]:
    color = color.lstrip("#")
    return tuple(int(color[index : index + 2], 16) / 255.0 for index in (0, 2, 4))


def _element_color(element: str) -> str:
    return DEFAULT_ELEMENT_COLORS.get(element, "#8b949e")


def _element_radius(element: str) -> float:
    try:
        atomic_number = atomic_numbers[element]
    except Exception:
        return 0.55
    radius = float(covalent_radii[atomic_number])
    if radius <= 0.0:
        return 0.55
    return max(radius, 0.16)


def _selection_cutoff(element: str) -> float:
    if element == "H":
        return 1.35
    if element == "O":
        return 2.4
    return 3.1


def _ovito_cell_matrix(cell: Cell) -> np.ndarray:
    vectors = np.asarray(cell.lattice_vectors(), dtype=float)
    origin = np.zeros(3, dtype=float)
    return np.column_stack((vectors[0], vectors[1], vectors[2], origin))


def _preview_cartesian_positions(structure: CifStructure) -> np.ndarray:
    return np.array(
        [
            structure.cell.frac_to_cart(
                structure.cell.wrap_frac(atom.frac) if PREVIEW_WRAP_TO_PRIMARY_CELL else atom.frac
            )
            for atom in structure.atoms
        ],
        dtype=float,
    )


def supports_interactive_qwidget() -> bool:
    try:
        from ovito.gui import create_qwidget
    except Exception:
        return False
    return callable(create_qwidget)


def _neighbor_indices_for_selection(structure: CifStructure, selected_index: int | None) -> list[int]:
    if selected_index is None:
        return []
    selected_atom = structure.atoms[selected_index]
    pairs = []
    for index, atom in enumerate(structure.atoms):
        if index == selected_index:
            continue
        distance = structure.cell.distance(selected_atom.frac, atom.frac)
        pairs.append((distance, index))
    pairs.sort(key=lambda item: item[0])
    cutoff = _selection_cutoff(selected_atom.element)
    within_cutoff = [index for distance, index in pairs if distance <= cutoff]
    if within_cutoff:
        return within_cutoff[:8]
    return [index for _, index in pairs[:6]]


def _overlay_color(
    zero_based_index: int,
    structure: CifStructure,
    assigned: AssignedStructure | None,
    overlay_mode: str,
    warning_atom_indices: set[int],
) -> tuple[float, float, float]:
    atom = structure.atoms[zero_based_index]
    if overlay_mode == "Element":
        return _hex_to_rgb(_element_color(atom.element))
    if overlay_mode == "ClayFF Type" and assigned is not None:
        ff_type = assigned.atoms[zero_based_index].ff_type
        palette = [
            "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
            "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
            "#bcbd22", "#17becf",
        ]
        return _hex_to_rgb(palette[sum(ord(char) for char in ff_type) % len(palette)])
    if overlay_mode == "Profile" and assigned is not None:
        ff_type = assigned.atoms[zero_based_index].ff_type
        if ff_type in {"Na", "K", "Cs", "Ca", "Ba", "Mg", "Sr", "Pb", "Cl"}:
            return _hex_to_rgb("#1b9aaa")
        if ff_type in {"at", "obts", "obss"}:
            return _hex_to_rgb("#4361ee")
        if ff_type in {"mgo", "feo", "lio", "obos", "ohs"}:
            return _hex_to_rgb("#2a9d8f")
        if ff_type in {"o*", "h*"}:
            return _hex_to_rgb("#4cc9f0")
        if ff_type in {"oh", "ho"}:
            return _hex_to_rgb("#f4a261")
        return _hex_to_rgb("#8d99ae")
    if overlay_mode == "Warnings":
        if zero_based_index in warning_atom_indices:
            return _hex_to_rgb("#d0006f")
        return _hex_to_rgb("#c8d0d8")
    return _hex_to_rgb(_element_color(atom.element))


def _configure_cell_vis(cell_vis, structure: CifStructure) -> None:
    cell_vis.enabled = True
    if hasattr(cell_vis, "render_cell"):
        cell_vis.render_cell = True
    if hasattr(cell_vis, "rendering_color"):
        cell_vis.rendering_color = (0.56, 0.61, 0.68)
    if hasattr(cell_vis, "line_width"):
        min_length = min(structure.cell.a, structure.cell.b, structure.cell.c)
        cell_vis.line_width = max(min_length * 0.002, 0.018)


def _build_structure_pipeline(
    structure: CifStructure,
    *,
    assigned: AssignedStructure | None = None,
    overlay_mode: str = "Element",
    validation_report: ValidationReport | None = None,
    selected_index: int | None = None,
):
    from ovito.data import DataCollection
    from ovito.pipeline import Pipeline, StaticSource

    data = DataCollection()
    data.create_cell(
        matrix=_ovito_cell_matrix(structure.cell),
        pbc=(True, True, True),
        vis_params={"enabled": True},
    )

    warning_atom_indices = {
        atom_index - 1
        for warning in (validation_report.warnings if validation_report else ())
        for atom_index in warning.atom_indices
    }
    neighbor_indices = set(_neighbor_indices_for_selection(structure, selected_index))
    positions = _preview_cartesian_positions(structure)

    particles = data.create_particles()
    particles.create_property("Position", data=positions)

    particle_types = particles.create_property(
        "Particle Type",
        data=np.arange(1, len(structure.atoms) + 1, dtype=np.int32),
    )
    ovito_default_colors = []
    ovito_default_radii = []
    for index, atom in enumerate(structure.atoms, start=1):
        particle_type = particle_types.add_type_name(atom.element, particles)
        particle_type.id = index
        ovito_default_colors.append(tuple(float(component) for component in particle_type.color))
        ovito_default_radii.append(float(particle_type.radius))

    colors = []
    radii = []
    for index, atom in enumerate(structure.atoms):
        base_radius = ovito_default_radii[index] if index < len(ovito_default_radii) else _element_radius(atom.element)
        if selected_index == index:
            color = _hex_to_rgb("#ff0054")
            radius = base_radius * 1.18
        elif index in neighbor_indices:
            color = _hex_to_rgb("#ffbd00")
            radius = base_radius * 1.06
        else:
            if overlay_mode == "Element":
                color = ovito_default_colors[index]
            else:
                color = _overlay_color(index, structure, assigned, overlay_mode, warning_atom_indices)
            radius = base_radius
        colors.append(color)
        radii.append(radius)

    particles.create_property("Color", data=np.asarray(colors, dtype=float))
    particles.create_property("Radius", data=np.asarray(radii, dtype=float))

    cell_vis = None
    if data.cell is not None:
        cell_vis = data.cell.vis
        _configure_cell_vis(cell_vis, structure)

    return Pipeline(source=StaticSource(data=data)), cell_vis


def create_ovito_preview_widget(
    structure: CifStructure,
    *,
    assigned: AssignedStructure | None = None,
    overlay_mode: str = "Element",
    validation_report: ValidationReport | None = None,
    selected_index: int | None = None,
    size: tuple[int, int] = DEFAULT_RENDER_SIZE,
    parent=None,
) -> OvitoPreviewScene:
    if not supports_interactive_qwidget():
        raise RuntimeError("Interactive OVITO Qt viewport is unavailable.")

    from ovito.gui import create_qwidget
    from ovito.vis import Viewport

    pipeline, cell_vis = _build_structure_pipeline(
        structure,
        assigned=assigned,
        overlay_mode=overlay_mode,
        validation_report=validation_report,
        selected_index=selected_index,
    )
    viewport = Viewport(type=Viewport.Type.Perspective, camera_dir=tuple(DEFAULT_CAMERA_DIR.tolist()))
    pipeline.add_to_scene()
    try:
        viewport.zoom_all(size)
        widget = create_qwidget(
            contents=viewport,
            parent=parent,
            show_orientation_indicator=True,
            show_title=False,
        )
    except Exception:
        pipeline.remove_from_scene()
        raise
    return OvitoPreviewScene(
        widget=widget,
        viewport=viewport,
        pipeline=pipeline,
        cell_vis=cell_vis,
        interactive=True,
        backend="ovito",
        zoom_all_size=size,
        in_scene=True,
    )


def dispose_preview_scene(scene: OvitoPreviewScene | None) -> None:
    if scene is None:
        return
    if scene.in_scene:
        try:
            scene.pipeline.remove_from_scene()
        except Exception:
            pass
        scene.in_scene = False
    widget = getattr(scene, "widget", None)
    if widget is not None:
        try:
            widget.setParent(None)
            widget.deleteLater()
        except Exception:
            pass


def render_structure_preview(
    structure: CifStructure,
    *,
    assigned: AssignedStructure | None = None,
    overlay_mode: str = "Element",
    validation_report: ValidationReport | None = None,
    selected_index: int | None = None,
    size: tuple[int, int] = DEFAULT_RENDER_SIZE,
) -> Path:
    try:
        from ovito.vis import Viewport
    except Exception as exc:  # pragma: no cover - package/environment dependent
        raise RuntimeError(
            "OVITO is required for structure rendering. Install with `pip install ovito`."
        ) from exc

    pipeline, _cell_vis = _build_structure_pipeline(
        structure,
        assigned=assigned,
        overlay_mode=overlay_mode,
        validation_report=validation_report,
        selected_index=selected_index,
    )
    viewport = Viewport(type=Viewport.Type.Perspective, camera_dir=tuple(DEFAULT_CAMERA_DIR.tolist()))

    temp_file = NamedTemporaryFile(suffix=".png", delete=False)
    temp_file.close()
    output_path = Path(temp_file.name)

    pipeline.add_to_scene()
    try:
        viewport.zoom_all(size)
        viewport.render_image(
            filename=str(output_path),
            size=size,
            background=(1.0, 1.0, 1.0),
            renderer=None,
        )
    finally:
        pipeline.remove_from_scene()

    return output_path
