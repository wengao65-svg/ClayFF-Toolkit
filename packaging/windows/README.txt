ClayFF-Toolkit for Windows
==========================

Quick start
-----------
1. Extract the entire ClayFF-Toolkit folder from the zip file.
2. Double-click ClayFF-Toolkit.exe to start the GUI.
3. Do not run ClayFF-Toolkit.exe from inside the zip preview window.

Diagnostics
-----------
To check the package without opening the GUI, run this in PowerShell:

  .\ClayFF-Toolkit.exe --smoke-test

If the GUI fails to start, a log is written to:

  %LOCALAPPDATA%\ClayFF-Toolkit\logs

The command-line installer is still available for developers and advanced users
who prefer a Python environment.
