"""High-level pipeline orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .assignment.service import assign_file
from .substitution import run_substitution_case
from .validation import ValidationReport, calculate_net_charge, validate_assigned_structure
from .assignment import assign_structure_file


@dataclass(frozen=True)
class ToolkitResult:
    input_path: Path
    output_path: Path
    net_charge: float
    substituted_path: Path | None = None
    substitution_log: dict[str, Any] | None = None
    validation_report: ValidationReport | None = None


class ToolkitPipeline:
    """Run ClayFF-Toolkit workflows."""

    def assign_and_validate(
        self,
        input_path: str | Path,
        output_path: str | Path,
        clayff_path: str | Path | None = None,
    ) -> ToolkitResult:
        _, assigned, _ = assign_structure_file(input_path, clayff_path)
        written = assign_file(input_path, output_path, clayff_path)
        return ToolkitResult(
            input_path=Path(input_path),
            output_path=written,
            net_charge=calculate_net_charge(written),
            validation_report=validate_assigned_structure(assigned),
        )

    def substitute_assign_validate(
        self,
        input_path: str | Path,
        substituted_structure_path: str | Path,
        output_path: str | Path,
        *,
        preset: str | None = "tetra-octa",
        interlayer_species: str = "Ca",
        clayff_path: str | Path | None = None,
        tetra_ratio: str | None = None,
        octa_ratio: str | None = None,
        rule_name: str = "custom",
        variant_index: int = 1,
        seed: int = 20260402,
        strict_ratio: bool = False,
    ) -> ToolkitResult:
        substitution_log = run_substitution_case(
            input_path=input_path,
            output_path=substituted_structure_path,
            preset=preset,
            interlayer_species=interlayer_species,
            tetra_ratio=tetra_ratio,
            octa_ratio=octa_ratio,
            rule_name=rule_name,
            variant_index=variant_index,
            seed=seed,
            strict_ratio=strict_ratio,
            dry_run=False,
        )
        written = assign_file(substituted_structure_path, output_path, clayff_path)
        _, assigned, _ = assign_structure_file(substituted_structure_path, clayff_path)
        return ToolkitResult(
            input_path=Path(input_path),
            substituted_path=Path(substituted_structure_path),
            output_path=written,
            net_charge=calculate_net_charge(written),
            substitution_log=substitution_log,
            validation_report=validate_assigned_structure(assigned),
        )
