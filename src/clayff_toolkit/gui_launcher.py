"""GUI-focused launcher for packaged ClayFF-Toolkit builds."""

from __future__ import annotations

import argparse
import datetime as _datetime
import importlib.util
import os
import sys
import traceback
from pathlib import Path

from .assignment.service import default_clayff_path
from .visualization.app import launch_visualizer


GUI_DEPENDENCIES = ("PySide6", "ovito")


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def default_log_dir() -> Path:
    env_log_dir = os.environ.get("CLAYFF_TOOLKIT_LOG_DIR")
    if env_log_dir:
        return Path(env_log_dir)
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "ClayFF-Toolkit" / "logs"
    return Path.home() / ".clayff-toolkit" / "logs"


def write_crash_log(exc: BaseException, log_dir: Path | None = None) -> Path:
    target_dir = log_dir or default_log_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = _datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = target_dir / f"gui-crash-{timestamp}.log"
    log_path.write_text(
        "".join(
            [
                "ClayFF-Toolkit GUI startup failure\n",
                f"python_executable={sys.executable}\n",
                f"exception={type(exc).__name__}: {exc}\n\n",
                "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
            ]
        ),
        encoding="utf-8",
    )
    return log_path


def show_crash_message(log_path: Path) -> None:
    if os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(
            None,
            f"ClayFF-Toolkit GUI failed to start.\n\nDetails were written to:\n{log_path}",
            "ClayFF-Toolkit",
            0x10,
        )
    except Exception:
        return


def build_smoke_report() -> tuple[int, list[str]]:
    lines = ["ClayFF-Toolkit GUI package smoke test"]
    missing: list[str] = []

    clayff_path = default_clayff_path()
    resource_status = "ok" if clayff_path.exists() else "missing"
    lines.append(f"resource.clayff={resource_status}")
    lines.append(f"resource.clayff_path={clayff_path}")
    if not clayff_path.exists():
        missing.append("clayff_resource")

    for module_name in GUI_DEPENDENCIES:
        status = "ok" if _module_available(module_name) else "missing"
        lines.append(f"gui_dependency.{module_name}={status}")
        if status != "ok":
            missing.append(module_name)

    if missing:
        lines.append(f"missing_required={','.join(missing)}")
        return 1, lines

    lines.append("status=ok")
    return 0, lines


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ClayFF-Toolkit")
    parser.add_argument("--clayff", help="Optional ClayFF parameter file path.")
    parser.add_argument("--data", help="Optional LAMMPS data file path.")
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Check packaged GUI dependencies without opening the window.",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Alias for --smoke-test.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    try:
        if args.smoke_test or args.doctor:
            exit_code, lines = build_smoke_report()
            print("\n".join(lines))
            return exit_code

        return launch_visualizer(args.clayff, args.data)
    except Exception as exc:
        log_path = write_crash_log(exc)
        print(f"ClayFF-Toolkit GUI failed to start. Details were written to: {log_path}", file=sys.stderr)
        show_crash_message(log_path)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
