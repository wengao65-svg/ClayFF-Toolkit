from __future__ import annotations

import os
from pathlib import Path

from scripts.install_clayff_toolkit import (
    InstallConfig,
    install,
    desktop_entry_text,
    posix_gui_launcher_text,
    posix_launcher_text,
    replace_marked_block,
    windows_launcher_text,
)


def test_posix_install_writes_launcher_and_path_block(tmp_path: Path) -> None:
    commands: list[list[str]] = []
    repo_root = tmp_path / "repo"
    venv_dir = tmp_path / "venv"
    bin_dir = tmp_path / "bin"
    bashrc = tmp_path / "home" / ".bashrc"
    profile = tmp_path / "home" / ".profile"
    repo_root.mkdir()

    config = InstallConfig(
        repo_root=repo_root,
        python=("python3",),
        venv_dir=venv_dir,
        bin_dir=bin_dir,
        gui=False,
        platform="posix",
        shell_rc_files=(bashrc, profile),
    )

    launcher = install(config, runner=lambda command: commands.append(list(command)))

    assert commands == [
        ["python3", "-m", "venv", str(venv_dir)],
        [str(venv_dir / "bin" / "python"), "-m", "pip", "install", "--upgrade", "pip"],
        [str(venv_dir / "bin" / "python"), "-m", "pip", "install", "-e", str(repo_root)],
    ]
    assert launcher == bin_dir / "clayff-toolkit"
    assert launcher.read_text(encoding="utf-8") == posix_launcher_text(venv_dir / "bin" / "python")
    assert os.access(launcher, os.X_OK)
    assert f'export PATH="{bin_dir}:$PATH"' in bashrc.read_text(encoding="utf-8")
    assert f'export PATH="{bin_dir}:$PATH"' in profile.read_text(encoding="utf-8")


def test_windows_install_writes_cmd_launcher_without_shell_rc(tmp_path: Path) -> None:
    commands: list[list[str]] = []
    repo_root = tmp_path / "repo"
    venv_dir = tmp_path / "venv"
    bin_dir = tmp_path / "bin"
    repo_root.mkdir()

    config = InstallConfig(
        repo_root=repo_root,
        python=("py", "-3"),
        venv_dir=venv_dir,
        bin_dir=bin_dir,
        gui=True,
        platform="windows",
    )

    launcher = install(config, runner=lambda command: commands.append(list(command)))

    assert commands == [
        ["py", "-3", "-m", "venv", str(venv_dir)],
        [str(venv_dir / "Scripts" / "python.exe"), "-m", "pip", "install", "--upgrade", "pip"],
        [str(venv_dir / "Scripts" / "python.exe"), "-m", "pip", "install", "-e", f"{repo_root}[gui]"],
    ]
    assert launcher == bin_dir / "clayff-toolkit.cmd"
    assert launcher.read_bytes() == windows_launcher_text(venv_dir / "Scripts" / "python.exe").encode("utf-8")


def test_posix_gui_install_writes_gui_launcher_and_desktop_entry(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    config = InstallConfig(
        repo_root=repo_root,
        python=("python3",),
        venv_dir=tmp_path / "venv",
        bin_dir=tmp_path / "bin",
        gui=True,
        update_path=False,
        platform="posix",
        desktop_dir=tmp_path / "applications",
    )

    install(config, runner=lambda command: None)

    assert config.gui_launcher_path.read_text(encoding="utf-8") == posix_gui_launcher_text(config.venv_python)
    assert os.access(config.gui_launcher_path, os.X_OK)
    assert config.desktop_entry_path is not None
    assert config.desktop_entry_path.read_text(encoding="utf-8") == desktop_entry_text(config.gui_launcher_path)
    assert f'Exec="{config.gui_launcher_path}"' in config.desktop_entry_path.read_text(encoding="utf-8")


def test_marked_path_block_replacement_is_idempotent(tmp_path: Path) -> None:
    old = "\n".join(
        [
            "export EXISTING=1",
            "",
            "# >>> ClayFF-Toolkit user command path >>>",
            'export PATH="/old/bin:$PATH"',
            "# <<< ClayFF-Toolkit user command path <<<",
            "alias ll='ls -l'",
        ]
    )
    new_block = "\n".join(
        [
            "# >>> ClayFF-Toolkit user command path >>>",
            f'export PATH="{tmp_path / "bin"}:$PATH"',
            "# <<< ClayFF-Toolkit user command path <<<",
        ]
    )

    replaced = replace_marked_block(old, new_block)

    assert "/old/bin" not in replaced
    assert "export EXISTING=1" in replaced
    assert "alias ll='ls -l'" in replaced
    assert replaced.count("# >>> ClayFF-Toolkit user command path >>>") == 1
