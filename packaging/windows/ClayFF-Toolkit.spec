# -*- mode: python ; coding: utf-8 -*-

import importlib.util
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules, copy_metadata


block_cipher = None
repo_root = Path(SPECPATH).parents[1]
src_root = repo_root / "src"
icon_path = repo_root / "packaging" / "windows" / "ClayFF-Toolkit.ico"

datas = [
    (
        str(src_root / "clayff_toolkit" / "resources" / "clayff.txt"),
        "clayff_toolkit/resources",
    ),
    (
        str(src_root / "clayff_toolkit" / "resources" / "icons" / "clayff-toolkit.png"),
        "clayff_toolkit/resources/icons",
    ),
]
binaries = []
hiddenimports = collect_submodules("clayff_toolkit")

# ASE resolves file readers and writers by module name at runtime. Include only
# the formats exposed by ClayFF-Toolkit instead of the complete ASE test suite.
hiddenimports += [
    "ase.io.cif",
    "ase.io.extxyz",
    "ase.io.res",
    "ase.io.vasp",
    "ase.io.xsd",
    "ase.io.xyz",
]

# OVITO discovers its extension modules dynamically. Keep those modules and
# plugin resources, while limiting Qt to the bindings used by ovito.qt_compat.
hiddenimports += collect_submodules("ovito")
hiddenimports += [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtNetwork",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "PySide6.QtWidgets",
    "PySide6.QtXml",
]
datas += collect_data_files("ovito")

for package_name in ("ase", "ovito", "PySide6"):
    try:
        datas += copy_metadata(package_name)
    except Exception:
        pass

binaries += collect_dynamic_libs("ovito")
ovito_spec = importlib.util.find_spec("ovito")
if ovito_spec and ovito_spec.submodule_search_locations:
    ovito_root = Path(next(iter(ovito_spec.submodule_search_locations)))
    binaries += [
        (str(path), "ovito/plugins")
        for path in (ovito_root / "plugins").glob("*.pyd")
    ]

shiboken_spec = importlib.util.find_spec("shiboken6")
if shiboken_spec and shiboken_spec.submodule_search_locations:
    shiboken_root = Path(next(iter(shiboken_spec.submodule_search_locations)))
    binaries += [
        (str(path), "PySide6")
        for path in shiboken_root.glob("*.dll")
    ]

a = Analysis(
    [str(src_root / "clayff_toolkit" / "gui_launcher.py")],
    pathex=[str(src_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["ase.test", "pytest", "_pytest"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="ClayFF-Toolkit",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    console=False,
    disable_windowed_traceback=False,
    icon=str(icon_path),
)
