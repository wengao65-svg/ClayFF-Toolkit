from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.install_clayff_toolkit import build_parser, config_from_args


REPO_ROOT = Path(__file__).resolve().parents[1]
WINDOWS_INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install-clayff-toolkit.ps1"


def test_windows_install_script_declares_expected_user_options() -> None:
    script = WINDOWS_INSTALL_SCRIPT.read_text(encoding="utf-8")

    assert "param(" in script
    assert "[switch]$NoGui" in script
    assert "[string]$BinDir" in script
    assert "[string]$Venv" in script
    assert "[switch]$NoPathUpdate" in script
    assert "[string]$Python" in script
    assert "install_clayff_toolkit.py" in script
    assert "clayff-toolkit.cmd" in script
    assert "SetEnvironmentVariable(\"Path\"" in script


def test_installer_core_parses_windows_python_launcher_args(tmp_path: Path) -> None:
    args = build_parser().parse_args(
        [
            "--platform",
            "windows",
            "--repo-root",
            str(tmp_path / "repo"),
            "--python",
            "py",
            "--python-arg",
            "-3",
            "--venv",
            str(tmp_path / "venv"),
            "--bin-dir",
            str(tmp_path / "bin"),
            "--no-gui",
        ]
    )

    config = config_from_args(args)

    assert config.platform == "windows"
    assert config.python == ("py", "-3")
    assert config.venv_python == tmp_path / "venv" / "Scripts" / "python.exe"
    assert config.launcher_path == tmp_path / "bin" / "clayff-toolkit.cmd"
    assert config.install_target == str((tmp_path / "repo").resolve())


def test_windows_install_script_has_valid_powershell_syntax_when_available() -> None:
    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    if not pwsh:
        pytest.skip("PowerShell is not available in this environment")

    command = (
        "$script = Get-Content -Raw -LiteralPath "
        f"'{WINDOWS_INSTALL_SCRIPT}'; "
        "[scriptblock]::Create($script) | Out-Null"
    )
    subprocess.run([pwsh, "-NoProfile", "-Command", command], check=True)


def test_installer_core_help_runs_from_dev_venv() -> None:
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "install_clayff_toolkit.py"), "--help"],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "--platform" in result.stdout
    assert "--python-arg" in result.stdout
