# -*- coding: utf-8 -*-
"""跨平台应用图标与平台工具（不依赖具体操作系统 API）。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtGui import QIcon

ASSETS = Path(__file__).resolve().parent.parent / "assets"
if getattr(sys, "frozen", False):
    # PyInstaller onedir：数据在可执行文件同级 _internal/assets。
    bundled = Path(sys.executable).resolve().parent / "_internal" / "assets"
    if bundled.is_dir():
        ASSETS = bundled


def app_icon() -> QIcon:
    """SVG 提供高分屏缩放；PNG 作为不支持 SVG 的平台回退。"""
    svg = ASSETS / "gitdesk.svg"
    if svg.is_file():
        icon = QIcon(str(svg))
        if not icon.isNull():
            return icon
    return QIcon(str(ASSETS / "gitdesk.png"))


def platform_font_families() -> tuple[str, str]:
    if sys.platform == "win32":
        return "Microsoft YaHei UI", "Consolas"
    if sys.platform == "darwin":
        return "PingFang SC", "Menlo"
    return "Noto Sans CJK SC", "DejaVu Sans Mono"


def prepare_environment() -> None:
    """在 QApplication 创建前调用；设置跨平台 Qt 兼容选项。"""
    if os.environ.get("QT_QPA_PLATFORM") in ("offscreen", "minimal"):
        return
    # Qt6 默认启用高 DPI；xcb 是 Linux 最通用的桌面后端。
    if sys.platform.startswith("linux") and os.environ.get("DISPLAY"):
        os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
    if sys.platform == "darwin":
        # macOS 使用系统原生 Cocoa，不使用 Windows pythonw 或 X11。
        os.environ.setdefault("QT_QPA_PLATFORM", "cocoa")
