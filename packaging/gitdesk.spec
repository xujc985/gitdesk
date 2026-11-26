# -*- mode: python ; coding: utf-8 -*-
"""GitDesk PyInstaller 跨平台构建配置。

用法：python -m PyInstaller --noconfirm --clean packaging/gitdesk.spec
onedir 避免 onefile 每次启动解压 Qt，启动更快、内存/磁盘更可控。
"""
from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPEC).resolve().parent.parent
IS_WINDOWS = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"

datas = [(str(ROOT / "assets"), "assets")]
# GitDesk 后端为项目模块，不依赖项目外绝对路径。
hiddenimports = collect_submodules("git_backend")

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "PySide6.QtWebEngine", "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets", "PySide6.QtQml", "PySide6.QtQuick",
        "numpy", "pandas", "matplotlib", "PIL",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="GitDesk",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=not IS_WINDOWS and not IS_MAC,
    disable_windowed_traceback=False,
    argv_emulation=IS_MAC,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "assets" / ("gitdesk.ico" if IS_WINDOWS else
                                 "gitdesk.icns" if IS_MAC else "gitdesk.png")),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="GitDesk",
)

if IS_MAC:
    app = BUNDLE(
        coll,
        name="GitDesk.app",
        icon=str(ROOT / "assets" / "gitdesk.icns"),
        bundle_identifier="dev.gitdesk.app",
        info_plist={
            "CFBundleName": "GitDesk",
            "CFBundleDisplayName": "GitDesk",
            "CFBundleShortVersionString": "1.0.0",
            "CFBundleVersion": "1",
            "NSHighResolutionCapable": True,
            "NSHumanReadableCopyright": "GitDesk contributors",
            "LSApplicationCategoryType": "public.app-category.developer-tools",
        },
    )
