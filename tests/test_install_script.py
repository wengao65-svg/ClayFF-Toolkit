from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install-clayff-toolkit.sh"


def _write_fake_python(tmp_path: Path) -> tuple[Path, Path]:
    fake_python = tmp_path / "fake-python"
    log_path = tmp_path / "fake-python.log"
    fake_python.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf 'CALL:%s:%s\\n' "$0" "$*" >> "$FAKE_PYTHON_LOG"

if [[ "${1:-}" == "-m" && "${2:-}" == "venv" ]]; then
  venv_dir="$3"
  mkdir -p "$venv_dir/bin"
  cp "$0" "$venv_dir/bin/python"
  chmod +x "$venv_dir/bin/python"
  exit 0
fi

if [[ "${1:-}" == "-m" && "${2:-}" == "pip" ]]; then
  exit 0
fi

if [[ "${1:-}" == "-m" && "${2:-}" == "clayff_toolkit" ]]; then
  exit 0
fi

if [[ "${1:-}" == *"install_clayff_toolkit.py" ]]; then
  exec "$REAL_PYTHON" "$@"
fi

exit 0
""",
        encoding="utf-8",
    )
    fake_python.chmod(fake_python.stat().st_mode | stat.S_IXUSR)
    return fake_python, log_path


def _run_installer(tmp_path: Path, *args: str) -> tuple[Path, Path, Path, Path]:
    home = tmp_path / "home"
    bin_dir = tmp_path / "bin"
    venv_dir = tmp_path / "venv"
    home.mkdir(exist_ok=True)
    fake_python, log_path = _write_fake_python(tmp_path)
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "PYTHON": str(fake_python),
            "FAKE_PYTHON_LOG": str(log_path),
            "REAL_PYTHON": sys.executable,
        }
    )

    subprocess.run(
        [
            "bash",
            str(INSTALL_SCRIPT),
            "--bin-dir",
            str(bin_dir),
            "--venv",
            str(venv_dir),
            *args,
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    return home, bin_dir, venv_dir, log_path


def test_install_script_has_valid_bash_syntax() -> None:
    subprocess.run(["bash", "-n", str(INSTALL_SCRIPT)], check=True)


def test_install_script_creates_launcher_and_persistent_path(tmp_path: Path) -> None:
    home, bin_dir, venv_dir, log_path = _run_installer(tmp_path, "--no-gui")

    launcher = bin_dir / "clayff-toolkit"
    assert launcher.exists()
    assert os.access(launcher, os.X_OK)
    assert f'exec "{venv_dir}/bin/python" -m clayff_toolkit "$@"' in launcher.read_text(encoding="utf-8")

    env = os.environ.copy()
    env["FAKE_PYTHON_LOG"] = str(log_path)
    subprocess.run([str(launcher), "--help"], check=True, env=env)
    assert "-m clayff_toolkit --help" in log_path.read_text(encoding="utf-8")

    for rc_name in (".bashrc", ".profile"):
        rc_text = (home / rc_name).read_text(encoding="utf-8")
        assert rc_text.count("# >>> ClayFF-Toolkit user command path >>>") == 1
        assert f'export PATH="{bin_dir}:$PATH"' in rc_text


def test_install_script_is_idempotent_for_shell_path_block(tmp_path: Path) -> None:
    home, _, _, _ = _run_installer(tmp_path, "--no-gui")
    _run_installer(tmp_path, "--no-gui")

    for rc_name in (".bashrc", ".profile"):
        rc_text = (home / rc_name).read_text(encoding="utf-8")
        assert rc_text.count("# >>> ClayFF-Toolkit user command path >>>") == 1


def test_install_script_can_skip_shell_rc_updates(tmp_path: Path) -> None:
    home, _, _, _ = _run_installer(tmp_path, "--no-gui", "--no-shell-rc")

    assert not (home / ".bashrc").exists()
    assert not (home / ".profile").exists()
