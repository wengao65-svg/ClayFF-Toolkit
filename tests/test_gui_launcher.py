from __future__ import annotations

from pathlib import Path

from clayff_toolkit import gui_launcher


def test_gui_launcher_smoke_report_success(monkeypatch, tmp_path: Path) -> None:
    clayff_path = tmp_path / "clayff.txt"
    clayff_path.write_text("# test resource\n", encoding="utf-8")
    monkeypatch.setattr(gui_launcher, "default_clayff_path", lambda: clayff_path)
    monkeypatch.setattr(gui_launcher, "_module_import_error", lambda module_name: None)

    exit_code, lines = gui_launcher.build_smoke_report()

    assert exit_code == 0
    assert "resource.clayff=ok" in lines
    assert "gui_dependency.PySide6=ok" in lines
    assert "gui_dependency.ovito=ok" in lines
    assert "status=ok" in lines


def test_gui_launcher_smoke_report_reports_missing_gui_dependency(monkeypatch, tmp_path: Path) -> None:
    clayff_path = tmp_path / "clayff.txt"
    clayff_path.write_text("# test resource\n", encoding="utf-8")
    monkeypatch.setattr(gui_launcher, "default_clayff_path", lambda: clayff_path)
    monkeypatch.setattr(
        gui_launcher,
        "_module_import_error",
        lambda module_name: None if module_name == "ovito.qt_compat" else "ImportError: missing",
    )

    exit_code, lines = gui_launcher.build_smoke_report()

    assert exit_code == 1
    assert "resource.clayff=ok" in lines
    assert "gui_dependency.PySide6=ok" in lines
    assert "gui_dependency.ovito=missing" in lines
    assert "missing_required=ovito" in lines


def test_gui_launcher_smoke_report_treats_import_failure_as_missing(monkeypatch, tmp_path: Path) -> None:
    clayff_path = tmp_path / "clayff.txt"
    clayff_path.write_text("# test resource\n", encoding="utf-8")
    monkeypatch.setattr(gui_launcher, "default_clayff_path", lambda: clayff_path)

    def fake_import_module(module_name: str):
        if module_name == "ovito":
            raise ImportError("missing Qt runtime")
        return object()

    monkeypatch.setattr(gui_launcher.importlib, "import_module", fake_import_module)

    exit_code, lines = gui_launcher.build_smoke_report()

    assert exit_code == 1
    assert "gui_dependency.PySide6=ok" in lines
    assert "gui_dependency.ovito=missing" in lines


def test_gui_launcher_smoke_test_command_prints_report(monkeypatch, tmp_path: Path, capsys) -> None:
    clayff_path = tmp_path / "clayff.txt"
    clayff_path.write_text("# test resource\n", encoding="utf-8")
    monkeypatch.setattr(gui_launcher, "default_clayff_path", lambda: clayff_path)
    monkeypatch.setattr(gui_launcher, "_module_import_error", lambda module_name: None)

    exit_code = gui_launcher.main(["--smoke-test"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "ClayFF-Toolkit GUI package smoke test" in captured.out
    assert "status=ok" in captured.out


def test_gui_launcher_smoke_test_writes_report_file(monkeypatch, tmp_path: Path) -> None:
    clayff_path = tmp_path / "clayff.txt"
    report_path = tmp_path / "smoke-report.txt"
    clayff_path.write_text("# test resource\n", encoding="utf-8")
    monkeypatch.setattr(gui_launcher, "default_clayff_path", lambda: clayff_path)
    monkeypatch.setattr(gui_launcher, "_module_import_error", lambda module_name: None)
    monkeypatch.setenv("CLAYFF_TOOLKIT_SMOKE_REPORT", str(report_path))

    exit_code = gui_launcher.main(["--smoke-test"])

    assert exit_code == 0
    assert "status=ok" in report_path.read_text(encoding="utf-8")


def test_gui_launcher_default_launches_visualizer(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        gui_launcher,
        "launch_visualizer",
        lambda clayff, data: calls.append((clayff, data)) or 0,
    )

    exit_code = gui_launcher.main(["--clayff", "params.txt", "--data", "input.data"])

    assert exit_code == 0
    assert calls == [("params.txt", "input.data")]


def test_gui_launcher_can_open_materials_studio_workspace(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        gui_launcher,
        "launch_visualizer",
        lambda clayff, data, *, initial_page: calls.append((clayff, data, initial_page)) or 0,
    )

    exit_code = gui_launcher.main(["--page", "materials-studio"])

    assert exit_code == 0
    assert calls == [(None, None, "materials-studio")]


def test_gui_launcher_writes_crash_log_on_startup_failure(monkeypatch, tmp_path: Path, capsys) -> None:
    log_dir = tmp_path / "logs"
    monkeypatch.setenv("CLAYFF_TOOLKIT_LOG_DIR", str(log_dir))
    monkeypatch.setattr(gui_launcher, "show_crash_message", lambda log_path: None)

    def fail_to_launch(clayff, data):
        raise RuntimeError("boom")

    monkeypatch.setattr(gui_launcher, "launch_visualizer", fail_to_launch)

    exit_code = gui_launcher.main([])
    captured = capsys.readouterr()
    logs = list(log_dir.glob("gui-crash-*.log"))

    assert exit_code == 1
    assert len(logs) == 1
    assert "Details were written to:" in captured.err
    log_text = logs[0].read_text(encoding="utf-8")
    assert "ClayFF-Toolkit GUI startup failure" in log_text
    assert "RuntimeError: boom" in log_text
