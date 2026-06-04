# -*- mode: python ; coding: utf-8 -*-


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
    ],
    hiddenimports=[],
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
    [],
    exclude_binaries=True,
    name='OCTooL',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icons/thumb_4.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='OCTooL',
)
