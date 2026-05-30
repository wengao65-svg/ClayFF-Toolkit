"""GUI-focused launcher for packaged ClayFF-Toolkit builds."""

from __future__ import annotations

import argparse
import datetime as _datetime
import importlib
import os
import sys
import traceback
from pathlib import Path

from clayff_toolkit.assignment.service import default_clayff_path
from clayff_toolkit.visualization.app import launch_visualizer


GUI_DEPENDENCY_IMPORTS = {
    "ovito": "ovito",
    "PySide6": "ovito.qt_compat",
}


def _module_import_error(module_name: str) -> str | None:
    try:
        importlib.import_module(module_name)
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"
    return None


def _module_available(module_name: str) -> bool:
    return _module_import_error(module_name) is None


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

    for dependency_name, import_target in GUI_DEPENDENCY_IMPORTS.items():
        import_error = _module_import_error(import_target)
        status = "ok" if import_error is None else "missing"
        lines.append(f"gui_dependency.{dependency_name}={status}")
        if import_error:
            lines.append(f"gui_dependency_error.{dependency_name}={import_error}")
        if status != "ok":
            missing.append(dependency_name)

    if missing:
        lines.append(f"missing_required={','.join(missing)}")
        return 1, lines

    lines.append("status=ok")
    return 0, lines


def write_smoke_report(lines: list[str]) -> Path | None:
    report_path = os.environ.get("CLAYFF_TOOLKIT_SMOKE_REPORT")
    if not report_path:
        return None
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


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
            write_smoke_report(lines)
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
