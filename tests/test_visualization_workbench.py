from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from clayff_toolkit.assignment.cif import AtomSite, Cell, CifStructure
from clayff_toolkit.assignment.material_studio_off import (
    MaterialStudioOffAuditIssue,
    MaterialStudioOffAuditReport,
)
from clayff_toolkit.visualization import app as visualization_app
from clayff_toolkit.visualization import build_visualizer_window
from clayff_toolkit.visualization.ovito_preview import (
    _build_structure_pipeline,
    _ovito_cell_matrix,
    _preview_cartesian_positions,
)


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _has_module(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ModuleNotFoundError):
        return False


OVITO_AVAILABLE = _has_module("ovito")
OVITO_QT_AVAILABLE = _has_module("ovito.qt_compat")


class _DummyApp:
    def __init__(self) -> None:
        self.font = None

    def setFont(self, font) -> None:
        self.font = font


class _FakeQFont:
    def __init__(self, family: str, point_size: int) -> None:
        self.family = family
        self.point_size = point_size


def test_ovito_cell_matrix_uses_abc_as_columns_for_triclinic_cell() -> None:
    cell = Cell(a=10.0, b=20.0, c=30.0, alpha=90.0, beta=90.0, gamma=60.0)
    a_vec, b_vec, c_vec = (np.asarray(vector, dtype=float) for vector in cell.lattice_vectors())

    matrix = _ovito_cell_matrix(cell)

    assert matrix.shape == (3, 4)
    assert np.allclose(matrix[:, 0], a_vec)
    assert np.allclose(matrix[:, 1], b_vec)
    assert np.allclose(matrix[:, 2], c_vec)
    assert np.allclose(matrix[:, 3], np.zeros(3, dtype=float))


def test_preview_positions_wrap_fractional_coordinates_without_mutating_structure() -> None:
    cell = Cell(a=10.0, b=20.0, c=30.0, alpha=90.0, beta=90.0, gamma=60.0)
    original_frac = (1.2, -0.1, 0.5)
    structure = CifStructure(
        title="wrapped-preview",
        path=Path("wrapped-preview.cif"),
        cell=cell,
        atoms=(
            AtomSite(index=1, label="Si1", element="Si", frac=original_frac),
        ),
    )

    positions = _preview_cartesian_positions(structure)
    wrapped = cell.wrap_frac(original_frac)
    expected = np.asarray(cell.frac_to_cart(wrapped), dtype=float)

    assert np.allclose(positions[0], expected)
    assert structure.atoms[0].frac == original_frac


@pytest.mark.skipif(not OVITO_QT_AVAILABLE, reason="OVITO Qt compatibility layer is unavailable.")
def test_visualizer_window_loads_structure_and_updates_local_environment() -> None:
    app = QApplication.instance() or QApplication([])
    window = build_visualizer_window(
        clayff_path=Path("src/clayff_toolkit/resources/clayff.txt"),
        data_path=FIXTURES / "assignment_reference" / "MMT_0W_rank3_d9.545.data",
    )

    assert not window.windowIcon().isNull()
    assert not app.windowIcon().isNull()
    window._load_structure(FIXTURES / "substitution_input" / "cammt_c2m_32.cif")
    app.processEvents()

    assert window._selected_atom_index == 0
    assert "Selected atom:" in window._local_environment.toPlainText()
    assert window._atom_table.rowCount() == len(window._structure.atoms)
    assert window._step_stack.count() == 4
    app.processEvents()
    window._go_to_step(2)
    app.processEvents()
    window.close()


@pytest.mark.skipif(not OVITO_QT_AVAILABLE, reason="OVITO Qt compatibility layer is unavailable.")
def test_visualizer_steps_are_independent() -> None:
    app = QApplication.instance() or QApplication([])
    window = build_visualizer_window(
        clayff_path=Path("src/clayff_toolkit/resources/clayff.txt"),
    )

    window._go_to_step(1)
    app.processEvents()
    assert window._step_stack.currentIndex() == 1

    window._assignment_source_input.setText(str(FIXTURES / "substitution_input" / "cammt_c2m_32.cif"))
    window._run_assignment_stage()
    app.processEvents()
    assert window._assigned is not None
    assert window._validation_data_input.text() == ""

    second = build_visualizer_window(
        clayff_path=Path("src/clayff_toolkit/resources/clayff.txt"),
    )
    second._go_to_step(2)
    second._validation_data_input.setText(str(FIXTURES / "assignment_reference" / "MMT_64W_rank1_d15.183.data"))
    second._run_validation_stage()
    app.processEvents()
    assert second._state.data_validation_report is not None
    assert "Data file:" in second._validation_summary.toPlainText()
    window.close()
    second.close()


@pytest.mark.skipif(not OVITO_QT_AVAILABLE, reason="OVITO Qt compatibility layer is unavailable.")
def test_rerunning_upstream_invalidates_previous_validation_data_file() -> None:
    app = QApplication.instance() or QApplication([])
    window = build_visualizer_window(
        clayff_path=Path("src/clayff_toolkit/resources/clayff.txt"),
    )

    first_source = FIXTURES / "substitution_input" / "cammt_c2m_32.cif"
    second_source = FIXTURES / "assignment_input" / "MMT_0W_rank3_d9.545.cif"

    window._assignment_source_input.setText(str(first_source))
    window._run_assignment_stage()
    window._prepare_data_from_assignment()
    first_data = window._validation_data_input.text()
    assert first_data.endswith("cammt_c2m_32.data")

    window._run_validation_stage()
    assert window._state.data_validation_report is not None

    window._assignment_source_input.setText(str(second_source))
    window._run_assignment_stage()
    app.processEvents()

    assert window._state.output_data_path is None
    assert window._validation_data_input.text() == ""
    assert window._data_path_input.text().endswith("MMT_0W_rank3_d9.545.data")
    assert window._warnings_table.rowCount() == 0
    window.close()


@pytest.mark.skipif(not OVITO_QT_AVAILABLE, reason="OVITO Qt compatibility layer is unavailable.")
def test_visualizer_materials_studio_workspace_exports_xsd(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    window = build_visualizer_window(
        clayff_path=Path("src/clayff_toolkit/resources/clayff.txt"),
    )
    source = FIXTURES / "assignment_input" / "MMT_0W_rank3_d9.545.cif"
    output = tmp_path / "assigned.xsd"
    window._go_to_step(window.PAGE_INDEX["materials-studio"])
    window._ms_structure_input.setText(str(source))
    window._ms_xsd_output_input.setText(str(output))
    window._ms_version.setCurrentIndex(window._ms_version.findData("2020"))

    window._run_material_studio_assignment()
    app.processEvents()

    assert output.exists()
    assert window._state.output_xsd_path == output
    assert '<XSD Version="20.1" WrittenBy="ClayFF-Toolkit">' in output.read_text(
        encoding="latin1"
    )
    assert "XSD 文档版本: 20.1" in window._ms_xsd_summary.toPlainText()
    assert "assigned.xsd" in window._ready_card.text()
    window.close()


@pytest.mark.skipif(not OVITO_QT_AVAILABLE, reason="OVITO Qt compatibility layer is unavailable.")
def test_assignment_page_opens_materials_studio_workspace() -> None:
    app = QApplication.instance() or QApplication([])
    window = build_visualizer_window(
        clayff_path=Path("src/clayff_toolkit/resources/clayff.txt"),
    )
    source = FIXTURES / "assignment_input" / "MMT_0W_rank3_d9.545.cif"
    window._assignment_source_input.setText(str(source))

    window._open_materials_studio_from_assignment()
    app.processEvents()

    assert window._step_stack.currentIndex() == window.PAGE_INDEX["materials-studio"]
    assert window._ms_structure_input.text() == str(source)
    assert window._ms_xsd_output_input.text().endswith("MMT_0W_rank3_d9.545_clayff.xsd")
    window.close()


@pytest.mark.skipif(not OVITO_QT_AVAILABLE, reason="OVITO Qt compatibility layer is unavailable.")
def test_visualizer_materials_studio_workspace_is_scrollable_on_laptop_viewport() -> None:
    app = QApplication.instance() or QApplication([])
    window = build_visualizer_window(
        clayff_path=Path("src/clayff_toolkit/resources/clayff.txt"),
        initial_page="materials-studio",
    )
    window.resize(1024, 768)
    window.show()
    app.processEvents()

    assert window.size().height() == 768
    assert window.minimumSizeHint().height() < 768
    assert window._content_scroll.verticalScrollBar().maximum() > 0
    window.close()


@pytest.mark.skipif(not OVITO_QT_AVAILABLE, reason="OVITO Qt compatibility layer is unavailable.")
def test_visualizer_materials_studio_off_audit_populates_report(monkeypatch, tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    window = build_visualizer_window(
        clayff_path=Path("src/clayff_toolkit/resources/clayff.txt"),
        initial_page="materials-studio",
    )
    off_path = tmp_path / "clayff.off"
    off_path.write_text("test", encoding="utf-8")
    report = MaterialStudioOffAuditReport(
        off_path=off_path,
        clayff_path=Path("src/clayff_toolkit/resources/clayff.txt"),
        atom_type_count=26,
        expected_atom_type_count=27,
        bond_count=3,
        angle_count=1,
        issues=(MaterialStudioOffAuditIssue("error", "missing-atom-type", "Missing ClayFF atom type: Cl"),),
    )
    monkeypatch.setattr(visualization_app, "audit_material_studio_off", lambda *args: report)
    window._ms_off_input.setText(str(off_path))

    window._run_material_studio_off_audit()
    app.processEvents()

    assert window._state.material_studio_off_report == report
    assert "状态: 未通过" in window._ms_off_summary.toPlainText()
    assert window._ms_off_issues.rowCount() == 1
    assert window._ms_off_issues.item(0, 1).text() == "missing-atom-type"
    window.close()


@pytest.mark.skipif(not OVITO_QT_AVAILABLE, reason="OVITO Qt compatibility layer is unavailable.")
def test_preview_uses_ovito_interactive_widget_when_available(monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    if not visualization_app.supports_interactive_qwidget():
        pytest.skip("Interactive OVITO Qt viewport is unavailable in this environment.")
    window = build_visualizer_window(
        clayff_path=Path("src/clayff_toolkit/resources/clayff.txt"),
    )

    def _fallback_should_not_run(*args, **kwargs):
        raise AssertionError("Static fallback should not be used when OVITO create_qwidget is available.")

    monkeypatch.setattr(visualization_app, "render_structure_preview", _fallback_should_not_run)
    window._render_substitution_preview(FIXTURES / "substitution_input" / "cammt_c2m_32.cif")
    app.processEvents()

    panel = window._substitution_preview
    assert panel.uses_ovito_widget is True
    assert panel.backend == "ovito"
    assert panel.preview_scene is not None
    assert panel._active_widget is panel.preview_scene.widget
    assert panel._active_widget is not panel.image
    window.close()


@pytest.mark.skipif(not OVITO_QT_AVAILABLE, reason="OVITO Qt compatibility layer is unavailable.")
def test_preview_enables_simulation_cell_vis_for_loaded_structure() -> None:
    app = QApplication.instance() or QApplication([])
    if not visualization_app.supports_interactive_qwidget():
        pytest.skip("Interactive OVITO Qt viewport is unavailable in this environment.")
    window = build_visualizer_window(
        clayff_path=Path("src/clayff_toolkit/resources/clayff.txt"),
    )

    window._render_substitution_preview(FIXTURES / "substitution_input" / "cammt_c2m_32.cif")
    app.processEvents()

    panel = window._substitution_preview
    assert panel.preview_scene is not None
    assert panel.cell_vis is not None
    assert panel.cell_vis.enabled is True
    assert panel.cell_vis.render_cell is True
    window.close()


@pytest.mark.skipif(not OVITO_AVAILABLE, reason="OVITO is unavailable.")
def test_build_structure_pipeline_keeps_simulation_cell_vis_enabled() -> None:
    structure = CifStructure(
        title="triclinic-preview",
        path=Path("triclinic-preview.cif"),
        cell=Cell(a=10.0, b=20.0, c=30.0, alpha=90.0, beta=90.0, gamma=60.0),
        atoms=(
            AtomSite(index=1, label="Si1", element="Si", frac=(1.2, -0.1, 0.5)),
        ),
    )

    pipeline, cell_vis = _build_structure_pipeline(structure)

    assert pipeline is not None
    assert cell_vis is not None
    assert cell_vis.enabled is True
    assert cell_vis.render_cell is True


@pytest.mark.skipif(not OVITO_QT_AVAILABLE, reason="OVITO Qt compatibility layer is unavailable.")
def test_loading_new_structure_recreates_ovito_preview_and_calls_zoom_all() -> None:
    app = QApplication.instance() or QApplication([])
    if not visualization_app.supports_interactive_qwidget():
        pytest.skip("Interactive OVITO Qt viewport is unavailable in this environment.")
    window = build_visualizer_window(
        clayff_path=Path("src/clayff_toolkit/resources/clayff.txt"),
    )

    panel = window._substitution_preview
    window._render_substitution_preview(FIXTURES / "substitution_input" / "cammt_c2m_32.cif")
    app.processEvents()
    first_scene = panel.preview_scene

    window._render_substitution_preview(FIXTURES / "assignment_input" / "MMT_0W_rank3_d9.545.cif")
    app.processEvents()
    second_scene = panel.preview_scene

    assert first_scene is not None
    assert second_scene is not None
    assert second_scene is not first_scene
    assert panel.zoom_all_size == panel.render_size
    window.close()


@pytest.mark.skipif(not OVITO_QT_AVAILABLE, reason="OVITO Qt compatibility layer is unavailable.")
def test_preview_falls_back_to_static_render_when_interactive_viewport_unavailable(monkeypatch, tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    window = build_visualizer_window(
        clayff_path=Path("src/clayff_toolkit/resources/clayff.txt"),
    )

    preview_path = tmp_path / "fallback-preview.png"
    pixmap = window.QPixmap(24, 24)
    pixmap.fill()
    pixmap.save(str(preview_path))

    monkeypatch.setattr(visualization_app, "supports_interactive_qwidget", lambda: False)
    monkeypatch.setattr(visualization_app, "render_structure_preview", lambda *args, **kwargs: preview_path)
    window._render_substitution_preview(FIXTURES / "substitution_input" / "cammt_c2m_32.cif")
    app.processEvents()

    panel = window._substitution_preview
    assert panel.uses_ovito_widget is False
    assert panel.backend == "fallback-static"
    assert panel.preview_scene is None
    window.close()


def test_configure_application_font_prefers_noto_sans_cjk_sc(monkeypatch, tmp_path: Path) -> None:
    class _FakeQFontDatabase:
        @staticmethod
        def addApplicationFont(path: str) -> int:
            return -1

        @staticmethod
        def applicationFontFamilies(font_id: int) -> list[str]:
            return []

        @staticmethod
        def families() -> list[str]:
            return ["Noto Sans CJK SC", "DejaVu Sans"]

    monkeypatch.setattr(visualization_app, "_qt_imports", lambda: {"QFont": _FakeQFont, "QFontDatabase": _FakeQFontDatabase})
    monkeypatch.setattr(visualization_app, "__file__", str(tmp_path / "app.py"))

    app = _DummyApp()
    family = visualization_app.configure_application_font(app)

    assert family == "Noto Sans CJK SC"
    assert app.font is not None
    assert app.font.family == "Noto Sans CJK SC"
    assert app.font.point_size == 10


def test_configure_application_font_falls_back_to_dejavu_sans(monkeypatch, tmp_path: Path) -> None:
    class _FakeQFontDatabase:
        @staticmethod
        def addApplicationFont(path: str) -> int:
            return -1

        @staticmethod
        def applicationFontFamilies(font_id: int) -> list[str]:
            return []

        @staticmethod
        def families() -> list[str]:
            return ["DejaVu Sans"]

    monkeypatch.setattr(visualization_app, "_qt_imports", lambda: {"QFont": _FakeQFont, "QFontDatabase": _FakeQFontDatabase})
    monkeypatch.setattr(visualization_app, "__file__", str(tmp_path / "app.py"))

    app = _DummyApp()
    family = visualization_app.configure_application_font(app)

    assert family == "DejaVu Sans"
    assert app.font is not None
    assert app.font.family == "DejaVu Sans"
    assert app.font.point_size == 10


def test_stylesheet_includes_cjk_font_fallbacks() -> None:
    assert '"Noto Sans CJK SC"' in visualization_app.STYLESHEET
    assert '"DejaVu Sans"' in visualization_app.STYLESHEET
