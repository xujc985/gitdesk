# -*- coding: utf-8 -*-
"""用 Qt 生成 macOS ICNS 图标（保留 alpha 通道）。"""
from __future__ import annotations

import struct
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, QSize
from PySide6.QtGui import QGuiApplication, QIcon


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    app = QGuiApplication([])
    icon = QIcon(str(root / "assets" / "gitdesk.svg"))
    if icon.isNull():
        raise RuntimeError("无法读取 SVG 图标")
    blocks = []
    # ICNS 官方支持 PNG 数据块；各尺寸已包含在容器内。
    for name, size in (("icp4", 16), ("icp5", 32), ("ic07", 128),
                       ("ic08", 256), ("ic09", 512), ("ic10", 1024)):
        image = icon.pixmap(QSize(size, size)).toImage()
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not image.save(buffer, "PNG"):
            raise RuntimeError(f"PNG 图标导出失败：{size}")
        payload = bytes(buffer.data())
        blocks.append(name.encode("ascii") + struct.pack(">I", len(payload) + 8) + payload)
    data = b"icns" + struct.pack(">I", sum(len(block) + 8 for block in blocks) + 8) + b"".join(blocks)
    (root / "assets" / "gitdesk.icns").write_bytes(data)
    print(f"生成 {len(blocks)} 尺寸 ICNS：{len(data)} bytes")


if __name__ == "__main__":
    main()
