# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('db', 'db'), ('sessions', 'sessions'), ('C:\\Users\\silen\\AppData\\Roaming\\Python\\Python314\\site-packages\\customtkinter', 'customtkinter')],
    hiddenimports=['customtkinter', 'tkinter', 'tkinter.messagebox', 'anthropic', 'telethon', 'telethon.tl.functions.account', 'zoneinfo', 'tzdata', 'sqlite3', 'asyncio', 'threading'],
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
    name='Selene',
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
    icon=['gui\\assets\\selene.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Selene',
)
