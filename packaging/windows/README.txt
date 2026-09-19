ClayFF-Toolkit for Windows
==========================

Quick start
-----------
1. Download and extract ClayFF-Toolkit-Windows-x64.zip from the release or CI artifact.
2. Double-click ClayFF-Toolkit.exe in the extracted folder to start the GUI.
3. The required Python, Qt, OVITO, and ClayFF resource files are bundled in the executable.
4. Use the Materials Studio workspace for XSD ClayFF assignment and auditing a user-selected OFF file.

Private OFF files are not bundled in the executable.

Licenses and source
-------------------
ClayFF-Toolkit is licensed under Apache-2.0. This folder includes the project
LICENSE and NOTICE, an exact dependency inventory, third-party notices, and
the license files supplied by the Python packages used for this build.

Application source and release build scripts are available at:

  https://github.com/wengao65-svg/ClayFF-Toolkit

PySide6, Shiboken6, and the bundled Qt libraries are used under LGPL-3.0.
Their source locations and user modification rights are documented under the
licenses\PySide6-Qt directory. Do not remove the license files when
redistributing this package.

Diagnostics
-----------
To check the package without opening the GUI, run this in PowerShell:

  .\ClayFF-Toolkit.exe --smoke-test

If the GUI fails to start, a log is written to:

  %LOCALAPPDATA%\ClayFF-Toolkit\logs

The command-line installer is still available for developers and advanced users
who prefer a Python environment.
