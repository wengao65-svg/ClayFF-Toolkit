# -*- mode: python ; coding: utf-8 -*-

import importlib.util
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules, copy_metadata


block_cipher = None
repo_root = Path(SPECPATH).parents[1]
src_root = repo_root / "src"

datas = [
    (
        str(src_root / "clayff_toolkit" / "resources" / "clayff.txt"),
        "clayff_toolkit/resources",
    )
]
binaries = []
hiddenimports = collect_submodules("clayff_toolkit")

for package_name in ("ase", "ovito", "PySide6"):
    datas += collect_data_files(package_name)
    hiddenimports += collect_submodules(package_name)
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
    excludes=[],
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
)
