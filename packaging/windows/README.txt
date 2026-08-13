ClayFF-Toolkit for Windows
==========================

Quick start
-----------
1. Download ClayFF-Toolkit.exe from the release or CI artifact.
2. Double-click ClayFF-Toolkit.exe to start the GUI.
3. The required Python, Qt, OVITO, and ClayFF resource files are bundled in the executable.
4. Use the Materials Studio workspace for XSD ClayFF assignment and auditing a user-selected OFF file.

Private OFF files are not bundled in the executable.

Diagnostics
-----------
To check the package without opening the GUI, run this in PowerShell:

  .\ClayFF-Toolkit.exe --smoke-test

If the GUI fails to start, a log is written to:

  %LOCALAPPDATA%\ClayFF-Toolkit\logs

The command-line installer is still available for developers and advanced users
who prefer a Python environment.
