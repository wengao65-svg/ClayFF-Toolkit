"""Unified command line interface for ClayFF-Toolkit."""

from __future__ import annotations

import argparse
import importlib
import shutil
import sys
from pathlib import Path

from .assignment.material_studio import (
    SUPPORTED_MATERIAL_STUDIO_VERSIONS,
    assign_material_studio_file,
)
from .assignment.material_studio_off import audit_material_studio_off
from .assignment.service import assign_file, default_clayff_path
from .pipeline import ToolkitPipeline
from .substitution.engine import main as substitution_main
from .validation.charges import calculate_net_charge
from .visualization.app import launch_visualizer

GUI_DEPENDENCY_IMPORTS = {
    "ovito": "ovito",
    "PySide6": "ovito.qt_compat",
}


def _resolve_output_path(input_path: Path, output_path: Path) -> Path:
    if output_path.exists() and output_path.is_dir():
        return output_path / f"{input_path.stem}.data"
    if output_path.suffix.lower() == ".data":
        return output_path
    if not output_path.exists() and output_path.suffix == "":
        output_path.mkdir(parents=True, exist_ok=True)
        return output_path / f"{input_path.stem}.data"
    return output_path


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="clayff-toolkit")
    subparsers = parser.add_subparsers(dest="command", required=True)

    assign_parser = subparsers.add_parser("assign", help="Assign ClayFF types and export a LAMMPS data file.")
    assign_parser.add_argument("input", help="Input CIF file.")
    assign_parser.add_argument("output", help="Output data file or directory.")
    assign_parser.add_argument(
        "--clayff",
        default=str(default_clayff_path()),
        help="Path to ClayFF parameter file.",
    )

    assign_ms_parser = subparsers.add_parser(
        "assign-ms",
        help="Assign ClayFF types and export a Materials Studio XSD file.",
    )
    assign_ms_parser.add_argument("input", help="Input periodic structure or XSD file.")
    assign_ms_parser.add_argument("output", help="Output Materials Studio .xsd file.")
    assign_ms_parser.add_argument(
        "--clayff",
        default=str(default_clayff_path()),
        help="Path to ClayFF parameter file.",
    )
    assign_ms_parser.add_argument(
        "--topology-conflict",
        choices=["rebuild", "error"],
        default="rebuild",
        help="How to handle an input XSD whose topology differs from ClayFF.",
    )
    assign_ms_parser.add_argument(
        "--ms-version",
        choices=["auto", *SUPPORTED_MATERIAL_STUDIO_VERSIONS],
        default="auto",
        help="Target Materials Studio version; auto preserves the existing export behavior.",
    )
    assign_ms_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing an existing output XSD.",
    )

    audit_ms_off_parser = subparsers.add_parser(
        "audit-ms-off",
        help="Audit a Materials Studio OFF file against ClayFF parameters.",
    )
    audit_ms_off_parser.add_argument("input", help="Input Materials Studio .off file.")
    audit_ms_off_parser.add_argument(
        "--clayff",
        default=str(default_clayff_path()),
        help="Path to ClayFF parameter file.",
    )

    pipeline_parser = subparsers.add_parser("pipeline", help="Run assignment followed by charge validation.")
    pipeline_parser.add_argument("input", help="Input CIF file.")
    pipeline_parser.add_argument("output", help="Output data file or directory.")
    pipeline_parser.add_argument(
        "--clayff",
        default=str(default_clayff_path()),
        help="Path to ClayFF parameter file.",
    )

    workflow_parser = subparsers.add_parser(
        "workflow",
        help="Run substitution, ClayFF assignment, and charge validation for a single structure.",
    )
    workflow_parser.add_argument("input", help="Input structure file.")
    workflow_parser.add_argument("substituted_output", help="Output substituted structure path.")
    workflow_parser.add_argument("data_output", help="Output LAMMPS data path.")
    workflow_parser.add_argument(
        "--preset",
        choices=["tetra-octa", "octa-only"],
        default="tetra-octa",
        help="Preset substitution rule.",
    )
    workflow_parser.add_argument(
        "--interlayer",
        choices=["Ca", "Na"],
        default="Ca",
        help="Target interlayer cation species.",
    )
    workflow_parser.add_argument(
        "--clayff",
        default=str(default_clayff_path()),
        help="Path to ClayFF parameter file.",
    )
    workflow_parser.add_argument("--seed", type=int, default=20260402, help="Random seed.")
    workflow_parser.add_argument(
        "--strict-ratio",
        action="store_true",
        help="Require preset ratios to map to exact integer substitution counts.",
    )

    charge_parser = subparsers.add_parser("charge", help="Calculate the net charge of a data file.")
    charge_parser.add_argument("path", help="LAMMPS data file path.")

    visualize_parser = subparsers.add_parser("visualize", help="Launch the PyQt visualizer.")
    visualize_parser.add_argument("--clayff", help="Optional ClayFF parameter file path.")
    visualize_parser.add_argument("--data", help="Optional LAMMPS data file path.")
    visualize_parser.add_argument(
        "--page",
        choices=["substitution", "assignment", "validation", "materials-studio"],
        default="substitution",
        help="Initial GUI workspace.",
    )

    doctor_parser = subparsers.add_parser("doctor", help="Check the current ClayFF-Toolkit environment.")
    doctor_parser.add_argument("--gui", action="store_true", help="Also check GUI dependencies.")

    substitute_parser = subparsers.add_parser(
        "substitute",
        help="Run the legacy random-layer substitution engine.",
    )
    substitute_parser.add_argument("substitution_args", nargs=argparse.REMAINDER)
    return parser


def _module_import_error(module_name: str) -> str | None:
    try:
        importlib.import_module(module_name)
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"
    return None


def _module_available(module_name: str) -> bool:
    return _module_import_error(module_name) is None


def build_doctor_report(require_gui: bool = False) -> tuple[int, list[str]]:
    package_root = Path(__file__).resolve().parents[1]
    launcher_path = shutil.which("clayff-toolkit")
    lines = [
        "ClayFF-Toolkit environment diagnostics",
        f"python_executable={sys.executable}",
        f"package_path={package_root}",
        f"console_script={launcher_path or 'not found on PATH'}",
    ]

    missing_required: list[str] = []
    if require_gui:
        for dependency_name, import_target in GUI_DEPENDENCY_IMPORTS.items():
            import_error = _module_import_error(import_target)
            available = import_error is None
            lines.append(f"gui_dependency.{dependency_name}={'ok' if available else 'missing'}")
            if import_error:
                lines.append(f"gui_dependency_error.{dependency_name}={import_error}")
            if not available:
                missing_required.append(dependency_name)

    if missing_required:
        lines.append(f"missing_required={','.join(missing_required)}")
        lines.append("Install GUI dependencies with the platform installer:")
        lines.append("  Linux: bash scripts/install-clayff-toolkit.sh")
        lines.append("  Windows: powershell -ExecutionPolicy Bypass -File scripts\\install-clayff-toolkit.ps1")
        return 1, lines

    lines.append("status=ok")
    return 0, lines


def main(argv: list[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    if args.command == "assign":
        input_path = Path(args.input)
        output_path = _resolve_output_path(input_path, Path(args.output))
        print(assign_file(input_path, output_path, args.clayff))
        return 0

    if args.command == "assign-ms":
        result = assign_material_studio_file(
            args.input,
            args.output,
            args.clayff,
            topology_conflict=args.topology_conflict,
            ms_version=args.ms_version,
            overwrite=args.overwrite,
        )
        print(result.path)
        print(f"mode={result.mode}")
        print(f"atoms={result.atom_count}")
        print(f"bonds={result.bond_count}")
        print(f"xsd_version={result.xsd_version}")
        return 0

    if args.command == "audit-ms-off":
        report = audit_material_studio_off(args.input, args.clayff)
        print(f"off={report.off_path}")
        print(f"clayff={report.clayff_path}")
        print(f"atom_types={report.atom_type_count}/{report.expected_atom_type_count}")
        print(f"bonds={report.bond_count}")
        print(f"angles={report.angle_count}")
        print(f"errors={report.error_count}")
        print(f"warnings={report.warning_count}")
        for issue in report.issues:
            print(f"{issue.severity}:{issue.code}:{issue.message}")
        return 0 if report.is_valid else 1

    if args.command == "pipeline":
        input_path = Path(args.input)
        output_path = _resolve_output_path(input_path, Path(args.output))
        result = ToolkitPipeline().assign_and_validate(input_path, output_path, args.clayff)
        print(result.output_path)
        print(f"net_charge={result.net_charge:.6f}")
        return 0

    if args.command == "workflow":
        result = ToolkitPipeline().substitute_assign_validate(
            input_path=args.input,
            substituted_structure_path=args.substituted_output,
            output_path=args.data_output,
            preset=args.preset,
            interlayer_species=args.interlayer,
            clayff_path=args.clayff,
            seed=args.seed,
            strict_ratio=args.strict_ratio,
        )
        print(result.substituted_path)
        print(result.output_path)
        print(f"net_charge={result.net_charge:.6f}")
        return 0

    if args.command == "charge":
        print(f"{calculate_net_charge(args.path):.6f}")
        return 0

    if args.command == "visualize":
        return launch_visualizer(args.clayff, args.data, initial_page=args.page)

    if args.command == "doctor":
        exit_code, lines = build_doctor_report(require_gui=args.gui)
        print("\n".join(lines))
        return exit_code

    if args.command == "substitute":
        forwarded = args.substitution_args
        if forwarded and forwarded[0] == "--":
            forwarded = forwarded[1:]
        return substitution_main(forwarded)

    parser.error(f"Unsupported command: {args.command}")
    return 2
