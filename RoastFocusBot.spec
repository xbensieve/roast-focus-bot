# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH)
SRC = ROOT / "src"

hiddenimports = collect_submodules("pyttsx3.drivers") + [
    "pyttsx3.drivers.sapi5",
    "comtypes.stream",
    "roast_focus_bot",
    "roast_focus_bot.cli",
    "roast_focus_bot.platform_windows",
]

a = Analysis(
    [str(SRC / "roast_focus_bot" / "__main__.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
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
    name="roast-focus-bot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
