# ClayFF-Toolkit Refactor Plan

## Scope

Integrate the legacy `lmp_project` and `random_layer_sub_project` code into a
single Python package with a clear module boundary between:

- isomorphic substitution
- ClayFF assignment
- charge validation
- LAMMPS data export
- visualization

## Behavior Lock

Before refactoring migrated logic, preserve current behavior with regression
tests around the working ClayFF assignment flow:

- sample CIF -> LAMMPS `.data` generation
- atom-type count parity against legacy reference outputs
- net-charge validation behavior

The substitution module currently has no equivalent formal test suite, so the
first pass will preserve its current CLI and structure-processing behavior with
smoke coverage only.

## Smells To Remove

1. Mixed script/package layout and duplicated entrypoints
2. Cross-cutting responsibilities in single files
3. Hard-coded project paths and ad hoc validation directories
4. Unclear package/API boundary between substitution and assignment
5. Missing project metadata and installation entrypoints

## Ordered Passes

1. Scaffold package and migrate immutable resources/fixtures
2. Lock current assignment behavior with regression tests
3. Move legacy assignment code into `src/clayff_toolkit/assignment`
4. Introduce a shared periodic-structure loading boundary so substitution output
   can flow directly into assignment
5. Move substitution engine into `src/clayff_toolkit/substitution`
6. Add unified CLI and pipeline orchestration
7. Add initial PyQt visualizer shell wired to shared services
8. Run verification and document remaining gaps

## Out Of Scope For This Pass

- full mineral-generalization rules for beidellite, mica, kaolinite, and other
  new species
- broad algorithmic redesign of site classification
- full GUI parity with the design document
- destructive cleanup of all historical sample/output folders outside this repo
