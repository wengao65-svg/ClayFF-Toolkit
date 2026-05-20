"""GUI-focused launcher for packaged ClayFF-Toolkit builds."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

from .assignment.service import default_clayff_path
from .visualization.app import launch_visualizer


GUI_DEPENDENCIES = ("PySide6", "ovito")


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


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

    if args.smoke_test or args.doctor:
        exit_code, lines = build_smoke_report()
        print("\n".join(lines))
        return exit_code

    return launch_visualizer(args.clayff, args.data)


if __name__ == "__main__":
    raise SystemExit(main())
