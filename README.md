# ClayFF-Toolkit

Unified toolkit for clay isomorphic substitution, ClayFF assignment, charge
validation, and LAMMPS `.data` export.

## Planned workflow

1. Apply random layer substitutions to a periodic clay structure
2. Assign ClayFF atom types and charges
3. Validate charge and parameter completeness
4. Export a LAMMPS data file
5. Inspect the workflow in a Qt wizard UI

## Current capabilities

- ClayFF assignment from periodic `cif` and periodic `xyz/extxyz` structures
- Random tetrahedral/octahedral substitution workflows migrated from the legacy
  prototype
- One-shot workflow entrypoint for:
  substitution -> assignment -> charge validation -> LAMMPS data export
- PySide6 + OVITO wizard GUI for:
  independent substitution, assignment, and validation pages with next-step
  navigation, OVITO default structure rendering in the substitution stage,
  local-environment inspection, and export review
- Mineral profile inference and validation reporting for:
  montmorillonite, beidellite, mica, and kaolinite-like assignments
- Visual overlay modes for:
  element colors, ClayFF type groups, profile markers, and validation warnings
- Baseline support for common clay-system species used by montmorillonite,
  beidellite, mica, and kaolinite family models:
  `Si`, `Al`, `Mg`, `Fe`, `Li`, `Na`, `K`, `Cs`, `Ca`, `Ba`, `Sr`, `Pb`,
  `Cl`, `O`, `H`
- CIF loading uses the toolkit's own periodic parser for triclinic cells, which
  avoids the previous ASE warning path during normal workflow execution

## CLI

Install as a persistent user command on Linux:

```bash
bash scripts/install-clayff-toolkit.sh
```

Install on Windows from PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-clayff-toolkit.ps1
```

The installer creates a local virtual environment and writes a stable launcher
to the user command path, so `clayff-toolkit` remains available after opening a
new terminal or rebooting. For CLI-only installs, run:

```bash
bash scripts/install-clayff-toolkit.sh --no-gui
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-clayff-toolkit.ps1 -NoGui
```

For development, editable installs still work inside the active Python
environment:

```bash
python -m pip install -e '.[gui]'
```

Run:

```bash
clayff-toolkit assign input.cif output.data
clayff-toolkit workflow input.cif substituted.cif output.data --preset octa-only --interlayer Ca
clayff-toolkit charge output.data
clayff-toolkit doctor --gui
clayff-toolkit visualize
```

On Debian/Ubuntu, if GUI Chinese text renders as boxes, install fallback fonts:

```bash
sudo apt install fontconfig fonts-noto-cjk fonts-noto-cjk-extra
sudo fc-cache -fv
```

## Current status

This repository consolidates legacy code from separate experimental directories
into a standard Python package layout under `src/`.

## Documentation

- 中文使用手册：`docs/user-manual.zh-CN.md`
