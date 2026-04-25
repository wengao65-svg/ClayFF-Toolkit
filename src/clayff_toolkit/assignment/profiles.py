"""Mineral profile inference heuristics for assigned clay structures."""

from __future__ import annotations

from dataclasses import dataclass

from .assigner import AssignedStructure


TETRA_SUB_TYPES = {"at", "obts", "obss"}
OCTA_SUB_TYPES = {"mgo", "feo", "lio", "obos", "ohs"}
INTERLAYER_TYPES = {"Na", "K", "Cs", "Ca", "Ba", "Mg", "Sr", "Pb", "Cl"}
WATER_TYPES = {"o*", "h*"}


@dataclass(frozen=True)
class MineralProfile:
    key: str
    display_name: str
    description: str
    preferred_interlayer: tuple[str, ...]
    expects_tetra_substitution: bool
    expects_octa_substitution: bool
    allows_water: bool
    allows_interlayer: bool


@dataclass(frozen=True)
class MineralProfileMatch:
    profile: MineralProfile
    score: float
    reasons: tuple[str, ...]


PROFILE_CATALOG: tuple[MineralProfile, ...] = (
    MineralProfile(
        key="montmorillonite",
        display_name="Montmorillonite",
        description="Smectite profile with dominant octahedral substitution and common Na/Ca interlayers.",
        preferred_interlayer=("Na", "Ca"),
        expects_tetra_substitution=False,
        expects_octa_substitution=True,
        allows_water=True,
        allows_interlayer=True,
    ),
    MineralProfile(
        key="beidellite",
        display_name="Beidellite",
        description="Smectite profile with stronger tetrahedral substitution and common Na/Ca interlayers.",
        preferred_interlayer=("Na", "Ca"),
        expects_tetra_substitution=True,
        expects_octa_substitution=False,
        allows_water=True,
        allows_interlayer=True,
    ),
    MineralProfile(
        key="mica",
        display_name="Mica",
        description="Layer silicate profile with fixed interlayer cations, commonly K, and limited swelling water.",
        preferred_interlayer=("K", "Cs"),
        expects_tetra_substitution=True,
        expects_octa_substitution=False,
        allows_water=False,
        allows_interlayer=True,
    ),
    MineralProfile(
        key="kaolinite",
        display_name="Kaolinite",
        description="Non-swelling 1:1 clay profile without interlayer cations or interlayer water.",
        preferred_interlayer=(),
        expects_tetra_substitution=False,
        expects_octa_substitution=False,
        allows_water=False,
        allows_interlayer=False,
    ),
)


def assignment_markers(assigned: AssignedStructure) -> dict[str, object]:
    ff_types = [atom.ff_type for atom in assigned.atoms]
    tetra_sub = sum(1 for ff_type in ff_types if ff_type in TETRA_SUB_TYPES)
    octa_sub = sum(1 for ff_type in ff_types if ff_type in OCTA_SUB_TYPES)
    water = sum(1 for ff_type in ff_types if ff_type == "o*")
    hydroxyl = sum(1 for ff_type in ff_types if ff_type in {"oh", "ohs", "ho"})
    interlayer_counts: dict[str, int] = {}
    for ff_type in ff_types:
        if ff_type in INTERLAYER_TYPES:
            interlayer_counts[ff_type] = interlayer_counts.get(ff_type, 0) + 1
    return {
        "tetra_sub": tetra_sub,
        "octa_sub": octa_sub,
        "water": water,
        "hydroxyl": hydroxyl,
        "interlayer_counts": interlayer_counts,
    }


def infer_mineral_profiles(assigned: AssignedStructure) -> list[MineralProfileMatch]:
    markers = assignment_markers(assigned)
    tetra_sub = int(markers["tetra_sub"])
    octa_sub = int(markers["octa_sub"])
    water = int(markers["water"])
    hydroxyl = int(markers["hydroxyl"])
    interlayer_counts = dict(markers["interlayer_counts"])

    matches: list[MineralProfileMatch] = []
    for profile in PROFILE_CATALOG:
        score = 0.0
        reasons: list[str] = []

        if profile.key == "montmorillonite":
            if octa_sub > 0:
                score += 4.0
                reasons.append("octahedral substitution detected")
            if octa_sub >= tetra_sub:
                score += 1.5
                reasons.append("octahedral substitution dominates tetrahedral substitution")
            if any(species in interlayer_counts for species in ("Na", "Ca")):
                score += 2.0
                reasons.append("Na/Ca interlayer ions detected")
            if water > 0:
                score += 1.0
                reasons.append("interlayer water detected")
            if "K" in interlayer_counts:
                score -= 2.0
                reasons.append("K interlayer is less typical for montmorillonite")

        elif profile.key == "beidellite":
            if tetra_sub > 0:
                score += 4.0
                reasons.append("tetrahedral substitution detected")
            if tetra_sub > octa_sub:
                score += 1.5
                reasons.append("tetrahedral substitution dominates octahedral substitution")
            if any(species in interlayer_counts for species in ("Na", "Ca")):
                score += 2.0
                reasons.append("Na/Ca interlayer ions detected")
            if water > 0:
                score += 1.0
                reasons.append("interlayer water detected")
            if "K" in interlayer_counts:
                score -= 1.5
                reasons.append("K interlayer is less typical for beidellite")

        elif profile.key == "mica":
            if any(species in interlayer_counts for species in ("K", "Cs")):
                score += 5.0
                reasons.append("fixed interlayer K/Cs detected")
            if interlayer_counts:
                score += 1.0
                reasons.append("interlayer cations detected")
            if water == 0:
                score += 1.5
                reasons.append("no interlayer water detected")
            if tetra_sub > 0:
                score += 1.0
                reasons.append("tetrahedral substitution compatible with mica-like charge balance")
            if water > 0:
                score -= 2.5
                reasons.append("significant interlayer water is less typical for mica")

        elif profile.key == "kaolinite":
            if not interlayer_counts:
                score += 4.0
                reasons.append("no interlayer ions detected")
            if water == 0:
                score += 3.0
                reasons.append("no interlayer water detected")
            if hydroxyl > 0:
                score += 2.0
                reasons.append("hydroxyl groups detected")
            if tetra_sub == 0 and octa_sub == 0:
                score += 1.0
                reasons.append("no substitution-driven layer charge detected")
            if interlayer_counts:
                score -= 4.0
                reasons.append("interlayer ions are incompatible with kaolinite")
            if water > 0:
                score -= 3.0
                reasons.append("interlayer water is incompatible with kaolinite")

        matches.append(
            MineralProfileMatch(
                profile=profile,
                score=score,
                reasons=tuple(reasons),
            )
        )

    matches.sort(key=lambda item: item.score, reverse=True)
    return matches
