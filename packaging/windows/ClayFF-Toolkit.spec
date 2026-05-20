# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata


block_cipher = None
repo_root = Path(SPECPATH).parents[1]
src_root = repo_root / "src"

datas = [
    (
        str(src_root / "clayff_toolkit" / "resources" / "clayff.txt"),
        "clayff_toolkit/resources",
    )
]
hiddenimports = collect_submodules("clayff_toolkit")

for package_name in ("ase", "ovito", "PySide6"):
    datas += collect_data_files(package_name)
    hiddenimports += collect_submodules(package_name)
    try:
        datas += copy_metadata(package_name)
    except Exception:
        pass

a = Analysis(
    [str(src_root / "clayff_toolkit" / "gui_launcher.py")],
    pathex=[str(src_root)],
    binaries=[],
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
    [],
    exclude_binaries=True,
    name="ClayFF-Toolkit",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ClayFF-Toolkit",
)
