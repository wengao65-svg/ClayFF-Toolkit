"""Modern wizard-style PyQt UI for ClayFF-Toolkit workflows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..assignment import (
    AssignedStructure,
    CifStructure,
    assign_file,
    assign_structure_file,
    default_clayff_path,
    load_clayff,
    load_structure,
    summarize_assignment,
    summarize_structure,
    write_material_studio_xsd,
)
from ..assignment.lammps_writer import write_lammps_data
from ..assignment.params import ClayFFParameters
from ..substitution import run_substitution_case
from ..validation import (
    DataValidationReport,
    ValidationReport,
    summarize_data_file,
    validate_assigned_structure,
    validate_data_file,
)
from .ovito_preview import (
    DEFAULT_RENDER_SIZE,
    create_ovito_preview_widget,
    dispose_preview_scene,
    render_structure_preview,
    supports_interactive_qwidget,
)


def _qt_imports():
    try:
        # OVITO owns the Qt compatibility layer used by the embedded preview.
        from ovito.qt_compat import QtCore, QtGui, QtWidgets

        Qt = QtCore.Qt
        QFont = QtGui.QFont
        QFontDatabase = QtGui.QFontDatabase
        QPixmap = QtGui.QPixmap
        QApplication = QtWidgets.QApplication
        QComboBox = QtWidgets.QComboBox
        QFileDialog = QtWidgets.QFileDialog
        QFrame = QtWidgets.QFrame
        QGridLayout = QtWidgets.QGridLayout
        QGroupBox = QtWidgets.QGroupBox
        QHBoxLayout = QtWidgets.QHBoxLayout
        QHeaderView = QtWidgets.QHeaderView
        QLabel = QtWidgets.QLabel
        QLineEdit = QtWidgets.QLineEdit
        QMainWindow = QtWidgets.QMainWindow
        QMessageBox = QtWidgets.QMessageBox
        QPushButton = QtWidgets.QPushButton
        QSpinBox = QtWidgets.QSpinBox
        QStackedWidget = QtWidgets.QStackedWidget
        QTableWidget = QtWidgets.QTableWidget
        QTableWidgetItem = QtWidgets.QTableWidgetItem
        QTextEdit = QtWidgets.QTextEdit
        QVBoxLayout = QtWidgets.QVBoxLayout
        QWidget = QtWidgets.QWidget
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "PySide6 and OVITO are required for the visualizer. "
            "Install GUI dependencies with `bash scripts/install-clayff-toolkit.sh` on Linux or "
            "`powershell -ExecutionPolicy Bypass -File scripts\\install-clayff-toolkit.ps1` on Windows."
        ) from exc
    return {
        "QApplication": QApplication,
        "QComboBox": QComboBox,
        "QFileDialog": QFileDialog,
        "QFrame": QFrame,
        "QFont": QFont,
        "QFontDatabase": QFontDatabase,
        "QGridLayout": QGridLayout,
        "QGroupBox": QGroupBox,
        "QHBoxLayout": QHBoxLayout,
        "QHeaderView": QHeaderView,
        "QLabel": QLabel,
        "QLineEdit": QLineEdit,
        "QMainWindow": QMainWindow,
        "QMessageBox": QMessageBox,
        "QPixmap": QPixmap,
        "QPushButton": QPushButton,
        "QSpinBox": QSpinBox,
        "QStackedWidget": QStackedWidget,
        "QTableWidget": QTableWidget,
        "QTableWidgetItem": QTableWidgetItem,
        "QTextEdit": QTextEdit,
        "QVBoxLayout": QVBoxLayout,
        "QWidget": QWidget,
        "Qt": Qt,
    }


STYLESHEET = """
QMainWindow, QWidget {
    background: #f6f8fb;
    color: #1f2a37;
    font-size: 13px;
    font-family: "Noto Sans CJK SC", "Noto Sans CJK", "Source Han Sans SC",
                 "Microsoft YaHei", "WenQuanYi Micro Hei", "DejaVu Sans", sans-serif;
}
QFrame#Sidebar {
    background: #ffffff;
    border-right: 1px solid #e6ebf2;
}
QFrame#ContentArea {
    background: #f6f8fb;
}
QFrame#Card {
    background: #ffffff;
    border: 1px solid #e7edf5;
    border-radius: 18px;
}
QPushButton#PrimaryAction {
    background: #1967d2;
    color: white;
    border: none;
    border-radius: 12px;
    padding: 12px 18px;
    font-weight: 600;
}
QPushButton#PrimaryAction:hover {
    background: #1659b6;
}
QPushButton#GhostAction {
    background: #ffffff;
    border: 1px solid #d8e1ee;
    border-radius: 12px;
    padding: 10px 16px;
}
QPushButton#StepButton {
    text-align: left;
    border: none;
    border-radius: 14px;
    padding: 14px 16px;
    background: transparent;
}
QPushButton#StepButton[active="true"] {
    background: #e8f0fe;
    color: #1967d2;
    font-weight: 700;
}
QPushButton#StepButton[done="true"] {
    background: #edf7ee;
    color: #1f7a44;
}
QLineEdit, QComboBox, QSpinBox, QTextEdit, QTableWidget {
    background: #ffffff;
    border: 1px solid #d8e1ee;
    border-radius: 10px;
    padding: 8px 10px;
}
QTableWidget {
    gridline-color: #edf1f7;
}
QHeaderView::section {
    background: #f7f9fc;
    border: none;
    border-bottom: 1px solid #e8edf4;
    padding: 8px;
    font-weight: 600;
}
QLabel#Badge {
    background: #eef6ff;
    color: #1967d2;
    border-radius: 999px;
    padding: 6px 10px;
}
QLabel#SuccessBadge {
    background: #edf7ee;
    color: #1f7a44;
    border-radius: 999px;
    padding: 6px 10px;
}
"""


FONT_FAMILY_PRIORITY = (
    "Noto Sans CJK SC",
    "Noto Sans CJK",
    "Source Han Sans SC",
    "Microsoft YaHei",
    "WenQuanYi Micro Hei",
    "DejaVu Sans",
)

_BUNDLED_FONT_FILES = (
    "NotoSansCJKsc-Regular.otf",
    "SourceHanSansSC-Regular.otf",
)


def configure_application_font(app) -> str:
    qt = _qt_imports()
    QFont = qt["QFont"]
    QFontDatabase = qt["QFontDatabase"]

    font_dir = Path(__file__).resolve().parent / "assets" / "fonts"
    for font_filename in _BUNDLED_FONT_FILES:
        font_path = font_dir / font_filename
        if not font_path.exists():
            continue
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        if font_id < 0:
            continue
        loaded_families = QFontDatabase.applicationFontFamilies(font_id)
        if not loaded_families:
            continue
        loaded_family = loaded_families[0]
        app.setFont(QFont(loaded_family, 10))
        return loaded_family

    available_families = set(QFontDatabase.families())
    for family in FONT_FAMILY_PRIORITY:
        if family in available_families:
            app.setFont(QFont(family, 10))
            return family

    fallback_family = "DejaVu Sans"
    app.setFont(QFont(fallback_family, 10))
    return fallback_family


@dataclass
class WorkflowState:
    clayff_path: Path
    input_structure_path: Path | None = None
    substituted_structure_path: Path | None = None
    assignment_source_path: Path | None = None
    output_data_path: Path | None = None
    output_xsd_path: Path | None = None
    structure: CifStructure | None = None
    assigned: AssignedStructure | None = None
    forcefield: ClayFFParameters | None = None
    substitution_log: dict[str, Any] | None = None
    validation_report: ValidationReport | None = None
    data_validation_report: DataValidationReport | None = None


def _warning_atom_indices(report: ValidationReport | None) -> set[int]:
    if report is None:
        return set()
    return {
        atom_index
        for warning in report.warnings
        for atom_index in warning.atom_indices
    }


def _neighbor_indices(structure: CifStructure, selected_index: int | None) -> list[int]:
    if selected_index is None:
        return []
    selected = structure.atoms[selected_index]
    pairs = []
    for index, atom in enumerate(structure.atoms):
        if index == selected_index:
            continue
        distance = structure.cell.distance(selected.frac, atom.frac)
        pairs.append((distance, index))
    pairs.sort(key=lambda item: item[0])
    return [index for _, index in pairs[:6]]


class _PreviewPanel:
    def __init__(self, qt: dict[str, object], title: str):
        QLabel = qt["QLabel"]
        QFrame = qt["QFrame"]
        QVBoxLayout = qt["QVBoxLayout"]
        QWidget = qt["QWidget"]

        self.root = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        self.title = QLabel(title)
        self.title.setObjectName("Badge")
        self.viewport_host = QFrame()
        self.viewport_host.setMinimumHeight(360)
        self.viewport_host.setStyleSheet(
            "background:#ffffff; border:1px solid #d8e1ee; border-radius:16px; padding:12px;"
        )
        self._viewport_layout = QVBoxLayout()
        self._viewport_layout.setContentsMargins(12, 12, 12, 12)
        self._viewport_layout.setSpacing(0)
        self.viewport_host.setLayout(self._viewport_layout)
        self.image = QLabel("No preview")
        self.image.setAlignment(qt["Qt"].AlignmentFlag.AlignCenter)
        self.caption = QLabel("Load or generate a structure to render.")
        self.caption.setWordWrap(True)
        self.render_size = DEFAULT_RENDER_SIZE
        self.projected_points = None
        self.preview_scene = None
        self.uses_ovito_widget = False
        self.backend = "empty"
        self.cell_vis = None
        self.zoom_all_size = None
        self._active_widget = None
        self._set_active_widget(self.image)
        layout.addWidget(self.title)
        layout.addWidget(self.viewport_host, 1)
        layout.addWidget(self.caption)
        self.root.setLayout(layout)

    def _set_active_widget(self, widget) -> None:
        while self._viewport_layout.count():
            item = self._viewport_layout.takeAt(0)
            child = item.widget()
            if child is not None:
                child.setParent(None)
        self._viewport_layout.addWidget(widget, 1)
        self._active_widget = widget

    def clear_scene(self) -> None:
        dispose_preview_scene(self.preview_scene)
        self.preview_scene = None
        self.uses_ovito_widget = False
        self.backend = "empty"
        self.cell_vis = None
        self.zoom_all_size = None

    def show_message(self, text: str) -> None:
        self.clear_scene()
        self.image.clear()
        self.image.setText(text)
        self._set_active_widget(self.image)

    def show_pixmap(self, pixmap) -> None:
        self.clear_scene()
        self.image.setPixmap(pixmap)
        self._set_active_widget(self.image)
        self.backend = "fallback-static"

    def show_ovito_scene(self, scene) -> None:
        self.clear_scene()
        self.preview_scene = scene
        self.uses_ovito_widget = True
        self.backend = scene.backend
        self.cell_vis = scene.cell_vis
        self.zoom_all_size = scene.zoom_all_size
        self._set_active_widget(scene.widget)

    def dispose(self) -> None:
        self.clear_scene()


class ClayFFWizardWindow:
    def __init__(self, clayff_path: str | Path | None = None, data_path: str | Path | None = None):
        qt = _qt_imports()
        self.qt = qt
        self.QApplication = qt["QApplication"]
        self.QComboBox = qt["QComboBox"]
        self.QFileDialog = qt["QFileDialog"]
        self.QFrame = qt["QFrame"]
        self.QGridLayout = qt["QGridLayout"]
        self.QGroupBox = qt["QGroupBox"]
        self.QHBoxLayout = qt["QHBoxLayout"]
        self.QHeaderView = qt["QHeaderView"]
        self.QLabel = qt["QLabel"]
        self.QLineEdit = qt["QLineEdit"]
        self.QMainWindow = qt["QMainWindow"]
        self.QMessageBox = qt["QMessageBox"]
        self.QPixmap = qt["QPixmap"]
        self.QPushButton = qt["QPushButton"]
        self.QSpinBox = qt["QSpinBox"]
        self.QStackedWidget = qt["QStackedWidget"]
        self.QTableWidget = qt["QTableWidget"]
        self.QTableWidgetItem = qt["QTableWidgetItem"]
        self.QTextEdit = qt["QTextEdit"]
        self.QVBoxLayout = qt["QVBoxLayout"]
        self.QWidget = qt["QWidget"]
        self.Qt = qt["Qt"]

        self._window = self.QMainWindow()
        self._window.setWindowTitle("ClayFF Toolkit Workbench")
        self._window.resize(1540, 980)
        self._window.setStyleSheet(STYLESHEET)

        self._state = WorkflowState(
            clayff_path=Path(clayff_path) if clayff_path else default_clayff_path()
        )
        self._last_data_path = Path(data_path) if data_path else None
        self._selected_atom_index: int | None = None
        self._suspend_atom_selection = False

        self._step_buttons: list[object] = []
        self._step_stack = self.QStackedWidget()
        self._current_step = 0

        self._build_ui()
        self._load_forcefield(self._state.clayff_path)
        if self._last_data_path:
            self._populate_export_preview(self._last_data_path)

    def __getattr__(self, name: str):
        return getattr(self._window, name)

    def show(self):
        return self._window.show()

    def close(self):
        if hasattr(self, "_substitution_preview"):
            self._substitution_preview.dispose()
        return self._window.close()

    @property
    def _structure(self):
        return self._state.structure

    @property
    def _assigned(self):
        return self._state.assigned

    @property
    def _validation_report(self):
        return self._state.validation_report

    def _build_ui(self):
        root = self.QWidget()
        main_layout = self.QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        sidebar = self._build_sidebar()
        content = self._build_content()
        main_layout.addWidget(sidebar)
        main_layout.addWidget(content, 1)
        root.setLayout(main_layout)
        self._window.setCentralWidget(root)

    def _build_sidebar(self):
        sidebar = self.QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(250)
        layout = self.QVBoxLayout()
        layout.setContentsMargins(18, 24, 18, 24)
        layout.setSpacing(16)

        brand = self.QLabel("ClayFF Toolkit")
        brand.setStyleSheet("font-size:18px; font-weight:700; color:#0f172a;")
        subtitle = self.QLabel("Step-by-step workflow")
        subtitle.setStyleSheet("color:#64748b;")
        layout.addWidget(brand)
        layout.addWidget(subtitle)

        steps = [
            ("1", "同晶替换", "生成替换后结构"),
            ("2", "力场赋予", "分配 ClayFF 类型与电荷"),
            ("3", "力场校验", "检查 profile、告警并导出"),
        ]
        for index, (_num, title, desc) in enumerate(steps):
            button = self.QPushButton(f"{title}\n{desc}")
            button.setObjectName("StepButton")
            button.clicked.connect(lambda _checked=False, idx=index: self._go_to_step(idx))
            layout.addWidget(button)
            self._step_buttons.append(button)

        layout.addStretch(1)
        self._ready_card = self.QLabel("Ready\n等待载入结构。")
        self._ready_card.setStyleSheet(
            "background:#ffffff; border:1px solid #e7edf5; border-radius:16px; padding:16px; "
            "color:#0f172a; line-height:1.5;"
        )
        layout.addWidget(self._ready_card)
        sidebar.setLayout(layout)
        self._update_step_buttons()
        return sidebar

    def _build_content(self):
        content = self.QFrame()
        content.setObjectName("ContentArea")
        layout = self.QVBoxLayout()
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        self._header_title = self.QLabel("同晶替换")
        self._header_title.setStyleSheet("font-size:28px; font-weight:700; color:#0f172a;")
        self._header_subtitle = self.QLabel("先生成替换后的结构，再进入力场赋予。")
        self._header_subtitle.setStyleSheet("color:#64748b; font-size:14px;")
        layout.addWidget(self._header_title)
        layout.addWidget(self._header_subtitle)

        self._build_substitution_page()
        self._build_assignment_page()
        self._build_validation_page()

        layout.addWidget(self._step_stack, 1)
        content.setLayout(layout)
        return content

    def _make_card(self, title: str):
        card = self.QFrame()
        card.setObjectName("Card")
        layout = self.QVBoxLayout()
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)
        title_label = self.QLabel(title)
        title_label.setStyleSheet("font-size:16px; font-weight:700;")
        layout.addWidget(title_label)
        card.setLayout(layout)
        return card, layout

    def _build_substitution_page(self):
        page = self.QWidget()
        layout = self.QHBoxLayout()
        layout.setSpacing(18)

        left_card, left_layout = self._make_card("步骤 1：同晶替换")
        form = self.QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(12)

        self._input_path_input = self.QLineEdit()
        self._sub_output_input = self.QLineEdit()
        self._preset_input = self.QComboBox()
        self._preset_input.addItems(["tetra-octa", "octa-only"])
        self._interlayer_input = self.QComboBox()
        self._interlayer_input.addItems(["Ca", "Na"])
        self._seed_input = self.QSpinBox()
        self._seed_input.setMaximum(999999999)
        self._seed_input.setValue(20260402)

        browse_input = self.QPushButton("选择结构")
        browse_input.setObjectName("GhostAction")
        browse_input.clicked.connect(self._choose_input_structure)
        browse_output = self.QPushButton("输出路径")
        browse_output.setObjectName("GhostAction")
        browse_output.clicked.connect(self._choose_substitution_output)
        import_existing = self.QPushButton("导入已有替换结果")
        import_existing.setObjectName("GhostAction")
        import_existing.clicked.connect(self._import_existing_substitution)
        run_button = self.QPushButton("运行同晶替换")
        run_button.setObjectName("PrimaryAction")
        run_button.clicked.connect(self._run_substitution_stage)
        next_button = self.QPushButton("下一步：力场赋予")
        next_button.setObjectName("GhostAction")
        next_button.clicked.connect(lambda: self._go_to_step(1))
        self._substitution_next_button = next_button
        self._substitution_next_button.setEnabled(False)

        form.addWidget(self.QLabel("输入结构"), 0, 0)
        form.addWidget(self._input_path_input, 0, 1)
        form.addWidget(browse_input, 0, 2)
        form.addWidget(self.QLabel("替换输出"), 1, 0)
        form.addWidget(self._sub_output_input, 1, 1)
        form.addWidget(browse_output, 1, 2)
        form.addWidget(self.QLabel("替换规则"), 2, 0)
        form.addWidget(self._preset_input, 2, 1)
        form.addWidget(self.QLabel("层间离子"), 3, 0)
        form.addWidget(self._interlayer_input, 3, 1)
        form.addWidget(self.QLabel("随机种子"), 4, 0)
        form.addWidget(self._seed_input, 4, 1)

        action_row = self.QHBoxLayout()
        action_row.addWidget(import_existing)
        action_row.addWidget(run_button)
        action_row.addWidget(next_button)
        action_row.addStretch(1)

        self._substitution_summary = self.QTextEdit()
        self._substitution_summary.setReadOnly(True)
        self._substitution_summary.setMinimumHeight(200)

        left_layout.addLayout(form)
        left_layout.addLayout(action_row)
        left_layout.addWidget(self._substitution_summary, 1)

        right_card, right_layout = self._make_card("结构预览")
        self._substitution_preview = _PreviewPanel(self.qt, "OVITO Preview")
        right_layout.addWidget(self._substitution_preview.root, 1)

        layout.addWidget(left_card, 1)
        layout.addWidget(right_card, 1)
        page.setLayout(layout)
        self._step_stack.addWidget(page)

    def _build_assignment_page(self):
        page = self.QWidget()
        layout = self.QHBoxLayout()
        layout.setSpacing(18)

        left_card, left_layout = self._make_card("步骤 2：力场赋予")
        form = self.QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(12)

        self._clayff_path_input = self.QLineEdit(str(self._state.clayff_path))
        self._assignment_source_input = self.QLineEdit()

        browse_clayff = self.QPushButton("ClayFF 文件")
        browse_clayff.setObjectName("GhostAction")
        browse_clayff.clicked.connect(self._choose_clayff)
        browse_assignment_source = self.QPushButton("结构文件")
        browse_assignment_source.setObjectName("GhostAction")
        browse_assignment_source.clicked.connect(self._choose_assignment_source)
        export_from_assignment = self.QPushButton("导出当前 data")
        export_from_assignment.setObjectName("GhostAction")
        export_from_assignment.clicked.connect(self._export_data)
        export_xsd = self.QPushButton("导出 Material Studio XSD")
        export_xsd.setObjectName("GhostAction")
        export_xsd.clicked.connect(self._export_material_studio_xsd)
        run_button = self.QPushButton("运行力场赋予")
        run_button.setObjectName("PrimaryAction")
        run_button.clicked.connect(self._run_assignment_stage)
        next_button = self.QPushButton("下一步：力场校验")
        next_button.setObjectName("GhostAction")
        next_button.clicked.connect(self._enter_validation_step)
        self._assignment_next_button = next_button
        self._assignment_next_button.setEnabled(False)

        form.addWidget(self.QLabel("ClayFF 文件"), 0, 0)
        form.addWidget(self._clayff_path_input, 0, 1)
        form.addWidget(browse_clayff, 0, 2)
        form.addWidget(self.QLabel("结构来源"), 1, 0)
        form.addWidget(self._assignment_source_input, 1, 1)
        form.addWidget(browse_assignment_source, 1, 2)

        action_row = self.QHBoxLayout()
        action_row.addWidget(export_from_assignment)
        action_row.addWidget(export_xsd)
        action_row.addWidget(run_button)
        action_row.addWidget(next_button)
        action_row.addStretch(1)

        search_row = self.QHBoxLayout()
        self._atom_search_input = self.QLineEdit()
        self._atom_search_input.setPlaceholderText("搜索原子标签、元素或类型")
        self._atom_search_input.textChanged.connect(self._apply_atom_filters)
        self._atom_element_filter = self.QComboBox()
        self._atom_element_filter.currentTextChanged.connect(self._apply_atom_filters)
        self._atom_type_filter = self.QComboBox()
        self._atom_type_filter.currentTextChanged.connect(self._apply_atom_filters)
        search_row.addWidget(self._atom_search_input, 2)
        search_row.addWidget(self._atom_element_filter, 1)
        search_row.addWidget(self._atom_type_filter, 1)

        self._assignment_summary = self.QTextEdit()
        self._assignment_summary.setReadOnly(True)
        self._assignment_summary.setMinimumHeight(180)
        self._local_environment = self.QTextEdit()
        self._local_environment.setReadOnly(True)
        self._local_environment.setMinimumHeight(160)

        self._atom_table = self.QTableWidget(0, 8)
        self._atom_table.setHorizontalHeaderLabels(
            ["ID", "Label", "Element", "ClayFF", "Charge", "fx", "fy", "fz"]
        )
        self._atom_table.setSelectionBehavior(self.QTableWidget.SelectionBehavior.SelectRows)
        self._atom_table.itemSelectionChanged.connect(self._on_atom_selection)
        self._atom_table.horizontalHeader().setSectionResizeMode(self.QHeaderView.ResizeMode.Stretch)

        left_layout.addLayout(form)
        left_layout.addLayout(action_row)
        left_layout.addWidget(self._assignment_summary)
        left_layout.addWidget(self._local_environment)
        left_layout.addLayout(search_row)
        left_layout.addWidget(self._atom_table, 1)
        layout.addWidget(left_card, 1)
        page.setLayout(layout)
        self._step_stack.addWidget(page)

    def _build_validation_page(self):
        page = self.QWidget()
        layout = self.QHBoxLayout()
        layout.setSpacing(18)

        left_card, left_layout = self._make_card("步骤 3：力场校验与导出")
        form = self.QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(12)

        self._validation_data_input = self.QLineEdit()
        choose_validation_data = self.QPushButton("选择 data")
        choose_validation_data.setObjectName("GhostAction")
        choose_validation_data.clicked.connect(self._choose_validation_data)
        use_assignment_data = self.QPushButton("使用当前赋予结果")
        use_assignment_data.setObjectName("GhostAction")
        use_assignment_data.clicked.connect(self._prepare_data_from_assignment)
        run_validation_button = self.QPushButton("运行力场校验")
        run_validation_button.setObjectName("PrimaryAction")
        run_validation_button.clicked.connect(self._run_validation_stage)

        form.addWidget(self.QLabel("校验 data"), 0, 0)
        form.addWidget(self._validation_data_input, 0, 1)
        form.addWidget(choose_validation_data, 0, 2)
        form.addWidget(self.QLabel("串联模式"), 1, 0)
        form.addWidget(use_assignment_data, 1, 1, 1, 2)

        top_row = self.QHBoxLayout()
        export_button = self.QPushButton("导出 LAMMPS data")
        export_button.setObjectName("PrimaryAction")
        export_button.clicked.connect(self._export_data)
        load_existing_data = self.QPushButton("载入已有 data")
        load_existing_data.setObjectName("GhostAction")
        load_existing_data.clicked.connect(self._load_existing_data)
        output_browse = self.QPushButton("输出路径")
        output_browse.setObjectName("GhostAction")
        output_browse.clicked.connect(self._choose_output_data)
        self._data_path_input = self.QLineEdit()
        top_row.addWidget(self.QLabel("输出 data"))
        top_row.addWidget(self._data_path_input, 1)
        top_row.addWidget(load_existing_data)
        top_row.addWidget(output_browse)
        top_row.addWidget(export_button)

        self._validation_summary = self.QTextEdit()
        self._validation_summary.setReadOnly(True)
        self._validation_summary.setMinimumHeight(220)
        self._warnings_table = self.QTableWidget(0, 3)
        self._warnings_table.setHorizontalHeaderLabels(["Severity", "Code", "Message"])
        self._warnings_table.horizontalHeader().setSectionResizeMode(self.QHeaderView.ResizeMode.Stretch)
        self._assignment_table = self.QTableWidget(0, 2)
        self._assignment_table.setHorizontalHeaderLabels(["Atom Type", "Count"])
        self._assignment_table.horizontalHeader().setSectionResizeMode(self.QHeaderView.ResizeMode.Stretch)
        self._data_summary = self.QTextEdit()
        self._data_summary.setReadOnly(True)
        self._data_summary.setMinimumHeight(180)

        left_layout.addLayout(form)
        left_layout.addWidget(run_validation_button)
        left_layout.addLayout(top_row)
        left_layout.addWidget(self._validation_summary)
        left_layout.addWidget(self.QLabel("Validation warnings"))
        left_layout.addWidget(self._warnings_table, 1)
        left_layout.addWidget(self.QLabel("Data atom type counts"))
        left_layout.addWidget(self._assignment_table, 1)
        left_layout.addWidget(self._data_summary)

        layout.addWidget(left_card, 1)
        page.setLayout(layout)
        self._step_stack.addWidget(page)

    def _go_to_step(self, index: int):
        self._current_step = index
        self._step_stack.setCurrentIndex(index)
        headers = [
            ("同晶替换", "可独立执行同晶替换，也可把结果作为后续力场赋予的上游输入。"),
            ("力场赋予", "可独立载入结构执行 ClayFF 分配，也可承接同晶替换结果。"),
            ("力场校验", "只校验 data 文件；可独立载入 data，也可承接当前赋予结果导出后的 data。"),
        ]
        self._header_title.setText(headers[index][0])
        self._header_subtitle.setText(headers[index][1])
        if index == 2 and self._state.data_validation_report is not None:
            self._populate_validation_views()
        self._update_step_buttons()

    def _update_step_buttons(self):
        for index, button in enumerate(self._step_buttons):
            button.setProperty("active", index == self._current_step)
            done = False
            if index == 0:
                done = self._state.substitution_log is not None
            elif index == 1:
                done = self._state.assigned is not None
            button.setProperty("done", done)
            button.style().unpolish(button)
            button.style().polish(button)

        ready_lines = ["Ready"]
        if self._state.input_structure_path:
            ready_lines.append(f"Input: {self._state.input_structure_path.name}")
        if self._state.substituted_structure_path:
            ready_lines.append(f"Substituted: {self._state.substituted_structure_path.name}")
        if self._state.assigned:
            ready_lines.append(f"Assigned atoms: {len(self._state.assigned.atoms)}")
        self._ready_card.setText("\n".join(ready_lines))

    def _default_data_output_path(self, source_path: Path | None) -> Path | None:
        if source_path is None:
            return None
        return source_path.with_suffix(".data")

    def _default_xsd_output_path(self, source_path: Path | None) -> Path | None:
        if source_path is None:
            return None
        return source_path.with_name(f"{source_path.stem}_clayff.xsd")

    def _invalidate_downstream_data_state(self, source_path: Path | None = None):
        self._state.output_data_path = None
        self._state.output_xsd_path = None
        self._state.data_validation_report = None
        if hasattr(self, "_validation_data_input"):
            self._validation_data_input.clear()
        suggested = self._default_data_output_path(source_path)
        if hasattr(self, "_data_path_input"):
            self._data_path_input.setText(str(suggested) if suggested is not None else "")
        if hasattr(self, "_validation_summary"):
            self._validation_summary.clear()
        if hasattr(self, "_data_summary"):
            self._data_summary.clear()
        if hasattr(self, "_warnings_table"):
            self._warnings_table.setRowCount(0)
        if hasattr(self, "_assignment_table"):
            self._assignment_table.setRowCount(0)

    def _choose_input_structure(self):
        path, _ = self.QFileDialog.getOpenFileName(
            self._window,
            "选择输入结构",
            "",
            "Structures (*.cif *.xyz *.extxyz *.vasp *.poscar *.contcar *.res);;All Files (*)",
        )
        if path:
            self._input_path_input.setText(path)
            input_path = Path(path)
            self._state.input_structure_path = input_path
            if not self._sub_output_input.text().strip():
                self._sub_output_input.setText(str(input_path.with_name(f"{input_path.stem}_substituted{input_path.suffix or '.cif'}")))
            self._render_substitution_preview(input_path)
            self._update_step_buttons()

    def _choose_substitution_output(self):
        path, _ = self.QFileDialog.getSaveFileName(
            self._window,
            "选择替换输出结构",
            "",
            "Structures (*.cif *.xyz);;All Files (*)",
        )
        if path:
            self._sub_output_input.setText(path)

    def _choose_assignment_source(self):
        path, _ = self.QFileDialog.getOpenFileName(
            self._window,
            "选择赋予用结构",
            "",
            "Structures (*.cif *.xsd *.xyz *.extxyz *.vasp *.poscar *.contcar *.res);;All Files (*)",
        )
        if path:
            self._assignment_source_input.setText(path)

    def _choose_clayff(self):
        path, _ = self.QFileDialog.getOpenFileName(self._window, "选择 ClayFF 文件", "", "Text (*.txt)")
        if path:
            self._clayff_path_input.setText(path)
            self._load_forcefield(Path(path))

    def _choose_validation_clayff(self):
        path, _ = self.QFileDialog.getOpenFileName(self._window, "选择 ClayFF 文件", "", "Text (*.txt)")
        if path:
            self._clayff_path_input.setText(path)

    def _choose_output_data(self):
        path, _ = self.QFileDialog.getSaveFileName(self._window, "选择 data 输出路径", "", "LAMMPS data (*.data)")
        if path:
            self._data_path_input.setText(path)

    def _choose_validation_data(self):
        path, _ = self.QFileDialog.getOpenFileName(
            self._window,
            "选择校验用 data",
            "",
            "LAMMPS data (*.data);;All Files (*)",
        )
        if path:
            self._validation_data_input.setText(path)

    def _load_forcefield(self, path: Path):
        try:
            self._state.forcefield = load_clayff(path)
        except Exception as exc:
            self.QMessageBox.critical(self._window, "ClayFF 载入失败", str(exc))
            return
        self._state.clayff_path = path
        if hasattr(self, "_clayff_path_input"):
            self._clayff_path_input.setText(str(path))

    def _run_substitution_stage(self):
        input_text = self._input_path_input.text().strip()
        output_text = self._sub_output_input.text().strip()
        if not input_text:
            self.QMessageBox.warning(self._window, "缺少输入", "请先选择输入结构。")
            return
        input_path = Path(input_text)
        output_path = Path(output_text) if output_text else input_path.with_name(f"{input_path.stem}_substituted{input_path.suffix or '.cif'}")
        try:
            payload = run_substitution_case(
                input_path=input_path,
                output_path=output_path,
                preset=self._preset_input.currentText(),
                interlayer_species=self._interlayer_input.currentText(),
                seed=self._seed_input.value(),
            )
        except Exception as exc:
            self.QMessageBox.critical(self._window, "同晶替换失败", str(exc))
            return
        self._state.input_structure_path = input_path
        self._state.substituted_structure_path = output_path
        self._state.assignment_source_path = output_path
        self._state.substitution_log = payload
        self._invalidate_downstream_data_state(output_path)
        self._assignment_source_input.setText(str(output_path))
        self._substitution_next_button.setEnabled(True)
        self._substitution_summary.setPlainText(
            "\n".join(
                [
                    f"输入结构: {input_path}",
                    f"输出结构: {output_path}",
                    f"规则: {payload['rule']}",
                    f"层间离子: {payload['charge_balance']['interlayer_species']}",
                    f"四面体替换数: {payload['substitutions']['tetra_count']}",
                    f"八面体替换数: {payload['substitutions']['octa_count']}",
                    f"层电荷: {payload['charge_balance']['layer_charge']}",
                    f"平衡层间离子数: {payload['charge_balance']['interlayer_count']}",
                    f"位置约束层级: {payload['placement_label']} #{payload['placement_tier_index']}",
                ]
            )
        )
        self._render_substitution_preview(output_path)
        self._update_step_buttons()
        self._ready_card.setText("Ready\n同晶替换完成，可进入力场赋予。")

    def _import_existing_substitution(self):
        path, _ = self.QFileDialog.getOpenFileName(
            self._window,
            "导入已有替换结果",
            "",
            "Structures (*.cif *.xyz *.extxyz *.vasp *.poscar *.contcar *.res);;All Files (*)",
        )
        if not path:
            return
        imported = Path(path)
        self._state.substituted_structure_path = imported
        self._state.assignment_source_path = imported
        self._invalidate_downstream_data_state(imported)
        self._assignment_source_input.setText(str(imported))
        self._substitution_summary.setPlainText(
            "\n".join(
                [
                    f"已导入替换结果: {imported}",
                    "该结构将作为力场赋予步骤的输入。",
                ]
            )
        )
        self._substitution_next_button.setEnabled(True)
        self._render_substitution_preview(imported)
        self._update_step_buttons()

    def _run_assignment_stage(self):
        source_text = self._assignment_source_input.text().strip()
        if not source_text:
            if self._state.substituted_structure_path:
                source_text = str(self._state.substituted_structure_path)
                self._assignment_source_input.setText(source_text)
            elif self._state.input_structure_path:
                source_text = str(self._state.input_structure_path)
                self._assignment_source_input.setText(source_text)
        if not source_text:
            self.QMessageBox.warning(self._window, "缺少结构", "请先选择赋予用结构。")
            return

        clayff_path = Path(self._clayff_path_input.text().strip() or str(default_clayff_path()))
        self._load_forcefield(clayff_path)
        if self._state.forcefield is None:
            return

        try:
            structure, assigned, forcefield = assign_structure_file(source_text, clayff_path)
        except Exception as exc:
            self.QMessageBox.critical(self._window, "力场赋予失败", str(exc))
            return

        self._state.assignment_source_path = Path(source_text)
        self._state.structure = structure
        self._state.assigned = assigned
        self._state.forcefield = forcefield
        self._state.validation_report = validate_assigned_structure(assigned)
        self._selected_atom_index = 0 if assigned.atoms else None
        self._invalidate_downstream_data_state(Path(source_text))

        self._populate_assignment_views()
        self._populate_validation_views()
        self._assignment_next_button.setEnabled(True)
        self._update_step_buttons()
        self._ready_card.setText("Ready\n力场赋予完成，可进入力场校验。")

    def _enter_validation_step(self):
        if self._state.output_data_path and not self._validation_data_input.text().strip():
            self._validation_data_input.setText(str(self._state.output_data_path))
        self._go_to_step(2)

    def _prepare_data_from_assignment(self):
        if self._state.assigned is None or self._state.forcefield is None or self._state.structure is None:
            self.QMessageBox.warning(self._window, "无法生成 data", "请先完成力场赋予。")
            return
        output_text = self._data_path_input.text().strip()
        if not output_text:
            if self._state.assignment_source_path:
                output_text = str(self._state.assignment_source_path.with_suffix(".data"))
                self._data_path_input.setText(output_text)
            else:
                self.QMessageBox.warning(self._window, "缺少输出路径", "请先设置 data 输出路径。")
                return
        output_path = Path(output_text)
        try:
            write_lammps_data(self._state.assigned, self._state.forcefield, output_path)
        except Exception as exc:
            self.QMessageBox.critical(self._window, "生成 data 失败", str(exc))
            return
        self._state.output_data_path = output_path
        self._validation_data_input.setText(str(output_path))
        self._populate_export_preview(output_path)
        self._ready_card.setText(f"Ready\n已生成校验用 data: {output_path.name}")

    def _run_validation_stage(self):
        data_text = self._validation_data_input.text().strip()
        if not data_text and self._state.output_data_path is not None:
            data_text = str(self._state.output_data_path)
            self._validation_data_input.setText(data_text)
        if not data_text:
            self.QMessageBox.warning(self._window, "缺少 data", "请先选择要校验的 data 文件。")
            return

        data_path = Path(data_text)
        try:
            report = validate_data_file(data_path)
        except Exception as exc:
            self.QMessageBox.critical(self._window, "力场校验失败", str(exc))
            return

        self._state.output_data_path = data_path
        self._state.data_validation_report = report
        self._populate_validation_views()
        self._ready_card.setText("Ready\n力场校验完成，可直接导出或继续检查。")

    def _export_data(self):
        if self._state.assigned is None or self._state.forcefield is None or self._state.structure is None:
            self.QMessageBox.warning(self._window, "无法导出", "请先完成力场赋予。")
            return
        output_text = self._data_path_input.text().strip()
        if not output_text:
            if self._state.assignment_source_path:
                output_text = str(self._state.assignment_source_path.with_suffix(".data"))
                self._data_path_input.setText(output_text)
            else:
                self.QMessageBox.warning(self._window, "缺少输出路径", "请先设置 data 输出路径。")
                return
        output_path = Path(output_text)
        try:
            write_lammps_data(self._state.assigned, self._state.forcefield, output_path)
        except Exception as exc:
            self.QMessageBox.critical(self._window, "导出失败", str(exc))
            return
        self._state.output_data_path = output_path
        self._populate_export_preview(output_path)
        self._ready_card.setText(f"Ready\n已导出: {output_path.name}")

    def _export_material_studio_xsd(self):
        if self._state.assigned is None or self._state.structure is None:
            self.QMessageBox.warning(self._window, "无法导出", "请先完成力场赋予。")
            return
        source_path = self._state.assignment_source_path
        suggested = self._default_xsd_output_path(source_path)
        path, _ = self.QFileDialog.getSaveFileName(
            self._window,
            "导出 Material Studio XSD",
            str(suggested) if suggested is not None else "",
            "Materials Studio XSD (*.xsd)",
        )
        if not path:
            return
        output_path = Path(path)
        source_xsd = source_path if source_path and source_path.suffix.lower() == ".xsd" else None
        try:
            result = write_material_studio_xsd(
                self._state.structure,
                self._state.assigned,
                output_path,
                source_xsd=source_xsd,
                topology_conflict="rebuild",
                overwrite=True,
            )
        except Exception as exc:
            self.QMessageBox.critical(self._window, "XSD 导出失败", str(exc))
            return
        self._state.output_xsd_path = result.path
        mode_text = "保留原 XSD 元数据" if result.mode == "patched" else "重建 P1 XSD"
        self._ready_card.setText(f"Ready\n已导出 {result.path.name}\n{mode_text}")

    def _load_existing_data(self):
        path, _ = self.QFileDialog.getOpenFileName(
            self._window,
            "载入已有 data",
            "",
            "LAMMPS data (*.data);;All Files (*)",
        )
        if not path:
            return
        self._validation_data_input.setText(path)
        self._populate_export_preview(Path(path))
        self._ready_card.setText(f"Ready\n已载入 data: {Path(path).name}")

    def _render_to_panel(
        self,
        panel: _PreviewPanel,
        structure: CifStructure | None,
        *,
        assigned: AssignedStructure | None = None,
        overlay_mode: str = "Element",
        validation_report: ValidationReport | None = None,
        selected_index: int | None = None,
        caption: str = "",
        reset_view: bool = False,
    ):
        if structure is None:
            panel.show_message("No preview")
            panel.caption.setText(caption or "暂无结构。")
            panel.projected_points = None
            return
        interactive_error = None
        if supports_interactive_qwidget():
            try:
                scene = create_ovito_preview_widget(
                    structure,
                    assigned=assigned,
                    overlay_mode=overlay_mode,
                    validation_report=validation_report,
                    selected_index=selected_index,
                    size=panel.render_size,
                    parent=panel.viewport_host,
                )
                panel.show_ovito_scene(scene)
                panel.caption.setText(caption or f"Rendered with OVITO interactive viewport | Overlay: {overlay_mode}")
                panel.projected_points = None
                return
            except Exception as exc:
                interactive_error = str(exc)
        try:
            rendered_path = render_structure_preview(
                structure,
                assigned=assigned,
                overlay_mode=overlay_mode,
                validation_report=validation_report,
                selected_index=selected_index,
            )
            pixmap = self.QPixmap(str(rendered_path))
            rendered_path.unlink(missing_ok=True)
            target_size = panel.image.size()
            if target_size.width() < 20 or target_size.height() < 20:
                target_width = 960
                target_height = 560
            else:
                target_width = target_size.width()
                target_height = target_size.height()
            panel.show_pixmap(
                pixmap.scaled(
                    target_width,
                    target_height,
                    self.Qt.AspectRatioMode.KeepAspectRatio,
                    self.Qt.TransformationMode.SmoothTransformation,
                )
            )
            fallback_caption = caption or f"Rendered with OVITO static preview | Overlay: {overlay_mode}"
            if interactive_error:
                fallback_caption = f"{fallback_caption}\n交互式 viewport 不可用，已回退静态预览：{interactive_error}"
            panel.caption.setText(fallback_caption)
            panel.projected_points = None
        except Exception as exc:
            panel.show_message("OVITO render unavailable")
            panel.caption.setText(f"渲染失败：{exc}")
            panel.projected_points = None

    def _render_substitution_preview(self, path: Path):
        try:
            structure = load_structure(path)
        except Exception as exc:
            self._substitution_preview.caption.setText(f"无法加载结构：{exc}")
            return
        self._render_to_panel(
            self._substitution_preview,
            structure,
            overlay_mode="Element",
            caption=f"当前预览：{path.name}",
            reset_view=True,
        )

    def _populate_assignment_views(self):
        if self._state.structure is None or self._state.assigned is None:
            return
        structure_summary = summarize_structure(self._state.structure)
        assignment_summary = summarize_assignment(self._state.assigned)
        self._assignment_summary.setPlainText(
            "\n".join(
                [
                    f"结构标题: {self._state.structure.title}",
                    f"原子数: {structure_summary.atom_count}",
                    (
                        "晶胞长度 (A): "
                        f"{structure_summary.cell_lengths[0]:.4f}, {structure_summary.cell_lengths[1]:.4f}, {structure_summary.cell_lengths[2]:.4f}"
                    ),
                    (
                        "晶胞角度 (deg): "
                        f"{structure_summary.cell_angles[0]:.3f}, {structure_summary.cell_angles[1]:.3f}, {structure_summary.cell_angles[2]:.3f}"
                    ),
                    f"Bonds: {assignment_summary.bond_count}",
                    f"Angles: {assignment_summary.angle_count}",
                    f"Net charge: {assignment_summary.net_charge:.6f} e",
                    f"元素统计: {assignment_summary.element_counts}",
                ]
            )
        )

        self._suspend_atom_selection = True
        atoms = self._state.structure.atoms
        self._atom_table.setRowCount(len(atoms))
        for row, atom in enumerate(atoms):
            assigned_atom = self._state.assigned.atoms[row]
            values = [
                str(atom.index),
                atom.label,
                atom.element,
                assigned_atom.ff_type,
                f"{assigned_atom.charge:.5f}",
                f"{atom.frac[0]:.5f}",
                f"{atom.frac[1]:.5f}",
                f"{atom.frac[2]:.5f}",
            ]
            for column, value in enumerate(values):
                self._atom_table.setItem(row, column, self.QTableWidgetItem(value))
        self._suspend_atom_selection = False

        element_values = sorted({atom.element for atom in atoms})
        ff_type_values = sorted({atom.ff_type for atom in self._state.assigned.atoms})
        self._atom_element_filter.blockSignals(True)
        self._atom_element_filter.clear()
        self._atom_element_filter.addItems(["All Elements", *element_values])
        self._atom_element_filter.blockSignals(False)
        self._atom_type_filter.blockSignals(True)
        self._atom_type_filter.clear()
        self._atom_type_filter.addItems(["All Types", *ff_type_values])
        self._atom_type_filter.blockSignals(False)
        self._apply_atom_filters()
        self._sync_atom_selection()
        self._update_local_environment()

    def _populate_validation_views(self):
        if self._state.data_validation_report is None or self._state.output_data_path is None:
            return
        report = self._state.data_validation_report
        data_summary = summarize_data_file(self._state.output_data_path)
        lines = [
            f"Data file: {self._state.output_data_path}",
            f"Atoms: {report.atom_count}",
            f"Bonds: {report.bond_count}",
            f"Angles: {report.angle_count}",
            f"Atom types: {report.atom_type_count}",
            f"Bond coeff types: {report.bond_type_count}",
            f"Angle coeff types: {report.angle_type_count}",
            f"Net charge: {report.net_charge:.6f} e",
        ]
        lines.append("")
        if report.warnings:
            lines.append("Warnings:")
            for warning in report.warnings:
                lines.append(f"- [{warning.severity}] {warning.message}")
        else:
            lines.append("Warnings: none")
        self._validation_summary.setPlainText("\n".join(lines))

        self._warnings_table.setRowCount(len(report.warnings))
        for row, warning in enumerate(report.warnings):
            self._warnings_table.setItem(row, 0, self.QTableWidgetItem(warning.severity))
            self._warnings_table.setItem(row, 1, self.QTableWidgetItem(warning.code))
            self._warnings_table.setItem(row, 2, self.QTableWidgetItem(warning.message))

        type_counts = list(data_summary.atom_type_counts.items())
        self._assignment_table.setRowCount(len(type_counts))
        for row, (atom_type, count) in enumerate(type_counts):
            self._assignment_table.setItem(row, 0, self.QTableWidgetItem(atom_type))
            self._assignment_table.setItem(row, 1, self.QTableWidgetItem(str(count)))

    def _populate_export_preview(self, data_path: Path):
        try:
            summary = summarize_data_file(data_path)
        except Exception as exc:
            self._data_summary.setPlainText(f"Data 预览失败：{exc}")
            return
        self._data_summary.setPlainText(
            "\n".join(
                [
                    f"Data file: {data_path}",
                    f"Atoms: {summary.atom_count}",
                    f"Bonds: {summary.bond_count}",
                    f"Angles: {summary.angle_count}",
                    f"Net charge: {summary.net_charge:.6f} e",
                    f"Type counts: {summary.atom_type_counts}",
                ]
            )
        )

    def _apply_atom_filters(self):
        if self._state.structure is None or self._state.assigned is None:
            return
        text = self._atom_search_input.text().strip().lower()
        element_filter = self._atom_element_filter.currentText()
        type_filter = self._atom_type_filter.currentText()

        for row, atom in enumerate(self._state.structure.atoms):
            assigned_atom = self._state.assigned.atoms[row]
            visible = True
            if text:
                haystack = f"{atom.label} {atom.element} {assigned_atom.ff_type}".lower()
                visible = text in haystack
            if visible and element_filter != "All Elements":
                visible = atom.element == element_filter
            if visible and type_filter != "All Types":
                visible = assigned_atom.ff_type == type_filter
            self._atom_table.setRowHidden(row, not visible)

    def _sync_atom_selection(self):
        if self._selected_atom_index is None:
            return
        self._suspend_atom_selection = True
        self._atom_table.clearSelection()
        self._atom_table.selectRow(self._selected_atom_index)
        self._suspend_atom_selection = False

    def _on_atom_selection(self):
        if self._suspend_atom_selection:
            return
        items = self._atom_table.selectedItems()
        if not items:
            return
        self._selected_atom_index = items[0].row()
        self._update_local_environment()

    def _update_local_environment(self):
        if self._state.structure is None or self._selected_atom_index is None:
            self._local_environment.setPlainText("No atom selected.")
            return
        atom = self._state.structure.atoms[self._selected_atom_index]
        lines = [
            f"Selected atom: #{atom.index} {atom.label} ({atom.element})",
            f"Fractional position: ({atom.frac[0]:.5f}, {atom.frac[1]:.5f}, {atom.frac[2]:.5f})",
        ]
        if self._state.assigned is not None:
            assigned_atom = self._state.assigned.atoms[self._selected_atom_index]
            lines.append(f"ClayFF type: {assigned_atom.ff_type}")
            lines.append(f"Charge: {assigned_atom.charge:.6f} e")
        warnings_for_atom = []
        if self._state.validation_report is not None:
            warnings_for_atom = [
                warning.message
                for warning in self._state.validation_report.warnings
                if atom.index in warning.atom_indices
            ]
        if warnings_for_atom:
            lines.append("Warnings:")
            lines.extend(f"- {message}" for message in warnings_for_atom)
        lines.append("")
        lines.append("Nearest neighbors:")
        for neighbor_index in _neighbor_indices(self._state.structure, self._selected_atom_index):
            neighbor = self._state.structure.atoms[neighbor_index]
            distance = self._state.structure.cell.distance(atom.frac, neighbor.frac)
            suffix = ""
            if self._state.assigned is not None:
                suffix = f" | {self._state.assigned.atoms[neighbor_index].ff_type}"
            lines.append(f"- #{neighbor.index} {neighbor.label} ({neighbor.element}) : {distance:.4f} A{suffix}")
        self._local_environment.setPlainText("\n".join(lines))

    def _panel_click_to_atom_index(self, panel: _PreviewPanel, x_pos: float, y_pos: float) -> int | None:
        if panel.projected_points is None or len(panel.projected_points) == 0:
            return None

        label_width = panel.image.width()
        label_height = panel.image.height()
        render_width, render_height = panel.render_size
        scale = min(label_width / render_width, label_height / render_height)
        shown_width = render_width * scale
        shown_height = render_height * scale
        offset_x = (label_width - shown_width) / 2.0
        offset_y = (label_height - shown_height) / 2.0

        if x_pos < offset_x or y_pos < offset_y or x_pos > offset_x + shown_width or y_pos > offset_y + shown_height:
            return None

        x_render = (x_pos - offset_x) / scale
        y_render = (y_pos - offset_y) / scale
        deltas = panel.projected_points - [[x_render, y_render]]
        distances = (deltas[:, 0] ** 2 + deltas[:, 1] ** 2) ** 0.5
        nearest = int(distances.argmin())
        if float(distances[nearest]) > 24.0:
            return None
        return nearest

    def _on_assignment_preview_click(self, x_pos: float, y_pos: float):
        atom_index = self._panel_click_to_atom_index(self._assignment_preview, x_pos, y_pos)
        if atom_index is None:
            return
        self._selected_atom_index = atom_index
        self._sync_atom_selection()
        self._update_local_environment()

    def _on_validation_preview_click(self, x_pos: float, y_pos: float):
        atom_index = self._panel_click_to_atom_index(self._validation_preview, x_pos, y_pos)
        if atom_index is None:
            return
        self._selected_atom_index = atom_index
        self._sync_atom_selection()
        self._update_local_environment()

    def _load_structure(self, path: Path):
        self._state.input_structure_path = path
        self._input_path_input.setText(str(path))
        if not self._assignment_source_input.text().strip():
            self._assignment_source_input.setText(str(path))
        self._render_substitution_preview(path)
        self._run_assignment_stage()


def build_visualizer_window(
    clayff_path: str | Path | None = None,
    data_path: str | Path | None = None,
):
    return ClayFFWizardWindow(clayff_path=clayff_path, data_path=data_path)


def launch_visualizer(
    clayff_path: str | Path | None = None,
    data_path: str | Path | None = None,
) -> int:
    qt = _qt_imports()
    app = qt["QApplication"].instance() or qt["QApplication"]([])
    configure_application_font(app)
    window = build_visualizer_window(clayff_path=clayff_path, data_path=data_path)
    window.show()
    return app.exec()
