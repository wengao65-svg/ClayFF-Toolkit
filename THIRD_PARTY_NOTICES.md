# Third-party notices

ClayFF-Toolkit source code is licensed under Apache-2.0. The components below
retain their own licenses. A Windows binary distribution also contains a
machine-generated dependency inventory and the license files shipped by the
exact Python wheels used for that build.

## ClayFF parameter data

`src/clayff_toolkit/resources/clayff.txt` is a newline-normalized copy of
LAMMPS `tools/msi2lmp/frc_files/clayff.frc` at commit
`d7c50255302f705e67df7ef2da0d1c288b9b1c18`:

https://github.com/lammps/lammps/blob/d7c50255302f705e67df7ef2da0d1c288b9b1c18/tools/msi2lmp/frc_files/clayff.frc

Its SHA-256 after normalizing line endings to LF is
`d5b693c780ae2545139337bc705167f971a010cd8e1f3cd28d1fa53233af45e5`.

The LAMMPS directory notice states that force-field files distributed in that
directory are openly available and in the public domain:

https://github.com/lammps/lammps/blob/d7c50255302f705e67df7ef2da0d1c288b9b1c18/tools/msi2lmp/frc_files/README

The parameter data is therefore not relicensed under Apache-2.0. Scientific
use should cite the original ClayFF publication listed in `CITATION.cff`.

## Direct software dependencies

| Component | License used for redistribution | Project |
| --- | --- | --- |
| NumPy | BSD-3-Clause | https://numpy.org/ |
| ASE | LGPL-2.1-or-later | https://ase-lib.org/ |
| OVITO Python module | MIT | https://www.ovito.org/ |
| Traits | BSD-3-Clause | https://docs.enthought.com/traits/ |
| PySide6 and Shiboken6 | LGPL-3.0-only | https://www.qt.io/qt-for-python |
| Qt libraries bundled by PySide6 | LGPL-3.0-only where applicable | https://www.qt.io/ |
| PyInstaller bootloader | GPL-2.0-or-later with bootloader exception | https://pyinstaller.org/ |
| CPython runtime | PSF-2.0 | https://www.python.org/ |

The Windows build must not include a GPL-only Qt module unless the complete
distribution is made compatible with that module's terms. The generated
inventory is authoritative for the versions and transitive components in a
particular release.
