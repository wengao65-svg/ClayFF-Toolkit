from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = REPO_ROOT / "packaging" / "windows" / "ClayFF-Toolkit.spec"
BUILD_SCRIPT = REPO_ROOT / "scripts" / "build-windows-gui.ps1"


def test_pyinstaller_spec_targets_gui_launcher_and_onedir_bundle() -> None:
    spec = SPEC_PATH.read_text(encoding="utf-8")

    assert "gui_launcher.py" in spec
    assert 'name="ClayFF-Toolkit"' in spec
    assert "console=False" in spec
    assert "COLLECT(" in spec
    assert "clayff_toolkit/resources" in spec
    assert '"ovito"' in spec
    assert '"PySide6"' in spec
    assert "collect_submodules(package_name)" in spec


def test_windows_gui_build_script_builds_and_zips_bundle() -> None:
    script = BUILD_SCRIPT.read_text(encoding="utf-8")

    assert "PyInstaller" in script
    assert "ClayFF-Toolkit.spec" in script
    assert "--smoke-test" in script
    assert "Compress-Archive" in script
    assert "ClayFF-Toolkit-Windows-x64.zip" in script
    assert "Windows GUI bundles must be built on Windows." in script
