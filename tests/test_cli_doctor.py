from __future__ import annotations

from clayff_toolkit.cli import build_argument_parser, build_doctor_report, main


def test_doctor_command_is_registered() -> None:
    parser = build_argument_parser()

    args = parser.parse_args(["doctor", "--gui"])

    assert args.command == "doctor"
    assert args.gui is True


def test_material_studio_assignment_command_is_registered() -> None:
    parser = build_argument_parser()

    args = parser.parse_args(
        [
            "assign-ms",
            "input.cif",
            "output.xsd",
            "--topology-conflict",
            "error",
            "--ms-version",
            "2020",
        ]
    )

    assert args.command == "assign-ms"
    assert args.topology_conflict == "error"
    assert args.ms_version == "2020"


def test_material_studio_off_audit_and_gui_page_are_registered() -> None:
    parser = build_argument_parser()

    audit_args = parser.parse_args(["audit-ms-off", "clayff.off"])
    gui_args = parser.parse_args(["visualize", "--page", "materials-studio"])

    assert audit_args.command == "audit-ms-off"
    assert audit_args.input == "clayff.off"
    assert gui_args.page == "materials-studio"


def test_doctor_report_without_gui_is_successful() -> None:
    exit_code, lines = build_doctor_report()

    assert exit_code == 0
    assert "ClayFF-Toolkit environment diagnostics" in lines
    assert any(line.startswith("python_executable=") for line in lines)
    assert any(line.startswith("package_path=") for line in lines)
    assert "status=ok" in lines


def test_doctor_command_prints_report(capsys) -> None:
    exit_code = main(["doctor"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "ClayFF-Toolkit environment diagnostics" in captured.out
    assert "status=ok" in captured.out


def test_doctor_gui_reports_missing_dependencies(monkeypatch) -> None:
    monkeypatch.setattr(
        "clayff_toolkit.cli._module_import_error",
        lambda module_name: "ImportError: missing" if module_name == "ovito" else None,
    )

    exit_code, lines = build_doctor_report(require_gui=True)

    assert exit_code == 1
    assert "gui_dependency.PySide6=ok" in lines
    assert "gui_dependency.ovito=missing" in lines
    assert "missing_required=ovito" in lines
    assert any("scripts\\install-clayff-toolkit.ps1" in line for line in lines)


def test_doctor_gui_treats_import_failure_as_missing(monkeypatch) -> None:
    def fake_import_module(module_name: str):
        if module_name == "ovito":
            raise ImportError("missing Qt runtime")
        return object()

    monkeypatch.setattr("clayff_toolkit.cli.importlib.import_module", fake_import_module)

    exit_code, lines = build_doctor_report(require_gui=True)

    assert exit_code == 1
    assert "gui_dependency.PySide6=ok" in lines
    assert "gui_dependency.ovito=missing" in lines
