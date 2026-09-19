from __future__ import annotations

import hashlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = REPO_ROOT / "packaging" / "windows" / "ClayFF-Toolkit.spec"
BUILD_SCRIPT = REPO_ROOT / "scripts" / "build-windows-gui.ps1"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "tests.yml"
RELEASE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release-windows.yml"
ICON_PATH = REPO_ROOT / "packaging" / "windows" / "ClayFF-Toolkit.ico"
RUNTIME_ICON_PATH = (
    REPO_ROOT / "src" / "clayff_toolkit" / "resources" / "icons" / "clayff-toolkit.png"
)
LICENSE_COLLECTOR = REPO_ROOT / "scripts" / "collect_third_party_licenses.py"


def test_pyinstaller_spec_targets_gui_launcher_and_onefile_executable() -> None:
    spec = SPEC_PATH.read_text(encoding="utf-8")

    assert "gui_launcher.py" in spec
    assert 'name="ClayFF-Toolkit"' in spec
    assert "console=False" in spec
    assert "COLLECT(" not in spec
    assert "a.binaries" in spec
    assert "a.datas" in spec
    assert "clayff_toolkit/resources" in spec
    assert '"README.md"' in spec
    assert "ClayFF-Toolkit.ico" in spec
    assert "icon=str(icon_path)" in spec
    assert "clayff-toolkit.png" in spec
    assert "clayff_toolkit/resources/icons" in spec
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


def test_windows_and_runtime_icon_assets_exist() -> None:
    assert ICON_PATH.read_bytes().startswith(b"\x00\x00\x01\x00")
    assert RUNTIME_ICON_PATH.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_windows_gui_build_script_builds_licensed_archive() -> None:
    script = BUILD_SCRIPT.read_text(encoding="utf-8")

    assert "PyInstaller" in script
    assert "ClayFF-Toolkit.spec" in script
    assert "--smoke-test" in script
    assert "Compress-Archive" in script
    assert "ClayFF-Toolkit.exe" in script
    assert "ClayFF-Toolkit-Windows-x64.zip" in script
    assert "collect_third_party_licenses.py" in script
    assert "build-constraints.txt" in script
    assert "-c $buildConstraintsPath" in script
    assert "THIRD_PARTY_NOTICES.md" in script
    assert "THIRD_PARTY_LICENSES.md" in script
    assert "DEPENDENCIES.txt" in script
    assert "PYINSTALLER-CONTENTS.txt" in script
    assert "LGPL-3.0-only.txt" in script
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
    assert 'Library\\bin' in script
    assert "[System.IO.Path]::GetTempPath()" in script
    assert "WorkingDirectory" in script


def test_ci_builds_and_uploads_windows_gui_archive() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "windows-gui-artifact:" in workflow
    assert "scripts\\build-windows-gui.ps1" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "dist/ClayFF-Toolkit-Windows-x64.zip" in workflow
    assert "ZipFile]::OpenRead" not in workflow
    assert "--smoke-test" in workflow
    assert "tests/test_material_studio_xsd.py" in workflow
    assert "tests/test_material_studio_off.py" in workflow
    assert "workflow_dispatch:" in workflow
    assert "github.ref == 'refs/heads/main'" in workflow
    assert "retention-days: 3" in workflow


def test_release_workflow_builds_and_attaches_windows_archive() -> None:
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "release:" in workflow
    assert "contents: write" in workflow
    assert "scripts\\build-windows-gui.ps1" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "gh release upload" in workflow
    assert "dist\\ClayFF-Toolkit-Windows-x64.zip" in workflow
    assert "if: github.event_name == 'workflow_dispatch'" in workflow
    assert "retention-days: 7" in workflow


def test_windows_bundle_readme_guides_gui_users() -> None:
    readme = (REPO_ROOT / "packaging" / "windows" / "README.txt").read_text(encoding="utf-8")

    assert "ClayFF-Toolkit-Windows-x64.zip" in readme
    assert "Double-click ClayFF-Toolkit.exe" in readme
    assert "--smoke-test" in readme
    assert "%LOCALAPPDATA%\\ClayFF-Toolkit\\logs" in readme
    assert "bundled in the executable" in readme
    assert "Materials Studio workspace" in readme
    assert "Private OFF files are not bundled" in readme
    assert "Apache-2.0" in readme
    assert "LGPL-3.0" in readme


def test_open_source_release_metadata_is_present() -> None:
    metadata = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert 'license = "Apache-2.0"' in metadata
    assert 'version = "0.2.0"' in metadata
    assert '{ name = "wengao65-svg" }' in metadata
    assert "OpenAI Codex" not in metadata
    assert (REPO_ROOT / "LICENSE").read_text(encoding="utf-8").lstrip().startswith(
        "Apache License"
    )
    for name in (
        "NOTICE",
        "THIRD_PARTY_NOTICES.md",
        "CITATION.cff",
        "CONTRIBUTING.md",
        "CODE_OF_CONDUCT.md",
        "SECURITY.md",
    ):
        assert (REPO_ROOT / name).is_file()
    manifest = (REPO_ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    assert "THIRD_PARTY_NOTICES.md" in manifest
    assert "CITATION.cff" in manifest


def test_clayff_resource_has_pinned_public_domain_provenance() -> None:
    resource = REPO_ROOT / "src" / "clayff_toolkit" / "resources" / "clayff.txt"
    normalized = resource.read_text(encoding="utf-8").replace("\r\n", "\n").encode()
    digest = hashlib.sha256(normalized).hexdigest()
    notices = (REPO_ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")

    assert digest == "d5b693c780ae2545139337bc705167f971a010cd8e1f3cd28d1fa53233af45e5"
    assert "d7c50255302f705e67df7ef2da0d1c288b9b1c18" in notices
    assert digest in notices
    assert "public domain" in notices


def test_license_collector_and_supplemental_licenses_exist() -> None:
    collector = LICENSE_COLLECTOR.read_text(encoding="utf-8")

    compile(collector, str(LICENSE_COLLECTOR), "exec")
    assert "importlib" in collector
    assert "DEPENDENCIES.txt" in collector
    assert "THIRD_PARTY_LICENSES.md" in collector
    assert (REPO_ROOT / "packaging/windows/licenses/LGPL-3.0-only.txt").is_file()
    assert (REPO_ROOT / "packaging/windows/licenses/GPL-3.0-only.txt").is_file()
    assert (REPO_ROOT / "packaging/windows/licenses/PySide6-Qt-NOTICE.txt").is_file()
    assert (REPO_ROOT / "packaging/windows/licenses/cpython/3.10.19-LICENSE.txt").is_file()
    assert (REPO_ROOT / "packaging/windows/build-constraints.txt").is_file()
