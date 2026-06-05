# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files

ctk_colorpicker_datas = collect_data_files('CTkColorPicker')
customtkinter_datas = collect_data_files('customtkinter')

a = Analysis(
    ['OCTooL.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('icons', 'icons'),
        ('assets/fonts', 'assets/fonts'),
        ('assets/instructions.json', 'assets'),
        ('HTML_docs/*.html', 'HTML_docs'),
        ('HTML_docs/images', 'HTML_docs/images'),
    ] + ctk_colorpicker_datas + customtkinter_datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Test-only / dev dependencies
        'pytest', 'pytest_cov', '_pytest', 'py', 'coverage',
        'cv2', 'tifffile', 'open3d',
        'tkinter.test',
        # Notebook / interactive tooling (never used by the app)
        'IPython', 'ipykernel', 'jupyter', 'jupyter_client',
        'notebook', 'jedi',
        # GUI toolkits matplotlib may try to bundle but we don't use
        'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'PyQt5.QtCore',
        'wx', 'gi', 'gtk', 'pygtk',
        # Unused matplotlib backends (app uses TkAgg only)
        'matplotlib.backends.backend_qt5agg',
        'matplotlib.backends.backend_qt5',
        'matplotlib.backends.backend_qtagg',
        'matplotlib.backends.backend_qtcairo',
        'matplotlib.backends.backend_wx',
        'matplotlib.backends.backend_wxagg',
        'matplotlib.backends.backend_gtk3agg',
        'matplotlib.backends.backend_gtk3',
        'matplotlib.backends.backend_gtk4agg',
        'matplotlib.backends.backend_webagg',
        'matplotlib.backends.backend_nbagg',
        'matplotlib.tests', 'matplotlib.sphinxext',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='OCTooL',
    debug='imports',
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icons/thumb_6.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='OCTooL',
)
