from __future__ import annotations

import argparse
import os
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal, Sequence


PlatformName = Literal["posix", "windows"]
Runner = Callable[[Sequence[str]], None]

PATH_BEGIN_MARKER = "# >>> ClayFF-Toolkit user command path >>>"
PATH_END_MARKER = "# <<< ClayFF-Toolkit user command path <<<"


@dataclass(frozen=True)
class InstallConfig:
    repo_root: Path
    python: str
    venv_dir: Path
    bin_dir: Path
    gui: bool = True
    update_path: bool = True
    platform: PlatformName = "posix"
    shell_rc_files: tuple[Path, ...] = ()

    @property
    def install_target(self) -> str:
        suffix = "[gui]" if self.gui else ""
        return f"{self.repo_root}{suffix}"

    @property
    def venv_python(self) -> Path:
        if self.platform == "windows":
            return self.venv_dir / "Scripts" / "python.exe"
        return self.venv_dir / "bin" / "python"

    @property
    def launcher_path(self) -> Path:
        suffix = ".cmd" if self.platform == "windows" else ""
        return self.bin_dir / f"clayff-toolkit{suffix}"


def default_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_platform() -> PlatformName:
    return "windows" if os.name == "nt" else "posix"


def default_venv_dir(repo_root: Path) -> Path:
    return Path(os.environ.get("CLAYFF_TOOLKIT_VENV", repo_root / ".venv"))


def default_bin_dir(platform: PlatformName) -> Path:
    env_bin_dir = os.environ.get("CLAYFF_TOOLKIT_BIN_DIR")
    if env_bin_dir:
        return Path(env_bin_dir)
    if platform == "windows":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "ClayFF-Toolkit" / "bin"
        return Path.home() / "AppData" / "Local" / "ClayFF-Toolkit" / "bin"
    return Path.home() / ".local" / "bin"


def default_shell_rc_files(home: Path | None = None) -> tuple[Path, ...]:
    base = home or Path.home()
    return (base / ".bashrc", base / ".profile")


def run_command(command: Sequence[str]) -> None:
    subprocess.run(list(command), check=True)


def create_venv_and_install(config: InstallConfig, runner: Runner = run_command) -> None:
    config.bin_dir.mkdir(parents=True, exist_ok=True)
    runner([config.python, "-m", "venv", str(config.venv_dir)])
    runner([str(config.venv_python), "-m", "pip", "install", "--upgrade", "pip"])
    runner([str(config.venv_python), "-m", "pip", "install", "-e", config.install_target])


def posix_launcher_text(venv_python: Path) -> str:
    return "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            f'exec "{venv_python}" -m clayff_toolkit "$@"',
            "",
        ]
    )


def windows_launcher_text(venv_python: Path) -> str:
    return "\r\n".join(
        [
            "@echo off",
            f'"{venv_python}" -m clayff_toolkit %*',
            "",
        ]
    )


def write_launcher(config: InstallConfig) -> Path:
    config.bin_dir.mkdir(parents=True, exist_ok=True)
    text = windows_launcher_text(config.venv_python) if config.platform == "windows" else posix_launcher_text(config.venv_python)
    launcher_path = config.launcher_path
    launcher_path.write_text(text, encoding="utf-8", newline="")
    if config.platform == "posix":
        launcher_path.chmod(launcher_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return launcher_path


def replace_marked_block(original: str, block: str) -> str:
    lines = original.splitlines()
    kept: list[str] = []
    skipping = False
    for line in lines:
        if line == PATH_BEGIN_MARKER:
            skipping = True
            continue
        if line == PATH_END_MARKER:
            skipping = False
            continue
        if not skipping:
            kept.append(line)
    prefix = "\n".join(kept).rstrip()
    if prefix:
        return f"{prefix}\n\n{block}\n"
    return f"{block}\n"


def posix_path_block(bin_dir: Path) -> str:
    return "\n".join(
        [
            PATH_BEGIN_MARKER,
            f'export PATH="{bin_dir}:$PATH"',
            PATH_END_MARKER,
        ]
    )


def update_posix_shell_path(bin_dir: Path, rc_files: Sequence[Path]) -> None:
    block = posix_path_block(bin_dir)
    for rc_file in rc_files:
        rc_file.parent.mkdir(parents=True, exist_ok=True)
        original = rc_file.read_text(encoding="utf-8") if rc_file.exists() else ""
        rc_file.write_text(replace_marked_block(original, block), encoding="utf-8")


def install(config: InstallConfig, runner: Runner = run_command) -> Path:
    create_venv_and_install(config, runner=runner)
    launcher_path = write_launcher(config)
    if config.update_path and config.platform == "posix":
        update_posix_shell_path(config.bin_dir, config.shell_rc_files or default_shell_rc_files())
    return launcher_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install ClayFF-Toolkit as a persistent user command.")
    parser.add_argument("--repo-root", type=Path, default=default_repo_root())
    parser.add_argument("--python", default=os.environ.get("PYTHON", "python3"))
    parser.add_argument("--venv", type=Path)
    parser.add_argument("--bin-dir", type=Path)
    parser.add_argument("--platform", choices=["posix", "windows"], default=default_platform())
    parser.add_argument("--no-gui", action="store_true")
    parser.add_argument("--no-path-update", action="store_true")
    parser.add_argument("--shell-rc", type=Path, action="append", default=[])
    return parser


def config_from_args(args: argparse.Namespace) -> InstallConfig:
    repo_root = args.repo_root.resolve()
    platform: PlatformName = args.platform
    return InstallConfig(
        repo_root=repo_root,
        python=args.python,
        venv_dir=(args.venv or default_venv_dir(repo_root)).resolve(),
        bin_dir=(args.bin_dir or default_bin_dir(platform)).resolve(),
        gui=not args.no_gui,
        update_path=not args.no_path_update,
        platform=platform,
        shell_rc_files=tuple(path.resolve() for path in args.shell_rc),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    config = config_from_args(parser.parse_args(argv))
    launcher_path = install(config)
    print(f"Installed ClayFF-Toolkit launcher: {launcher_path}")
    print("Verify with: clayff-toolkit --help")
    if config.platform == "posix" and str(config.bin_dir) not in os.environ.get("PATH", "").split(os.pathsep):
        print(f'Open a new terminal or run: export PATH="{config.bin_dir}:$PATH"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
