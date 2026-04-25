# ClayFF-Toolkit Architecture

## Package Layout

- `src/clayff_toolkit/assignment`
  - periodic structure loading from CIF and ASE-readable formats
  - custom CIF-to-ASE bridge for warning-free triclinic handling
  - ClayFF parameter loading
  - atom-type assignment
  - mineral profile inference markers
  - LAMMPS data export
- `src/clayff_toolkit/substitution`
  - random layer and framework substitution engine migrated from the legacy
    prototype
- `src/clayff_toolkit/validation`
  - charge parsing and batch net-charge checks
  - profile-aware validation warnings
- `src/clayff_toolkit/visualization`
  - PySide6 wizard UI for substitution -> assignment -> validation flow
  - OVITO-based default rendering in the substitution stage
  - local-environment inspection, profile/warning text summaries, and export review
- `src/clayff_toolkit/pipeline.py`
  - orchestration layer for `substitution -> assignment -> validation`

## Current Execution Surfaces

- CLI
  - `clayff-toolkit assign`
  - `clayff-toolkit pipeline`
  - `clayff-toolkit workflow`
  - `clayff-toolkit charge`
  - `clayff-toolkit substitute`
  - `clayff-toolkit visualize`
- Python API
  - `ToolkitPipeline`
  - `assign_file`
  - `calculate_net_charge`
  - `infer_mineral_profiles`
  - `validate_assigned_structure`
  - `summarize_structure`
  - `summarize_assignment`
  - `summarize_data_file`

## Explicitly Preserved Legacy Behavior

- Current montmorillonite-oriented ClayFF assignment rules are preserved as the
  migration baseline.
- `cammt_c2m_32` keeps the legacy semantic behavior for atom typing and charge,
  but intentionally exports a reduced ClayFF-minimal topology instead of the
  old `msi2lmp`-style expanded framework topology.
- Random substitution logic is carried over without algorithmic redesign in
  this pass.

## Planned Next Refactor Steps

1. Explicit mineral profiles for beidellite, mica, kaolinite, and other clay families
2. Central validation service for assignment, topology, charge, and parameter
   completeness
3. Richer visual overlays for bond/topology ambiguity and substitution provenance
4. Editable user-override workflow for profile selection and manual warning acknowledgement
