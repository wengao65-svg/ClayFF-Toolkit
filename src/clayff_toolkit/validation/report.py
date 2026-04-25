"""Profile inference and validation warnings for assigned structures."""

from __future__ import annotations

from dataclasses import dataclass

from ..assignment.assigner import AssignedStructure
from ..assignment.profiles import (
    INTERLAYER_TYPES,
    OCTA_SUB_TYPES,
    TETRA_SUB_TYPES,
    WATER_TYPES,
    MineralProfileMatch,
    assignment_markers,
    infer_mineral_profiles,
)


@dataclass(frozen=True)
class ValidationWarning:
    severity: str
    code: str
    message: str
    atom_indices: tuple[int, ...] = ()


@dataclass(frozen=True)
class ValidationReport:
    inferred_profile: MineralProfileMatch
    alternatives: tuple[MineralProfileMatch, ...]
    confidence: float
    warnings: tuple[ValidationWarning, ...]


def _atom_indices_for_types(assigned: AssignedStructure, ff_types: set[str]) -> tuple[int, ...]:
    return tuple(atom.index for atom in assigned.atoms if atom.ff_type in ff_types)


def validate_assigned_structure(assigned: AssignedStructure) -> ValidationReport:
    profile_matches = infer_mineral_profiles(assigned)
    inferred = profile_matches[0]
    alternatives = tuple(profile_matches[1:3])
    second_score = profile_matches[1].score if len(profile_matches) > 1 else inferred.score
    confidence = max(0.0, min(1.0, 0.5 + 0.12 * (inferred.score - second_score)))

    markers = assignment_markers(assigned)
    tetra_sub = int(markers["tetra_sub"])
    octa_sub = int(markers["octa_sub"])
    water = int(markers["water"])
    interlayer_counts = dict(markers["interlayer_counts"])
    net_charge = sum(atom.charge for atom in assigned.atoms)

    warnings: list[ValidationWarning] = []
    if abs(net_charge) > 1e-3:
        warnings.append(
            ValidationWarning(
                severity="error",
                code="net-charge",
                message=f"Net charge is {net_charge:.6f} e; export should be reviewed before simulation.",
            )
        )

    if confidence < 0.6:
        warnings.append(
            ValidationWarning(
                severity="warning",
                code="profile-confidence",
                message=(
                    f"Mineral profile inference is low-confidence. Top match is "
                    f"{inferred.profile.display_name} with score {inferred.score:.2f}."
                ),
            )
        )

    if inferred.profile.key == "montmorillonite" and tetra_sub > octa_sub:
        warnings.append(
            ValidationWarning(
                severity="warning",
                code="montmorillonite-tetra-dominant",
                message="Tetrahedral substitution dominates, which is more beidellite-like than montmorillonite-like.",
                atom_indices=_atom_indices_for_types(assigned, TETRA_SUB_TYPES),
            )
        )
    if inferred.profile.key == "beidellite" and octa_sub >= tetra_sub and octa_sub > 0:
        warnings.append(
            ValidationWarning(
                severity="warning",
                code="beidellite-octa-dominant",
                message="Octahedral substitution is comparable to or greater than tetrahedral substitution.",
                atom_indices=_atom_indices_for_types(assigned, OCTA_SUB_TYPES),
            )
        )
    if inferred.profile.key == "mica" and not any(species in interlayer_counts for species in ("K", "Cs")):
        warnings.append(
            ValidationWarning(
                severity="warning",
                code="mica-interlayer",
                message="Mica-like profile inferred without dominant K/Cs interlayer ions.",
                atom_indices=_atom_indices_for_types(assigned, INTERLAYER_TYPES),
            )
        )
    if inferred.profile.key == "kaolinite":
        if interlayer_counts:
            warnings.append(
                ValidationWarning(
                    severity="error",
                    code="kaolinite-interlayer",
                    message="Kaolinite-like profile inferred but interlayer ions are present.",
                    atom_indices=_atom_indices_for_types(assigned, INTERLAYER_TYPES),
                )
            )
        if water > 0:
            warnings.append(
                ValidationWarning(
                    severity="error",
                    code="kaolinite-water",
                    message="Kaolinite-like profile inferred but interlayer water is present.",
                    atom_indices=_atom_indices_for_types(assigned, WATER_TYPES),
                )
            )

    return ValidationReport(
        inferred_profile=inferred,
        alternatives=alternatives,
        confidence=confidence,
        warnings=tuple(warnings),
    )
