# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build spec for SearchGlossary.

Used by both local builds and the GitHub Actions workflow, so that CI
produces the same thing you get on your own machine:

    pyinstaller SearchGlossary.spec

Produces a one-folder build in dist/SearchGlossary/.
"""

import sys
from pathlib import Path

# SPECPATH is the folder holding this .spec file — the repo root.
REPO_ROOT = Path(SPECPATH)

# Files that must ship alongside the app. Each entry is
# (path on the build machine, folder name inside the bundle).
# At runtime these land in sys._MEIPASS, which main.py already knows
# to look in via _get_bundled_glossaries_dir().
datas = [
    (str(REPO_ROOT / "glossaries" / "*.csv"), "glossaries"),
    (str(REPO_ROOT / "glossaries" / "glossary-versions.json"), "glossaries"),
    (str(REPO_ROOT / "resources" / "icons" / "*"), "resources/icons"),
]

# Windows wants .ico; macOS wants .icns and errors on .ico. Linux ignores
# the icon entirely, since the desktop environment supplies it.
icon = None
if sys.platform == "win32":
    icon = str(REPO_ROOT / "resources" / "icons" / "app_icon.ico")

# Qt modules the app never imports. Excluding them cuts build size
# and avoids PyInstaller bundling half of Qt for no reason.
excludes = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
    "PySide6.Qt3DCore", "PySide6.QtCharts", "PySide6.QtMultimedia",
    "PySide6.QtQuick", "PySide6.QtQml",
    "tkinter", "pandas", "numpy", "matplotlib",
]

a = Analysis(
    [str(REPO_ROOT / "src" / "main.py")],
    pathex=[str(REPO_ROOT / "src")],   # so "from core.glossary import ..." resolves
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,      # one-folder build: binaries go in COLLECT
    name="SearchGlossary",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                  # UPX corrupts Qt DLLs on some Windows setups
    console=False,              # GUI app: no terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SearchGlossary",
)

# On macOS, wrap the folder into a proper .app bundle so it can be
# double-clicked from Finder.
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="SearchGlossary.app",
        icon=None,              # supply an .icns here if you make one
        bundle_identifier="com.kohkun.searchglossary",
        info_plist={
            "NSHighResolutionCapable": True,
            "CFBundleShortVersionString": "1.0.0",
        },
    )
