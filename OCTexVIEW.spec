# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Collect ttkbootstrap themes and assets
datas = collect_data_files('ttkbootstrap')

# Collect all ttkbootstrap submodules
hiddenimports = collect_submodules('ttkbootstrap')

a = Analysis(
    ['OCTexVIEW.py'],
    pathex=[],
    binaries=[],
    datas=datas + [('fonts', 'fonts'), ('icons', 'icons')],
    hiddenimports=hiddenimports + [
        'PIL._tkinter_finder',
        'tksheet',
        'openpyxl',
        'scipy',
        'sklearn',
        'matplotlib',
        'numpy',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='OCTexVIEW',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
