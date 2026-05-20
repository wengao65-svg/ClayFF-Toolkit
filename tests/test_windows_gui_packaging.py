from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = REPO_ROOT / "packaging" / "windows" / "ClayFF-Toolkit.spec"
BUILD_SCRIPT = REPO_ROOT / "scripts" / "build-windows-gui.ps1"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "tests.yml"
RELEASE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release-windows.yml"


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
    assert "Assert-AnyBundleFile" in script
    assert "qwindows.dll" in script
    assert "ovito*.pyd" in script
    assert "clayff.txt" in script
    assert "packaging\\windows\\README.txt" in script
    assert "Copy-Item" in script


def test_ci_builds_and_uploads_windows_gui_artifact() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "windows-gui-artifact:" in workflow
    assert "scripts\\build-windows-gui.ps1" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "ClayFF-Toolkit-Windows-x64.zip" in workflow
    assert "ZipFile]::OpenRead" in workflow
    assert "qwindows.dll" in workflow
    assert "clayff.txt" in workflow
    assert "ClayFF-Toolkit/README.txt" in workflow


def test_release_workflow_builds_and_attaches_windows_zip() -> None:
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "release:" in workflow
    assert "contents: write" in workflow
    assert "scripts\\build-windows-gui.ps1" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "gh release upload" in workflow
    assert "ClayFF-Toolkit-Windows-x64.zip" in workflow


def test_windows_bundle_readme_guides_gui_users() -> None:
    readme = (REPO_ROOT / "packaging" / "windows" / "README.txt").read_text(encoding="utf-8")

    assert "Double-click ClayFF-Toolkit.exe" in readme
    assert "--smoke-test" in readme
    assert "%LOCALAPPDATA%\\ClayFF-Toolkit\\logs" in readme
    assert "Do not run ClayFF-Toolkit.exe from inside the zip" in readme
