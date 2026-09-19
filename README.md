# ClayFF-Toolkit

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

Unified toolkit for clay isomorphic substitution, ClayFF assignment, charge
validation, LAMMPS `.data` export, and Materials Studio `.xsd` export.

## Planned workflow

1. Apply random layer substitutions to a periodic clay structure
2. Assign ClayFF atom types and charges
3. Validate charge and parameter completeness
4. Export a LAMMPS data file
5. Inspect the workflow in a Qt wizard UI

## Current capabilities

- ClayFF assignment from periodic `cif` and periodic `xyz/extxyz` structures
- ClayFF assignment from Materials Studio `xsd` structures and export of
  Forcite-ready P1 `xsd` files with ClayFF types, charges, and H-O topology
- Materials Studio `off` parsing and consistency auditing against the active
  ClayFF/LAMMPS parameter source
- Random tetrahedral/octahedral substitution workflows migrated from the legacy
  prototype
- One-shot workflow entrypoint for:
  substitution -> assignment -> charge validation -> LAMMPS data export
- PySide6 + OVITO workbench with independent substitution, assignment,
  validation, and Materials Studio workspaces
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

## Install And Run

For Windows GUI users, download and extract
`ClayFF-Toolkit-Windows-x64.zip` from the release or CI artifact, then
double-click the executable:

```text
ClayFF-Toolkit.exe
```

To verify the packaged GUI without opening the window, run:

```powershell
.\ClayFF-Toolkit.exe --smoke-test
```

For Linux users, install as a persistent user command:

```bash
bash scripts/install-clayff-toolkit.sh
```

The Linux installer creates both `clayff-toolkit` and
`clayff-toolkit-gui`, plus a user application-menu entry. Start the full GUI
or open the Materials Studio workspace directly with:

```bash
clayff-toolkit-gui
clayff-toolkit-gui --page materials-studio
```

For Windows developers or command-line users who prefer a Python environment,
install from PowerShell:

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
clayff-toolkit assign-ms input.cif output_clayff.xsd
clayff-toolkit assign-ms input.xsd output_clayff.xsd
clayff-toolkit assign-ms input.xsd output_ms2020.xsd --ms-version 2020
clayff-toolkit audit-ms-off clayff.off --clayff clayff.frc
clayff-toolkit workflow input.cif substituted.cif output.data --preset octa-only --interlayer Ca
clayff-toolkit charge output.data
clayff-toolkit doctor --gui
clayff-toolkit visualize
clayff-toolkit visualize --page materials-studio
```

Private Materials Studio force-field files are not distributed. The
repository keeps `test-temp/` ignored; OFF auditing operates on a file chosen
by the user.

On Debian/Ubuntu, if GUI Chinese text renders as boxes, install fallback fonts:

```bash
sudo apt install fontconfig fonts-noto-cjk fonts-noto-cjk-extra
sudo fc-cache -fv
```

## Current status

This repository consolidates legacy code from separate experimental directories
into a standard Python package layout under `src/`.

## Citation

If this toolkit contributes to published work, cite the specific GitHub
release URL and the original ClayFF publication:

> R. T. Cygan, J.-J. Liang, and A. G. Kalinichev, “Molecular Models of
> Hydroxide, Oxyhydroxide, and Clay Phases and the Development of a General
> Force Field,” *J. Phys. Chem. B* **108** (2004), 1255–1266.
> https://doi.org/10.1021/jp0363287

Machine-readable citation metadata is provided in `CITATION.cff`.

## License and third-party material

ClayFF-Toolkit source code is licensed under the Apache License 2.0. The
bundled `clayff.txt` parameter data is a public-domain file copied from the
LAMMPS repository and is not relicensed under Apache-2.0. See `NOTICE` and
`THIRD_PARTY_NOTICES.md` for provenance and dependency licenses.

Materials Studio is proprietary software. Private OFF and other licensed
force-field files are not distributed by this project. ClayFF-Toolkit is not
affiliated with or endorsed by BIOVIA, Dassault Systèmes, LAMMPS, OVITO, or
the authors of ClayFF.

## Contributing

Contributions are welcome under Apache-2.0 and the Developer Certificate of
Origin 1.1. See `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, and `SECURITY.md`.

## Documentation

- 中文使用手册：`docs/user-manual.zh-CN.md`
