from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = REPO_ROOT / "packaging" / "windows" / "ClayFF-Toolkit.spec"
BUILD_SCRIPT = REPO_ROOT / "scripts" / "build-windows-gui.ps1"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "tests.yml"
RELEASE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release-windows.yml"


def test_pyinstaller_spec_targets_gui_launcher_and_onefile_executable() -> None:
    spec = SPEC_PATH.read_text(encoding="utf-8")

    assert "gui_launcher.py" in spec
    assert 'name="ClayFF-Toolkit"' in spec
    assert "console=False" in spec
    assert "COLLECT(" not in spec
    assert "a.binaries" in spec
    assert "a.datas" in spec
    assert "clayff_toolkit/resources" in spec
    assert '"ovito"' in spec
    assert '"PySide6"' in spec
    assert "collect_dynamic_libs" in spec
    assert "ovito/plugins" in spec
    assert "shiboken6" in spec
    assert 'collect_submodules("ovito")' in spec
    assert 'collect_submodules("ase")' not in spec
    assert 'collect_submodules("PySide6")' not in spec
    assert 'collect_data_files("PySide6")' not in spec
    assert '"ase.io.xsd"' in spec
    assert '"PySide6.QtWidgets"' in spec
    assert 'excludes=["ase.test", "pytest", "_pytest"]' in spec
    assert (REPO_ROOT / "src" / "clayff_toolkit" / "assignment" / "material_studio_off.py").exists()


def test_windows_gui_build_script_builds_single_executable() -> None:
    script = BUILD_SCRIPT.read_text(encoding="utf-8")

    assert "PyInstaller" in script
    assert "ClayFF-Toolkit.spec" in script
    assert "--smoke-test" in script
    assert "Compress-Archive" not in script
    assert "ClayFF-Toolkit.exe" in script
    assert "Windows GUI executables must be built on Windows." in script
    assert "standalone Windows executable" in script
    assert "Start-Process" in script
    assert "CLAYFF_TOOLKIT_SMOKE_REPORT" in script
    assert "packaging\\windows\\README.txt" in script
    assert "Assert-GuiDependenciesImport" in script
    assert "gui_dependency_preflight=ok" in script
    assert "official CPython 3.10+" in script
    assert "Set-IsolatedPythonBuildPath" in script
    assert "PYTHONNOUSERSITE" in script
    assert "PYTHONPATH" in script
    assert "sys.base_prefix" in script
    assert "[System.IO.Path]::GetTempPath()" in script
    assert "WorkingDirectory" in script


def test_ci_builds_and_uploads_windows_gui_executable() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "windows-gui-artifact:" in workflow
    assert "scripts\\build-windows-gui.ps1" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "dist/ClayFF-Toolkit.exe" in workflow
    assert "ZipFile]::OpenRead" not in workflow
    assert "--smoke-test" in workflow
    assert "tests/test_material_studio_xsd.py" in workflow
    assert "tests/test_material_studio_off.py" in workflow
    assert "workflow_dispatch:" in workflow
    assert "github.ref == 'refs/heads/main'" in workflow
    assert "retention-days: 3" in workflow


def test_release_workflow_builds_and_attaches_windows_executable() -> None:
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "release:" in workflow
    assert "contents: write" in workflow
    assert "scripts\\build-windows-gui.ps1" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "gh release upload" in workflow
    assert "dist\\ClayFF-Toolkit.exe" in workflow
    assert "if: github.event_name == 'workflow_dispatch'" in workflow
    assert "retention-days: 7" in workflow


def test_windows_bundle_readme_guides_gui_users() -> None:
    readme = (REPO_ROOT / "packaging" / "windows" / "README.txt").read_text(encoding="utf-8")

    assert "Double-click ClayFF-Toolkit.exe" in readme
    assert "--smoke-test" in readme
    assert "%LOCALAPPDATA%\\ClayFF-Toolkit\\logs" in readme
    assert "bundled in the executable" in readme
    assert "Materials Studio workspace" in readme
    assert "Private OFF files are not bundled" in readme
